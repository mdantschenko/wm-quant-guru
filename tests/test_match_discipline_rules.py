"""Tests for the fouls and cards of a match, and for who is home.

Two things here are easy to get wrong and were wrong in the scripts this
replaces. The Wyscout match file numbers its teams rather than naming a home
side, and in roughly half the matches the first one played away. And a second
yellow is a sending off, so a match row that only counts straight reds says a
team finished with eleven when it did not.

The counting is a group by over a table now, so the counters these tests build
are tables too: one row per event that was a foul or carried a card.
"""

import pandas as pd

from wmguru.helpers.data_class import WyscoutMatchFacts
from wmguru.helpers.utils import (
    MatchDisciplineCounter,
    PreparedStatsBombTables,
    TextNormalizer,
    WyscoutDataReader,
)
from wmguru.preprocessing.builders.statsbomb_match_discipline_builder import (
    StatsBombMatchDisciplineBuilder,
)

COUNTED_NAMES = ["fouls", "yellow", "red", "second_yellow"]


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


def make_counted_rows(rows: list[dict[str, int | str]]) -> pd.DataFrame:
    """Build the table of what every team or player of one match collected."""
    filled = [
        {
            "game_identifier": "1",
            "team_identifier": "home",
            "player_identifier": "",
            **dict.fromkeys(COUNTED_NAMES, 0),
            **row,
        }
        for row in rows
    ]
    return pd.DataFrame(
        filled,
        columns=["game_identifier", "team_identifier", "player_identifier"]
        + COUNTED_NAMES,
    )


def make_one_match(per_team: pd.DataFrame) -> pd.DataFrame:
    """Fold one match whose two sides are called home and away into its row."""
    sides = pd.DataFrame(
        [
            {
                "game_identifier": "1",
                "home_team_identifier": "home",
                "away_team_identifier": "away",
            }
        ]
    )
    return MatchDisciplineCounter().summarise_both_sides(per_team, sides)


def make_two_sides(
    of_the_home_team: dict[str, int], of_the_away_team: dict[str, int]
) -> pd.DataFrame:
    """Fold the counts of the two sides of one match into its row."""
    per_team = make_counted_rows(
        [
            {"team_identifier": "home", **of_the_home_team},
            {"team_identifier": "away", **of_the_away_team},
        ]
    )
    return make_one_match(per_team)


def test_a_second_yellow_counts_as_a_sending_off():
    summary = make_two_sides({"red": 1, "second_yellow": 1}, {})

    assert summary["home_red"].iloc[0] == 2


def test_every_card_of_both_sides_is_in_the_total():
    summary = make_two_sides({"yellow": 3, "red": 1}, {"yellow": 2, "second_yellow": 1})

    assert summary["total_cards"].iloc[0] == 7


def test_a_match_where_nobody_fouled_gives_zeros_rather_than_nothing():
    summary = make_one_match(make_counted_rows([]))

    assert summary["home_fouls"].iloc[0] == 0
    assert summary["total_cards"].iloc[0] == 0


def test_the_fouls_of_the_two_sides_are_not_mixed_up():
    summary = make_two_sides({"fouls": 12}, {"fouls": 7})

    assert summary["home_fouls"].iloc[0] == 12
    assert summary["away_fouls"].iloc[0] == 7


def test_the_players_of_a_team_are_added_up_into_one_side():
    counter = MatchDisciplineCounter()
    per_player = counter.count_every_player(
        make_counted_rows(
            [
                {"player_identifier": "8", "fouls": 2, "yellow": 1},
                {"player_identifier": "9", "fouls": 3},
            ]
        )
    )

    assert counter.count_every_team(per_player)["fouls"].iloc[0] == 5


class PreparedTablesWithFixedRows(PreparedStatsBombTables):
    """Prepared tables that hand out given rows instead of reading a file."""

    def __init__(self, events: pd.DataFrame, identities: pd.DataFrame) -> None:
        self._events = events
        self._identities = identities

    def read_the_events(self) -> pd.DataFrame:
        """Return the events this stub was built with."""
        return self._events

    def read_the_match_identities(self) -> pd.DataFrame:
        """Return the one match this stub was built with."""
        return self._identities


