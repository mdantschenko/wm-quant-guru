"""Tests for the style numbers both event sources are turned into.

The calculation is shared, so a mistake here would be wrong in both halves at
once. The awkward parts are the ones that need the other team, and the pass
share per score line, which has to know what the score was at the moment of
each pass rather than at the end.
"""

from wmguru.helpers.data_class import MatchAction, MatchIdentity
from wmguru.helpers.utils import MatchStyleCalculator

IDENTITY = MatchIdentity(
    game_identifier="1",
    competition_name="Serie A",
    season_name="2018",
    match_date="2018-05-13",
    home_team_name="Juventus",
    away_team_name="Napoli",
)


def make_action(
    team_name: str,
    kind: str,
    start_x: float = 50.0,
    start_y: float = 34.0,
    end_x: float = 60.0,
    end_y: float = 34.0,
    was_successful: bool = True,
    scoring_team: str | None = None,
    expected_goals: float | None = None,
    was_after_a_set_piece: bool = False,
    second_in_period: float = 0.0,
) -> MatchAction:
    """Build one action, with everything not named left harmless."""
    return MatchAction(
        team_name=team_name,
        kind=kind,
        was_successful=was_successful,
        start_x_in_metres=start_x,
        start_y_in_metres=start_y,
        end_x_in_metres=end_x,
        end_y_in_metres=end_y,
        scoring_team=scoring_team,
        expected_goals=expected_goals,
        was_after_a_set_piece=was_after_a_set_piece,
        period_number=1,
        second_in_period=second_in_period,
    )


def calculate_rows(
    actions: list[MatchAction], has_expected_goals: bool = False
) -> dict[str, dict]:
    """Run one match through the calculator and key the rows by team."""
    rows = MatchStyleCalculator().calculate_rows_of_one_match(
        actions, IDENTITY, "wyscout", has_expected_goals
    )
    return {row["team"]: row for row in rows}


def test_the_pass_share_of_both_teams_adds_up_to_one():
    rows = calculate_rows(
        [make_action("Juventus", "open_pass")] * 3
        + [make_action("Napoli", "open_pass")]
    )

    assert rows["Juventus"]["pass_share"] == 0.75
    assert rows["Napoli"]["pass_share"] == 0.25


def test_a_team_without_a_single_pass_gets_no_row():
    """Its half of the match never arrived, and a row of zeros would lie."""
    rows = calculate_rows([make_action("Juventus", "open_pass")])

    assert "Napoli" not in rows


def test_pressing_counts_the_passes_of_the_other_team():
    """Passes per defensive action is their build up against our defending."""
    rows = calculate_rows(
        [
            make_action("Napoli", "open_pass", start_x=20.0),
            make_action("Napoli", "open_pass", start_x=30.0),
            make_action("Napoli", "open_pass", start_x=40.0),
            make_action("Napoli", "open_pass", start_x=50.0),
            make_action("Juventus", "tackle", start_x=60.0),
            make_action("Juventus", "open_pass"),
        ]
    )

    assert rows["Juventus"]["passes_per_defensive_action"] == 4.0


def test_a_team_that_never_defended_high_gets_an_empty_cell_not_a_zero():
    """A zero would claim it pressed nobody, when it had no chance to."""
    rows = calculate_rows(
        [
            make_action("Napoli", "open_pass", start_x=20.0),
            make_action("Juventus", "open_pass"),
        ]
    )

    assert rows["Juventus"]["passes_per_defensive_action"] == ""


def test_a_pass_that_ends_in_the_box_is_counted():
    rows = calculate_rows(
        [
            make_action("Juventus", "open_pass", end_x=95.0, end_y=34.0),
            make_action("Juventus", "open_pass", end_x=95.0, end_y=5.0),
            make_action("Napoli", "open_pass"),
        ]
    )

    assert rows["Juventus"]["passes_into_box"] == 1


