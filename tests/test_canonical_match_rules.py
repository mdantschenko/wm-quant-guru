"""Tests for the canonical match dataset, the backbone every model learns on.

The traps here are all in the source, and pandas adds one of its own. A
fixture carries the text NA where a score belongs, which pandas reads as a
missing value unless it is told not to, so the whole 2026 World Cup turns into
rows that claim to be played. Two sources date the same match one day apart.
And two rows share a day and both team names, so the obvious identifier is not
unique.
"""

import pandas as pd

from wmguru.data.builders.canonical_match_builder import CanonicalMatchBuilder
from wmguru.helpers.constant import CanonicalMatchDataset


def make_results(**overrides: list[str]) -> pd.DataFrame:
    """Build a small results table, one row unless a column says otherwise."""
    columns = {
        "date": ["2018-06-17"],
        "home_team": ["Germany"],
        "away_team": ["Brazil"],
        "home_score": ["2"],
        "away_score": ["1"],
        "tournament": ["Friendly"],
        "city": ["Munich"],
        "country": ["Germany"],
        "neutral": ["FALSE"],
    }
    columns.update(overrides)
    frame = pd.DataFrame(columns)
    return frame.assign(
        match_day=pd.to_datetime(frame["date"]),
        team_pair=CanonicalMatchBuilder()._team_pair_of(
            frame["home_team"], frame["away_team"]
        ),
    )


def make_other_table(
    match_date: str, home_team: str, away_team: str, column: str, value: str
) -> pd.DataFrame:
    """Build a table to join onto the matches, in the shape the joiner wants."""
    return pd.DataFrame(
        {
            "match_day": pd.to_datetime([match_date]),
            "team_pair": CanonicalMatchBuilder()._team_pair_of(
                pd.Series([home_team]), pd.Series([away_team])
            ),
            column: [value],
        }
    )


def test_pandas_does_not_read_the_fixture_placeholder_as_a_missing_value():
    """The source writes NA, which pandas takes for a missing value by default."""
    results = pd.read_csv(
        CanonicalMatchDataset.OUTPUT_FILE.parent.parent
        / "International football results from 1872 to 2026"
        / "results.csv",
        dtype=str,
        keep_default_na=False,
        nrows=None,
    )
    fixtures = results[
        results["home_score"] == CanonicalMatchDataset.UNPLAYED_SCORE_TEXT
    ]

    assert len(fixtures) == 72
    assert set(fixtures["tournament"]) == {"FIFA World Cup"}


def test_a_fixture_is_told_apart_from_a_played_match():
    builder = CanonicalMatchBuilder()
    results = make_results(
        date=["2018-06-17", "2026-06-11"],
        home_team=["Germany", "Mexico"],
        away_team=["Brazil", "Poland"],
        home_score=["2", "NA"],
        away_score=["1", "NA"],
        tournament=["Friendly", "FIFA World Cup"],
        city=["Munich", "Mexico City"],
        country=["Germany", "Mexico"],
        neutral=["FALSE", "FALSE"],
    )

    built = builder._with_canonical_columns(
        results.assign(shootout_winner=None, tournament_stage=None)
    )

    assert list(built["was_played"]) == [True, False]


def test_a_real_goalless_draw_is_still_a_played_match():
    built = CanonicalMatchBuilder()._with_canonical_columns(
        make_results(home_score=["0"], away_score=["0"]).assign(
            shootout_winner=None, tournament_stage=None
        )
    )

    assert bool(built["was_played"].iloc[0]) is True


def test_two_matches_of_the_same_day_and_teams_get_two_identifiers():
    """The source holds two such rows, and one would overwrite the other."""
    results = make_results(
        date=["2018-06-17", "2018-06-17"],
        home_team=["Germany", "Germany"],
        away_team=["Brazil", "Brazil"],
        home_score=["2", "1"],
        away_score=["1", "2"],
        tournament=["Friendly", "Friendly"],
        city=["Munich", "Munich"],
        country=["Germany", "Germany"],
        neutral=["FALSE", "FALSE"],
    )

    identifiers = list(
        CanonicalMatchBuilder()._with_match_identifier(results)["match_id"]
    )

    assert identifiers == ["2018-06-17|Germany|Brazil", "2018-06-17|Germany|Brazil#2"]


def test_a_match_is_found_although_the_sources_date_it_one_day_apart():
    """A late kick off in the Americas is dated one day on in UTC."""
    builder = CanonicalMatchBuilder()
    results = builder._with_match_identifier(
        make_results(date=["2024-06-20"], home_team=["Argentina"], away_team=["Canada"])
    )
    stages = make_other_table(
        "2024-06-21", "Argentina", "Canada", "tournament_stage", "Group Stage"
    )

    joined = builder._joined_with(results, stages)

    assert joined["tournament_stage"].iloc[0] == "Group Stage"


