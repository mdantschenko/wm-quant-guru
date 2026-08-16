"""Tests for the card reading of both event sources.

The two sources mark a card in completely different ways, and both are easy to
read wrongly: Wyscout hides the card in a tag list among other numbers, and
StatsBomb carries a card without a foul on a second event type that is easy to
forget.
"""

import pandas as pd

from wmguru.helpers.utils import (
    StatsBombOpenDataReader,
    TextNormalizer,
    WyscoutDataReader,
)


def cards_of(*tag_lists: str) -> list[list[str]]:
    """Read a few tag cells at once and name the cards each one carries."""
    read = WyscoutDataReader(TextNormalizer()).read_the_card_of_every_event(
        pd.Series(list(tag_lists))
    )
    return [
        [name for name in read.columns if row[name]] for _index, row in read.iterrows()
    ]


def make_statsbomb_reader() -> StatsBombOpenDataReader:
    """Build the StatsBomb reader, which fetches nothing in these tests."""
    return StatsBombOpenDataReader(None)


def test_a_yellow_card_tag_is_recognised():
    assert cards_of("[{'id': 1702}]") == [["yellow"]]


def test_a_red_and_a_second_yellow_are_told_apart():
    assert cards_of("[{'id': 1701}]", "[{'id': 1703}]") == [["red"], ["second_yellow"]]


def test_a_tag_that_only_starts_with_the_same_digits_is_no_card():
    """1704 and 1700 sit right next to the card tags and mean something else."""
    assert cards_of("[{'id': 1704}]", "[{'id': 1700}]") == [[], []]


def test_a_tag_that_merely_contains_a_card_number_is_no_card():
    """17020 holds 1702 in its digits without ever being a yellow."""
    assert cards_of("[{'id': 17020}]", "[{'id': 21702}]") == [[], []]


def test_a_card_tag_is_found_among_other_tags():
    assert cards_of("[{'id': 401}, {'id': 1702}]") == [["yellow"]]


def test_an_event_without_any_tag_carries_no_card():
    assert cards_of("[]") == [[]]


def test_a_statsbomb_card_on_a_foul_is_read():
    event = {
        "type": {"name": "Foul Committed"},
        "foul_committed": {"card": {"name": "Yellow Card"}},
    }

    assert make_statsbomb_reader().read_card_name_of(event) == "yellow"


def test_a_statsbomb_card_without_a_foul_is_read_too():
    """Dissent gets a card on a Bad Behaviour event and would go missing."""
    event = {
        "type": {"name": "Bad Behaviour"},
        "bad_behaviour": {"card": {"name": "Red Card"}},
    }

    assert make_statsbomb_reader().read_card_name_of(event) == "red"


def test_a_foul_without_a_card_carries_none():
    reader = make_statsbomb_reader()

    assert reader.read_card_name_of({"type": {"name": "Foul Committed"}}) is None


def test_an_event_of_another_kind_carries_no_card():
    reader = make_statsbomb_reader()

    assert reader.read_card_name_of({"type": {"name": "Pass"}}) is None
