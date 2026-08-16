"""All data containers of the whole project live in this file.

MatchRecord is the canonical match schema from section 4.1 of the concept
(docs/konzept.tex). Every source dataset is mapped onto this shape before it
enters the pipeline. The datasets do not arrive in this shape, this is the
state we want them in.

Validation runs through pydantic. Every field declared below is checked on
every row, so a column can never be forgotten by accident.
"""

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from wmguru.helpers.constant import MatchRecordRule

RequiredText = Annotated[str, Field(min_length=MatchRecordRule.MINIMUM_TEXT_LENGTH)]
GoalCount = Annotated[int, Field(ge=MatchRecordRule.MINIMUM_GOAL_COUNT)]


@dataclass(frozen=True)
class StatsBombCompetition:
    """One season of one competition in the StatsBomb open data.

    The two identifiers address the data, the two names go into the output
    file and are what a later run compares against to know it is done.
    """

    competition_identifier: int
    season_identifier: int
    competition_name: str
    season_name: str

    @property
    def finished_key(self) -> tuple[str, str]:
        """The pair a builder writes into its file to mark this season done."""
        return (self.competition_name, self.season_name)


@dataclass(frozen=True)
class WyscoutNameLookups:
    """The readable name of every team, player, competition and referee.

    The Wyscout files store identifiers everywhere, so a builder that wants to
    write names needs all four tables at once. They belong together, which is
    why they travel as one thing rather than as four parameters.
    """

    team_names: dict[str, str]
    player_names: dict[str, str]
    competition_names: dict[str, str]
    referee_names: dict[str, str]


@dataclass(frozen=True)
class WyscoutMatchFacts:
    """Who played whom in one Wyscout match, and who refereed it.

    Everything is an identifier, not a name. A builder looks the names up
    itself, because some of them it never needs.
    """

    game_identifier: str
    home_team_identifier: str
    away_team_identifier: str
    referee_identifier: str
    competition_identifier: str
    season_name: str
    match_date: str

    def opponent_of(self, team_identifier: str) -> str:
        """Return the other team of this match."""
        if team_identifier == self.home_team_identifier:
            return self.away_team_identifier
        return self.home_team_identifier


@dataclass(frozen=True)
class MatchIdentity:
    """Which match a row belongs to, in the words the output file uses.

    Names, not identifiers. A builder has looked them up by the time it
    builds a row, and both event sources end up with the same six values.
    """

    game_identifier: str
    competition_name: str
    season_name: str
    match_date: str
    home_team_name: str
    away_team_name: str


@dataclass(frozen=True)
class MatchAction:
    """One action of one team, in the one shape both event sources are read into.

    The coordinates are in metres and the acting team always attacks towards
    x=105, so the two sources can be compared at all. Wyscout attacks the
    other way and StatsBomb counts on a 120 by 80 pitch, and both are
    converted before an action is built.

    Attributes:
        scoring_team: Says who a goal counted for, "self" for the acting team
            and "opponent" for an own goal. None when the action was no goal.
        expected_goals: Only StatsBomb carries this, so it is None for every
            Wyscout action.
        player_name: Empty for an action the source left to nobody, which
            happens for the ones it could not place.
        player_identifier: What to count a player by. Two players can share a
            name, and their matches must not be added together.
    """

    team_name: str
    kind: str
    was_successful: bool
    start_x_in_metres: float
    start_y_in_metres: float
    end_x_in_metres: float
    end_y_in_metres: float
    scoring_team: str | None
    expected_goals: float | None
    was_after_a_set_piece: bool
    period_number: int
    second_in_period: float
    player_name: str = ""
    player_identifier: str = ""

    @property
    def order_in_the_match(self) -> tuple[int, float]:
        """The key that puts the actions of a match into the order they happened."""
        return (self.period_number, self.second_in_period)


@dataclass(frozen=True)
class PlayerAppearance:
    """That one player was on the pitch in one match, and for how long.

    A player who never came on has no appearance at all, so a row is only
    built for somebody who actually played.
    """

    player_name: str
    team_identifier: str
    minutes_played: int


@dataclass(frozen=True)
class TeamPass:
    """One pass of one team, in the shape both event sources are read into.

    Attributes:
        receiver_name: Empty when the pass did not arrive, or when the source
            does not say who got it.
    """

    passer_name: str
    receiver_name: str
    start_x_in_metres: float
    start_y_in_metres: float
    end_x_in_metres: float
    end_y_in_metres: float
    was_successful: bool

    @property
    def forward_gain_in_metres(self) -> float:
        """How much ground the pass won towards the goal being attacked."""
        return self.end_x_in_metres - self.start_x_in_metres

    @property
    def has_reached_somebody_else(self) -> bool:
        """True when the pass arrived at a team mate, so it forms a lane."""
        return (
            self.was_successful
            and bool(self.receiver_name)
            and self.receiver_name != self.passer_name
        )


@dataclass(frozen=True)
class PricedMatch:
    """One match with a three way price, in the shape every odds source is read into.

    Attributes:
        result_index: Which of the three outcomes really happened, home, draw
            or away, in that order.
        odds: The price of each of the three outcomes, in the same order.
    """

    source: str
    match_date: str
    competition: str
    home_team: str
    away_team: str
    result_index: int
    odds: tuple[float, float, float]


@dataclass(frozen=True)
class OutcomeOddsSummary:
    """What the bookmakers offered for one outcome of one match.

    Opening odds are the first point of the time series, closing odds the last
    one. The highest closing odds say what the best bookmaker paid, the average
    says what the market as a whole thought.
    """

    average_opening_odds: float | None
    average_closing_odds: float | None
    highest_closing_odds: float | None
    bookmaker_count: int

    @property
    def has_any_odds(self) -> bool:
        """True when at least one bookmaker priced this outcome."""
        return self.average_closing_odds is not None


