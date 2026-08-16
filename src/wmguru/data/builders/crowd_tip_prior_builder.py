"""What the other players will tip, before anybody has tipped.

Mode B2 of the concept (docs/konzept.tex, section 9) needs a distribution over
the scorelines the other players pick. They do not pick at random: they crowd
onto a handful of results that simply feel right.

The prior mixes what really happens with that known preference, split by how
strong the favourite is. Where the two disagree most is where a contrarian tip
is worth the most.
"""

from typing import Any

from wmguru.helpers.constant import CrowdTipPriorCalculation, InternationalResultSource
from wmguru.helpers.utils import CsvFile


class CrowdTipPriorBuilder:
    """The tip distribution of the other players, per favourite band."""

    def build_the_prior(self) -> int:
        """Write the prior of every scoreline and the summary per band.

        Returns:
            How many favourite bands the summary holds.
        """
        counts = self._count_the_real_results()
        prior_rows, summary_rows = self._build_rows(counts)

        CsvFile(
            CrowdTipPriorCalculation.BY_BAND_OUTPUT_FILE,
            CrowdTipPriorCalculation.BY_BAND_COLUMN_NAMES,
        ).write_dict_rows(prior_rows)
        CsvFile(
            CrowdTipPriorCalculation.SUMMARY_OUTPUT_FILE,
            CrowdTipPriorCalculation.SUMMARY_COLUMN_NAMES,
        ).write_dict_rows(summary_rows)
        print(
            f"  OK    {len(prior_rows)} prior cells over "
            f"{len(summary_rows)} favourite bands"
        )
        return len(summary_rows)

    def _count_the_real_results(self) -> dict[str, dict[tuple[int, int], int]]:
        """Count how often each scoreline really happened, per favourite band.

        The result is written from the point of view of the favourite, so a
        1:0 always means the stronger side won by one, whether it played at
        home or away.
        """
        rating_before = self._read_the_ratings()
        counts: dict[str, dict[tuple[int, int], int]] = {}
        for row in CsvFile(CrowdTipPriorCalculation.RESULT_FILE).read_rows():
            scoreline = self._scoreline_of(row)
            ratings = rating_before.get(
                (
                    row[InternationalResultSource.DATE_COLUMN],
                    row[InternationalResultSource.HOME_TEAM_COLUMN],
                    row[InternationalResultSource.AWAY_TEAM_COLUMN],
                )
            )
            if scoreline is None or ratings is None:
                continue
            expectation = self._home_win_expectation(ratings, row)
            band = self._band_of(max(expectation, 1.0 - expectation))
            if band is None:
                continue
            home_goals, away_goals = scoreline
            cell = (
                (home_goals, away_goals)
                if expectation >= 0.5
                else (away_goals, home_goals)
            )
            counts.setdefault(band, {})[cell] = (
                counts.setdefault(band, {}).get(cell, 0) + 1
            )
        return counts

    def _read_the_ratings(self) -> dict[tuple[str, str, str], tuple[float, float]]:
        """Read what both teams were rated before each match they played."""
        return {
            (
                row["date"],
                row["home_team"],
                row["away_team"],
            ): (float(row["elo_home_pre"]), float(row["elo_away_pre"]))
            for row in CsvFile(CrowdTipPriorCalculation.ELO_HISTORY_FILE).read_rows()
        }

    def _scoreline_of(self, row: dict[str, str]) -> tuple[int, int] | None:
        """Read the result, cut down to the grid the tips are given on.

        Returns:
            The goals of both sides, or None for a match that was never
            played. Anything above the grid counts as the highest cell,
            because nobody tips a seven.
        """
        try:
            home_goals = int(row["home_score"])
            away_goals = int(row["away_score"])
        except (KeyError, TypeError, ValueError):
            return None
        highest = CrowdTipPriorCalculation.HIGHEST_GOALS_IN_THE_GRID
        return min(home_goals, highest), min(away_goals, highest)

    def _home_win_expectation(
        self, ratings: tuple[float, float], row: dict[str, str]
    ) -> float:
        """How likely the home side was to win, out of the two ratings.

        The home advantage falls away on a neutral pitch, which is most of a
        tournament.
        """
        home_rating, away_rating = ratings
        advantage = (
            CrowdTipPriorCalculation.HOME_ADVANTAGE
            if row[InternationalResultSource.NEUTRAL_VENUE_COLUMN].strip().upper()
            == InternationalResultSource.NOT_NEUTRAL_TEXT
            else 0.0
        )
        difference = home_rating + advantage - away_rating
        return 1.0 / (
            1.0
            + CrowdTipPriorCalculation.LOGISTIC_BASE
            ** (-difference / CrowdTipPriorCalculation.RATING_SCALE)
        )

    def _band_of(self, favourite_expectation: float) -> str | None:
        """Say which band a favourite of this strength falls into."""
        edges = CrowdTipPriorCalculation.BAND_EDGES
        for lower, upper in zip(edges[:-1], edges[1:], strict=False):
            if lower <= favourite_expectation < upper:
                return f"{lower:.2f}_{min(upper, 1.0):.2f}"
        return None

    def _build_rows(
        self, counts: dict[str, dict[tuple[int, int], int]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Mix the real results with the crowd preference, per band."""
        heuristic = self._normalised_heuristic()
        weight = CrowdTipPriorCalculation.HEURISTIC_WEIGHT
        places = CrowdTipPriorCalculation.PROBABILITY_DECIMAL_PLACES

        prior_rows: list[dict[str, Any]] = []
        summary_rows: list[dict[str, Any]] = []
        for band in sorted(counts):
            counts_of_cell = counts[band]
            match_count = sum(counts_of_cell.values())
            distance = 0.0
            most_likely_cell, highest_prior = (0, 0), -1.0
            for cell in self._every_cell():
                real = counts_of_cell.get(cell, 0) / match_count
                expected_of_the_crowd = heuristic.get(cell, 0.0)
                prior = (1.0 - weight) * real + weight * expected_of_the_crowd
                distance += abs(real - expected_of_the_crowd)
                if prior > highest_prior:
                    most_likely_cell, highest_prior = cell, prior
                prior_rows.append(
                    {
                        "favorite_band": band,
                        "favorite_goals": cell[0],
                        "underdog_goals": cell[1],
                        "empirical_probability": round(real, places),
                        "heuristic_probability": round(expected_of_the_crowd, places),
                        "crowd_prior_probability": round(prior, places),
                    }
                )
            summary_rows.append(
                {
                    "favorite_band": band,
                    "matches": match_count,
                    "crowd_distortion": round(0.5 * distance, places),
                    "top_crowd_scoreline": (
                        f"{most_likely_cell[0]}"
                        f"{CrowdTipPriorCalculation.SCORELINE_SEPARATOR}"
                        f"{most_likely_cell[1]}"
                    ),
                    "top_crowd_probability": round(highest_prior, places),
                }
            )
        return prior_rows, summary_rows

    def _every_cell(self) -> list[tuple[int, int]]:
        """Every scoreline of the grid, from the favourite's point of view."""
        highest = CrowdTipPriorCalculation.HIGHEST_GOALS_IN_THE_GRID
        return [
            (favorite_goals, underdog_goals)
            for favorite_goals in range(highest + 1)
            for underdog_goals in range(highest + 1)
        ]

    def _normalised_heuristic(self) -> dict[tuple[int, int], float]:
        """Turn the crowd preference into probabilities that add up to one."""
        weights = CrowdTipPriorCalculation.HEURISTIC_WEIGHT_OF_SCORELINE
        total = sum(weights.values())
        return {cell: weight / total for cell, weight in weights.items()}


if __name__ == "__main__":
    CrowdTipPriorBuilder().build_the_prior()
