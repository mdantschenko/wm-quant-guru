"""Tests for the rules inside the builders that carry real arithmetic.

The Elo engine decides how much every past match moves a rating, so a mistake
here quietly poisons every model that uses the feature. None of these tests
reads a file.
"""

from datetime import date

from wmguru.data.builders.elo_rating_builder import EloRatingBuilder
from wmguru.data.builders.referee_profile_builder import RefereeProfileBuilder
from wmguru.data.builders.squad_value_builder import SquadValueBuilder


def test_a_world_cup_match_moves_a_rating_three_times_as_much_as_a_friendly():
    builder = EloRatingBuilder()

    assert builder.k_factor_of("FIFA World Cup") == 60.0
    assert builder.k_factor_of("Friendly") == 20.0


def test_a_qualification_counts_less_than_a_final_round():
    builder = EloRatingBuilder()

    assert builder.k_factor_of("FIFA World Cup qualification") == 40.0
    assert builder.k_factor_of("UEFA Nations League") == 40.0
    assert builder.k_factor_of("UEFA Euro") == 50.0


def test_a_qualification_is_checked_before_the_final_round_name():
    """UEFA Euro qualification holds both names and must count as a qualifier."""
    assert EloRatingBuilder().k_factor_of("UEFA Euro qualification") == 40.0


def test_an_unknown_competition_falls_back_to_the_middle():
    assert EloRatingBuilder().k_factor_of("Kirin Cup") == 30.0


def test_a_narrow_win_is_not_multiplied():
    builder = EloRatingBuilder()

    assert builder.goal_multiplier_of(0) == 1.0
    assert builder.goal_multiplier_of(1) == 1.0


def test_a_clear_win_counts_more_but_ever_more_slowly():
    builder = EloRatingBuilder()

    assert builder.goal_multiplier_of(2) == 1.5
    assert builder.goal_multiplier_of(3) == (11.0 + 3) / 8.0
    assert builder.goal_multiplier_of(6) > builder.goal_multiplier_of(3)


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
    builder = EloRatingBuilder()

    assert builder._was_played({"home_score": "2", "away_score": "1"}) is True
    assert builder._was_played({"home_score": "NA", "away_score": "NA"}) is False
    assert builder._was_played({"home_score": "", "away_score": "1"}) is False


def test_a_neutral_venue_gives_no_home_advantage():
    builder = EloRatingBuilder()

    assert builder._home_advantage_of({"neutral": "TRUE"}) == 0.0
    assert builder._home_advantage_of({"neutral": "FALSE"}) == 100.0


def test_the_result_is_read_as_one_a_half_or_nothing():
    builder = EloRatingBuilder()

    assert builder._actual_score_of(2, 1) == 1.0
    assert builder._actual_score_of(1, 1) == 0.5
    assert builder._actual_score_of(0, 3) == 0.0


def test_the_key_dates_are_january_and_july():
    key_dates = SquadValueBuilder().key_dates_between(
        date(2020, 1, 1), date(2021, 3, 1)
    )

    assert key_dates == [date(2020, 1, 1), date(2020, 7, 1), date(2021, 1, 1)]


def test_a_valuation_after_the_key_date_is_never_used():
    """A value from the future would make every backtest meaningless."""
    valuations = [(date(2020, 1, 1), 100), (date(2021, 1, 1), 900)]

    assert SquadValueBuilder().value_on(valuations, date(2020, 6, 1)) == 100


def test_the_newest_valuation_up_to_the_key_date_wins():
    valuations = [(date(2020, 1, 1), 100), (date(2020, 5, 1), 300)]

    assert SquadValueBuilder().value_on(valuations, date(2020, 6, 1)) == 300


def test_a_stale_valuation_is_dropped_instead_of_carried_forward():
    valuations = [(date(2015, 1, 1), 100)]

    assert SquadValueBuilder().value_on(valuations, date(2020, 1, 1)) is None


def test_a_player_without_any_valuation_yet_has_no_value():
    assert SquadValueBuilder().value_on([], date(2020, 1, 1)) is None


def test_a_missing_card_count_is_read_as_zero():
    builder = RefereeProfileBuilder()

    assert builder._as_whole_number("3") == 3
    assert builder._as_whole_number("") == 0
    assert builder._as_whole_number(None) == 0
    assert builder._as_whole_number("N/A") == 0


def test_only_a_finished_match_carries_a_usable_referee():
    builder = RefereeProfileBuilder()

    assert builder._usable_referee_of({"status": "complete", "referee": "Kuipers"}) == (
        "Kuipers"
    )
    assert (
        builder._usable_referee_of({"status": "incomplete", "referee": "Kuipers"})
        is None
    )
    assert builder._usable_referee_of({"status": "complete", "referee": "N/A"}) is None
