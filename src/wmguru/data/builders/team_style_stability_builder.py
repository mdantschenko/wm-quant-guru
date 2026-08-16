"""How much a team's style swings from match to match.

Reads the style rows both event sources wrote and, per competition and season,
standardises every dimension so a share and a distance in metres can be
compared at all. The swing of a team is then the average spread of those
standardised values over its matches.
"""

from statistics import mean, pstdev
from typing import Any

from wmguru.helpers.constant import (
    MatchStyleFeature,
    TeamStyleStabilityCalculation,
)
from wmguru.helpers.utils import CsvFile


class TeamStyleStabilityBuilder:
    """The style rows of every match, as one row per team and season."""

    def build_every_team(self) -> int:
        """Write one row per team that played enough matches to judge.

        Returns:
            How many teams the file holds.
        """
        style_rows = CsvFile(MatchStyleFeature.OUTPUT_FILE).read_rows()
        scales = self._scales_of_every_season(style_rows)
        rows = self._build_rows(self._group_by_team(style_rows), scales)

        output_file = CsvFile(
            TeamStyleStabilityCalculation.OUTPUT_FILE,
            TeamStyleStabilityCalculation.COLUMN_NAMES,
        )
        output_file.write_dict_rows(rows)
        print(
            f"  OK    {len(rows)} team rows with at least "
            f"{TeamStyleStabilityCalculation.MINIMUM_MATCHES} matches"
        )
        return len(rows)

    def _scales_of_every_season(
        self, style_rows: list[dict[str, str]]
    ) -> dict[tuple[str, str, str], dict[str, tuple[float, float]]]:
        """Work out the middle and the spread of each dimension per season.

        Returns:
            The two numbers a value is standardised with, per source,
            competition, season and dimension. A dimension with fewer than two
            values is left out, because a spread needs two.
        """
        values_of_season: dict[tuple[str, str, str], dict[str, list[float]]] = {}
        for row in style_rows:
            season_key = (row["source"], row["competition"], row["season"])
            values_of_dimension = values_of_season.setdefault(
                season_key,
                {name: [] for name in TeamStyleStabilityCalculation.DIMENSIONS},
            )
            for name in TeamStyleStabilityCalculation.DIMENSIONS:
                value = self._as_number(row.get(name))
                if value is not None:
                    values_of_dimension[name].append(value)

        return {
            season_key: {
                name: (mean(values), pstdev(values))
                for name, values in values_of_dimension.items()
                if len(values)
                >= TeamStyleStabilityCalculation.MINIMUM_VALUES_FOR_A_SCALE
            }
            for season_key, values_of_dimension in values_of_season.items()
        }

    def _group_by_team(
        self, style_rows: list[dict[str, str]]
    ) -> dict[tuple[str, str, str, str], list[dict[str, str]]]:
        """Collect the matches of each team of each season."""
        matches_of_team: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
        for row in style_rows:
            key = (row["source"], row["competition"], row["season"], row["team"])
            matches_of_team.setdefault(key, []).append(row)
        return matches_of_team

    def _build_rows(
        self,
        matches_of_team: dict[tuple[str, str, str, str], list[dict[str, str]]],
        scales: dict[tuple[str, str, str], dict[str, tuple[float, float]]],
    ) -> list[dict[str, Any]]:
        """Build one row per team that played enough matches."""
        rows: list[dict[str, Any]] = []
        for (source, competition, season, team), matches in matches_of_team.items():
            if len(matches) < TeamStyleStabilityCalculation.MINIMUM_MATCHES:
                continue
            scale_of_dimension = scales.get((source, competition, season), {})
            row: dict[str, Any] = {
                "source": source,
                "competition": competition,
                "season": season,
                "team": team,
                "matches": len(matches),
            }
            swings: list[float] = []
            for name in TeamStyleStabilityCalculation.DIMENSIONS:
                middle, swing = self._summarise_one_dimension(
                    matches, name, scale_of_dimension.get(name)
                )
                row[name + TeamStyleStabilityCalculation.MEAN_SUFFIX] = middle
                row[name + TeamStyleStabilityCalculation.VOLATILITY_SUFFIX] = swing
                if isinstance(swing, float):
                    swings.append(swing)
            row["style_volatility"] = (
                round(mean(swings), TeamStyleStabilityCalculation.DECIMAL_PLACES)
                if swings
                else ""
            )
            rows.append(row)
        return sorted(
            rows,
            key=lambda one: (
                str(one["source"]),
                str(one["competition"]),
                str(one["season"]),
                str(one["team"]),
            ),
        )

    def _summarise_one_dimension(
        self,
        matches: list[dict[str, str]],
        dimension_name: str,
        scale: tuple[float, float] | None,
    ) -> tuple[Any, Any]:
        """Say what a team usually did in one dimension, and how much it varied.

        Args:
            matches: Every style row of the team in that season.
            dimension_name: Which style column to look at.
            scale: The middle and the spread of this dimension over the whole
                season, or None when the season gave too few values to say.

        Returns:
            The plain average of the team, and the spread of its standardised
            values. Both are empty when the team has no value at all, and the
            swing alone is empty when the season could not be standardised.
        """
        values = [
            value
            for value in (
                self._as_number(match.get(dimension_name)) for match in matches
            )
            if value is not None
        ]
        if not values:
            return "", ""
        places = TeamStyleStabilityCalculation.DECIMAL_PLACES
        if scale is None or not scale[1]:
            return round(mean(values), places), ""
        middle, spread = scale
        standardised = [(value - middle) / spread for value in values]
        return round(mean(values), places), round(pstdev(standardised), places)

    def _as_number(self, value: str | None) -> float | None:
        """Read a cell as a number, or None when it holds none.

        A style column is left empty where the match gave nothing to divide
        by, and an empty cell must not be read as a zero.
        """
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    TeamStyleStabilityBuilder().build_every_team()