def test_the_field_tilt_compares_the_final_third_of_both_teams():
    rows = calculate_rows(
        [
            make_action("Juventus", "open_pass", start_x=80.0),
            make_action("Juventus", "open_pass", start_x=80.0),
            make_action("Juventus", "open_pass", start_x=80.0),
            make_action("Napoli", "open_pass", start_x=80.0),
        ]
    )

    assert rows["Juventus"]["field_tilt"] == 0.75


def test_a_pass_after_a_goal_counts_under_the_new_score():
    """The score at the moment of the pass, not the score at the end."""
    rows = calculate_rows(
        [
            make_action("Juventus", "open_pass", second_in_period=10.0),
            make_action(
                "Juventus",
                "shot",
                scoring_team="self",
                second_in_period=20.0,
            ),
            make_action("Juventus", "open_pass", second_in_period=30.0),
            make_action("Napoli", "open_pass", second_in_period=40.0),
        ]
    )

    assert rows["Juventus"]["pass_share_while_level"] == 0.5
    assert rows["Juventus"]["pass_share_while_leading"] == 0.5
    assert rows["Napoli"]["pass_share_while_trailing"] == 1.0


def test_an_own_goal_counts_for_the_other_team():
    rows = calculate_rows(
        [
            make_action("Juventus", "other", scoring_team="self", second_in_period=1.0),
            make_action("Juventus", "open_pass", second_in_period=2.0),
            make_action("Napoli", "open_pass", second_in_period=3.0),
        ]
    )

    assert rows["Juventus"]["pass_share_while_leading"] == 1.0
    assert rows["Napoli"]["pass_share_while_trailing"] == 1.0


def test_a_source_without_expected_goals_leaves_those_columns_empty():
    rows = calculate_rows(
        [
            make_action("Juventus", "open_pass"),
            make_action("Juventus", "shot", start_x=95.0),
            make_action("Napoli", "open_pass"),
        ]
    )

    assert rows["Juventus"]["shots"] == 1
    assert rows["Juventus"]["expected_goals"] == ""
    assert rows["Juventus"]["expected_goals_per_shot"] == ""


def test_a_penalty_is_in_the_expected_goals_but_not_in_the_non_penalty_ones():
    rows = calculate_rows(
        [
            make_action("Juventus", "open_pass"),
            make_action("Juventus", "shot", start_x=95.0, expected_goals=0.1),
            make_action("Juventus", "penalty_shot", start_x=95.0, expected_goals=0.76),
            make_action("Napoli", "open_pass"),
        ],
        has_expected_goals=True,
    )

    assert rows["Juventus"]["expected_goals"] == 0.86
    assert rows["Juventus"]["non_penalty_expected_goals"] == 0.1


def test_what_one_team_created_is_what_the_other_one_conceded():
    calculator = MatchStyleCalculator()
    rows = calculator.calculate_rows_of_one_match(
        [
            make_action("Juventus", "open_pass"),
            make_action("Juventus", "shot", start_x=95.0, expected_goals=0.4),
            make_action("Napoli", "open_pass"),
            make_action("Napoli", "shot", start_x=95.0, expected_goals=0.1),
        ],
        IDENTITY,
        "statsbomb",
        has_expected_goals=True,
    )
    calculator.fill_expected_goals_against(rows)
    by_team = {row["team"]: row for row in rows}

    assert by_team["Juventus"]["expected_goals"] == 0.4
    assert by_team["Juventus"]["expected_goals_against"] == 0.1
    assert by_team["Napoli"]["expected_goals_against"] == 0.4


def test_a_take_on_that_was_lost_lowers_the_success_rate():
    rows = calculate_rows(
        [
            make_action("Juventus", "open_pass"),
            make_action("Juventus", "take_on", was_successful=True),
            make_action("Juventus", "take_on", was_successful=False),
            make_action("Napoli", "open_pass"),
        ]
    )

    assert rows["Juventus"]["take_on_success_rate"] == 0.5
