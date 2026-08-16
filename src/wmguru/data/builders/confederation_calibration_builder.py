"""What the Elo ratings get wrong between the confederations.

National teams play mostly inside their own confederation, so how the
confederations stand against each other is barely in the ratings. That is
exactly the comparison a World Cup turns on.

Three files come out: the residual of every pair and era, the estimated Elo
offset of every confederation, and an audit of which team was put where.
"""

import math
from typing import Any

from wmguru.helpers.constant import (
    ConfederationCalibration,
    CrowdTipPriorCalculation,
    InternationalResultSource,
    ResidualFeatureCalculation,
)
from wmguru.helpers.utils import ConfederationLookup, CsvFile, TextNormalizer


class ConfederationCalibrationBuilder:
    """The rating bias between confederations, per era."""

    def __init__(self, confederation_lookup: ConfederationLookup) -> None:
        self._confederation_lookup = confederation_lookup

    def build_the_calibration(self) -> int:
        """Write the pair residuals, the offsets and the team audit.

        Returns:
            How many matches across confederations carried a rating.
        """
        matches, matches_of_team = self._read_cross_confederation_matches()

        pair_rows = self._build_pair_rows(matches)
        offset_rows = self._build_offset_rows(matches)
        team_rows = self._build_team_rows(matches_of_team)

        CsvFile(
            ConfederationCalibration.PAIR_OUTPUT_FILE,
            ConfederationCalibration.PAIR_COLUMN_NAMES,
        ).write_dict_rows(pair_rows)
        CsvFile(
            ConfederationCalibration.OFFSET_OUTPUT_FILE,
            ConfederationCalibration.OFFSET_COLUMN_NAMES,
        ).write_dict_rows(offset_rows)
        CsvFile(
            ConfederationCalibration.TEAM_MAP_OUTPUT_FILE,
            ConfederationCalibration.TEAM_MAP_COLUMN_NAMES,
        ).write_dict_rows(team_rows)

        unmapped = sum(
            1
            for row in team_rows
            if row["confederation"] == ConfederationCalibration.UNMAPPED_NAME
        )
        print(f"  OK    {len(matches)} cross confederation matches with a rating")
        print(f"  OK    {len(pair_rows)} pair rows, {len(offset_rows)} offset rows")
        print(f"  INFO  {unmapped} teams without a confederation")
        return len(matches)

    def _read_cross_confederation_matches(
        self,
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        """Read every played match between two confederations that has a rating.

        Returns:
            The matches, and how many matches each team played at all. The
            second is only for the audit file, so a team that fell out of the
            table is easy to spot.
        """
        ratings_of_match = {
            (row["date"], row["home_team"], row["away_team"]): (
                float(row["elo_home_pre"]),
                float(row["elo_away_pre"]),
            )
            for row in CsvFile(CrowdTipPriorCalculation.ELO_HISTORY_FILE).read_rows()
        }

        matches: list[dict[str, Any]] = []
        matches_of_team: dict[str, dict[str, Any]] = {}
        for row in CsvFile(CrowdTipPriorCalculation.RESULT_FILE).read_rows():
            home_team = row[InternationalResultSource.HOME_TEAM_COLUMN]
            away_team = row[InternationalResultSource.AWAY_TEAM_COLUMN]
            home_confederation = self._confederation_lookup.confederation_of(home_team)
            away_confederation = self._confederation_lookup.confederation_of(away_team)
            self._note_the_teams(
                matches_of_team,
                ((home_team, home_confederation), (away_team, away_confederation)),
            )

            points = self._home_points_of(row)
            ratings = ratings_of_match.get(
                (
                    row[InternationalResultSource.DATE_COLUMN],
                    home_team,
                    away_team,
                )
            )
            if (
                points is None
                or ratings is None
                or home_confederation is None
                or away_confederation is None
                or home_confederation == away_confederation
            ):
                continue
            matches.append(
                {
                    "era": self.era_of(
                        int(row[InternationalResultSource.DATE_COLUMN][:4])
                    ),
                    "home_confederation": home_confederation,
                    "away_confederation": away_confederation,
                    "home_rating": ratings[0],
                    "away_rating": ratings[1],
                    "was_neutral": row[InternationalResultSource.NEUTRAL_VENUE_COLUMN]
                    .strip()
                    .upper()
                    == ResidualFeatureCalculation.NEUTRAL_TEXT,
                    "home_points": points,
                    "goal_difference": int(row["home_score"]) - int(row["away_score"]),
                }
            )
        return matches, matches_of_team

    def _note_the_teams(
        self,
        matches_of_team: dict[str, dict[str, Any]],
        teams: tuple[tuple[str, str | None], ...],
    ) -> None:
        """Count one match for both teams, for the audit file."""
        for team_name, confederation in teams:
            record = matches_of_team.setdefault(
                team_name,
                {
                    "confederation": confederation
                    or ConfederationCalibration.UNMAPPED_NAME,
                    "matches": 0,
                },
            )
            record["matches"] += 1

    def _home_points_of(self, row: dict[str, str]) -> float | None:
        """Read what the home side took out of the match, or None if unplayed."""
        try:
            home_goals = int(row["home_score"])
            away_goals = int(row["away_score"])
        except (KeyError, TypeError, ValueError):
            return None
        if home_goals > away_goals:
            return ResidualFeatureCalculation.WIN_POINTS
        if home_goals == away_goals:
            return ResidualFeatureCalculation.DRAW_POINTS
        return ResidualFeatureCalculation.LOSS_POINTS

    def era_of(self, year: int) -> str:
        """Say which era a year belongs to."""
        for last_year, name in ConfederationCalibration.ERA_EDGES:
            if year < last_year:
                return name
        return ConfederationCalibration.LATEST_ERA_NAME

    def _expectation_of(
        self, home_rating: float, away_rating: float, was_neutral: bool
    ) -> float:
        """What the rating said the home side would take out of the match."""
        advantage = 0.0 if was_neutral else CrowdTipPriorCalculation.HOME_ADVANTAGE
        difference = home_rating + advantage - away_rating
        return 1.0 / (
            1.0
            + CrowdTipPriorCalculation.LOGISTIC_BASE
            ** (-difference / CrowdTipPriorCalculation.RATING_SCALE)
        )

    def _build_pair_rows(self, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Average the residual of every pair of confederations, per era."""
        values_of_pair: dict[tuple[str, str, str], list[tuple[float, float, int]]] = {}
        for match in matches:
            expectation = self._expectation_of(
                match["home_rating"], match["away_rating"], match["was_neutral"]
            )
            values = (
                match["home_points"] - expectation,
                expectation,
                match["goal_difference"],
            )
            for era in (match["era"], ConfederationCalibration.EVERY_ERA_NAME):
                values_of_pair.setdefault(
                    (era, match["home_confederation"], match["away_confederation"]),
                    [],
                ).append(values)

        rows: list[dict[str, Any]] = []
        for (era, home_confederation, away_confederation), values in sorted(
            values_of_pair.items()
        ):
            match_count = len(values)
            rows.append(
                {
                    "era": era,
                    "confederation_home": home_confederation,
                    "confederation_away": away_confederation,
                    "matches": match_count,
                    "mean_result_residual": round(
                        sum(one[0] for one in values) / match_count,
                        ConfederationCalibration.RESIDUAL_DECIMAL_PLACES,
                    ),
                    "mean_elo_expected": round(
                        sum(one[1] for one in values) / match_count,
                        ConfederationCalibration.RESIDUAL_DECIMAL_PLACES,
                    ),
                    "mean_goal_difference": round(
                        sum(one[2] for one in values) / match_count,
                        ConfederationCalibration.GOAL_DECIMAL_PLACES,
                    ),
                }
            )
        return rows

    def _build_offset_rows(self, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Estimate the offsets of every era that has enough matches."""
        matches_of_era: dict[str, list[dict[str, Any]]] = {
            ConfederationCalibration.EVERY_ERA_NAME: list(matches)
        }
        for match in matches:
            matches_of_era.setdefault(match["era"], []).append(match)

        rows: list[dict[str, Any]] = []
        for era, era_matches in sorted(matches_of_era.items()):
            if len(era_matches) < ConfederationCalibration.MINIMUM_MATCHES_FOR_A_FIT:
                continue
            for confederation, offset in sorted(self._fit_offsets(era_matches).items()):
                rows.append(
                    {
                        "era": era,
                        "confederation": confederation,
                        ConfederationCalibration.OFFSET_COLUMN: offset,
                        "matches_in_era": len(era_matches),
                    }
                )
        return rows

    def _fit_offsets(self, matches: list[dict[str, Any]]) -> dict[str, float]:
        """Find the rating offsets that explain these matches best.

        The step divides by the curvature rather than by a fixed rate,
        because one Elo point barely moves a probability and a plain gradient
        step would crawl. The reference confederation is held at zero, the
        offsets only mean anything against each other.
        """
        confederations = sorted(
            {match["home_confederation"] for match in matches}
            | {match["away_confederation"] for match in matches}
        )
        offsets = {confederation: 0.0 for confederation in confederations}
        sensitivity_scale = (
            math.log(CrowdTipPriorCalculation.LOGISTIC_BASE)
            / CrowdTipPriorCalculation.RATING_SCALE
        )

        for _round in range(ConfederationCalibration.FITTING_ROUNDS):
            slope = {confederation: 0.0 for confederation in confederations}
            curvature = {confederation: 0.0 for confederation in confederations}
            for match in matches:
                home = match["home_confederation"]
                away = match["away_confederation"]
                expectation = self._expectation_of(
                    match["home_rating"] + offsets[home],
                    match["away_rating"] + offsets[away],
                    match["was_neutral"],
                )
                steepness = expectation * (1.0 - expectation) * sensitivity_scale
                error = (expectation - match["home_points"]) * steepness
                slope[home] += error
                slope[away] -= error
                curvature[home] += steepness * steepness
                curvature[away] += steepness * steepness
            for confederation in confederations:
                if confederation == ConfederationCalibration.REFERENCE_CONFEDERATION:
                    continue
                offsets[confederation] -= slope[confederation] / (
                    curvature[confederation]
                    + ConfederationCalibration.SMALLEST_USABLE_CURVATURE
                )
        return {
            confederation: round(offset, ConfederationCalibration.OFFSET_DECIMAL_PLACES)
            for confederation, offset in offsets.items()
        }

    def _build_team_rows(
        self, matches_of_team: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Build the audit rows, the busiest team first."""
        rows = [
            {
                "team": team_name,
                "confederation": record["confederation"],
                "matches": record["matches"],
            }
            for team_name, record in matches_of_team.items()
        ]
        return sorted(rows, key=lambda one: -int(one["matches"]))


if __name__ == "__main__":
    ConfederationCalibrationBuilder(
        ConfederationLookup(TextNormalizer())
    ).build_the_calibration()