def make_statsbomb_event(
    event_name: str, player: str, team: str, card: str = ""
) -> dict[str, str]:
    """Build one row of the prepared StatsBomb event table."""
    return {
        "game_identifier": "3888787",
        "event_name": event_name,
        "team_name": team,
        "player_name": player,
        "player_identifier": player,
        "card_name": card,
    }


def build_statsbomb_rows(
    events: list[dict[str, str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run one match through the StatsBomb half and hand both kinds of row back."""
    identities = pd.DataFrame(
        [
            {
                "game_identifier": "3888787",
                "competition_name": "UEFA Euro",
                "season_name": "2020",
                "match_date": "2021-07-11",
                "home_team_name": "Italy",
                "away_team_name": "England",
                "referee_name": "B. Kuipers",
            }
        ]
    )
    builder = StatsBombMatchDisciplineBuilder(
        PreparedTablesWithFixedRows(
            pd.DataFrame(
                events,
                columns=[
                    "game_identifier",
                    "event_name",
                    "team_name",
                    "player_name",
                    "player_identifier",
                    "card_name",
                ],
            ),
            identities,
        ),
        MatchDisciplineCounter(),
    )
    sides = builder._prepared_tables.read_the_sides_of_every_match()
    marked = builder._prepared_tables.read_every_card_and_foul()
    per_player = builder._discipline_counter.count_every_player(marked)
    per_team = builder._discipline_counter.count_every_team(per_player)
    return (
        builder._build_player_rows(per_player, marked, sides),
        builder._build_match_rows(per_team, sides),
    )


def test_a_player_who_only_fouled_gets_a_row_without_a_card():
    player_rows, _ = build_statsbomb_rows(
        [make_statsbomb_event("Foul Committed", "Jorginho", "Italy")]
    )

    assert len(player_rows) == 1
    assert player_rows["fouls"].iloc[0] == 1
    assert player_rows["yellow"].iloc[0] == 0
    assert player_rows["opponent"].iloc[0] == "England"


def test_a_card_without_a_foul_still_gives_the_player_a_row():
    """Dissent sits on another event type and would otherwise go missing."""
    player_rows, match_rows = build_statsbomb_rows(
        [make_statsbomb_event("Bad Behaviour", "H. Maguire", "England", "yellow")]
    )

    assert player_rows["fouls"].iloc[0] == 0
    assert player_rows["yellow"].iloc[0] == 1
    assert match_rows["away_yellow"].iloc[0] == 1


def test_the_cards_of_a_match_land_on_the_right_side():
    player_rows, match_rows = build_statsbomb_rows(
        [
            make_statsbomb_event("Foul Committed", "Jorginho", "Italy", "yellow"),
            make_statsbomb_event("Foul Committed", "Jorginho", "Italy"),
            make_statsbomb_event("Foul Committed", "H. Maguire", "England", "red"),
        ]
    )

    assert len(player_rows) == 2
    assert match_rows["home"].iloc[0] == "Italy"
    assert match_rows["home_fouls"].iloc[0] == 2
    assert match_rows["home_yellow"].iloc[0] == 1
    assert match_rows["away_red"].iloc[0] == 1
    assert match_rows["total_cards"].iloc[0] == 2
    assert match_rows["referee"].iloc[0] == "B. Kuipers"


def test_an_event_of_a_player_of_neither_team_does_not_reach_the_match_row():
    """A team name that is not one of the two must not silently vanish twice."""
    _, match_rows = build_statsbomb_rows(
        [make_statsbomb_event("Foul Committed", "Someone", "Third Team")]
    )

    assert match_rows["home_fouls"].iloc[0] == 0
    assert match_rows["away_fouls"].iloc[0] == 0


def test_a_match_nobody_was_booked_in_still_gives_one_row():
    player_rows, match_rows = build_statsbomb_rows([])

    assert len(player_rows) == 0
    assert match_rows["total_cards"].iloc[0] == 0
    assert match_rows["game_id"].iloc[0] == "3888787"
