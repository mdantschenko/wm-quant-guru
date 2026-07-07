"""
Below is the desired end state for our data.
    match_id: str             
    match_date: str 
    home_team_id: str  
    away_team_id: str  
    home_goals_regular_time: int 
    away_goals_regular_time: int 
    home_goals_final: int 
    away_goals_final: int 
    is_regular_time_score_reconstructed_unreliable: bool 
    is_neutral_venue: bool 
    tournament_name: str 
    competition_category: str 
    city: str = ""
    country: str = ""
    home_shootout_goals: int | None = None
    away_shootout_goals: int | None = None

For this test we use from the dataset "International football results from 1872 to 2026" the following data:
date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2022-12-18,Argentina,France,3,3,FIFA World Cup,Lusail,Qatar,TRUE
"""

from wmguru.data.schema import MatchRecord

def make_valid_row():
    return {
        "match_id": "test",
        "match_date": "2022-12-18",
        "home_team_id": "Argentina",
        "away_team_id": "France",
        "home_goals_regular_time": "2",
        "away_goals_regular_time": "2",
        "home_goals_final": "3",
        "away_goals_final": "3",
        "is_regular_time_score_reconstructed_unreliable": "0",
        "is_neutral_venue": "1",
        "tournament_name": "FIFA World Cup",
        "competition_category": "FIFA World Cup",
        "city": "Lusail",
        "country": "Qatar",
        "home_shootout_goals": "4",
        "away_shootout_goals": "2"
    }

def test_valid_row_parses():
    row_that_needs_to_be_validated = make_valid_row()
    match_record, errors = MatchRecord.parse_and_validate_row(row_that_needs_to_be_validated)

    assert errors == []
    assert match_record is not None
    assert match_record.home_goals_regular_time == 2

def test_invalid_row_parses_1():
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["home_goals_regular_time"] = "-1"
    match_record, errors = MatchRecord.parse_and_validate_row(row_that_needs_to_be_validated)

    assert len(errors) > 0
    assert match_record is None

def test_invalid_row_parses_2():
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["home_team_id"] = ""
    match_record, errors = MatchRecord.parse_and_validate_row(row_that_needs_to_be_validated)

    assert len(errors) > 0
    assert match_record is None

def test_invalid_row_parses_3():
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["home_goals_regular_time"] = "3"
    row_that_needs_to_be_validated["home_goals_final"] = "2"
    match_record, errors = MatchRecord.parse_and_validate_row(row_that_needs_to_be_validated)

    assert len(errors) > 0
    assert match_record is None

def test_invalid_row_parses_4():
    row_that_needs_to_be_validated = make_valid_row()
    row_that_needs_to_be_validated["home_team_id"] = None 
    row_that_needs_to_be_validated["match_id"] = None
    match_record, errors = MatchRecord.parse_and_validate_row(row_that_needs_to_be_validated)

    assert len(errors) > 0
    assert match_record is None