"""The two residual datasets that separate form and luck from strength.

Form is what a team won against what its rating said it would. Finishing is
what it scored against the chances it created. Both are what is left once the
expectation is taken away, and both are the kind of signal a rating cannot
carry because the rating is the expectation.

Every row holds the smoothed state as it stood before its own match. The state
is updated only after the row has been written, so nothing in a row was known
only afterwards.
"""

from typing import Any

from wmguru.helpers.constant import (
    CrowdTipPriorCalculation,
    InternationalResultSource,
    ResidualFeatureCalculation,
)
from wmguru.helpers.utils import CsvFile, PreMatchRollingAverage


class ResidualFeatureBuilder:
    """The form residuals of every international, and the finishing ones."""

    def build_both_datasets(self) -> int:
        """Write both files.

        Returns:
            How many team rows the form file holds.
        """
        form_rows = self._build_form_rows()
        finishing_rows = self._build_finishing_rows()

        CsvFile(
            ResidualFeatureCalculation.FORM_OUTPUT_FILE,
            ResidualFeatureCalculation.FORM_COLUMN_NAMES,
        ).write_dict_rows(form_rows)
        CsvFile(
            ResidualFeatureCalculation.FINISHING_OUTPUT_FILE,
            ResidualFeatureCalculation.FINISHING_COLUMN_NAMES,
        ).write_dict_rows(finishing_rows)
        print(f"  OK    {len(form_rows)} team rows of form residuals")
        print(f"  OK    {len(finishing_rows)} team rows of finishing residuals")
        return len(form_rows)

    def _build_form_rows(self) -> list[dict[str, Any]]:
        """Build one row per team and international, oldest match first."""
        rolling_form = PreMatchRollingAverage(
            ResidualFeatureCalculation.FADING_WEIGHT,
            ResidualFeatureCalculation.WINDOW_LENGTH,
        )
        rows: list[dict[str, Any]] = []
        for match in self._read_matches_with_ratings():
            expectation = self._home_win_expectation(match)
            home_residual = match["home_points"] - expectation
            for team_name, opponent_name, is_home, points, expected, residual in (
                (
                    match["home_team"],
                    match["away_team"],
                    1,
                    match["home_points"],
                    expectation,
                    home_residual,
                ),
                (
                    match["away_team"],
                    match["home_team"],
                    0,
                    1.0 - match["home_points"],
                    1.0 - expectation,
                    -home_residual,
                ),
            ):
                rows.append(
                    self._build_one_form_row(
                        match,
                        team_name,
                        opponent_name,
                        is_home,
                        points,
                        expected,
                        residual,
                        rolling_form,
                    )
                )
                rolling_form.add_one_match(team_name, residual)
        return rows

    def _build_one_form_row(
        self,
        match: dict[str, Any],
        team_name: str,
        opponent_name: str,
        is_home: int,
        points: float,
        expected: float,
        residual: float,
        rolling_form: PreMatchRollingAverage,
    ) -> dict[str, Any]:
        """Build the row of one team of one international."""
        faded, window_mean, match_count = rolling_form.before_the_next_match(team_name)
        places = ResidualFeatureCalculation.FORM_DECIMAL_PLACES
        return {
            "date": match["date"],
            "tournament": match["tournament"],
            "team": team_name,
            "opponent": opponent_name,
            "is_home": is_home,
            "neutral": int(match["was_neutral"]),
            "result": points,
            "elo_expected": round(expected, places),
            "elo_residual": round(residual, places),
            "prematch_form_faded_average": round(faded, places),
            "prematch_form_mean_of_last_five": round(window_mean, places),
            "prematch_matches": match_count,
        }

    def _read_matches_with_ratings(self) -> list[dict[str, Any]]:
        """Read every played international that also has a rating, oldest first."""
        ratings_of_match = {
            (row["date"], row["home_team"], row["away_team"]): (
                float(row["elo_home_pre"]),
                float(row["elo_away_pre"]),
            )
            for row in CsvFile(CrowdTipPriorCalculation.ELO_HISTORY_FILE).read_rows()
        }

        matches: list[dict[str, Any]] = []
        for row in CsvFile(CrowdTipPriorCalculation.RESULT_FILE).read_rows():
            points = self._home_points_of(row)
            ratings = ratings_of_match.get(
                (
                    row[InternationalResultSource.DATE_COLUMN],
                    row[InternationalResultSource.HOME_TEAM_COLUMN],
                    row[InternationalResultSource.AWAY_TEAM_COLUMN],
                )
            )
            if points is None or ratings is None:
                continue
            matches.append(
                {
                    "date": row[InternationalResultSource.DATE_COLUMN],
                    "tournament": row[InternationalResultSource.TOURNAMENT_COLUMN],
                    "home_team": row[InternationalResultSource.HOME_TEAM_COLUMN],
                    "away_team": row[InternationalResultSource.AWAY_TEAM_COLUMN],
                    "was_neutral": row[InternationalResultSource.NEUTRAL_VENUE_COLUMN]
                    .strip()
                    .upper()
                    == ResidualFeatureCalculation.NEUTRAL_TEXT,
                    "home_rating": ratings[0],
                    "away_rating": ratings[1],
                    "home_points": points,
                }
            )
        return sorted(matches, key=lambda one: str(one["date"]))

    def _home_points_of(self, row: dict[str, str]) -> float | None:
        """Read what the home side took out of the match.

        Returns:
            One for a win, a half for a draw, nothing for a defeat, or None
            for a match that was never played.
        """
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

    def _home_win_expectation(self, match: dict[str, Any]) -> float:
        """How likely the home side was to win, out of the two ratings."""
        advantage = (
            0.0 if match["was_neutral"] else CrowdTipPriorCalculation.HOME_ADVANTAGE
        )
        difference = match["home_rating"] + advantage - match["away_rating"]
        return 1.0 / (
            1.0
            + CrowdTipPriorCalculation.LOGISTIC_BASE
            ** (-difference / CrowdTipPriorCalculation.RATING_SCALE)
        )

    def _build_finishing_rows(self) -> list[dict[str, Any]]:
        """Build one row per team and tournament match, oldest match first."""
        rolling_finishing = PreMatchRollingAverage(
            ResidualFeatureCalculation.FADING_WEIGHT,
            ResidualFeatureCalculation.WINDOW_LENGTH,
        )
        rows: list[dict[str, Any]] = []
        for match in self._read_tournament_matches():
            for team_name, opponent_name, is_home, side, other_side in (
                (match["home_team"], match["away_team"], 1, "home", "away"),
                (match["away_team"], match["home_team"], 0, "away", "home"),
            ):
                rows.append(
                    self._build_one_finishing_row(
                        match,
                        team_name,
                        opponent_name,
                        is_home,
                        side,
                        other_side,
                        rolling_finishing,
                    )
                )
                rolling_finishing.add_one_match(
                    team_name,
                    match[f"{side}_goals"] - match[f"{side}_expected_goals"],
                )
        return rows

    def _build_one_finishing_row(
        self,
        match: dict[str, Any],
        team_name: str,
        opponent_name: str,
        is_home: int,
        side: str,
        other_side: str,
        rolling_finishing: PreMatchRollingAverage,
    ) -> dict[str, Any]:
        """Build the row of one team of one tournament match."""
        goals_for = match[f"{side}_goals"]
        created = match[f"{side}_expected_goals"]
        goals_against = match[f"{other_side}_goals"]
        conceded_chances = match[f"{other_side}_expected_goals"]
        faded, window_mean, match_count = rolling_finishing.before_the_next_match(
            team_name
        )
        places = ResidualFeatureCalculation.GOAL_DECIMAL_PLACES
        return {
            "match_date": match["date"],
            "tournament": match["tournament"],
            "team": team_name,
            "opponent": opponent_name,
            "is_home": is_home,
            "goals_for": goals_for,
            "expected_goals_for": round(created, places),
            "goals_against": goals_against,
            "expected_goals_against": round(conceded_chances, places),
            "finishing_residual": round(goals_for - created, places),
            "defensive_residual": round(goals_against - conceded_chances, places),
            "prematch_finishing_faded_average": round(faded, places),
            "prematch_finishing_mean_of_last_five": round(window_mean, places),
            "prematch_matches": match_count,
        }

    def _read_tournament_matches(self) -> list[dict[str, Any]]:
        """Read every tournament match that carries expected goals, oldest first.

        Other builders write their own files into the same folder, so a file
        without the expected goals columns is skipped rather than read as a
        match list.
        """
        matches: list[dict[str, Any]] = []
        for match_file in sorted(
            ResidualFeatureCalculation.TOURNAMENT_FOLDER.glob(
                ResidualFeatureCalculation.MATCH_FILE_PATTERN
            )
        ):
            for row in CsvFile(match_file).read_rows():
                if not (
                    row.get(ResidualFeatureCalculation.HOME_EXPECTED_GOALS_COLUMN)
                    and row.get(ResidualFeatureCalculation.AWAY_EXPECTED_GOALS_COLUMN)
                ):
                    continue
                matches.append(
                    {
                        "date": row["match_date"],
                        "tournament": match_file.stem,
                        "home_team": row["home_team"],
                        "away_team": row["away_team"],
                        "home_goals": int(row["home_score"]),
                        "away_goals": int(row["away_score"]),
                        "home_expected_goals": float(
                            row[ResidualFeatureCalculation.HOME_EXPECTED_GOALS_COLUMN]
                        ),
                        "away_expected_goals": float(
                            row[ResidualFeatureCalculation.AWAY_EXPECTED_GOALS_COLUMN]
                        ),
                    }
                )
        return sorted(matches, key=lambda one: str(one["date"]))


if __name__ == "__main__":
    ResidualFeatureBuilder().build_both_datasets()
