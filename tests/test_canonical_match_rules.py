"""Tests for the canonical match dataset, the backbone every model learns on.

The traps here are all in the source. A fixture carries the text NA where a
score belongs, so a plain emptiness check reads the whole 2026 World Cup as a
row of nil nil draws. Two sources date the same match one day apart. And two
rows share a day and both team names, so the obvious identifier is not unique.
"""

from datetime import date

from wmguru.data.builders.canonical_match_builder import CanonicalMatchBuilder
from wmguru.helpers.constant import CanonicalMatchDataset


def make_result_row(
    home_score: str = "2",
    away_score: str = "1",
    tournament: str = "Friendly",
    home_team: str = "Germany",
    away_team: str = "Brazil",
    country: str = "Germany",
    neutral: str = "FALSE",
    match_date: str = "2018-06-17",
) -> dict[str, str]:
    """Build one row of the results file."""
    return {
        "date": match_date,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "tournament": tournament,
        "city": "Munich",
        "country": country,
        "neutral": neutral,
    }


def test_a_fixture_is_not_read_as_a_goalless_draw():
    """The source writes NA, which is text, so an emptiness check misses it."""
    builder = CanonicalMatchBuilder()

    assert builder._was_played(make_result_row()) is True
    assert builder._was_played(make_result_row("NA", "NA")) is False


def test_a_real_goalless_draw_is_still_a_played_match():
    assert CanonicalMatchBuilder()._was_played(make_result_row("0", "0")) is True


def test_two_matches_of_the_same_day_and_teams_get_two_identifiers():
    """The source holds two such rows, and one would overwrite the other."""
    builder = CanonicalMatchBuilder()
    used: set[str] = set()

    first = builder._identifier_of(make_result_row(), used)
    second = builder._identifier_of(make_result_row(), used)

    assert first != second
    assert first == "2018-06-17|Germany|Brazil"
    assert second.startswith(first)


def test_the_identifier_says_which_match_it_is():
    used: set[str] = set()

    identifier = CanonicalMatchBuilder()._identifier_of(make_result_row(), used)

    assert identifier == "2018-06-17|Germany|Brazil"


def test_a_match_is_found_although_the_sources_date_it_one_day_apart():
    """A late kick off in the Americas is dated one day on in UTC."""
    builder = CanonicalMatchBuilder()
    stage_of_match = {
        (date(2024, 6, 21), frozenset(("Argentina", "Canada"))): "Group Stage"
    }
    row = make_result_row(
        home_team="Argentina", away_team="Canada", match_date="2024-06-20"
    )

    assert builder._looked_up(row, stage_of_match, "unknown") == "Group Stage"


def test_a_match_two_days_apart_is_not_joined():
    """Otherwise a return leg would be given the stage of the first one."""
    builder = CanonicalMatchBuilder()
    stage_of_match = {
        (date(2024, 6, 23), frozenset(("Argentina", "Canada"))): "Group Stage"
    }
    row = make_result_row(
        home_team="Argentina", away_team="Canada", match_date="2024-06-20"
    )

    assert builder._looked_up(row, stage_of_match, "unknown") == "unknown"


def test_the_teams_are_joined_whichever_way_round_they_are_written():
    """The tournament files and the results file disagree on who was at home."""
    builder = CanonicalMatchBuilder()
    stage_of_match = {(date(2018, 6, 17), frozenset(("Germany", "Brazil"))): "Final"}
    row = make_result_row(home_team="Brazil", away_team="Germany")

    assert builder._looked_up(row, stage_of_match, "unknown") == "Final"


def test_every_kind_of_competition_gets_a_category():
    builder = CanonicalMatchBuilder()

    assert builder.category_of("Friendly") == CanonicalMatchDataset.FRIENDLY_CATEGORY
    assert (
        builder.category_of("FIFA World Cup qualification")
        == CanonicalMatchDataset.QUALIFICATION_CATEGORY
    )
    assert (
        builder.category_of("FIFA World Cup")
        == CanonicalMatchDataset.MAJOR_TOURNAMENT_CATEGORY
    )
    assert (
        builder.category_of("UEFA Nations League")
        == CanonicalMatchDataset.NATIONS_LEAGUE_CATEGORY
    )
    assert (
        builder.category_of("Island Games")
        == CanonicalMatchDataset.OTHER_TOURNAMENT_CATEGORY
    )


def test_a_qualification_is_never_counted_as_the_tournament_itself():
    """Both names hold the tournament, and the order of the checks decides."""
    builder = CanonicalMatchBuilder()

    assert (
        builder.category_of("AFC Asian Cup qualification")
        == CanonicalMatchDataset.QUALIFICATION_CATEGORY
    )


def test_the_home_team_is_host_when_it_plays_in_its_own_country():
    builder = CanonicalMatchBuilder()

    columns = builder._shared_columns(make_result_row(), "identifier", {})

    assert columns["home_team_is_host"] is True
    assert columns["away_team_is_host"] is False
    assert columns["is_neutral_venue"] is False


def test_nobody_is_host_at_a_neutral_venue():
    builder = CanonicalMatchBuilder()
    row = make_result_row(country="Qatar", neutral="TRUE")

    columns = builder._shared_columns(row, "identifier", {})

    assert columns["home_team_is_host"] is False
    assert columns["away_team_is_host"] is False
    assert columns["is_neutral_venue"] is True


def test_a_match_that_went_to_a_shootout_flags_its_regular_time_score():
    """The source score is the one after extra time, so ninety minutes is a guess."""
    builder = CanonicalMatchBuilder()
    row = make_result_row("1", "1", home_team="England", away_team="Italy")
    winner_of_match = {
        (date(2018, 6, 17), frozenset(("England", "Italy"))): "Italy",
    }

    built = builder._build_row(row, "identifier", {}, winner_of_match)

    assert built["shootout_winner"] == "Italy"
    assert built["is_regular_time_score_reconstructed_unreliable"] is True
    assert built["home_goals_final"] == "1"


def test_a_match_without_a_shootout_keeps_its_regular_time_score():
    builder = CanonicalMatchBuilder()

    built = builder._build_row(make_result_row(), "identifier", {}, {})

    assert built["shootout_winner"] == ""
    assert built["is_regular_time_score_reconstructed_unreliable"] is False
    assert built["home_goals_regular_time"] == built["home_goals_final"]
