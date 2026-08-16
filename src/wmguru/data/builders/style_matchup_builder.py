"""Which style of play beats which, out of the style rows.

Every team of every season gets an archetype from its standardised style
values, and every pairing of archetypes gets the expected goals it produced
and conceded. That is the rock paper scissors effect in numbers.

Two files come out: the archetype of each team, and the matrix of pairings.
The matrix rests on expected goals, so it mostly covers StatsBomb.
"""

from statistics import mean, pstdev
from typing import Any

from wmguru.helpers.constant import MatchStyleFeature, StyleMatchupCalculation
from wmguru.helpers.utils import CsvFile


class StyleMatchupBuilder:
    """A style archetype per team, and every archetype paired off."""

    def build_the_matrix(self) -> int:
        """Write the archetype of every team and the matrix of pairings.

        Returns:
            How many pairings the matrix holds.
        """
        style_rows = CsvFile(MatchStyleFeature.OUTPUT_FILE).read_rows()
        profiles = self._average_every_team(style_rows)
        standardised = self._standardise_within_the_season(profiles)
        archetype_rows, archetype_of_team = self._build_archetype_rows(
            profiles, standardised
        )
        matrix_rows = self._build_matrix_rows(style_rows, archetype_of_team)

        CsvFile(
            StyleMatchupCalculation.ARCHETYPE_OUTPUT_FILE,
            StyleMatchupCalculation.ARCHETYPE_COLUMN_NAMES,
        ).write_dict_rows(archetype_rows)
        CsvFile(
            StyleMatchupCalculation.MATRIX_OUTPUT_FILE,
            StyleMatchupCalculation.MATRIX_COLUMN_NAMES,
        ).write_dict_rows(matrix_rows)
        print(
            f"  OK    {len(archetype_rows)} team archetypes, "
            f"{len(matrix_rows)} pairings"
        )
        return len(matrix_rows)

    def _average_every_team(
        self, style_rows: list[dict[str, str]]
    ) -> dict[tuple[str, str, str, str], dict[str, Any]]:
        """Average each style dimension over the matches of a team."""
        values_of_team: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for row in style_rows:
            key = (row["source"], row["competition"], row["season"], row["team"])
            collected = values_of_team.setdefault(
                key,
                {
                    "matches": 0,
                    **{name: [] for name in StyleMatchupCalculation.DIMENSIONS},
                },
            )
            collected["matches"] += 1
            for name in StyleMatchupCalculation.DIMENSIONS:
                value = self._as_number(row.get(name))
                if value is not None:
                    collected[name].append(value)

        return {
            key: {
                "matches": collected["matches"],
                **{
                    name: (mean(collected[name]) if collected[name] else None)
                    for name in StyleMatchupCalculation.DIMENSIONS
                },
            }
            for key, collected in values_of_team.items()
        }

    def _standardise_within_the_season(
        self, profiles: dict[tuple[str, str, str, str], dict[str, Any]]
    ) -> dict[tuple[str, str, str, str], dict[str, float]]:
        """Say how far each team sits from the middle of its own league.

        A share and a distance in metres cannot be compared as they are, and
        a league where everybody passes a lot would otherwise make every one
        of its teams look like a possession side.
        """
        teams_of_season: dict[tuple[str, str, str], list[tuple[Any, dict]]] = {}
        for (source, competition, season, team), profile in profiles.items():
            teams_of_season.setdefault((source, competition, season), []).append(
                ((source, competition, season, team), profile)
            )

        standardised: dict[tuple[str, str, str, str], dict[str, float]] = {}
        for members in teams_of_season.values():
            for name in StyleMatchupCalculation.DIMENSIONS:
                values = [
                    profile[name]
                    for _key, profile in members
                    if profile[name] is not None
                ]
                middle, spread = self._scale_of(values)
                for key, profile in members:
                    standardised.setdefault(key, {})[name] = (
                        (profile[name] - middle) / spread
                        if profile[name] is not None and spread
                        else 0.0
                    )
        return standardised

    def _scale_of(self, values: list[float]) -> tuple[float, float]:
        """The middle and the spread a value is standardised with."""
        if len(values) < StyleMatchupCalculation.MINIMUM_VALUES_FOR_A_SCALE:
            return 0.0, 0.0
        return mean(values), pstdev(values)

    def _build_archetype_rows(
        self,
        profiles: dict[tuple[str, str, str, str], dict[str, Any]],
        standardised: dict[tuple[str, str, str, str], dict[str, float]],
    ) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str, str], str]]:
        """Build one row per team, and the lookup the matrix needs.

        Returns:
            The rows, and the archetype of every team the matrix can look up.
            A team with too few matches is left out of both.
        """
        rows: list[dict[str, Any]] = []
        archetype_of_team: dict[tuple[str, str, str, str], str] = {}
        for key, profile in profiles.items():
            if profile["matches"] < StyleMatchupCalculation.MINIMUM_MATCHES:
                continue
            values = standardised[key]
            archetype = self.archetype_of(values)
            archetype_of_team[key] = archetype
            source, competition, season, team = key
            places = StyleMatchupCalculation.STANDARDISED_DECIMAL_PLACES
            rows.append(
                {
                    "source": source,
                    "competition": competition,
                    "season": season,
                    "team": team,
                    "matches": profile["matches"],
                    "pass_share_standardised": round(values["pass_share"], places),
                    "field_tilt_standardised": round(values["field_tilt"], places),
                    "passes_per_defensive_action_standardised": round(
                        values["passes_per_defensive_action"], places
                    ),
                    "directness_standardised": round(
                        values["directness_in_metres"], places
                    ),
                    "defensive_action_height_standardised": round(
                        values["defensive_action_height_in_metres"], places
                    ),
                    "archetype": archetype,
                    "has_empty_possession": int(self._has_empty_possession(values)),
                }
            )
        return (
            sorted(
                rows,
                key=lambda one: (
                    str(one["source"]),
                    str(one["competition"]),
                    str(one["season"]),
                    str(one["team"]),
                ),
            ),
            archetype_of_team,
        )

    def archetype_of(self, values: dict[str, float]) -> str:
        """Name the style a team played, out of its standardised values.

        Args:
            values: How far the team sat from the middle of its league in
                each dimension.

        Returns:
            The archetype. The order of the checks matters: a side that keeps
            the ball without ever getting near the box is its own thing, and
            has to be caught before it is called dominant.
        """
        high = StyleMatchupCalculation.HIGH_FROM
        low = StyleMatchupCalculation.LOW_UP_TO
        if values["pass_share"] >= high and values["field_tilt"] >= high:
            return StyleMatchupCalculation.POSSESSION_DOMINANCE_NAME
        if self._has_empty_possession(values):
            return StyleMatchupCalculation.EMPTY_POSSESSION_NAME
        if values["directness_in_metres"] >= high and values["pass_share"] <= low:
            return StyleMatchupCalculation.DIRECT_AND_PHYSICAL_NAME
        if values["pass_share"] <= low and (
            values["passes_per_defensive_action"] >= high
            or values["defensive_action_height_in_metres"] <= low
        ):
            return StyleMatchupCalculation.DEEP_BLOCK_AND_COUNTER_NAME
        return StyleMatchupCalculation.BALANCED_NAME

    def _has_empty_possession(self, values: dict[str, float]) -> bool:
        """Return True when a team keeps the ball but never gets anywhere with it."""
        return (
            values["pass_share"] >= StyleMatchupCalculation.HIGH_FROM
            and values["field_tilt"] < 0
        )

    def _build_matrix_rows(
        self,
        style_rows: list[dict[str, str]],
        archetype_of_team: dict[tuple[str, str, str, str], str],
    ) -> list[dict[str, Any]]:
        """Average the expected goals of every pairing of archetypes."""
        cells: dict[tuple[str, str], list[float]] = {}
        for row in style_rows:
            season_key = (row["source"], row["competition"], row["season"])
            archetype_for = archetype_of_team.get((*season_key, row["team"]))
            archetype_against = archetype_of_team.get((*season_key, row["opponent"]))
            created = self._as_number(row.get("expected_goals"))
            conceded = self._as_number(row.get("expected_goals_against"))
            if None in (archetype_for, archetype_against, created, conceded):
                continue
            cell = cells.setdefault((archetype_for, archetype_against), [0.0, 0.0, 0.0])
            cell[0] += 1
            cell[1] += created
            cell[2] += conceded

        places = StyleMatchupCalculation.EXPECTED_GOALS_DECIMAL_PLACES
        rows = [
            {
                "archetype_for": archetype_for,
                "archetype_against": archetype_against,
                "matches": int(matches),
                "mean_expected_goals_for": round(created / matches, places),
                "mean_expected_goals_against": round(conceded / matches, places),
                "mean_expected_goals_difference": round(
                    (created - conceded) / matches, places
                ),
            }
            for (archetype_for, archetype_against), (
                matches,
                created,
                conceded,
            ) in cells.items()
        ]
        return sorted(
            rows,
            key=lambda one: (one["archetype_for"], one["archetype_against"]),
        )

    def _as_number(self, value: str | None) -> float | None:
        """Read a cell as a number, or None when it holds none."""
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    StyleMatchupBuilder().build_the_matrix()