def test_a_match_two_days_apart_is_not_joined():
    """Otherwise a return leg would be given the stage of the first one."""
    builder = CanonicalMatchBuilder()
    results = builder._with_match_identifier(
        make_results(date=["2024-06-20"], home_team=["Argentina"], away_team=["Canada"])
    )
    stages = make_other_table(
        "2024-06-23", "Argentina", "Canada", "tournament_stage", "Group Stage"
    )

    joined = builder._joined_with(results, stages)

    assert pd.isna(joined["tournament_stage"].iloc[0])


def test_the_teams_are_joined_whichever_way_round_they_are_written():
    """The tournament files and the results file disagree on who was at home."""
    builder = CanonicalMatchBuilder()
    results = builder._with_match_identifier(
        make_results(home_team=["Brazil"], away_team=["Germany"])
    )
    stages = make_other_table(
        "2018-06-17", "Germany", "Brazil", "tournament_stage", "Final"
    )

    joined = builder._joined_with(results, stages)

    assert joined["tournament_stage"].iloc[0] == "Final"


def test_a_join_never_adds_a_row():
    """A widened join table can match twice, and would double the match."""
    builder = CanonicalMatchBuilder()
    results = builder._with_match_identifier(
        make_results(date=["2024-06-21"], home_team=["Peru"], away_team=["Chile"])
    )
    stages = pd.concat(
        [
            make_other_table(
                "2024-06-21", "Peru", "Chile", "tournament_stage", "Group Stage"
            ),
            make_other_table(
                "2024-06-22", "Peru", "Chile", "tournament_stage", "Quarter-finals"
            ),
        ],
        ignore_index=True,
    )

    joined = builder._joined_with(results, stages)

    assert len(joined) == 1
    assert joined["tournament_stage"].iloc[0] == "Group Stage"


def test_every_kind_of_competition_gets_a_category():
    names = pd.Series(
        [
            "Friendly",
            "FIFA World Cup qualification",
            "FIFA World Cup",
            "UEFA Nations League",
            "Island Games",
        ]
    )

    categories = list(
        CanonicalMatchBuilder().which_kind_of_competition_each_name_is(names)
    )

    assert categories == [
        CanonicalMatchDataset.FRIENDLY_CATEGORY,
        CanonicalMatchDataset.QUALIFICATION_CATEGORY,
        CanonicalMatchDataset.MAJOR_TOURNAMENT_CATEGORY,
        CanonicalMatchDataset.NATIONS_LEAGUE_CATEGORY,
        CanonicalMatchDataset.OTHER_TOURNAMENT_CATEGORY,
    ]


def test_a_qualification_is_never_counted_as_the_tournament_itself():
    """Both names hold the tournament, and the order of the tests decides."""
    categories = CanonicalMatchBuilder().which_kind_of_competition_each_name_is(
        pd.Series(["AFC Asian Cup qualification"])
    )

    assert categories.iloc[0] == CanonicalMatchDataset.QUALIFICATION_CATEGORY


def test_the_home_team_is_host_when_it_plays_in_its_own_country():
    built = CanonicalMatchBuilder()._with_canonical_columns(
        make_results().assign(shootout_winner=None, tournament_stage=None)
    )

    assert bool(built["home_team_is_host"].iloc[0]) is True
    assert bool(built["away_team_is_host"].iloc[0]) is False
    assert bool(built["is_neutral_venue"].iloc[0]) is False


def test_nobody_is_host_at_a_neutral_venue():
    built = CanonicalMatchBuilder()._with_canonical_columns(
        make_results(country=["Qatar"], neutral=["TRUE"]).assign(
            shootout_winner=None, tournament_stage=None
        )
    )

    assert bool(built["home_team_is_host"].iloc[0]) is False
    assert bool(built["away_team_is_host"].iloc[0]) is False
    assert bool(built["is_neutral_venue"].iloc[0]) is True


def test_a_match_that_went_to_a_shootout_flags_its_regular_time_score():
    """The source score is the one after extra time, so ninety minutes is a guess."""
    built = CanonicalMatchBuilder()._with_canonical_columns(
        make_results(home_score=["1"], away_score=["1"]).assign(
            shootout_winner="Italy", tournament_stage=None
        )
    )

    assert built["shootout_winner"].iloc[0] == "Italy"
    assert bool(built["is_regular_time_score_reconstructed_unreliable"].iloc[0]) is True


def test_a_match_without_a_shootout_keeps_its_regular_time_score():
    built = CanonicalMatchBuilder()._with_canonical_columns(
        make_results().assign(shootout_winner=None, tournament_stage=None)
    )

    assert built["shootout_winner"].iloc[0] == ""
    assert (
        bool(built["is_regular_time_score_reconstructed_unreliable"].iloc[0]) is False
    )
    assert built["home_goals_regular_time"].iloc[0] == built["home_goals_final"].iloc[0]


def test_an_unknown_stage_is_named_rather_than_left_empty():
    built = CanonicalMatchBuilder()._with_canonical_columns(
        make_results().assign(shootout_winner=None, tournament_stage=None)
    )

    assert built["tournament_stage"].iloc[0] == CanonicalMatchDataset.UNKNOWN_STAGE
