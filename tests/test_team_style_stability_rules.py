"""Tests for the style swing of a team, and for the columns it is written to.

The column names are written out by hand while the builder builds the same
names out of the dimensions. If the two ever drift apart the file would be
written with an unknown column, so one test holds them together.
"""

from wmguru.data.builders.team_style_stability_builder import TeamStyleStabilityBuilder
from wmguru.helpers.constant import TeamStyleStabilityCalculation


def make_match(pass_share: str) -> dict[str, str]:
    """Build one style row of one match."""
    return {
        "source": "wyscout",
        "competition": "Serie A",
        "season": "2018",
        "team": "Juventus",
        "pass_share": pass_share,
    }


def test_the_written_columns_match_the_dimensions():
    expected = (
        ("source", "competition", "season", "team", "matches")
        + tuple(
            name + suffix
            for name in TeamStyleStabilityCalculation.DIMENSIONS
            for suffix in (
                TeamStyleStabilityCalculation.MEAN_SUFFIX,
                TeamStyleStabilityCalculation.VOLATILITY_SUFFIX,
            )
        )
        + ("style_volatility",)
    )

    assert expected == TeamStyleStabilityCalculation.COLUMN_NAMES


def test_a_team_that_played_the_same_way_every_time_has_no_swing():
    builder = TeamStyleStabilityBuilder()
    matches = [make_match("0.5") for _ in range(5)]

    _, swing = builder._summarise_one_dimension(matches, "pass_share", (0.5, 0.1))

    assert swing == 0.0


def test_a_team_that_swung_shows_it():
    builder = TeamStyleStabilityBuilder()
    matches = [make_match(value) for value in ("0.3", "0.7", "0.3", "0.7")]

    middle, swing = builder._summarise_one_dimension(matches, "pass_share", (0.5, 0.1))

    assert middle == 0.5
    assert swing == 2.0


def test_a_season_that_cannot_be_standardised_leaves_the_swing_empty():
    """Without a spread there is nothing to measure the swing against."""
    builder = TeamStyleStabilityBuilder()
    matches = [make_match("0.3"), make_match("0.7")]

    middle, swing = builder._summarise_one_dimension(matches, "pass_share", None)

    assert middle == 0.5
    assert swing == ""


def test_an_empty_cell_is_not_read_as_a_zero():
    """A style column is empty where the match gave nothing to divide by."""
    builder = TeamStyleStabilityBuilder()
    matches = [make_match("0.5"), make_match(""), make_match("0.5")]

    middle, _ = builder._summarise_one_dimension(matches, "pass_share", (0.5, 0.1))

    assert middle == 0.5


def test_a_team_with_too_few_matches_gets_no_row():
    builder = TeamStyleStabilityBuilder()
    too_few = TeamStyleStabilityCalculation.MINIMUM_MATCHES - 1
    grouped = {
        ("wyscout", "Serie A", "2018", "Juventus"): [make_match("0.5")] * too_few
    }

    assert builder._build_rows(grouped, {}) == []
