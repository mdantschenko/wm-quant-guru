"""Tests for the small rules inside the downloaders that are easy to get wrong.

These check internals on purpose. The rules were carried over from the old
scripts by hand, so they need a net that says whether they still behave the
same. None of these tests touches the network.
"""

from wmguru.data.downloads.football_data_downloader import FootballDataDownloader
from wmguru.data.downloads.footystats_international_downloader import (
    FootyStatsInternationalDownloader,
)
from wmguru.data.downloads.statsbomb_lineup_downloader import StatsBombLineupDownloader


def make_football_data_downloader() -> FootballDataDownloader:
    """Build a downloader without a web client, no test here asks a server."""
    return FootballDataDownloader(None)


def test_the_season_code_of_the_source_is_two_short_years():
    downloader = make_football_data_downloader()

    assert downloader._season_code(2013) == "1314"
    assert downloader._season_code(1993) == "9394"


def test_the_season_code_around_the_year_two_thousand_keeps_its_zeroes():
    assert make_football_data_downloader()._season_code(2000) == "0001"


def test_the_readable_season_label_uses_the_full_first_year():
    downloader = make_football_data_downloader()

    assert downloader._season_label(2013) == "2013-14"
    assert downloader._season_label(1999) == "1999-00"


def test_a_csv_file_with_a_byte_order_marker_is_still_usable():
    payload = b"\xef\xbb\xbfDiv,HomeTeam,AwayTeam" + b"x" * 200

    assert (
        make_football_data_downloader()._looks_like_a_usable_file(
            payload, check_header=True
        )
        is True
    )


def test_a_short_answer_is_not_taken_for_a_csv_file():
    assert (
        make_football_data_downloader()._looks_like_a_usable_file(
            b"<html>404</html>", check_header=True
        )
        is False
    )


def test_a_long_season_year_becomes_a_range():
    downloader = FootyStatsInternationalDownloader(None)

    assert downloader._season_label(20162018) == "2016-2018"
    assert downloader._season_label(2024) == "2024"


def test_a_competition_of_the_youth_or_the_women_is_left_out():
    downloader = FootyStatsInternationalDownloader(None)

    assert downloader._is_a_senior_national_team_competition("International Friendlies")
    assert not downloader._is_a_senior_national_team_competition(
        "International UEFA U21 Championship"
    )
    assert not downloader._is_a_senior_national_team_competition(
        "International FIFA Club World Cup"
    )
    assert not downloader._is_a_senior_national_team_competition(
        "England Premier League"
    )


def test_the_minute_is_read_out_of_the_timestamp():
    downloader = StatsBombLineupDownloader(None, None)

    assert downloader._read_minute("47:12") == "47"
    assert downloader._read_minute(None) == ""
    assert downloader._read_minute("broken") == ""


def test_a_player_who_never_came_on_is_marked_as_unused_bench():
    downloader = StatsBombLineupDownloader(None, None)

    role, position, minute_on, minute_off = downloader._read_role_of({"positions": []})

    assert role == "bench_unused"
    assert (position, minute_on, minute_off) == ("", "", "")


def test_a_starter_is_marked_as_starting_in_minute_zero():
    downloader = StatsBombLineupDownloader(None, None)
    player = {
        "positions": [
            {"start_reason": "Starting XI", "position": "Right Back", "to": "90:00"}
        ]
    }

    role, position, minute_on, minute_off = downloader._read_role_of(player)

    assert role == "starter"
    assert position == "Right Back"
    assert minute_on == "0"
    assert minute_off == "90"


def test_a_substitute_is_marked_with_the_minute_he_came_on():
    downloader = StatsBombLineupDownloader(None, None)
    player = {
        "positions": [
            {"start_reason": "Substitution", "position": "Striker", "from": "62:30"}
        ]
    }

    role, _, minute_on, _ = downloader._read_role_of(player)

    assert role == "sub_used"
    assert minute_on == "62"
