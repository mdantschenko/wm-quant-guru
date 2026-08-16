"""Tests for the rules inside the extractors that are easy to get wrong.

The competition filter and the opening and closing summary were duplicated
across three old scripts, one of which changed the filter of another at run
time. They now live in one place, so they get a proper net.
"""

from wmguru.data.extractors.beat_the_bookie_odds_extractor import (
    BeatTheBookieOddsExtractor,
)
from wmguru.helpers.constant import InternationalOddsExtract, UefaClubOddsExtract
from wmguru.helpers.utils import TextNormalizer


def make_extractor() -> BeatTheBookieOddsExtractor:
    """Build an extractor, no test here reads a file."""
    return BeatTheBookieOddsExtractor(TextNormalizer())


def test_the_region_in_front_of_the_competition_is_cut_off():
    normalizer = TextNormalizer()

    assert (
        normalizer.competition_out_of_league_name("Europe: Champions League")
        == "champions league"
    )
    assert normalizer.competition_out_of_league_name("World: World Cup") == "world cup"


def test_an_accent_in_the_competition_name_does_not_hide_it():
    """Copa América Centenario used to slip through the filter."""
    normalizer = TextNormalizer()

    assert (
        normalizer.competition_out_of_league_name("America: Copa América")
        == "copa america"
    )


def test_a_national_team_competition_is_kept():
    extractor = make_extractor()

    assert extractor._is_a_wanted_competition(
        "World: World Cup", InternationalOddsExtract.COMPETITIONS
    )
    assert extractor._is_a_wanted_competition(
        "America: Copa América", InternationalOddsExtract.COMPETITIONS
    )


def test_a_club_competition_never_counts_as_a_national_one():
    """Exact matching is what keeps Euro from catching Europa League."""
    extractor = make_extractor()

    assert not extractor._is_a_wanted_competition(
        "Europe: Europa League", InternationalOddsExtract.COMPETITIONS
    )
    assert not extractor._is_a_wanted_competition(
        "Europe: Euro U21", InternationalOddsExtract.COMPETITIONS
    )


def test_the_same_reader_keeps_the_uefa_club_competitions():
    """The old scripts needed a run time hack for exactly this."""
    extractor = make_extractor()

    assert extractor._is_a_wanted_competition(
        "Europe: Champions League", UefaClubOddsExtract.COMPETITIONS
    )
    assert not extractor._is_a_wanted_competition(
        "Europe: Champions League", InternationalOddsExtract.COMPETITIONS
    )


def test_a_column_name_is_split_into_outcome_bookmaker_and_hour():
    header = ["match_id", "home_b1_2", "home_b1_1", "draw_b2_1", "away_b1_1", "other"]

    columns_of_outcome = make_extractor()._map_columns(header)

    assert len(columns_of_outcome["home"]) == 1
    assert columns_of_outcome["draw"] == [[3]]
    assert columns_of_outcome["away"] == [[4]]


def test_the_hours_of_a_bookmaker_come_out_in_time_order():
    """Hour 1 has to come before hour 2, whatever order the columns stand in."""
    column_of_hour_two = 1
    column_of_hour_one = 2
    header = ["match_id", "home_b1_2", "home_b1_1"]

    columns_of_outcome = make_extractor()._map_columns(header)

    assert columns_of_outcome["home"] == [[column_of_hour_one, column_of_hour_two]]


def test_opening_is_the_first_and_closing_the_last_priced_point():
    opening_odds = "2.00"
    middle_odds = "2.50"
    closing_odds = "3.00"
    row = ["id", opening_odds, middle_odds, closing_odds]

    summary = make_extractor()._summarise_outcome(row, [[1, 2, 3]])

    assert summary.average_opening_odds == float(opening_odds)
    assert summary.average_closing_odds == float(closing_odds)
    assert summary.highest_closing_odds == float(closing_odds)
    assert summary.bookmaker_count == 1
    assert summary.has_any_odds is True


def test_the_average_runs_over_the_bookmakers():
    first_bookmaker_columns = [1, 2]
    second_bookmaker_columns = [3, 4]
    row = ["id", "2.00", "4.00", "3.00", "5.00"]

    summary = make_extractor()._summarise_outcome(
        row, [first_bookmaker_columns, second_bookmaker_columns]
    )

    assert summary.average_opening_odds == (2.00 + 3.00) / 2
    assert summary.average_closing_odds == (4.00 + 5.00) / 2
    assert summary.highest_closing_odds == 5.0
    assert summary.bookmaker_count == 2


def test_an_empty_or_impossible_cell_is_not_a_price():
    row = ["id", "", "nan", "1.00", "2.20"]

    summary = make_extractor()._summarise_outcome(row, [[1, 2, 3, 4]])

    assert summary.average_opening_odds == 2.2
    assert summary.bookmaker_count == 1


def test_an_outcome_nobody_priced_says_so():
    row = ["id", "", ""]

    summary = make_extractor()._summarise_outcome(row, [[1, 2]])

    assert summary.has_any_odds is False
    assert summary.bookmaker_count == 0
