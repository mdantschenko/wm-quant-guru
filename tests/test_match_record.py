"""Tests for MatchRecord, the canonical match schema in wmguru/helpers/data_class.py.

The example row is the 2022 World Cup final from the dataset
"International football results from 1872 to 2026":
date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2022-12-18,Argentina,France,3,3,FIFA World Cup,Lusail,Qatar,TRUE
"""

from datetime import date

from wmguru.helpers.data_class import MatchRecord


def make_valid_row() -> dict[str, str]:
    """Build a raw source row in which every column is good, as a CSV gives it."""
    return {
        "match_id": "test",
        "match_date": "2022-12-18",
        "home_team_name": "Argentina",
        "home_team_is_host": "0",
        "away_team_name": "France",
        "away_team_is_host": "0",
        "home_goals_regular_time": "2",
        "away_goals_regular_time": "2",
        "home_goals_final": "3",
        "away_goals_final": "3",
        "is_regular_time_score_reconstructed_unreliable": "0",
        "is_neutral_venue": "1",
        "tournament_name": "FIFA World Cup",
        "tournament_stage": "Finals",
        "competition_category": "FIFA World Cup",
        "city": "Lusail",
        "country": "Qatar",
        "home_shootout_goals": "4",
        "away_shootout_goals": "2",
        "shootout_winner": "Argentina",
    }


def test_valid_row_becomes_a_match_record():
    match_record, problem_list = MatchRecord.parse_and_validate_row(make_valid_row())

    assert problem_list == []
    assert match_record is not None
    assert match_record.home_goals_regular_time == 2
    assert match_record.match_date == date(2022, 12, 18)


def test_every_column_of_a_valid_row_is_filled():
    """No column may be dropped on the way from the raw row into the record."""
    match_record, _ = MatchRecord.parse_and_validate_row(make_valid_row())

    assert match_record is not None
    assert match_record.home_team_is_host is False
    assert match_record.away_team_is_host is False
    assert match_record.is_neutral_venue is True
    assert match_record.tournament_stage == "Finals"
    assert match_record.shootout_winner == "Argentina"


def test_the_word_true_is_read_as_a_boolean():
    """The raw dataset writes TRUE and FALSE, not 1 and 0."""
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["is_neutral_venue"] = "TRUE"
    match_record, problem_list = MatchRecord.parse_and_validate_row(
        row_that_needs_to_be_validated
    )

    assert problem_list == []
    assert match_record is not None
    assert match_record.is_neutral_venue is True


def test_a_match_without_a_shootout_is_valid():
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["home_shootout_goals"] = ""
    row_that_needs_to_be_validated["away_shootout_goals"] = ""
    row_that_needs_to_be_validated["shootout_winner"] = ""
    match_record, problem_list = MatchRecord.parse_and_validate_row(
        row_that_needs_to_be_validated
    )

    assert problem_list == []
    assert match_record is not None
    assert match_record.home_shootout_goals is None


def test_negative_goal_count_is_rejected():
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["home_goals_regular_time"] = "-1"
    match_record, problem_list = MatchRecord.parse_and_validate_row(
        row_that_needs_to_be_validated
    )

    assert len(problem_list) > 0
    assert match_record is None


def test_empty_home_team_name_is_rejected():
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["home_team_name"] = ""
    match_record, problem_list = MatchRecord.parse_and_validate_row(
        row_that_needs_to_be_validated
    )

    assert len(problem_list) > 0
    assert match_record is None


def test_more_goals_after_ninety_minutes_than_at_the_end_is_rejected():
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["home_goals_regular_time"] = "3"
    row_that_needs_to_be_validated["home_goals_final"] = "2"
    match_record, problem_list = MatchRecord.parse_and_validate_row(
        row_that_needs_to_be_validated
    )

    assert len(problem_list) > 0
    assert match_record is None


def test_missing_values_are_rejected():
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["home_team_name"] = None
    row_that_needs_to_be_validated["match_id"] = None
    match_record, problem_list = MatchRecord.parse_and_validate_row(
        row_that_needs_to_be_validated
    )

    assert len(problem_list) > 0
    assert match_record is None


def test_a_missing_column_is_reported_by_name():
    """A column that is not in the source row at all must be named in the problem."""
    row_that_needs_to_be_validated = make_valid_row()
    del row_that_needs_to_be_validated["tournament_stage"]
    match_record, problem_list = MatchRecord.parse_and_validate_row(
        row_that_needs_to_be_validated
    )

    assert match_record is None
    assert any("tournament_stage" in problem for problem in problem_list)


def test_a_team_cannot_play_against_itself():
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["away_team_name"] = "Argentina"
    match_record, problem_list = MatchRecord.parse_and_validate_row(
        row_that_needs_to_be_validated
    )

    assert match_record is None
    assert len(problem_list) > 0
