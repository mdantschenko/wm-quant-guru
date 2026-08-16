"""The two residual datasets that separate form and luck from strength.

Form is what a team won against what its rating said it would. Finishing is
what it scored against the chances it created. Both are what is left once the
expectation is taken away, and both are the kind of signal a rating cannot
carry because the rating is the expectation.

Every row holds the smoothed state as it stood before its own match. The state
is shifted by one row inside each team, so nothing in a row was known only
afterwards.
"""

import numpy as np
import pandas as pd

from wmguru.helpers.constant import (
    CrowdTipPriorCalculation,
    InternationalResultSource,
    ResidualFeatureCalculation,
)
from wmguru.helpers.utils import CsvFile, DecimalRounder, PreMatchRollingAverage


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
        ).write_table(form_rows)
        CsvFile(
            ResidualFeatureCalculation.FINISHING_OUTPUT_FILE,
            ResidualFeatureCalculation.FINISHING_COLUMN_NAMES,
        ).write_table(finishing_rows)
        print(f"  OK    {len(form_rows)} team rows of form residuals")
        print(f"  OK    {len(finishing_rows)} team rows of finishing residuals")
        return len(form_rows)

    def _build_form_rows(self) -> pd.DataFrame:
        """Build one row per team and international, oldest match first."""
        matches = self._read_matches_with_ratings()
        home_win_chance = self._home_win_chance(matches)
        home_residual = matches["home_points"] - home_win_chance

        both_sides = self._one_row_per_side(
            matches,
            home_side={
                "result": matches["home_points"],
                "elo_expected": home_win_chance,
                "elo_residual": home_residual,
            },
            away_side={
                "result": 1.0 - matches["home_points"],
                "elo_expected": 1.0 - home_win_chance,
                "elo_residual": -home_residual,
            },
        )
        brought_along = PreMatchRollingAverage(
            ResidualFeatureCalculation.FADING_WEIGHT,
            ResidualFeatureCalculation.WINDOW_LENGTH,
        ).what_every_team_brought_into_its_match(
            both_sides["team"], both_sides["elo_residual"]
        )

        rounder = DecimalRounder(ResidualFeatureCalculation.FORM_DECIMAL_PLACES)
        return both_sides.assign(
            neutral=both_sides["was_neutral"].astype(int),
            elo_expected=rounder.round_every_value(both_sides["elo_expected"]),
            elo_residual=rounder.round_every_value(both_sides["elo_residual"]),
            prematch_form_faded_average=rounder.round_every_value(
                brought_along["faded_average"]
            ),
            prematch_form_mean_of_last_five=rounder.round_every_value(
                brought_along["mean_of_the_window"]
            ),
            prematch_matches=brought_along["matches_played_before"],
        )

    def _build_finishing_rows(self) -> pd.DataFrame:
        """Build one row per team and tournament match, oldest match first."""
        matches = self._read_tournament_matches()
        both_sides = self._one_row_per_side(
            matches,
            home_side={
                "goals_for": matches["home_goals"],
                "expected_goals_for": matches["home_expected_goals"],
                "goals_against": matches["away_goals"],
                "expected_goals_against": matches["away_expected_goals"],
            },
            away_side={
                "goals_for": matches["away_goals"],
                "expected_goals_for": matches["away_expected_goals"],
                "goals_against": matches["home_goals"],
                "expected_goals_against": matches["home_expected_goals"],
            },
        )
        finishing_residual = both_sides["goals_for"] - both_sides["expected_goals_for"]
        brought_along = PreMatchRollingAverage(
            ResidualFeatureCalculation.FADING_WEIGHT,
            ResidualFeatureCalculation.WINDOW_LENGTH,
        ).what_every_team_brought_into_its_match(both_sides["team"], finishing_residual)

        rounder = DecimalRounder(ResidualFeatureCalculation.GOAL_DECIMAL_PLACES)
        return both_sides.assign(
            match_date=both_sides["date"],
            expected_goals_for=rounder.round_every_value(
                both_sides["expected_goals_for"]
            ),
            expected_goals_against=rounder.round_every_value(
                both_sides["expected_goals_against"]
            ),
            finishing_residual=rounder.round_every_value(finishing_residual),
            defensive_residual=rounder.round_every_value(
                both_sides["goals_against"] - both_sides["expected_goals_against"]
            ),
            prematch_finishing_faded_average=rounder.round_every_value(
                brought_along["faded_average"]
            ),
            prematch_finishing_mean_of_last_five=rounder.round_every_value(
                brought_along["mean_of_the_window"]
            ),
            prematch_matches=brought_along["matches_played_before"],
        )

    def _one_row_per_side(
        self,
        matches: pd.DataFrame,
        home_side: dict[str, pd.Series],
        away_side: dict[str, pd.Series],
    ) -> pd.DataFrame:
        """Split every match into the row of its home team and its away team.

        Args:
            matches: One row per match, already oldest first.
            home_side: The columns as the home team sees them.
            away_side: The same columns as the away team sees them.

        Returns:
            Two rows per match, the home team first, in the order the
            rolling averages have to walk them.
        """
        numbered = matches.rename_axis("match_order").reset_index()
        as_the_home_team = numbered.assign(
            side_order=0,
            team=numbered["home_team"],
            opponent=numbered["away_team"],
            is_home=1,
            **home_side,
        )
        as_the_away_team = numbered.assign(
            side_order=1,
            team=numbered["away_team"],
            opponent=numbered["home_team"],
            is_home=0,
            **away_side,
        )
        return (
            pd.concat([as_the_home_team, as_the_away_team])
            .sort_values(["match_order", "side_order"], kind="stable")
            .reset_index(drop=True)
        )

    def _read_matches_with_ratings(self) -> pd.DataFrame:
        """Read every played international that also has a rating, oldest first.

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

        with_ratings = played.merge(
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
        return (
            with_ratings.assign(
                was_neutral=with_ratings[InternationalResultSource.NEUTRAL_VENUE_COLUMN]
                .str.strip()
                .str.upper()
                == ResidualFeatureCalculation.NEUTRAL_TEXT,
                home_points=self._home_points_of(with_ratings),
            )
            .sort_values("date", kind="stable")
            .reset_index(drop=True)
        )

    def _home_points_of(self, matches: pd.DataFrame) -> pd.Series:
        """Read what the home side took out of every match.

        Returns:
            One for a win, a half for a draw, nothing for a defeat.
        """
        return pd.Series(
            np.select(
                [
                    matches["home_goals"] > matches["away_goals"],
                    matches["home_goals"] == matches["away_goals"],
                ],
                [
                    ResidualFeatureCalculation.WIN_POINTS,
                    ResidualFeatureCalculation.DRAW_POINTS,
                ],
                default=ResidualFeatureCalculation.LOSS_POINTS,
            ),
            index=matches.index,
        )

    def _home_win_chance(self, matches: pd.DataFrame) -> pd.Series:
        """How likely the home side was to win, out of the two ratings."""
        advantage = np.where(
            matches["was_neutral"], 0.0, CrowdTipPriorCalculation.HOME_ADVANTAGE
        )
        rating_gap = matches["home_rating"] + advantage - matches["away_rating"]
        return 1.0 / (
            1.0
            + CrowdTipPriorCalculation.LOGISTIC_BASE
            ** (-rating_gap / CrowdTipPriorCalculation.RATING_SCALE)
        )

    def _read_tournament_matches(self) -> pd.DataFrame:
        """Read every tournament match that carries expected goals, oldest first.

        Other builders write their own files into the same folder, and a row
        without both expected goals columns drops out on its own, which also
        takes care of a file that has no such columns at all.
        """
        match_files = sorted(
            ResidualFeatureCalculation.TOURNAMENT_FOLDER.glob(
                ResidualFeatureCalculation.MATCH_FILE_PATTERN
            )
        )
        every_file = pd.concat(
            [
                CsvFile(match_file).read_table().assign(tournament=match_file.stem)
                for match_file in match_files
            ],
            ignore_index=True,
        )
        home_expected = pd.to_numeric(
            every_file.get(ResidualFeatureCalculation.HOME_EXPECTED_GOALS_COLUMN),
            errors="coerce",
        )
        away_expected = pd.to_numeric(
            every_file.get(ResidualFeatureCalculation.AWAY_EXPECTED_GOALS_COLUMN),
            errors="coerce",
        )
        priced = every_file.assign(
            date=every_file["match_date"],
            home_expected_goals=home_expected,
            away_expected_goals=away_expected,
            home_goals=pd.to_numeric(every_file["home_score"], errors="coerce"),
            away_goals=pd.to_numeric(every_file["away_score"], errors="coerce"),
        ).dropna(subset=["home_expected_goals", "away_expected_goals"])

        return (
            priced.astype({"home_goals": int, "away_goals": int})
            .sort_values("date", kind="stable")
            .reset_index(drop=True)
        )


if __name__ == "__main__":
    ResidualFeatureBuilder().build_both_datasets()
