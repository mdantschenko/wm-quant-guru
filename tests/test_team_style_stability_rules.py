"""Tests for the style swing of a team, and for the columns it is written to.

The column names are written out by hand while the builder builds the same
names out of the dimensions. If the two ever drift apart the file would be
written with an unknown column, so one test holds them together.

The swing itself is measured on standardised values, so a season that gives no
spread to standardise against must leave the swing empty rather than call it
zero.
"""

import pandas as pd

from wmguru.data.builders.team_style_stability_builder import TeamStyleStabilityBuilder
from wmguru.helpers.constant import TeamStyleStabilityCalculation

OTHER_DIMENSIONS = [
    name for name in TeamStyleStabilityCalculation.DIMENSIONS if name != "pass_share"
]


def make_style_rows(
    pass_shares: list[str], team: str = "Juventus", season: str = "2018"
) -> pd.DataFrame:
    """Build a style table of one team, one row per given pass share."""
    return pd.DataFrame(
        {
            "source": ["wyscout"] * len(pass_shares),
            "competition": ["Serie A"] * len(pass_shares),
            "season": [season] * len(pass_shares),
            "team": [team] * len(pass_shares),
            "pass_share": pass_shares,
            **{name: [""] * len(pass_shares) for name in OTHER_DIMENSIONS},
        }
    )


def summarise(style_rows: pd.DataFrame) -> pd.DataFrame:
    """Run a style table through the builder, the way the build does."""
    builder = TeamStyleStabilityBuilder()
    numbers = style_rows.assign(
        **{
            name: pd.to_numeric(style_rows[name], errors="coerce")
            for name in TeamStyleStabilityCalculation.DIMENSIONS
        }
    )
    return builder._summarise_every_team(
        numbers, builder._standardised_within_the_season(numbers)
    )


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
    """The season needs a spread of its own, or there is nothing to measure against."""
    steady = make_style_rows(["0.5"] * 5, team="Juventus")
    varied = make_style_rows(["0.3", "0.7", "0.4", "0.6", "0.5"], team="Napoli")

    summary = summarise(pd.concat([steady, varied], ignore_index=True))
    steady_row = summary[summary["team"] == "Juventus"]

    assert steady_row["pass_share_volatility"].iloc[0] == 0.0


def test_a_team_that_swung_shows_it():
    summary = summarise(make_style_rows(["0.3", "0.7", "0.3", "0.7", "0.5"]))

    assert summary["pass_share_mean"].iloc[0] == 0.5
    assert summary["pass_share_volatility"].iloc[0] > 0.9


def test_a_dimension_the_season_never_measured_leaves_the_swing_empty():
    """Without a spread there is nothing to measure the swing against."""
    summary = summarise(make_style_rows(["0.5"] * 5))

    assert pd.isna(summary[OTHER_DIMENSIONS[0] + "_volatility"].iloc[0])


def test_an_empty_cell_is_not_read_as_a_zero():
    """A style column is empty where the match gave nothing to divide by."""
    summary = summarise(make_style_rows(["0.5", "", "0.5", "0.5", "0.5"]))

    assert summary["pass_share_mean"].iloc[0] == 0.5


def test_a_team_with_too_few_matches_gets_no_row():
    too_few = TeamStyleStabilityCalculation.MINIMUM_MATCHES - 1

    summary = summarise(make_style_rows(["0.5"] * too_few))

    assert len(summary) == 0


def test_every_team_of_a_season_is_standardised_against_that_season():
    """A league where everybody passes a lot must not look like one big favourite."""
    calm = make_style_rows(["0.5"] * 5, team="Juventus")
    busy = make_style_rows(["0.9"] * 5, team="Napoli")

    summary = summarise(pd.concat([calm, busy], ignore_index=True))

    assert len(summary) == 2
    assert sorted(summary["pass_share_mean"]) == [0.5, 0.9]
