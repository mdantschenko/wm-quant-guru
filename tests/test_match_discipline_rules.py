"""Tests for the fouls and cards of a match, and for who is home.

Two things here are easy to get wrong and were wrong in the scripts this
replaces. The Wyscout match file numbers its teams rather than naming a home
side, and in roughly half the matches the first one played away. And a second
yellow is a sending off, so a match row that only counts straight reds says a
team finished with eleven when it did not.
"""

from typing import Any

from wmguru.helpers.data_class import StatsBombCompetition, WyscoutMatchFacts
from wmguru.helpers.utils import (
    MatchDisciplineCounter,
    StatsBombOpenDataReader,
    TextNormalizer,
    WyscoutDataReader,
)
from wmguru.preprocessing.builders.statsbomb_match_discipline_builder import (
    StatsBombMatchDisciplineBuilder,
)


class StatsBombReaderWithFixedEvents(StatsBombOpenDataReader):
    """A reader that hands out given events instead of fetching them."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        super().__init__(None)
        self._events = events

    def read_events(self, match: dict[str, Any]) -> list[dict[str, Any]]:
        """Return the events this reader was built with."""
        return self._events


def make_counter_with(
    fouls: int = 0, yellow: int = 0, red: int = 0, second_yellow: int = 0
) -> dict[str, int]:
    """Build the counter of one team or player."""
    return {
        "fouls": fouls,
        "yellow": yellow,
        "red": red,
        "second_yellow": second_yellow,
    }


def make_match_row(team_one_side: str) -> dict[str, str]:
    """Build one row of a Wyscout match file, with team 1 on the given side."""
    return {
        "wyId": "2500091",
        "team1.teamId": "1673",
        "team2.teamId": "1609",
        "team1.side": team_one_side,
        "competitionId": "524",
        "seasonId": "181150",
        "dateutc": "2018-05-13 18:00:00",
        "referees": "[{'refereeId': 377171, 'role': 'referee'}, "
        "{'refereeId': 386354, 'role': 'firstAssistant'}]",
    }


def read_facts_of(team_one_side: str) -> WyscoutMatchFacts:
    """Read one match row, with team one on the given side."""
    reader = WyscoutDataReader(TextNormalizer())
    return reader._read_facts_of_one_match(make_match_row(team_one_side), "2500091")


def test_the_first_team_is_at_home_when_the_side_says_so():
    facts = read_facts_of("home")

    assert facts.home_team_identifier == "1673"
    assert facts.away_team_identifier == "1609"


def test_the_first_team_can_be_the_away_team():
    """The old script took team 1 as home and had it backwards half the time."""
    facts = read_facts_of("away")

    assert facts.home_team_identifier == "1609"
    assert facts.away_team_identifier == "1673"


def test_the_opponent_is_the_other_side():
    facts = read_facts_of("home")

    assert facts.opponent_of("1673") == "1609"
    assert facts.opponent_of("1609") == "1673"


def test_only_the_main_referee_is_read_out_of_the_official_list():
    """The cell names the assistants too, and they did not blow the whistle."""
    facts = read_facts_of("home")

    assert facts.referee_identifier == "377171"


def test_a_match_without_any_official_named_leaves_the_referee_empty():
    reader = WyscoutDataReader(TextNormalizer())
    match = make_match_row("home") | {"referees": ""}

    assert reader.read_main_referee_identifier(match) == ""


def test_the_time_is_cut_off_the_match_date():
    assert read_facts_of("home").match_date == "2018-05-13"


def test_a_second_yellow_counts_as_a_sending_off():
    summary = MatchDisciplineCounter().summarise_both_sides(
        make_counter_with(red=1, second_yellow=1), make_counter_with()
    )

    assert summary["home_red"] == 2


def test_every_card_of_both_sides_is_in_the_total():
    summary = MatchDisciplineCounter().summarise_both_sides(
        make_counter_with(yellow=3, red=1),
        make_counter_with(yellow=2, second_yellow=1),
    )

    assert summary["total_cards"] == 7


def test_a_match_where_nobody_fouled_gives_zeros_rather_than_nothing():
    summary = MatchDisciplineCounter().summarise_both_sides(
        MatchDisciplineCounter().start_a_counter_at_zero(),
        MatchDisciplineCounter().start_a_counter_at_zero(),
    )

    assert summary["home_fouls"] == 0
    assert summary["total_cards"] == 0


def test_the_fouls_of_the_two_sides_are_not_mixed_up():
    summary = MatchDisciplineCounter().summarise_both_sides(
        make_counter_with(fouls=12), make_counter_with(fouls=7)
    )

    assert summary["home_fouls"] == 12
    assert summary["away_fouls"] == 7


def make_statsbomb_event(
    event_name: str, player: str, team: str, card: str | None = None
) -> dict[str, Any]:
    """Build one StatsBomb event, with a card on it when one is named."""
    event: dict[str, Any] = {
        "type": {"name": event_name},
        "player": {"name": player},
        "team": {"name": team},
    }
    if card is not None:
        field = "foul_committed" if event_name == "Foul Committed" else "bad_behaviour"
        event[field] = {"card": {"name": card}}
    return event


def build_statsbomb_rows(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run one match through the StatsBomb half and hand both kinds of row back."""
    builder = StatsBombMatchDisciplineBuilder(
        StatsBombReaderWithFixedEvents(events), MatchDisciplineCounter()
    )
    match = {
        "match_id": 3888787,
        "match_date": "2021-07-11",
        "home_team": {"home_team_name": "Italy"},
        "away_team": {"away_team_name": "England"},
        "referee": {"name": "B. Kuipers"},
    }
    competition = StatsBombCompetition(55, 43, "UEFA Euro", "2020")
    return builder._build_rows_of_one_match(match, competition)


