"""The Elo rating of every national team before every match it played.

The downloaded Elo dataset holds only about 400 snapshot days, but the concept
needs the rating as it stood *before* each match, because a feature that knows
the result would make every backtest meaningless.

This engine therefore walks the whole result file in date order and computes
the history itself, following the method of eloratings.net: a K factor per
competition type, a multiplier for the goal difference, a home advantage that
falls away on a neutral pitch, and 1500 as the rating a new team starts with.

It writes one row per match with the pre match rating of both teams, plus a
closing ranking that can be checked against the live table of eloratings.net.
"""

import numpy as np
import pandas as pd

from wmguru.helpers.constant import EloRatingCalculation, InternationalResultSource
from wmguru.helpers.utils import CsvFile, DecimalRounder


class EloRatingBuilder:
    """A running rating per team, over every match in date order."""

    def build_history(self) -> tuple[int, int]:
        """Write the pre match history and the closing ranking.

        Returns:
            How many matches went into the history, and how many teams the
            closing ranking holds.
        """
        matches = self._read_played_matches()
        history, closing_ratings = self._play_every_match_in_order(matches)

        history_file = CsvFile(
            EloRatingCalculation.OUTPUT_FOLDER / EloRatingCalculation.HISTORY_FILE_NAME,
            EloRatingCalculation.HISTORY_COLUMN_NAMES,
        )
        history_file.write_table(history)
        snapshot_file = self._write_snapshot(closing_ratings)

        print(f"{len(history)} matches -> {history_file.path}")
        print(
            f"{len(closing_ratings)} teams in the closing ranking "
            f"-> {snapshot_file.path}"
        )
        return len(history), len(closing_ratings)

    def k_factor_of(self, tournament_names: pd.Series) -> pd.Series:
        """Read how much one match of each competition may move a rating.

        Args:
            tournament_names: The competition as the result file writes it.

        Returns:
            60 for a World Cup final round, 50 for a continental final round,
            40 for a qualification or the Nations League, 20 for a friendly
            and 30 for anything else.
        """
        name = tournament_names.str.strip()
        lowered = name.str.lower()
        return pd.Series(
            np.select(
                [
                    name == EloRatingCalculation.WORLD_CUP_NAME,
                    self._carries_any_of_these_parts(
                        lowered, EloRatingCalculation.QUALIFIER_NAME_PARTS
                    ),
                    self._carries_any_of_these_parts(
                        name, EloRatingCalculation.CONTINENTAL_FINALS_NAMES
                    ),
                    lowered == EloRatingCalculation.FRIENDLY_NAME,
                ],
                [
                    EloRatingCalculation.K_FACTOR_WORLD_CUP,
                    EloRatingCalculation.K_FACTOR_QUALIFIER,
                    EloRatingCalculation.K_FACTOR_CONTINENTAL_FINALS,
                    EloRatingCalculation.K_FACTOR_FRIENDLY,
                ],
                default=EloRatingCalculation.K_FACTOR_OTHER_TOURNAMENT,
            ),
            index=tournament_names.index,
        )

    def _carries_any_of_these_parts(
        self, names: pd.Series, wanted_parts: tuple[str, ...]
    ) -> pd.Series:
        """Return True where a name carries any one of the given parts."""
        return names.str.contains("|".join(wanted_parts), regex=True, na=False)

    def goal_multiplier_of(self, goal_differences: pd.Series) -> pd.Series:
        """Read how much a clear win counts over a narrow one.

        Args:
            goal_differences: The margin, always taken as a positive number.

        Returns:
            One up to a one goal margin, one and a half at two goals, and a
            value that keeps growing but ever more slowly above that.
        """
        return pd.Series(
            np.select(
                [
                    goal_differences <= EloRatingCalculation.NARROW_GOAL_DIFFERENCE,
                    goal_differences == EloRatingCalculation.TWO_GOAL_DIFFERENCE,
                ],
                [
                    EloRatingCalculation.MULTIPLIER_NARROW,
                    EloRatingCalculation.MULTIPLIER_TWO_GOALS,
                ],
                default=(EloRatingCalculation.MULTIPLIER_OFFSET + goal_differences)
                / EloRatingCalculation.MULTIPLIER_DIVISOR,
            ),
            index=goal_differences.index,
        )

    def expected_score_of(self, rating_difference: float) -> float:
        """Work out how likely the stronger side is to win.

        Args:
            rating_difference: Rating of the home team minus that of the away
                team, with the home advantage already added when it applies.

        Returns:
            A value between zero and one, one half when both are equal.
        """
        return 1.0 / (
            1.0
            + EloRatingCalculation.LOGISTIC_BASE
            ** (-rating_difference / EloRatingCalculation.RATING_SCALE)
        )

    def _read_played_matches(self) -> pd.DataFrame:
        """Read every match that has a result, in date order, ready to be played.

        Everything a rating step needs except the two ratings themselves is
        worked out here for the whole table at once: the K factor, the goal
        multiplier, the home advantage and the result as a number.

        A fixture that has not been played yet carries no score and would
        move the ratings by nothing, so it is left out.
        """
        with_a_score = self.only_the_played_matches(
            CsvFile(InternationalResultSource.RESULT_FILE).read_table()
        )
        tournament = with_a_score[InternationalResultSource.TOURNAMENT_COLUMN]
        goal_difference = (
            with_a_score["home_goals"] - with_a_score["away_goals"]
        ).abs()
        return (
            with_a_score.assign(
                k_factor=self.k_factor_of(tournament),
                goal_multiplier=self.goal_multiplier_of(goal_difference),
                home_advantage=self._home_advantage_of(with_a_score),
                actual_score=self._actual_score_of(with_a_score),
            )
            .sort_values(InternationalResultSource.DATE_COLUMN, kind="stable")
            .reset_index(drop=True)
        )

    def only_the_played_matches(self, results: pd.DataFrame) -> pd.DataFrame:
        """Keep the matches that really have both scores.

        The source writes NA and empty cells for a fixture that has not been
        played yet, and such a match would move the ratings by nothing.

        Returns:
            The played matches, with both scores as numbers.
        """
        return results.assign(
            home_goals=pd.to_numeric(
                results[EloRatingCalculation.HOME_SCORE_COLUMN], errors="coerce"
            ),
            away_goals=pd.to_numeric(
                results[EloRatingCalculation.AWAY_SCORE_COLUMN], errors="coerce"
            ),
        ).dropna(subset=["home_goals", "away_goals"])

    def _home_advantage_of(self, matches: pd.DataFrame) -> pd.Series:
        """Read the home advantage, which is nothing on a neutral pitch."""
        plays_at_home = (
            matches[InternationalResultSource.NEUTRAL_VENUE_COLUMN]
            .str.strip()
            .str.upper()
            == InternationalResultSource.NOT_NEUTRAL_TEXT
        )
        return pd.Series(
            np.where(plays_at_home, EloRatingCalculation.HOME_ADVANTAGE, 0.0),
            index=matches.index,
        )

    def _actual_score_of(self, matches: pd.DataFrame) -> pd.Series:
        """Read the result as a number, one for a home win and zero for a loss."""
        return pd.Series(
            np.select(
                [
                    matches["home_goals"] > matches["away_goals"],
                    matches["home_goals"] == matches["away_goals"],
                ],
                [EloRatingCalculation.WIN_SCORE, EloRatingCalculation.DRAW_SCORE],
                default=EloRatingCalculation.LOSS_SCORE,
            ),
            index=matches.index,
        )

    def _play_every_match_in_order(
        self, matches: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Walk the matches in date order and carry both ratings along.

        This is the one step of the whole project that cannot be a table
        operation. What a team is rated before its next match is the result
        of every match it played before, so the matches have to be played in
        order and each one has to see what the one before it left behind.
        Everything that does not depend on the running rating has already
        been worked out for the whole table.

        Returns:
            The history with the pre match rating of both sides, and the
            rating every team ended on.
        """
        home_teams = matches[InternationalResultSource.HOME_TEAM_COLUMN].to_numpy()
        away_teams = matches[InternationalResultSource.AWAY_TEAM_COLUMN].to_numpy()
        k_factor = matches["k_factor"].to_numpy()
        goal_multiplier = matches["goal_multiplier"].to_numpy()
        home_advantage = matches["home_advantage"].to_numpy()
        actual_score = matches["actual_score"].to_numpy()

        rating_of_team: dict[str, float] = {}
        home_rating_before = np.empty(len(matches))
        away_rating_before = np.empty(len(matches))
        start = EloRatingCalculation.START_RATING

        for match in range(len(matches)):
            home_team, away_team = home_teams[match], away_teams[match]
            home_rating = rating_of_team.get(home_team, start)
            away_rating = rating_of_team.get(away_team, start)
            home_rating_before[match] = home_rating
            away_rating_before[match] = away_rating

            change = (
                k_factor[match]
                * goal_multiplier[match]
                * (
                    actual_score[match]
                    - self.expected_score_of(
                        home_rating - away_rating + home_advantage[match]
                    )
                )
            )
            rating_of_team[home_team] = home_rating + change
            rating_of_team[away_team] = away_rating - change

        rounder = DecimalRounder(EloRatingCalculation.RATING_DECIMAL_PLACES)
        history = matches.assign(
            date=matches[InternationalResultSource.DATE_COLUMN],
            home_team=matches[InternationalResultSource.HOME_TEAM_COLUMN],
            away_team=matches[InternationalResultSource.AWAY_TEAM_COLUMN],
            tournament=matches[InternationalResultSource.TOURNAMENT_COLUMN],
            neutral=matches[InternationalResultSource.NEUTRAL_VENUE_COLUMN],
            elo_home_pre=rounder.round_every_value(
                pd.Series(home_rating_before, index=matches.index)
            ),
            elo_away_pre=rounder.round_every_value(
                pd.Series(away_rating_before, index=matches.index)
            ),
        )
        return history, pd.Series(rating_of_team, dtype=float)

    def _write_snapshot(self, closing_ratings: pd.Series) -> CsvFile:
        """Write the closing ranking, the strongest team first."""
        snapshot_file = CsvFile(
            EloRatingCalculation.OUTPUT_FOLDER
            / EloRatingCalculation.SNAPSHOT_FILE_NAME,
            EloRatingCalculation.SNAPSHOT_COLUMN_NAMES,
        )
        strongest_first = closing_ratings.sort_values(
            ascending=False, kind="stable"
        ).rename_axis("team")
        rounder = DecimalRounder(EloRatingCalculation.RATING_DECIMAL_PLACES)
        snapshot_file.write_table(
            strongest_first.rename("elo")
            .reset_index()
            .assign(
                rank=range(1, len(strongest_first) + 1),
                elo=rounder.round_every_value(strongest_first).to_numpy(),
            )
        )
        return snapshot_file


if __name__ == "__main__":
    EloRatingBuilder().build_history()
