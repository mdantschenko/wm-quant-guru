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

from typing import Any

from wmguru.helpers.constant import EloRatingCalculation, InternationalResultSource
from wmguru.helpers.utils import CsvFile


class EloRatingBuilder:
    """A running rating per team, over every match in date order."""

    def build_history(self) -> tuple[int, int]:
        """Write the pre match history and the closing ranking.

        Returns:
            How many matches went into the history, and how many teams the
            closing ranking holds.
        """
        matches = self._read_played_matches()
        ratings: dict[str, float] = {}

        history_file = CsvFile(
            EloRatingCalculation.OUTPUT_FOLDER / EloRatingCalculation.HISTORY_FILE_NAME,
            EloRatingCalculation.HISTORY_COLUMN_NAMES,
        )
        with history_file.writing_writer() as writer:
            for match in matches:
                writer.writerow(self._build_history_row(match, ratings))
                self._move_the_ratings(match, ratings)

        snapshot_file = self._write_snapshot(ratings)
        print(f"{len(matches)} matches -> {history_file.path}")
        print(f"{len(ratings)} teams in the closing ranking -> {snapshot_file.path}")
        return len(matches), len(ratings)

    def k_factor_of(self, tournament_name: str) -> float:
        """Read how much one match of this competition may move a rating.

        Args:
            tournament_name: The competition as the result file writes it.

        Returns:
            60 for a World Cup final round, 50 for a continental final round,
            40 for a qualification or the Nations League, 20 for a friendly
            and 30 for anything else.
        """
        name = tournament_name.strip()
        lowered = name.lower()
        if name == EloRatingCalculation.WORLD_CUP_NAME:
            return EloRatingCalculation.K_FACTOR_WORLD_CUP
        if any(part in lowered for part in EloRatingCalculation.QUALIFIER_NAME_PARTS):
            return EloRatingCalculation.K_FACTOR_QUALIFIER
        if any(
            final in name for final in EloRatingCalculation.CONTINENTAL_FINALS_NAMES
        ):
            return EloRatingCalculation.K_FACTOR_CONTINENTAL_FINALS
        if lowered == EloRatingCalculation.FRIENDLY_NAME:
            return EloRatingCalculation.K_FACTOR_FRIENDLY
        return EloRatingCalculation.K_FACTOR_OTHER_TOURNAMENT

    def goal_multiplier_of(self, goal_difference: int) -> float:
        """Read how much a clear win counts over a narrow one.

        Args:
            goal_difference: The margin, always taken as a positive number.

        Returns:
            One up to a one goal margin, one and a half at two goals, and a
            value that keeps growing but ever more slowly above that.
        """
        if goal_difference <= EloRatingCalculation.NARROW_GOAL_DIFFERENCE:
            return EloRatingCalculation.MULTIPLIER_NARROW
        if goal_difference == EloRatingCalculation.TWO_GOAL_DIFFERENCE:
            return EloRatingCalculation.MULTIPLIER_TWO_GOALS
        return (
            EloRatingCalculation.MULTIPLIER_OFFSET + goal_difference
        ) / EloRatingCalculation.MULTIPLIER_DIVISOR

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

    def _read_played_matches(self) -> list[dict[str, str]]:
        """Read every match that has a result, in date order.

        A fixture that has not been played yet carries no score and would
        move the ratings by nothing, so it is left out.
        """
        matches = [
            match
            for match in CsvFile(InternationalResultSource.RESULT_FILE).read_rows()
            if self._was_played(match)
        ]
        matches.sort(key=lambda match: match[InternationalResultSource.DATE_COLUMN])
        return matches

    def _was_played(self, match: dict[str, str]) -> bool:
        """Return True when both scores are filled in."""
        return (
            match[EloRatingCalculation.HOME_SCORE_COLUMN]
            not in EloRatingCalculation.MISSING_SCORE_TEXTS
            and match[EloRatingCalculation.AWAY_SCORE_COLUMN]
            not in EloRatingCalculation.MISSING_SCORE_TEXTS
        )

    def _build_history_row(
        self, match: dict[str, str], ratings: dict[str, float]
    ) -> list[Any]:
        """Build one row with the ratings as they stand before this match."""
        home_team = match[InternationalResultSource.HOME_TEAM_COLUMN]
        away_team = match[InternationalResultSource.AWAY_TEAM_COLUMN]
        return [
            match[InternationalResultSource.DATE_COLUMN],
            home_team,
            away_team,
            match[InternationalResultSource.TOURNAMENT_COLUMN],
            match[InternationalResultSource.NEUTRAL_VENUE_COLUMN],
            self._rounded(self._rating_of(home_team, ratings)),
            self._rounded(self._rating_of(away_team, ratings)),
        ]

    def _move_the_ratings(
        self, match: dict[str, str], ratings: dict[str, float]
    ) -> None:
        """Move both ratings by what the result says, one up and one down."""
        home_team = match[InternationalResultSource.HOME_TEAM_COLUMN]
        away_team = match[InternationalResultSource.AWAY_TEAM_COLUMN]
        home_rating = self._rating_of(home_team, ratings)
        away_rating = self._rating_of(away_team, ratings)
        home_goals = int(match[EloRatingCalculation.HOME_SCORE_COLUMN])
        away_goals = int(match[EloRatingCalculation.AWAY_SCORE_COLUMN])

        rating_difference = home_rating - away_rating + self._home_advantage_of(match)
        change = (
            self.k_factor_of(match[InternationalResultSource.TOURNAMENT_COLUMN])
            * self.goal_multiplier_of(abs(home_goals - away_goals))
            * (
                self._actual_score_of(home_goals, away_goals)
                - self.expected_score_of(rating_difference)
            )
        )
        ratings[home_team] = home_rating + change
        ratings[away_team] = away_rating - change

    def _home_advantage_of(self, match: dict[str, str]) -> float:
        """Read the home advantage, which is nothing on a neutral pitch."""
        venue_is_neutral = (
            match[InternationalResultSource.NEUTRAL_VENUE_COLUMN].strip().upper()
            != InternationalResultSource.NOT_NEUTRAL_TEXT
        )
        return 0.0 if venue_is_neutral else EloRatingCalculation.HOME_ADVANTAGE

    def _actual_score_of(self, home_goals: int, away_goals: int) -> float:
        """Read the result as a number, one for a home win and zero for a loss."""
        if home_goals > away_goals:
            return EloRatingCalculation.WIN_SCORE
        if home_goals == away_goals:
            return EloRatingCalculation.DRAW_SCORE
        return EloRatingCalculation.LOSS_SCORE

    def _rating_of(self, team_name: str, ratings: dict[str, float]) -> float:
        """Read the rating of a team, or the value every new team starts at."""
        return ratings.get(team_name, EloRatingCalculation.START_RATING)

    def _rounded(self, rating: float) -> float:
        """Cut a rating down to a readable number of digits."""
        return round(rating, EloRatingCalculation.RATING_DECIMAL_PLACES)

    def _write_snapshot(self, ratings: dict[str, float]) -> CsvFile:
        """Write the closing ranking, the strongest team first."""
        snapshot_file = CsvFile(
            EloRatingCalculation.OUTPUT_FOLDER
            / EloRatingCalculation.SNAPSHOT_FILE_NAME,
            EloRatingCalculation.SNAPSHOT_COLUMN_NAMES,
        )
        ranking = sorted(ratings.items(), key=lambda entry: -entry[1])
        snapshot_file.write_rows(
            [
                [rank, team_name, self._rounded(rating)]
                for rank, (team_name, rating) in enumerate(ranking, start=1)
            ]
        )
        return snapshot_file


if __name__ == "__main__":
    EloRatingBuilder().build_history()
