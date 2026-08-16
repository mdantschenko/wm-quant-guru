"""What the other players will tip, before anybody has tipped.

Mode B2 of the concept (docs/konzept.tex, section 9) needs a distribution over
the scorelines the other players pick. They do not pick at random: they crowd
onto a handful of results that simply feel right.

The prior mixes what really happens with that known preference, split by how
strong the favourite is. Where the two disagree most is where a contrarian tip
is worth the most.
"""

import numpy as np
import pandas as pd

from wmguru.helpers.constant import CrowdTipPriorCalculation, InternationalResultSource
from wmguru.helpers.utils import CsvFile

SCORELINE_KEYS = ["favorite_goals", "underdog_goals"]
CELL_KEYS = ["favorite_band", *SCORELINE_KEYS]


class CrowdTipPriorBuilder:
    """The tip distribution of the other players, per favourite band."""

    def build_the_prior(self) -> int:
        """Write the prior of every scoreline and the summary per band.

        Returns:
            How many favourite bands the summary holds.
        """
        counted_cells = self._count_the_real_results()
        prior_cells = self._mix_the_crowd_preference_in(counted_cells)
        band_summary = self._summarise_every_band(prior_cells)

        CsvFile(
            CrowdTipPriorCalculation.BY_BAND_OUTPUT_FILE,
            CrowdTipPriorCalculation.BY_BAND_COLUMN_NAMES,
        ).write_table(self._rounded_for_writing(prior_cells))
        CsvFile(
            CrowdTipPriorCalculation.SUMMARY_OUTPUT_FILE,
            CrowdTipPriorCalculation.SUMMARY_COLUMN_NAMES,
        ).write_table(band_summary)
        print(
            f"  OK    {len(prior_cells)} prior cells over "
            f"{len(band_summary)} favourite bands"
        )
        return len(band_summary)

    def _count_the_real_results(self) -> pd.DataFrame:
        """Count how often each scoreline really happened, per favourite band.

        Every band gets the whole grid, so a scoreline that never happened
        still carries its row with a count of nothing.
        """
        matches = self._read_matches_that_carry_a_rating()
        seen_from_the_favourite = self._turned_towards_the_favourite(matches)
        counted = (
            seen_from_the_favourite.groupby(CELL_KEYS, dropna=False, observed=True)
            .size()
            .rename("matches_with_this_scoreline")
            .reset_index()
        )
        whole_grid = (
            counted[["favorite_band"]]
            .drop_duplicates()
            .merge(self._every_scoreline_of_the_grid(), how="cross")
        )
        return (
            whole_grid.merge(counted, on=CELL_KEYS, how="left")
            .fillna({"matches_with_this_scoreline": 0})
            .astype({"matches_with_this_scoreline": int})
            .sort_values(CELL_KEYS)
            .reset_index(drop=True)
        )

    def _read_matches_that_carry_a_rating(self) -> pd.DataFrame:
        """Join every played international onto the rating both sides had.

        Four fixtures are listed twice on the same day against the same
        opponent, and only the later rating of such a pair is kept, so the
        join cannot multiply a match out into several rows.
        """
        results = CsvFile(CrowdTipPriorCalculation.RESULT_FILE).read_table()
        ratings = (
            CsvFile(CrowdTipPriorCalculation.ELO_HISTORY_FILE)
            .read_table()
            .drop_duplicates(subset=["date", "home_team", "away_team"], keep="last")
        )
        played = results.assign(
            home_goals=pd.to_numeric(results["home_score"], errors="coerce"),
            away_goals=pd.to_numeric(results["away_score"], errors="coerce"),
        ).dropna(subset=["home_goals", "away_goals"])

        return played.merge(
            ratings.assign(
                home_rating=pd.to_numeric(ratings["elo_home_pre"]),
                away_rating=pd.to_numeric(ratings["elo_away_pre"]),
            )[["date", "home_team", "away_team", "home_rating", "away_rating"]],
            left_on=[
                InternationalResultSource.DATE_COLUMN,
                InternationalResultSource.HOME_TEAM_COLUMN,
                InternationalResultSource.AWAY_TEAM_COLUMN,
            ],
            right_on=["date", "home_team", "away_team"],
            how="inner",
        )

    def _turned_towards_the_favourite(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Write every result from the point of view of the stronger side.

        A 1:0 then always means the favourite won by one, whether it played
        at home or away. Anything above the grid counts as the highest cell,
        because nobody tips a seven.
        """
        home_win_chance = self._home_win_chance(matches)
        home_is_the_favourite = home_win_chance >= 0.5
        highest = CrowdTipPriorCalculation.HIGHEST_GOALS_IN_THE_GRID
        home_goals = matches["home_goals"].clip(upper=highest).astype(int)
        away_goals = matches["away_goals"].clip(upper=highest).astype(int)

        return matches.assign(
            favorite_band=self._which_band_the_favourite_falls_into(
                np.maximum(home_win_chance, 1.0 - home_win_chance)
            ),
            favorite_goals=np.where(home_is_the_favourite, home_goals, away_goals),
            underdog_goals=np.where(home_is_the_favourite, away_goals, home_goals),
        ).dropna(subset=["favorite_band"])

    def _home_win_chance(self, matches: pd.DataFrame) -> pd.Series:
        """How likely the home side was to win, out of the two ratings.

        The home advantage falls away on a neutral pitch, which is most of a
        tournament.
        """
        plays_at_home = (
            matches[InternationalResultSource.NEUTRAL_VENUE_COLUMN]
            .str.strip()
            .str.upper()
            == InternationalResultSource.NOT_NEUTRAL_TEXT
        )
        advantage = np.where(
            plays_at_home, CrowdTipPriorCalculation.HOME_ADVANTAGE, 0.0
        )
        rating_gap = matches["home_rating"] + advantage - matches["away_rating"]
        return 1.0 / (
            1.0
            + CrowdTipPriorCalculation.LOGISTIC_BASE
            ** (-rating_gap / CrowdTipPriorCalculation.RATING_SCALE)
        )

    def _which_band_the_favourite_falls_into(
        self, favourite_chance: pd.Series
    ) -> pd.Series:
        """Say which band a favourite of this strength falls into."""
        edges = CrowdTipPriorCalculation.BAND_EDGES
        names = [
            f"{lower:.2f}_{min(upper, 1.0):.2f}"
            for lower, upper in zip(edges[:-1], edges[1:], strict=False)
        ]
        return pd.cut(
            favourite_chance, bins=list(edges), labels=names, right=False
        ).astype(object)

    def _every_scoreline_of_the_grid(self) -> pd.DataFrame:
        """Every scoreline a tip may be given on, with the crowd weight on it."""
        highest = CrowdTipPriorCalculation.HIGHEST_GOALS_IN_THE_GRID
        goals = range(highest + 1)
        grid = pd.MultiIndex.from_product(
            [goals, goals], names=SCORELINE_KEYS
        ).to_frame(index=False)

        preference = pd.Series(CrowdTipPriorCalculation.HEURISTIC_WEIGHT_OF_SCORELINE)
        weight_of_cell = (
            preference.reindex(pd.MultiIndex.from_frame(grid)).fillna(0.0).to_numpy()
        )
        return grid.assign(heuristic_probability=weight_of_cell / preference.sum())

    def _mix_the_crowd_preference_in(self, counted_cells: pd.DataFrame) -> pd.DataFrame:
        """Blend what really happened with what the crowd likes to tip."""
        matches_of_the_band = counted_cells.groupby("favorite_band")[
            "matches_with_this_scoreline"
        ].transform("sum")
        really_happened = (
            counted_cells["matches_with_this_scoreline"] / matches_of_the_band
        )
        crowd_weight = CrowdTipPriorCalculation.HEURISTIC_WEIGHT
        return counted_cells.assign(
            matches=matches_of_the_band,
            empirical_probability=really_happened,
            crowd_prior_probability=(1.0 - crowd_weight) * really_happened
            + crowd_weight * counted_cells["heuristic_probability"],
        )

    def _summarise_every_band(self, prior_cells: pd.DataFrame) -> pd.DataFrame:
        """Say per band how far the crowd sits from reality, and what it tips.

        The distortion is the total variation distance, so half the summed
        gap over the whole grid.
        """
        gap_to_reality = (
            prior_cells["empirical_probability"] - prior_cells["heuristic_probability"]
        ).abs()
        grouped = prior_cells.assign(gap_to_reality=gap_to_reality).groupby(
            "favorite_band", sort=True
        )
        summary = grouped.agg(
            matches=("matches", "first"),
            crowd_distortion=("gap_to_reality", "sum"),
        )
        most_tipped = prior_cells.loc[
            grouped["crowd_prior_probability"].idxmax()
        ].set_index("favorite_band")

        places = CrowdTipPriorCalculation.PROBABILITY_DECIMAL_PLACES
        separator = CrowdTipPriorCalculation.SCORELINE_SEPARATOR
        return summary.assign(
            crowd_distortion=(0.5 * summary["crowd_distortion"]).round(places),
            top_crowd_scoreline=most_tipped["favorite_goals"].astype(str)
            + separator
            + most_tipped["underdog_goals"].astype(str),
            top_crowd_probability=most_tipped["crowd_prior_probability"].round(places),
        ).reset_index()

    def _rounded_for_writing(self, prior_cells: pd.DataFrame) -> pd.DataFrame:
        """Cut every probability down to the digits the file carries."""
        places = CrowdTipPriorCalculation.PROBABILITY_DECIMAL_PLACES
        probability_columns = [
            "empirical_probability",
            "heuristic_probability",
            "crowd_prior_probability",
        ]
        return prior_cells.assign(
            **{name: prior_cells[name].round(places) for name in probability_columns}
        )


if __name__ == "__main__":
    CrowdTipPriorBuilder().build_the_prior()