class MatchRecord(BaseModel):
    """One finished match in the canonical schema of the concept, section 4.1.

    The object is frozen, so a record cannot be changed once it passed the
    checks. Build one through parse_and_validate_row, which turns the text of
    a CSV row into the right types and collects every problem at once.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        str_strip_whitespace=True,
    )

    match_id: RequiredText
    match_date: date
    home_team_name: RequiredText
    home_team_is_host: bool
    away_team_name: RequiredText
    away_team_is_host: bool
    home_goals_regular_time: GoalCount
    away_goals_regular_time: GoalCount
    home_goals_final: GoalCount
    away_goals_final: GoalCount
    is_regular_time_score_reconstructed_unreliable: bool
    is_neutral_venue: bool
    tournament_name: RequiredText
    tournament_stage: RequiredText
    competition_category: RequiredText
    city: str = MatchRecordRule.MISSING_TEXT_PLACEHOLDER
    country: str = MatchRecordRule.MISSING_TEXT_PLACEHOLDER
    home_shootout_goals: GoalCount | None = None
    away_shootout_goals: GoalCount | None = None
    shootout_winner: str = MatchRecordRule.MISSING_TEXT_PLACEHOLDER

    @field_validator("home_shootout_goals", "away_shootout_goals", mode="before")
    @classmethod
    def read_empty_cell_as_no_shootout(cls, raw_value: Any) -> Any:
        """Read an empty cell as no shootout instead of as a broken number."""
        if raw_value == MatchRecordRule.MISSING_TEXT_PLACEHOLDER:
            return None
        return raw_value

    @field_validator("city", "country", "shootout_winner", mode="before")
    @classmethod
    def read_missing_cell_as_empty_text(cls, raw_value: Any) -> Any:
        """Read a missing cell of an optional column as empty text."""
        if raw_value is None:
            return MatchRecordRule.MISSING_TEXT_PLACEHOLDER
        return raw_value

    @model_validator(mode="after")
    def check_that_the_columns_fit_together(self) -> "MatchRecord":
        """Check the rules that need more than one column at once.

        Raises:
            ValueError: When a rule is broken, naming every problem at once so
                a caller sees all of them rather than the first.
        """
        problem_list = (
            self._collect_team_problems()
            + self._collect_goal_problems()
            + self._collect_shootout_problems()
        )
        if problem_list:
            raise ValueError(MatchRecordRule.PROBLEM_SEPARATOR.join(problem_list))
        return self

    def _collect_team_problems(self) -> list[str]:
        """Collect the problem that a team was entered against itself."""
        if self.home_team_name == self.away_team_name:
            return [
                f"home_team_name={self.home_team_name} and "
                f"away_team_name={self.away_team_name} must not be equal."
            ]
        return []

    def _collect_goal_problems(self) -> list[str]:
        """Collect the problems where the 90 minute score beats the final score."""
        if self.is_regular_time_score_reconstructed_unreliable:
            return []

        problem_list = []
        if self.home_goals_regular_time > self.home_goals_final:
            problem_list.append(
                f"home_goals_regular_time={self.home_goals_regular_time} must not be "
                f"larger than home_goals_final={self.home_goals_final}."
            )
        if self.away_goals_regular_time > self.away_goals_final:
            problem_list.append(
                f"away_goals_regular_time={self.away_goals_regular_time} must not be "
                f"larger than away_goals_final={self.away_goals_final}."
            )
        return problem_list

    def _collect_shootout_problems(self) -> list[str]:
        """Collect the problems of a shootout that is half filled or impossible."""
        home_goals_are_missing = self.home_shootout_goals is None
        away_goals_are_missing = self.away_shootout_goals is None

        if home_goals_are_missing and away_goals_are_missing:
            return []
        if home_goals_are_missing or away_goals_are_missing:
            return [
                "home_shootout_goals and away_shootout_goals must both be filled or "
                f"both be empty. Found home_shootout_goals={self.home_shootout_goals} "
                f"and away_shootout_goals={self.away_shootout_goals}."
            ]

        problem_list = []
        if self.home_shootout_goals == self.away_shootout_goals:
            problem_list.append(
                f"A shootout needs a winner, but home_shootout_goals="
                f"{self.home_shootout_goals} equals away_shootout_goals="
                f"{self.away_shootout_goals}."
            )
        if self.home_goals_final != self.away_goals_final:
            problem_list.append(
                f"A shootout only happens after a draw, but home_goals_final="
                f"{self.home_goals_final} and away_goals_final={self.away_goals_final}."
            )
        return problem_list

    @classmethod
    def parse_and_validate_row(
        cls, row_from_source: dict[str, Any]
    ) -> tuple["MatchRecord | None", list[str]]:
        """Build one MatchRecord from a raw source row.

        Args:
            row_from_source: One row as a CSV reader hands it over, so every
                value may still be text. A column the schema does not know is
                ignored, a column it does know is converted and checked.

        Returns:
            The record and an empty list when the row is good. None and one
            readable sentence per problem when it is not, so a caller can
            write every problem of a whole file into one report.
        """
        try:
            return cls.model_validate(row_from_source), []
        except ValidationError as validation_error:
            return None, [
                cls._describe_problem(problem) for problem in validation_error.errors()
            ]

    @staticmethod
    def _describe_problem(problem: dict[str, Any]) -> str:
        """Turn one pydantic problem into a sentence that names the column."""
        column_name = ".".join(str(part) for part in problem["loc"])
        if not column_name:
            return f"The columns do not fit together: {problem['msg']}"
        return f"The column {column_name} is not usable: {problem['msg']}"
