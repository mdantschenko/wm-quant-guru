"""Tests for the rules inside the builders that carry real arithmetic.

The Elo engine decides how much every past match moves a rating, so a mistake
here quietly poisons every model that uses the feature. None of these tests
reads a file.
"""

from datetime import date

import pandas as pd

from wmguru.helpers.constant import RefereeProfileCalculation
from wmguru.preprocessing.builders.elo_rating_builder import EloRatingBuilder
from wmguru.preprocessing.builders.referee_profile_builder import RefereeProfileBuilder
from wmguru.preprocessing.builders.squad_value_builder import SquadValueBuilder


def k_factor_of(tournament_name: str) -> float:
    """Read the K factor of one competition, out of the column of them."""
    return float(EloRatingBuilder().k_factor_of(pd.Series([tournament_name])).iloc[0])


def goal_multiplier_of(goal_difference: int) -> float:
    """Read the multiplier of one margin, out of the column of them."""
    return float(
        EloRatingBuilder().goal_multiplier_of(pd.Series([goal_difference])).iloc[0]
    )


def test_a_world_cup_match_moves_a_rating_three_times_as_much_as_a_friendly():
    assert k_factor_of("FIFA World Cup") == 60.0
    assert k_factor_of("Friendly") == 20.0


def test_a_qualification_counts_less_than_a_final_round():
    assert k_factor_of("FIFA World Cup qualification") == 40.0
    assert k_factor_of("UEFA Nations League") == 40.0
    assert k_factor_of("UEFA Euro") == 50.0


def test_a_qualification_is_checked_before_the_final_round_name():
    """UEFA Euro qualification holds both names and must count as a qualifier."""
    assert k_factor_of("UEFA Euro qualification") == 40.0


def test_an_unknown_competition_falls_back_to_the_middle():
    assert k_factor_of("Kirin Cup") == 30.0


def test_a_narrow_win_is_not_multiplied():
    assert goal_multiplier_of(0) == 1.0
    assert goal_multiplier_of(1) == 1.0


def test_a_clear_win_counts_more_but_ever_more_slowly():
    assert goal_multiplier_of(2) == 1.5
    assert goal_multiplier_of(3) == (11.0 + 3) / 8.0
    assert goal_multiplier_of(6) > goal_multiplier_of(3)


def test_two_equal_teams_are_expected_to_draw():
    assert EloRatingBuilder().expected_score_of(0.0) == 0.5


def test_the_stronger_team_is_expected_to_win_more_often():
    builder = EloRatingBuilder()

    assert builder.expected_score_of(400.0) > 0.9
    assert builder.expected_score_of(-400.0) < 0.1


def test_the_expectations_of_both_sides_add_up_to_one():
    builder = EloRatingBuilder()

    assert builder.expected_score_of(120.0) + builder.expected_score_of(-120.0) == 1.0


def test_a_match_that_was_not_played_is_left_out():
    """The source writes NA for a fixture, and NA is no result."""
    results = pd.DataFrame(
        {"home_score": ["2", "NA", ""], "away_score": ["1", "NA", "1"]}
    )

    played = EloRatingBuilder().only_the_played_matches(results)

    assert list(played["home_goals"]) == [2.0]


def test_a_neutral_venue_gives_no_home_advantage():
    matches = pd.DataFrame({"neutral": ["TRUE", "FALSE"]})

    advantage = EloRatingBuilder()._home_advantage_of(matches)

    assert list(advantage) == [0.0, 100.0]


def test_the_result_is_read_as_one_a_half_or_nothing():
    matches = pd.DataFrame({"home_goals": [2, 1, 0], "away_goals": [1, 1, 3]})

    score = EloRatingBuilder()._actual_score_of(matches)

    assert list(score) == [1.0, 0.5, 0.0]


def test_the_key_dates_are_january_and_july():
    key_dates = SquadValueBuilder().key_dates_between(
        date(2020, 1, 1), date(2021, 3, 1)
    )

    assert key_dates == [date(2020, 1, 1), date(2020, 7, 1), date(2021, 1, 1)]


def make_valuations(dated_values: list[tuple[date, int]]) -> pd.DataFrame:
    """Build the value history of one player, as the builder reads it."""
    return pd.DataFrame(
        {
            "player_identifier": [1] * len(dated_values),
            "valuation_date": pd.to_datetime([one for one, _ in dated_values]),
            "value": [value for _, value in dated_values],
            "player_first_seen": [0] * len(dated_values),
        }
    )


def value_on(dated_values: list[tuple[date, int]], key_date: date) -> int | None:
    """Look one player up on one key date, the way the whole build does."""
    found = SquadValueBuilder().value_of_every_player_on_every_key_date(
        make_valuations(dated_values), [key_date]
    )
    return None if found.empty else int(found["value"].iloc[0])


def test_a_valuation_after_the_key_date_is_never_used():
    """A value from the future would make every backtest meaningless."""
    valuations = [(date(2020, 1, 1), 100), (date(2021, 1, 1), 900)]

    assert value_on(valuations, date(2020, 6, 1)) == 100


def test_the_newest_valuation_up_to_the_key_date_wins():
    valuations = [(date(2020, 1, 1), 100), (date(2020, 5, 1), 300)]

    assert value_on(valuations, date(2020, 6, 1)) == 300


def test_a_stale_valuation_is_dropped_instead_of_carried_forward():
    valuations = [(date(2015, 1, 1), 100)]

    assert value_on(valuations, date(2020, 1, 1)) is None


def make_tournament_matches() -> pd.DataFrame:
    """Build a small tournament file, one row per referee to be judged."""
    return pd.DataFrame(
        {
            "status": ["complete", "incomplete", "complete", "complete"],
            "referee": ["Kuipers", "Kuipers", "N/A", "Marciniak"],
            "home_team_yellow_cards": ["3", "1", "1", ""],
            "away_team_yellow_cards": ["", "1", "1", "N/A"],
            "home_team_red_cards": ["0", "0", "0", "0"],
            "away_team_red_cards": ["0", "0", "0", "0"],
            "home_team_fouls": ["10", "9", "9", "12"],
            "away_team_fouls": ["8", "9", "9", "N/A"],
            "tournament": ["Euro 2024", "Euro 2024", "Euro 2024", "Euro 2024"],
        }
    )


def test_a_missing_card_count_is_read_as_zero():
    """The source writes N/A and empty cells where it collected nothing."""
    builder = RefereeProfileBuilder()
    matches = make_tournament_matches()

    added_up = builder._sum_of_the_named_columns(
        matches, RefereeProfileCalculation.YELLOW_CARD_COLUMNS
    )

    assert list(added_up) == [3.0, 2.0, 2.0, 0.0]


def test_only_a_finished_match_carries_a_usable_referee():
    builder = RefereeProfileBuilder()

    usable = builder._only_the_usable_matches(make_tournament_matches())

    assert list(usable["referee"]) == ["Kuipers", "Marciniak"]