def test_a_player_who_only_fouled_gets_a_row_without_a_card():
    player_rows, _ = build_statsbomb_rows(
        [make_statsbomb_event("Foul Committed", "Jorginho", "Italy")]
    )

    assert len(player_rows) == 1
    assert player_rows[0]["fouls"] == 1
    assert player_rows[0]["yellow"] == 0
    assert player_rows[0]["opponent"] == "England"


def test_a_card_without_a_foul_still_gives_the_player_a_row():
    """Dissent sits on another event type and would otherwise go missing."""
    player_rows, match_row = build_statsbomb_rows(
        [make_statsbomb_event("Bad Behaviour", "H. Maguire", "England", "Yellow Card")]
    )

    assert player_rows[0]["fouls"] == 0
    assert player_rows[0]["yellow"] == 1
    assert match_row["away_yellow"] == 1


def test_the_cards_of_a_match_land_on_the_right_side():
    player_rows, match_row = build_statsbomb_rows(
        [
            make_statsbomb_event("Foul Committed", "Jorginho", "Italy", "Yellow Card"),
            make_statsbomb_event("Foul Committed", "Jorginho", "Italy"),
            make_statsbomb_event("Foul Committed", "H. Maguire", "England", "Red Card"),
        ]
    )

    assert len(player_rows) == 2
    assert match_row["home"] == "Italy"
    assert match_row["home_fouls"] == 2
    assert match_row["home_yellow"] == 1
    assert match_row["away_red"] == 1
    assert match_row["total_cards"] == 2
    assert match_row["referee"] == "B. Kuipers"


def test_an_event_of_a_player_of_neither_team_does_not_reach_the_match_row():
    """A team name that is not one of the two must not silently vanish twice."""
    _, match_row = build_statsbomb_rows(
        [make_statsbomb_event("Foul Committed", "Someone", "Third Team")]
    )

    assert match_row["home_fouls"] == 0
    assert match_row["away_fouls"] == 0


def test_a_match_nobody_was_booked_in_still_gives_one_row():
    player_rows, match_row = build_statsbomb_rows([])

    assert player_rows == []
    assert match_row["total_cards"] == 0
    assert match_row["game_id"] == 3888787
