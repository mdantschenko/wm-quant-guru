"""Tests for the small rules inside the fetchers that are easy to get wrong.

These check internals on purpose, the same way test_downloader_rules.py does:
the rules were carried over from the old scripts by hand and need a net. None of
these tests touches the network.
"""

from datetime import date

from wmguru.helpers.utils import (
    StadiumLocator,
    TextNormalizer,
    WorldCupTeamNameReader,
)
from wmguru.preprocessing.fetchers.club_elo_fetcher import ClubEloFetcher
from wmguru.preprocessing.fetchers.match_weather_fetcher import MatchWeatherFetcher
from wmguru.preprocessing.fetchers.reddit_activity_fetcher import RedditActivityFetcher


def make_weather_fetcher() -> MatchWeatherFetcher:
    """Build a fetcher without a web client, no test here asks a server."""
    return MatchWeatherFetcher(None, StadiumLocator(TextNormalizer()))


def test_the_kick_off_hour_is_read_out_of_the_time():
    fetcher = make_weather_fetcher()

    assert fetcher._kick_off_hour("18:00:00.000") == 18
    assert fetcher._kick_off_hour("09:30:00") == 9


def test_a_broken_kick_off_time_falls_back_to_the_afternoon():
    fetcher = make_weather_fetcher()

    assert fetcher._kick_off_hour("") == 15
    assert fetcher._kick_off_hour("not a time") == 15


def test_an_hour_outside_the_day_is_pulled_back_into_it():
    fetcher = make_weather_fetcher()

    assert fetcher._kick_off_hour("99:00:00") == 23


def test_a_stadium_is_found_by_part_of_its_name():
    fetcher = make_weather_fetcher()

    assert fetcher._stadium_locator.find_place("Lusail Stadium") == (
        "Doha",
        25.29,
        51.53,
    )
    assert fetcher._stadium_locator.find_place("Wembley Stadium") == (
        "London",
        51.51,
        -0.13,
    )


def test_a_stadium_is_found_although_it_is_written_with_accents():
    fetcher = make_weather_fetcher()

    assert fetcher._stadium_locator.find_place("Bakı Olimpiya Stadionu") == (
        "Baku",
        40.41,
        49.87,
    )


def test_an_unknown_stadium_is_reported_as_not_found():
    assert make_weather_fetcher()._stadium_locator.find_place("Some New Arena") is None


def test_one_rating_snapshot_per_year_plus_today():
    fetcher = ClubEloFetcher(None)

    days = fetcher._list_the_snapshot_days(date(2003, 3, 15))

    assert days == [
        "2000-06-01",
        "2001-06-01",
        "2002-06-01",
        "2003-06-01",
        "2003-03-15",
    ]


def test_today_is_not_asked_for_twice():
    """On the first of June today already is one of the yearly snapshots."""
    fetcher = ClubEloFetcher(None)

    days = fetcher._list_the_snapshot_days(date(2001, 6, 1))

    assert days == ["2000-06-01", "2001-06-01"]


def test_an_iso_day_becomes_the_start_of_that_day():
    fetcher = RedditActivityFetcher(None, WorldCupTeamNameReader(), None)

    assert fetcher._to_seconds_since_epoch("2022-11-20") == 1668902400


def test_the_footystats_suffix_comes_off_the_team_name():
    reader = WorldCupTeamNameReader()

    assert reader.take_the_suffix_off("Turkey National Team") == "Turkey"
    assert reader.take_the_suffix_off("Brazil Men's National Team") == "Brazil"
    assert reader.take_the_suffix_off("  Japan  ") == "Japan"


def test_a_team_name_that_holds_the_word_national_elsewhere_is_kept():
    reader = WorldCupTeamNameReader()

    assert reader.take_the_suffix_off("National Team of Nowhere") == (
        "National Team of Nowhere"
    )
