"""Tests for the card reading of both event sources.

The two sources mark a card in completely different ways, and both are easy to
read wrongly: Wyscout hides the card in a tag list among other numbers, and
StatsBomb carries a card without a foul on a second event type that is easy to
forget.
"""

from wmguru.helpers.utils import (
    StatsBombOpenDataReader,
    TextNormalizer,
    WyscoutDataReader,
)


def make_wyscout_reader() -> WyscoutDataReader:
    """Build the Wyscout reader, which reads no file in these tests."""
    return WyscoutDataReader(TextNormalizer())


def make_statsbomb_reader() -> StatsBombOpenDataReader:
    """Build the StatsBomb reader, which fetches nothing in these tests."""
    return StatsBombOpenDataReader(None)


def test_a_yellow_card_tag_is_recognised():
    reader = make_wyscout_reader()

    assert reader.read_card_names_out_of_tag_list("[{'id': 1702}]") == ["yellow"]


def test_a_red_and_a_second_yellow_are_told_apart():
    reader = make_wyscout_reader()

    assert reader.read_card_names_out_of_tag_list("[{'id': 1701}]") == ["red"]
    assert reader.read_card_names_out_of_tag_list("[{'id': 1703}]") == ["second_yellow"]


def test_a_tag_that_only_starts_with_the_same_digits_is_no_card():
    """1704 and 1700 sit right next to the card tags and mean something else."""
    reader = make_wyscout_reader()

    assert reader.read_card_names_out_of_tag_list("[{'id': 1704}]") == []
    assert reader.read_card_names_out_of_tag_list("[{'id': 1700}]") == []


def test_a_card_tag_is_found_among_other_tags():
    names = make_wyscout_reader().read_card_names_out_of_tag_list(
        "[{'id': 401}, {'id': 1702}]"
    )

    assert names == ["yellow"]


def test_an_event_without_any_tag_carries_no_card():
    assert make_wyscout_reader().read_card_names_out_of_tag_list("[]") == []


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
