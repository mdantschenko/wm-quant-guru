"""All shared helper classes of the whole project live in this file.

Anything more than one class needs belongs here, never copied into a second
place. Together with constant.py and data_class.py these are the three files
that hold many small classes on purpose.

The classes are sorted so that a class only ever uses one above it:
   1. PreparedTableFile        one table the preprocessing step wrote, on disk
   2. PreparedWyscoutTables    the two tables prepared out of the Wyscout files
   3. PreparedStatsBombTables  the four tables prepared out of the StatsBomb data
   4. ExactNumberReader        read written numbers without losing the last bit
   5. DecimalRounder           cut a column of numbers down to a few digits
   6. TextNormalizer           compare two spellings of the same name
   7. DateNormalizer           one date format out of the many sources use
   8. ConfederationLookup      which confederation a national team is in
   9. ApiKeyReader             get a key without putting it into the code
  10. GeographyCalculator      distance and time zone between two places
  11. CsvFile                  read and write a CSV file, resumable
  12. SharedFeatureFile        one file that both event sources write into
  13. MatchDisciplineCounter   fouls and cards, counted the same way by both
  14. MatchStyleCalculator     the actions of a match to two style rows
  15. PassingLaneCounter       the passes between two players of a team
  16. PassingNetworkCalculator the passing network of a team, summarised
  17. PlayerMatchMetricCalculator what one player did in one match
  18. ExpectedThreatGrid       what a place on the pitch is worth
  19. ExpectedThreatGridFile   that grid on disk, for both sources
  20. PreMatchRollingAverage   the form of a team before its next match
  21. ZipArchiveExtractor      unpack an archive that was downloaded
  22. StadiumLocator           stadium name to city and coordinates
  23. WebFileDownloader        fetch a file over HTTP
  24. WikipediaPageReader      read the raw wikitext of a page
  25. WyscoutDataReader        the lookup tables of the Wyscout dataset
  26. StatsBombOpenDataReader  competitions, matches and events of StatsBomb
  27. WorldCupTeamNameReader   the 48 team names of the 2026 World Cup
"""

import ast
import contextlib
import csv
import http.client
import io
import json
import math
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wmguru.helpers.constant import (
    ConfederationCalibration,
    CsvFileSetting,
    EventSourceSetting,
    ExpectedThreatFeature,
    GeographySetting,
    KaggleSetting,
    MatchDisciplineFeature,
    MatchStyleFeature,
    MatchWeatherSource,
    PassingLaneFeature,
    PassingNetworkFeature,
    PitchGeometry,
    PlayerMatchMetricFeature,
    PreparedTablePath,
    PressResistanceFeature,
    StatsBombOpenDataSource,
    StatsBombPreparedTable,
    SubstitutionFeature,
    TimeStampFormat,
    WebRequestSetting,
    WikipediaSource,
    WorldCupTeamListSource,
    WyscoutEventFile,
)
from wmguru.helpers.data_class import (
    MatchAction,
    StatsBombCompetition,
    WyscoutMatchFacts,
    WyscoutNameLookups,
)


class PreparedTableFile:
    """One table that the preprocessing step prepared once, on disk.

    A builder reads a table that is already in the shape it groups over,
    instead of parsing the raw source again. Parquet keeps the column types,
    so a coordinate comes back as the very number that was written.
    """

    def __init__(self, target_file: Path, prepare_command: str) -> None:
        """Keep the file and the command that writes it, named in the message.

        Args:
            target_file: Where the prepared table lies.
            prepare_command: What a caller has to run when the table is
                missing. Each source has its own, so the message cannot send
                somebody to the wrong one.
        """
        self._target_file = target_file
        self._prepare_command = prepare_command

    @property
    def path(self) -> Path:
        """Where the file lies, for the message at the end of a run."""
        return self._target_file

    def read(self) -> pd.DataFrame:
        """Read the prepared table back.

        Raises:
            SystemExit: When the table has not been prepared yet. Guessing
                would mean silently working on nothing at all.
        """
        if not self._target_file.exists():
            raise SystemExit(
                f"{self._target_file} is missing. Prepare it first:\n"
                f"    {self._prepare_command}"
            )
        return pd.read_parquet(self._target_file)

    def write(self, table: pd.DataFrame) -> None:
        """Write the prepared table, so every builder can read it."""
        self._target_file.parent.mkdir(parents=True, exist_ok=True)
        table.to_parquet(self._target_file, index=False)


class PreparedWyscoutTables:
    """The two tables the Wyscout preprocessing step left behind.

    A builder asks this for the table it groups over instead of naming a path
    and the command that writes it, which every one of them would otherwise
    have to repeat.
    """

    def read_the_actions(self) -> pd.DataFrame:
        """Read every action of every match, in the order they were played."""
        return self._table(PreparedTablePath.WYSCOUT_ACTION_FILE).read()

    def read_the_match_identities(self) -> pd.DataFrame:
        """Read one row per match, with the competition and both teams named."""
        return self._table(PreparedTablePath.WYSCOUT_MATCH_IDENTITY_FILE).read()

    def read_the_actions_with_the_next_player(self) -> pd.DataFrame:
        """Read the actions, each carrying who played the action after it.

        Wyscout names nobody as the receiver of a pass, so whoever plays the
        following action is taken to have had the ball. In a table that next
        action is the row below, inside the same match.

        Returns:
            The action table with the team and the player of the next action
            added, both empty for the last action of a match.
        """
        actions = self.read_the_actions()
        of_the_next_action = actions.groupby("game_identifier", sort=False)[
            ["team_name", "player_name"]
        ].shift(-1)
        return actions.assign(
            team_of_the_next_action=of_the_next_action["team_name"].fillna(""),
            player_of_the_next_action=of_the_next_action["player_name"].fillna(""),
        )

    def _table(self, target_file: Path) -> PreparedTableFile:
        """Name the file together with the command that writes it."""
        return PreparedTableFile(target_file, PreparedTablePath.WYSCOUT_PREPARE_COMMAND)


class PreparedStatsBombTables:
    """The four tables the StatsBomb preprocessing step left behind.

    The events are fetched over the network one match at a time, so preparing
    them costs the better part of an hour. Every builder reads these instead,
    and none of them touches the network at all.

    A few readings of those tables are wanted by more than one builder, so
    they stand here rather than in each of them: which team a match names as
    home, and which events were a foul or carried a card.
    """

    def read_the_actions(self) -> pd.DataFrame:
        """Read the actions, in the fifteen columns the Wyscout table has too."""
        return self._table(PreparedTablePath.STATSBOMB_ACTION_FILE).read()

    def read_the_events(self) -> pd.DataFrame:
        """Read one row per event, with what the action shape throws away."""
        return self._table(PreparedTablePath.STATSBOMB_EVENT_FILE).read()

    def read_the_match_identities(self) -> pd.DataFrame:
        """Read one row per match, the referee named alongside both teams."""
        return self._table(PreparedTablePath.STATSBOMB_MATCH_IDENTITY_FILE).read()

    def read_the_starting_line_ups(self) -> pd.DataFrame:
        """Read one row per player who started, with the position they held."""
        return self._table(PreparedTablePath.STATSBOMB_LINE_UP_FILE).read()

    def read_the_sides_of_every_match(self) -> pd.DataFrame:
        """Read the matches, with the two sides named the way an event names a team.

        Returns:
            The identity table with a home and an away team identifier added.
            StatsBomb names a team rather than numbering it, so that name is
            what a team is identified by.
        """
        identities = self.read_the_match_identities()
        return identities.assign(
            home_team_identifier=identities["home_team_name"],
            away_team_identifier=identities["away_team_name"],
        )

    def read_every_card_and_foul(self) -> pd.DataFrame:
        """Read the events that were a foul or carried a card, marked up.

        Returns:
            One row per such event, with a one or a zero under each counted
            name and the player named beside their identifier. An event that
            names no player is kept: a card of a whole bench belongs to no
            player but still counts towards the team.
        """
        events = self.read_the_events()
        is_a_foul = (
            events["event_name"] == StatsBombOpenDataSource.FOUL_EVENT_NAME
        ).astype(int)
        cards = pd.DataFrame(
            {
                card_name: (events["card_name"] == card_name).astype(int)
                for card_name in MatchDisciplineFeature.CARD_NAMES
            }
        )
        marked = pd.DataFrame(
            {
                "game_identifier": events["game_identifier"],
                "team_identifier": events["team_name"],
                "player_identifier": events["player_identifier"],
                "player_name": events["player_name"],
                EventSourceSetting.FOUL_NAME: is_a_foul,
                **cards,
            }
        )
        counts_towards_anything = is_a_foul.astype(bool) | cards.any(axis="columns")
        return marked[counts_towards_anything]

    def name_every_counted_player(
        self, per_player: pd.DataFrame, marked_events: pd.DataFrame, sides: pd.DataFrame
    ) -> pd.DataFrame:
        """Put the match around every counted player, and their name beside it.

        Args:
            per_player: One row per player of a match, keyed by game, player
                and team identifier, with whatever was counted alongside.
            marked_events: The rows the counts came out of, which still carry
                the name every player identifier belongs to.
            sides: The matches, with both sides named.

        Returns:
            The counts with the columns of their match beside them and a
            team_name, opponent_name and player_name added.
        """
        with_the_name = per_player.merge(
            marked_events[["player_identifier", "player_name"]].drop_duplicates(
                "player_identifier"
            ),
            on="player_identifier",
            how="left",
        )
        of_named_matches = with_the_name.merge(sides, on="game_identifier")
        plays_at_home = (
            of_named_matches["team_identifier"]
            == of_named_matches["home_team_identifier"]
        )
        return of_named_matches.assign(
            team_name=of_named_matches["team_identifier"],
            opponent_name=of_named_matches["away_team_name"].where(
                plays_at_home, of_named_matches["home_team_name"]
            ),
        )

    def _table(self, target_file: Path) -> PreparedTableFile:
        """Name the file together with the command that writes it."""
        return PreparedTableFile(
            target_file, PreparedTablePath.STATSBOMB_PREPARE_COMMAND
        )


class ExactNumberReader:
    """Reading a column of written numbers without losing the last bit.

    The pandas routine to_numeric parses a float with a fast method that can
    land one bit away from what Python's own float reads out of the very same
    text. The event sources write a coordinate with seventeen digits, so that
    bit is really in the file, and a value that sits one bit off can fall on
    the other side of a rounding boundary further down. Converting the text
    straight into a float type reads it the way Python does.
    """

    def read_every_number(self, written_numbers: pd.Series) -> pd.Series:
        """Read a whole column, leaving a cell that is no number empty."""
        is_a_number = pd.to_numeric(written_numbers, errors="coerce").notna()
        return written_numbers.where(is_a_number).astype(float)


class DecimalRounder:
    """Cutting a column of numbers down to a fixed number of digits.

    NumPy rounds by scaling a value up, rounding it and scaling it back
    down, and that detour turns 1.1535 into 1.154 although the stored
    number sits just below the halfway point. Writing the value out with
    the wanted digits rounds on the stored number itself, which is what
    Python's own round does, so a file built from a table carries the same
    digits as one built row by row.
    """

    def __init__(self, decimal_places: int) -> None:
        self._write_out_the_digits = f"%.{decimal_places}f"

    def round_every_value(self, values: pd.Series) -> pd.Series:
        """Cut a whole column down to the digits this rounder was built with."""
        rounded = np.char.mod(
            self._write_out_the_digits, values.to_numpy(dtype=float)
        ).astype(float)
        return pd.Series(rounded, index=values.index)

    def round_every_column(
        self, table: pd.DataFrame, column_names: list[str]
    ) -> pd.DataFrame:
        """Cut the named columns of a table down, and leave the rest alone."""
        return table.assign(
            **{name: self.round_every_value(table[name]) for name in column_names}
        )


class TextNormalizer:
    """A name in the one form it can be compared across sources in.

    The sources spell a city, a stadium or a competition differently, with and
    without accents and in different cases. Comparing the normalised form makes
    the match work.
    """

    DOTLESS_I: str = "ı"
    PLAIN_I: str = "i"
    REGION_SEPARATOR: str = ":"

    def to_comparable_text(self, text: str) -> str:
        """Fold a name to lower case and strip its accents, so Bakı becomes baki.

        The Turkish dotless i is a letter of its own and not a letter with an
        accent, so taking the accents off would leave it standing. It is
        replaced first.

        Args:
            text: A name as one source writes it.

        Returns:
            The same name in the one form every source can be compared in.
        """
        lower_case = text.lower().replace(self.DOTLESS_I, self.PLAIN_I)
        decomposed = unicodedata.normalize("NFKD", lower_case)
        return "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )

    def mean_the_same_country(self, first_country: str, second_country: str) -> bool:
        """Return True when one country name contains the other.

        Args:
            first_country: One spelling, for example Korea.
            second_country: The other, for example Korea Republic.

        Returns:
            True when either name contains the other once the accents and the
            case are gone. False when one of them is empty, because empty text
            is contained in everything and would match anything.
        """
        first = self.to_comparable_text(first_country)
        second = self.to_comparable_text(second_country)
        if not first or not second:
            return False
        return first in second or second in first

    def decode_escaped_characters(self, text: str) -> str:
        r"""Turn literal escape sequences of the source into real characters.

        The Wyscout name tables store the six characters ć instead of the
        letter ć, so every name that leaves that dataset goes through here.

        Args:
            text: The name as the source wrote it.

        Returns:
            The readable name. Text without an escape comes back untouched,
            and text that cannot be decoded comes back as it was rather than
            raising.
        """
        if WyscoutEventFile.ESCAPE_MARKER not in text:
            return text
        try:
            return text.encode("latin-1", "backslashreplace").decode("unicode_escape")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return text

    def competition_out_of_league_name(self, league_name: str) -> str:
        """Cut the region off, so Europe: Champions League becomes champions league.

        The odds sources write the region in front of the competition. Only the
        part behind the colon says which competition it is, and it has to be
        compared without accents, otherwise Copa América slips through a filter
        that looks for copa america.

        Args:
            league_name: The league field of the odds source, region and all.

        Returns:
            The competition name alone, ready to be matched against a set of
            wanted competitions. A name without a colon comes back whole.
        """
        behind_the_region = league_name.split(self.REGION_SEPARATOR, 1)[-1].strip()
        return self.to_comparable_text(behind_the_region)


class DateNormalizer:
    """The date of any source, in the one form everything is joined on.

    The odds sources write a date in three different ways, day first with
    slashes and a two or four digit year, and a month by name with a kick off
    time behind it. Nothing can be sorted or joined until they all read the
    same way.
    """

    def to_iso_date(self, value: str) -> str:
        """Rewrite a date as yyyy-mm-dd.

        Args:
            value: The date as one of the sources wrote it.

        Returns:
            The date, or an empty string when the text is no date at all. An
            empty result is better than a guess, because a wrong date joins a
            match to the wrong odds.
        """
        text = value.strip()
        if not text:
            return ""
        if self._is_already_iso(text):
            return text[: TimeStampFormat.ISO_DAY_LENGTH]
        if TimeStampFormat.SLASH in text:
            return self._read_a_slash_date(text)
        return self._read_a_named_month_date(text)

    def to_iso_date_of_every_row(self, written_dates: pd.Series) -> pd.Series:
        """Rewrite a whole column of dates as yyyy-mm-dd.

        Only the spellings that really occur are rewritten, and a date
        repeats over every match of its day, so the work is done once per
        day and not once per match.
        """
        every_spelling = pd.Series(written_dates.unique())
        return written_dates.map(
            pd.Series(
                every_spelling.map(self.to_iso_date).to_numpy(), index=every_spelling
            )
        )

    def _is_already_iso(self, text: str) -> bool:
        """Return True when the text already starts with yyyy-mm-dd."""
        return (
            len(text) >= TimeStampFormat.ISO_DAY_LENGTH
            and text[4] == TimeStampFormat.DASH
            and text[7] == TimeStampFormat.DASH
        )

    def _read_a_slash_date(self, text: str) -> str:
        """Read a date written day first with slashes."""
        parts = text.split(TimeStampFormat.SLASH)
        if len(parts) != 3:
            return ""
        try:
            day, month, year = (int(part) for part in parts)
        except ValueError:
            return ""
        return self._written_as_an_iso_date(self._four_digit_year_of(year), month, day)

    def _read_a_named_month_date(self, text: str) -> str:
        """Read a date whose month is spelled out, with a time behind it."""
        tokens = text.replace(TimeStampFormat.DASH, " ").split()
        if len(tokens) < 3:
            return ""
        month = TimeStampFormat.MONTH_OF_ABBREVIATION.get(tokens[0][:3].lower())
        if month is None:
            return ""
        try:
            return self._written_as_an_iso_date(int(tokens[2]), month, int(tokens[1]))
        except ValueError:
            return ""

    def _four_digit_year_of(self, year: int) -> int:
        """Turn a two digit year into a full one.

        The odds files reach back to 1993, so a year of 90 or more belongs to
        the last century and anything below it to this one.
        """
        if year >= 100:
            return year
        if year >= TimeStampFormat.LAST_CENTURY_FROM:
            return 1900 + year
        return 2000 + year

    def _written_as_an_iso_date(self, year: int, month: int, day: int) -> str:
        """Build the date, or an empty string when the three make no day."""
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return ""


class ConfederationLookup:
    """Which confederation a national team belongs to.

    The results file spells a country in more than one way, and a team that
    no longer exists still has matches in it. Both are looked up through the
    normaliser, so Cote d'Ivoire and Ivory Coast find the same entry.
    """

    def __init__(self, text_normalizer: TextNormalizer) -> None:
        """Build the lookup once, over every spelling of every member."""
        self._text_normalizer = text_normalizer
        self._confederation_of_name = {
            self._text_normalizer.to_comparable_text(member): confederation
            for confederation, members in (
                ConfederationCalibration.MEMBERS_OF_CONFEDERATION.items()
            )
            for member in members
        }

    def confederation_of(self, team_name: str) -> str | None:
        """Name the confederation of one team.

        Returns:
            The confederation, or None for a team the table does not know.
            A caller must decide what to do with those rather than guess.
        """
        return self._confederation_of_name.get(
            self._text_normalizer.to_comparable_text(team_name)
        )

    def confederation_of_every_team(self, team_names: pd.Series) -> pd.Series:
        """Name the confederation behind a whole column of team names.

        Only the spellings that really occur are looked up, so the work is
        done once per name and not once per match.

        Returns:
            The confederation per row, and nothing where the table does not
            know the team.
        """
        every_spelling = pd.Series(team_names.unique())
        return team_names.map(
            pd.Series(
                every_spelling.map(self.confederation_of).to_numpy(),
                index=every_spelling,
            )
        )


class ApiKeyReader:
    """An API key, out of an environment variable or out of a file.

    A key belongs in an environment variable or in a file that git ignores,
    never in a source file and never in a commit.
    """

    def read_key(
        self, environment_variable_name: str, key_file: Path | None = None
    ) -> str | None:
        """Read the key, looking at the environment first and the file second.

        Args:
            environment_variable_name: The variable the key is expected in.
            key_file: A file holding nothing but the key. Left out when the
                source offers no file route.

        Returns:
            The key with the whitespace stripped, or None when neither the
            variable nor the file holds one.
        """
        key_from_environment = os.environ.get(environment_variable_name, "").strip()
        if key_from_environment:
            return key_from_environment
        if key_file is not None and key_file.exists():
            key_from_file = key_file.read_text(encoding=CsvFileSetting.ENCODING).strip()
            if key_from_file:
                return key_from_file
        return None

    def explain_how_to_set_the_key(
        self, environment_variable_name: str, sign_up_url: str
    ) -> str:
        """Build the message a caller shows when the key is missing.

        Args:
            environment_variable_name: The variable the reader looked in.
            sign_up_url: Where a free key can be had.

        Returns:
            A ready to print text with the command for PowerShell and bash.
        """
        return (
            f"No API key found. Sign up for free at {sign_up_url} and set it:\n"
            f'  $env:{environment_variable_name} = "<your-key>"   (PowerShell)\n'
            f'  export {environment_variable_name}="<your-key>"   (bash)'
        )


class GeographyCalculator:
    """Distance and time zone between two places on the globe.

    Two calculations need this: the travel load of the historical tournaments
    and the travel load of the 2026 group stage.
    """

    def distance_in_kilometres(
        self,
        first_latitude: float,
        first_longitude: float,
        second_latitude: float,
        second_longitude: float,
    ) -> float:
        """Measure the great circle distance, the way a plane really flies.

        Args:
            first_latitude: Latitude of the starting place, in degrees.
            first_longitude: Longitude of the starting place, in degrees.
            second_latitude: Latitude of the target place, in degrees.
            second_longitude: Longitude of the target place, in degrees.

        Returns:
            The distance in kilometres, not rounded.
        """
        first_latitude_in_radians = math.radians(first_latitude)
        second_latitude_in_radians = math.radians(second_latitude)
        latitude_difference = math.radians(second_latitude - first_latitude)
        longitude_difference = math.radians(second_longitude - first_longitude)
        half_chord = (
            math.sin(latitude_difference / 2) ** 2
            + math.cos(first_latitude_in_radians)
            * math.cos(second_latitude_in_radians)
            * math.sin(longitude_difference / 2) ** 2
        )
        return (
            2
            * GeographySetting.EARTH_RADIUS_IN_KILOMETRES
            * math.asin(math.sqrt(half_chord))
        )

    def time_zone_of(self, longitude: float) -> int:
        """Work out a stand in for the time zone, one hour per fifteen degrees.

        This is good enough as a proxy for the body clock and needs no time
        zone database, which no source of this project carries anyway.

        Args:
            longitude: Longitude of the place, in degrees.

        Returns:
            The offset in whole hours, negative west of Greenwich.
        """
        return round(longitude / GeographySetting.DEGREES_PER_TIME_ZONE)

    def time_zone_shift(self, first_longitude: float, second_longitude: float) -> int:
        """Count the hours the body clock has to move between two places.

        Args:
            first_longitude: Longitude of the place travelled from.
            second_longitude: Longitude of the place travelled to.

        Returns:
            The number of hours, always positive, whichever way the trip went.
        """
        return abs(
            self.time_zone_of(second_longitude) - self.time_zone_of(first_longitude)
        )

    def distance_of_every_leg(
        self,
        first_latitude: pd.Series,
        first_longitude: pd.Series,
        second_latitude: pd.Series,
        second_longitude: pd.Series,
    ) -> pd.Series:
        """Measure a whole column of trips at once, in kilometres.

        Returns:
            The great circle distance per row, not rounded, and nothing at
            all where one of the two places is missing.
        """
        first_latitude_in_radians = np.radians(first_latitude)
        second_latitude_in_radians = np.radians(second_latitude)
        latitude_difference = np.radians(second_latitude - first_latitude)
        longitude_difference = np.radians(second_longitude - first_longitude)
        half_chord = (
            np.sin(latitude_difference / 2) ** 2
            + np.cos(first_latitude_in_radians)
            * np.cos(second_latitude_in_radians)
            * np.sin(longitude_difference / 2) ** 2
        )
        return (
            2
            * GeographySetting.EARTH_RADIUS_IN_KILOMETRES
            * np.arcsin(np.sqrt(half_chord))
        )

    def time_zone_shift_of_every_leg(
        self, first_longitude: pd.Series, second_longitude: pd.Series
    ) -> pd.Series:
        """Count the hours the body clock has to move, for a whole column."""
        return (
            self._time_zone_of_every_place(second_longitude)
            - self._time_zone_of_every_place(first_longitude)
        ).abs()

    def _time_zone_of_every_place(self, longitude: pd.Series) -> pd.Series:
        """Put a whole column of places into their time zone."""
        return np.round(longitude / GeographySetting.DEGREES_PER_TIME_ZONE)


class CsvFile:
    """One CSV file of the project, with its column names.

    Every writer of the project goes through this class, so the encoding, the
    line ending and the header line are handled in one place. A file that is
    written by appending can be picked up again after a stopped run: the header
    is only written when the file is new, and the keys that are already in the
    file can be read back so they are not asked for a second time.

    Attributes:
        path: Where the file lies, for the message at the end of a run.
    """

    def __init__(self, target_file: Path, column_names: tuple[str, ...] = ()) -> None:
        self._target_file = target_file
        self._column_names = column_names

    @property
    def path(self) -> Path:
        """Where the file lies, for the message at the end of a run."""
        return self._target_file

    def read_table(self) -> pd.DataFrame:
        """Read the whole file as a table of text.

        Every cell comes back as it stands in the file, so nothing is guessed
        away: the sources write NA where a value is still missing, which
        pandas would otherwise read as a missing value and a caller would
        then take for a real one. Convert a column on purpose afterwards.

        Returns:
            The table, or an empty one with the column names this file was
            built with when the file does not exist yet.
        """
        if not self._target_file.exists():
            return pd.DataFrame(columns=list(self._column_names), dtype=str)
        try:
            return pd.read_csv(self._target_file, **self._reading_settings())
        except pd.errors.ParserError:
            return self._read_the_file_with_ragged_rows()

    def _reading_settings(self) -> dict[str, Any]:
        """How every read of this project has to be set up."""
        return {
            "dtype": str,
            "keep_default_na": False,
            "encoding": CsvFileSetting.ENCODING,
            "encoding_errors": CsvFileSetting.IGNORE_BROKEN_CHARACTERS,
        }

    def _read_the_file_with_ragged_rows(self) -> pd.DataFrame:
        """Read a file whose rows carry more fields than its header names.

        Some of the football-data files have a stray extra field in a row,
        which stops a reader that expects every row to be as wide as the
        header. Reading with a fixed number of nameless columns keeps such a
        row instead of dropping it, and the fields behind the last header
        name are then cut off again.
        """
        widened = pd.read_csv(
            self._target_file,
            header=None,
            names=range(CsvFileSetting.WIDEST_ROW_TO_EXPECT),
            **self._reading_settings(),
        )
        header_names = widened.iloc[0].dropna().reset_index(drop=True)
        return (
            widened.iloc[1:, : len(header_names)]
            .set_axis(self._numbered_where_a_name_repeats(header_names), axis="columns")
            .fillna("")
            .reset_index(drop=True)
        )

    def _numbered_where_a_name_repeats(self, header_names: pd.Series) -> pd.Series:
        """Number the header names that turn up more than once.

        A file that names two columns the same way, or leaves both of them
        unnamed, would otherwise give a table nothing can be joined onto.
        The second one becomes name.1, which is what pandas calls it when it
        reads the header itself.
        """
        seen_before = header_names.groupby(header_names).cumcount()
        return header_names.where(
            seen_before == 0, header_names + "." + seen_before.astype(str)
        )

    def write_table(self, table: pd.DataFrame) -> None:
        """Write a whole table, in the column order this file was built with.

        Args:
            table: What to write. A column the file does not know is left
                out, a column it knows but the table lacks is written empty,
                so the file always has the same shape.
        """
        self._target_file.parent.mkdir(parents=True, exist_ok=True)
        wanted = list(self._column_names) if self._column_names else list(table.columns)
        table.reindex(columns=wanted).to_csv(
            self._target_file,
            index=False,
            encoding=CsvFileSetting.ENCODING,
            lineterminator=CsvFileSetting.LINE_TERMINATOR,
        )

    def read_rows(self) -> list[dict[str, str]]:
        """Read the whole file, one dictionary per row.

        Returns:
            One entry per data row, keyed by the header line of the file. An
            empty list when the file does not exist yet, so a first run does
            not have to check for it.
        """
        if not self._target_file.exists():
            return []
        with self._target_file.open(
            encoding=CsvFileSetting.ENCODING,
            newline=CsvFileSetting.NEW_LINE,
            errors=CsvFileSetting.IGNORE_BROKEN_CHARACTERS,
        ) as file_handle:
            return list(csv.DictReader(file_handle))

    def read_finished_values(self, column_name: str) -> set[str]:
        """Read the values of one column that are already in the file.

        Args:
            column_name: The column that identifies a finished piece of work,
                for example the team of a series that was already fetched.

        Returns:
            Every value the column holds, so a caller can skip that work.
        """
        return {row[column_name] for row in self.read_rows()}

    def read_finished_value_pairs(
        self, first_column_name: str, second_column_name: str
    ) -> set[tuple[str, str]]:
        """Read the value pairs of two columns that are already in the file.

        Args:
            first_column_name: First half of the key, for example the city.
            second_column_name: Second half of the key, for example the country.

        Returns:
            Every pair the file holds, for work that only one column cannot
            identify.
        """
        return {
            (row[first_column_name], row[second_column_name])
            for row in self.read_rows()
        }

    def write_rows(self, rows: list[list[Any]]) -> None:
        """Write a fresh file with its header and these rows.

        Anything the file held before is gone. The folder is created when it
        is missing.

        Args:
            rows: One list per row, in the order of the column names.
        """
        with self.writing_writer() as writer:
            writer.writerows(rows)

    def write_dict_rows(self, rows: list[dict[str, Any]]) -> None:
        """Write a fresh file from rows that name their columns themselves.

        This is the counterpart of read_rows. Use it where building a row as a
        dictionary reads better than counting positions in a list.

        Args:
            rows: One dictionary per row, keyed by the column names this file
                was built with. A key the file does not know raises.

        Raises:
            ValueError: When a row holds a key that is not a column of this
                file.
        """
        self._target_file.parent.mkdir(parents=True, exist_ok=True)
        with self._target_file.open(
            CsvFileSetting.WRITE_MODE,
            encoding=CsvFileSetting.ENCODING,
            newline=CsvFileSetting.NEW_LINE,
        ) as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=self._column_names)
            writer.writeheader()
            writer.writerows(rows)

    def append_rows(self, rows: list[list[Any]]) -> None:
        """Add rows to the end of the file, keeping what is already in it.

        Args:
            rows: One list per row, in the order of the column names.
        """
        with self.appending_writer() as writer:
            writer.writerows(rows)

    @contextlib.contextmanager
    def writing_writer(self) -> Iterator[Any]:
        """Open a fresh file, with the header line already written.

        Use this when the whole file is built in one run.

        Yields:
            A csv writer. Anything the file held before is gone the moment
            this is entered.
        """
        with self._open_the_csv_file(CsvFileSetting.WRITE_MODE) as writer:
            yield writer

    @contextlib.contextmanager
    def appending_writer(self) -> Iterator[Any]:
        """Open the file for appending, with the header line if it is new.

        Use this when the rows come in one at a time and every finished row
        should survive a crash of the run.

        Yields:
            A csv writer positioned at the end of the file.
        """
        file_is_new = not self._target_file.exists()
        with self._open_the_csv_file(
            CsvFileSetting.APPEND_MODE, write_header=file_is_new
        ) as writer:
            yield writer

    @contextlib.contextmanager
    def _open_the_csv_file(self, mode: str, write_header: bool = True) -> Iterator[Any]:
        """Open the file the one way the whole project opens a CSV file.

        Args:
            mode: The file mode, write or append.
            write_header: Whether the column names go in first. False for an
                append onto a file that already carries them.

        Yields:
            A csv writer, with the header already written when asked for.
        """
        self._target_file.parent.mkdir(parents=True, exist_ok=True)
        with self._target_file.open(
            mode,
            encoding=CsvFileSetting.ENCODING,
            newline=CsvFileSetting.NEW_LINE,
        ) as file_handle:
            writer = csv.writer(file_handle)
            if write_header and self._column_names:
                writer.writerow(self._column_names)
            yield writer


class SharedFeatureFile:
    """One output file that both event sources write into.

    Nine features exist twice, once out of the Wyscout files and once out of
    the StatsBomb data, and a model wants one table rather than two. A row
    therefore carries a source column, and a run of one source has to leave
    the rows of the other alone.

    Hold one of these per output file. A feature that writes two files, such
    as the discipline one, holds two.
    """

    def __init__(
        self,
        csv_file: CsvFile,
        source_name: str,
        sort_key_names: tuple[str, ...],
    ) -> None:
        self._csv_file = csv_file
        self._source_name = source_name
        self._sort_key_names = sort_key_names

    @property
    def path(self) -> Path:
        """Where the file lies, for the message at the end of a run."""
        return self._csv_file.path

    def read_own_table(self) -> pd.DataFrame:
        """Read back what this source wrote before, as a table."""
        every_row = self._csv_file.read_table()
        if EventSourceSetting.SOURCE_COLUMN not in every_row.columns:
            return every_row.iloc[0:0]
        return every_row[
            every_row[EventSourceSetting.SOURCE_COLUMN] == self._source_name
        ]

    def read_finished_keys(self) -> set[tuple[str, str]]:
        """Read which competition and season this source already covered.

        Returns:
            One competition and season pair per finished season, so a stopped
            run knows what to skip. Only rows of this source count; what the
            other half did is none of its business, otherwise it would skip a
            season it never touched.
        """
        own_rows = self.read_own_table()
        return set(
            zip(
                own_rows[EventSourceSetting.COMPETITION_COLUMN],
                own_rows[EventSourceSetting.SEASON_COLUMN],
                strict=True,
            )
        )

    def read_the_table_of_the_other_source(self) -> pd.DataFrame:
        """Read what the other source wrote, as a table."""
        every_row = self._csv_file.read_table()
        if EventSourceSetting.SOURCE_COLUMN not in every_row.columns:
            return every_row
        return every_row[
            every_row[EventSourceSetting.SOURCE_COLUMN] != self._source_name
        ]

    def write_the_table_keeping_the_other_source(self, own_rows: pd.DataFrame) -> int:
        """Write this source's table without dropping the other source's.

        Args:
            own_rows: Everything this source produced. It replaces whatever
                this source wrote before, and nothing else.

        Returns:
            How many rows the file holds afterwards, both sources counted.
        """
        both_sources = pd.concat(
            [own_rows, self.read_the_table_of_the_other_source()], ignore_index=True
        )
        self._csv_file.write_table(self._sorted_the_way_a_table_is(both_sources))
        return len(both_sources)

    def _sorted_the_way_a_table_is(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Sort a table the one way this file is always sorted.

        The keys are compared as text, the way they are when the rows are
        sorted one dictionary at a time, so both writers agree on the order.
        """
        as_text = pd.DataFrame(
            {name: rows[name].astype(str) for name in self._sort_key_names},
            index=rows.index,
        )
        return rows.loc[
            as_text.sort_values(list(self._sort_key_names), kind="stable").index
        ]


class MatchDisciplineCounter:
    """Fouls and cards, counted per player and folded into one match row.

    Both event sources end up with the same numbers, so both count into the
    same shape and both add the two sides up the same way. Only where the
    fouls and cards are read differs, and that is each source's own business.

    A marked table is what both sources hand over: one row per event that was
    a foul or carried a card, with a one or a zero under each counted name,
    keyed by game, team and player.
    """

    PLAYER_KEYS = ["game_identifier", "player_identifier", "team_identifier"]
    TEAM_KEYS = ["game_identifier", "team_identifier"]

    def count_every_player(self, marked_events: pd.DataFrame) -> pd.DataFrame:
        """Add the fouls and cards of every player of every match up.

        Returns:
            One row per player who fouled or was carded, in the order they
            first appear in the events. An event the source names no player
            for counts towards no player at all.
        """
        of_a_named_player = marked_events[marked_events["player_identifier"] != ""]
        return self._added_up_over(of_a_named_player, self.PLAYER_KEYS)

    def count_every_team(self, per_player: pd.DataFrame) -> pd.DataFrame:
        """Add the players of a team up, so a match has two rows left."""
        return self._added_up_over(per_player, self.TEAM_KEYS)

    def _added_up_over(self, counts: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
        """Add every counted name up over the given keys, in first seen order."""
        return (
            counts.groupby(keys, sort=False)[list(MatchDisciplineFeature.COUNTED_NAMES)]
            .sum()
            .reset_index()
        )

    def summarise_both_sides(
        self, per_team: pd.DataFrame, sides: pd.DataFrame
    ) -> pd.DataFrame:
        """Fold the two teams of every match into the columns of one match row.

        Args:
            per_team: What every team of every match collected, one row each.
            sides: One row per match, naming the team identifier of the home
                and of the away side. Every one of its rows gets a row back,
                a match in which nobody was carded included.

        Returns:
            The fouls and cards of both sides, indexed the way sides was. A
            red counts a second yellow as well, because both end with a player
            leaving the pitch.
        """
        of_the_home_team = self._counted_for_one_side(
            sides, per_team, "home_team_identifier"
        )
        of_the_away_team = self._counted_for_one_side(
            sides, per_team, "away_team_identifier"
        )
        cards = list(MatchDisciplineFeature.CARD_NAMES)
        return pd.DataFrame(
            {
                "home_fouls": of_the_home_team[EventSourceSetting.FOUL_NAME],
                "away_fouls": of_the_away_team[EventSourceSetting.FOUL_NAME],
                "home_yellow": of_the_home_team[EventSourceSetting.YELLOW_NAME],
                "home_red": self._sendings_off_of(of_the_home_team),
                "away_yellow": of_the_away_team[EventSourceSetting.YELLOW_NAME],
                "away_red": self._sendings_off_of(of_the_away_team),
                "total_cards": of_the_home_team[cards].sum(axis="columns")
                + of_the_away_team[cards].sum(axis="columns"),
            }
        )

    def _counted_for_one_side(
        self, sides: pd.DataFrame, per_team: pd.DataFrame, side_column: str
    ) -> pd.DataFrame:
        """Look one side of every match up, with a zero where it collected none."""
        looked_up = sides.merge(
            per_team,
            left_on=["game_identifier", side_column],
            right_on=self.TEAM_KEYS,
            how="left",
        )
        counted = list(MatchDisciplineFeature.COUNTED_NAMES)
        return looked_up[counted].fillna(0).astype(int).set_axis(sides.index)

    def _sendings_off_of(self, of_one_side: pd.DataFrame) -> pd.Series:
        """Count how many players of one side had to leave the pitch."""
        return (
            of_one_side[EventSourceSetting.RED_NAME]
            + of_one_side[EventSourceSetting.SECOND_YELLOW_NAME]
        )


class MatchStyleCalculator:
    """The actions of every match, as two rows per match, one per team.

    Both event sources are read into the same action table first, so the whole
    calculation stands here once. A number that needs the other side, such as
    the share of the passes, comes out of a join of the counts onto themselves
    with the two teams swapped.
    """

    MATCH_KEYS = ["game_identifier", "team_name"]
    SCORE_LINE_COLUMNS = [
        "passes_while_leading",
        "passes_while_level",
        "passes_while_trailing",
    ]

    def summarise_every_match(
        self,
        actions: pd.DataFrame,
        identities: pd.DataFrame,
        source_name: str,
        has_expected_goals: bool,
    ) -> pd.DataFrame:
        """Build the row of each team of every match.

        Args:
            actions: Every action of every match, both teams together, in the
                order they were played.
            identities: One row per match, with both teams already named.
            source_name: Which of the two event sources the actions came out
                of, written into the source column.
            has_expected_goals: False for a source that carries none, which
                leaves those columns empty rather than writing a zero.

        Returns:
            Two rows per match, or one where a team played no pass at all,
            which means its half of the match never arrived.
        """
        of_the_two_teams = self._only_the_actions_of_the_two_named_teams(
            actions, identities
        )
        counts = self._count_every_team(of_the_two_teams)
        return self._build_the_rows(counts, identities, source_name, has_expected_goals)

    def _only_the_actions_of_the_two_named_teams(
        self, actions: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Join the two team names onto every action and drop anybody else."""
        named = actions.merge(identities, on="game_identifier", how="inner")
        plays_in_this_match = (named["team_name"] == named["home_team_name"]) | (
            named["team_name"] == named["away_team_name"]
        )
        return named[plays_in_this_match]

    def _count_every_team(self, actions: pd.DataFrame) -> pd.DataFrame:
        """Add every action of every team up, and its passes per score line."""
        marked = self._marked_up(actions)
        counts = marked.groupby(self.MATCH_KEYS, sort=False).agg(
            passes_any=("is_a_pass", "sum"),
            passes_open_play=("is_an_open_play_pass", "sum"),
            passes_set_piece=("is_a_set_piece_pass", "sum"),
            crosses=("is_a_cross", "sum"),
            into_box=("went_into_the_box", "sum"),
            forward_metres=("forward_metres", "sum"),
            passes_in_own_half=("started_in_the_own_half", "sum"),
            final_third=("started_in_the_final_third", "sum"),
            defensive_actions_high=("is_a_high_defensive_action", "sum"),
            defensive_height_sum=("defensive_height_in_metres", "sum"),
            defensive_action_count=("is_a_defensive_line_action", "sum"),
            take_ons=("is_a_take_on", "sum"),
            take_ons_won=("is_a_won_take_on", "sum"),
            shots=("is_a_shot", "sum"),
            shots_in_box=("is_a_shot_from_the_box", "sum"),
            expected_goals=("shot_expected_goals", "sum"),
            non_penalty_expected_goals=("non_penalty_expected_goals", "sum"),
            set_piece_expected_goals=("set_piece_expected_goals", "sum"),
        )
        return counts.join(self._count_the_passes_per_score_line(marked)).reset_index()

    def _marked_up(self, actions: pd.DataFrame) -> pd.DataFrame:
        """Say of every single action what it counts towards.

        Every column here answers one question about one action, so all the
        counting afterwards is a sum over each of them.
        """
        kind = actions["kind"]
        start_x = actions["start_x_in_metres"]
        end_x = actions["end_x_in_metres"]
        is_an_open_play_pass = kind.isin(MatchStyleFeature.OPEN_PLAY_PASS_KINDS)
        is_on_the_defensive_line = kind.isin(MatchStyleFeature.DEFENSIVE_LINE_KINDS)
        is_a_take_on = kind == MatchStyleFeature.TAKE_ON_KIND
        is_a_shot = kind.isin(MatchStyleFeature.SHOT_KINDS)
        shot_expected_goals = actions["expected_goals"].where(is_a_shot).fillna(0.0)

        return actions.assign(
            is_a_pass=kind.isin(MatchStyleFeature.EVERY_PASS_KIND),
            is_an_open_play_pass=is_an_open_play_pass,
            is_a_set_piece_pass=kind == MatchStyleFeature.SET_PIECE_PASS_KIND,
            is_a_cross=is_an_open_play_pass & (kind == MatchStyleFeature.CROSS_KIND),
            went_into_the_box=is_an_open_play_pass
            & self._lies_in_the_box(end_x, actions["end_y_in_metres"]),
            forward_metres=(end_x - start_x).where(is_an_open_play_pass, 0.0),
            started_in_the_own_half=is_an_open_play_pass
            & (start_x <= MatchStyleFeature.PRESSING_PASS_MAXIMUM_X),
            started_in_the_final_third=is_an_open_play_pass
            & (start_x >= MatchStyleFeature.FINAL_THIRD_START_X),
            is_a_high_defensive_action=self._is_a_high_defensive_action(kind, start_x),
            is_a_defensive_line_action=is_on_the_defensive_line,
            defensive_height_in_metres=start_x.where(is_on_the_defensive_line, 0.0),
            is_a_take_on=is_a_take_on,
            is_a_won_take_on=is_a_take_on & actions["was_successful"],
            is_a_shot=is_a_shot,
            is_a_shot_from_the_box=is_a_shot
            & self._lies_in_the_box(start_x, actions["start_y_in_metres"]),
            shot_expected_goals=shot_expected_goals,
            non_penalty_expected_goals=shot_expected_goals.where(
                kind != MatchStyleFeature.PENALTY_SHOT_KIND, 0.0
            ),
            set_piece_expected_goals=shot_expected_goals.where(
                actions["was_after_a_set_piece"], 0.0
            ),
        )

    def _is_a_high_defensive_action(
        self, kind: pd.Series, start_x: pd.Series
    ) -> pd.Series:
        """Return True for a defensive action played high up the pitch.

        A pass never counts here: the walk this replaces only reached the
        pressing branch once both pass branches had missed.
        """
        return (
            ~kind.isin(MatchStyleFeature.OPEN_PLAY_PASS_KINDS)
            & (kind != MatchStyleFeature.SET_PIECE_PASS_KIND)
            & kind.isin(MatchStyleFeature.PRESSING_DEFENCE_KINDS)
            & (start_x >= MatchStyleFeature.PRESSING_DEFENCE_MINIMUM_X)
        )

    def _lies_in_the_box(
        self, x_in_metres: pd.Series, y_in_metres: pd.Series
    ) -> pd.Series:
        """Return True where a point lies inside the penalty area being attacked."""
        return (
            (x_in_metres >= MatchStyleFeature.BOX_START_X)
            & (y_in_metres >= MatchStyleFeature.BOX_MINIMUM_Y)
            & (y_in_metres <= MatchStyleFeature.BOX_MAXIMUM_Y)
        )

    def _count_the_passes_per_score_line(self, marked: pd.DataFrame) -> pd.DataFrame:
        """Count each pass under the score line that stood when it was played.

        A team that is ahead lets the other one have the ball, so the plain
        share of the passes says as much about the score as about the style.
        The running score is a cumulative sum in the order the actions were
        played, with the action itself taken off again, so a goal never
        counts towards the moment it was scored in.
        """
        in_order = marked.sort_values(
            ["game_identifier", "period_number", "second_in_period"], kind="stable"
        )
        scored_before = self._score_before_every_action(in_order)
        plays_at_home = in_order["team_name"] == in_order["home_team_name"]
        lead = np.where(
            plays_at_home,
            scored_before["home"] - scored_before["away"],
            scored_before["away"] - scored_before["home"],
        )
        with_the_score_line = in_order.assign(
            score_line=np.select(
                [lead > 0, lead == 0],
                ["passes_while_leading", "passes_while_level"],
                default="passes_while_trailing",
            )
        )
        counted = (
            with_the_score_line[with_the_score_line["is_an_open_play_pass"]]
            .groupby([*self.MATCH_KEYS, "score_line"], sort=False)
            .size()
            .unstack("score_line")
        )
        return counted.reindex(columns=self.SCORE_LINE_COLUMNS).fillna(0).astype(int)

    def _score_before_every_action(self, in_order: pd.DataFrame) -> pd.DataFrame:
        """Count the goals of both sides that had fallen before each action."""
        plays_at_home = in_order["team_name"] == in_order["home_team_name"]
        scored_for_itself = (
            in_order["scoring_team"] == MatchStyleFeature.SCORED_FOR_THE_ACTING_TEAM
        )
        scored_for_the_other = (
            in_order["scoring_team"] == MatchStyleFeature.SCORED_FOR_THE_OTHER_TEAM
        )
        goals = pd.DataFrame(
            {
                "home": (plays_at_home & scored_for_itself)
                | (~plays_at_home & scored_for_the_other),
                "away": (~plays_at_home & scored_for_itself)
                | (plays_at_home & scored_for_the_other),
            }
        ).astype(int)
        return goals.groupby(in_order["game_identifier"], sort=False).cumsum() - goals

    def _build_the_rows(
        self,
        counts: pd.DataFrame,
        identities: pd.DataFrame,
        source_name: str,
        has_expected_goals: bool,
    ) -> pd.DataFrame:
        """Put each team next to its opponent and work every column out."""
        both_sides = self._one_row_per_side(identities)
        own = both_sides.merge(counts, on=self.MATCH_KEYS, how="inner")
        against = own.merge(
            counts.rename(columns={"team_name": "opponent_name"}),
            on=["game_identifier", "opponent_name"],
            how="left",
            suffixes=("", "_of_the_opponent"),
        )
        played_at_all = against["passes_any"] > 0
        return self._every_column_of(
            against[played_at_all].reset_index(drop=True),
            source_name,
            has_expected_goals,
        )

    def _one_row_per_side(self, identities: pd.DataFrame) -> pd.DataFrame:
        """Split every match into the row of its home team and its away team."""
        as_the_home_team = identities.assign(
            team_name=identities["home_team_name"],
            opponent_name=identities["away_team_name"],
            is_home=1,
        )
        as_the_away_team = identities.assign(
            team_name=identities["away_team_name"],
            opponent_name=identities["home_team_name"],
            is_home=0,
        )
        return pd.concat([as_the_home_team, as_the_away_team]).sort_values(
            ["game_identifier", "is_home"], ascending=[True, False], kind="stable"
        )

    def _every_column_of(
        self, against: pd.DataFrame, source_name: str, has_expected_goals: bool
    ) -> pd.DataFrame:
        """Work every written column out of the two counts side by side."""
        share_places = MatchStyleFeature.SHARE_DECIMAL_PLACES
        passes_per_score_line = against[self.SCORE_LINE_COLUMNS].sum(axis="columns")
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: source_name,
                "game_id": against["game_identifier"],
                "competition": against["competition_name"],
                "season": against["season_name"],
                "date": against["match_date"],
                "team": against["team_name"],
                "opponent": against["opponent_name"],
                "is_home": against["is_home"],
                "passes": against["passes_any"],
                "pass_share": self._divided_or_left_empty(
                    against["passes_any"],
                    against["passes_any"] + against["passes_any_of_the_opponent"],
                    share_places,
                ),
                "field_tilt": self._divided_or_left_empty(
                    against["final_third"],
                    against["final_third"] + against["final_third_of_the_opponent"],
                    share_places,
                ),
                "passes_per_defensive_action": self._divided_or_left_empty(
                    against["passes_in_own_half_of_the_opponent"],
                    against["defensive_actions_high"],
                    MatchStyleFeature.PRESSING_DECIMAL_PLACES,
                ),
                "defensive_action_height_in_metres": self._divided_or_left_empty(
                    against["defensive_height_sum"],
                    against["defensive_action_count"],
                    MatchStyleFeature.HEIGHT_DECIMAL_PLACES,
                ),
                "passes_into_box": against["into_box"],
                "directness_in_metres": self._divided_or_left_empty(
                    against["forward_metres"],
                    against["passes_open_play"],
                    MatchStyleFeature.PRESSING_DECIMAL_PLACES,
                ),
                "set_piece_pass_share": self._divided_or_left_empty(
                    against["passes_set_piece"], against["passes_any"], share_places
                ),
                "take_on_success_rate": self._divided_or_left_empty(
                    against["take_ons_won"], against["take_ons"], share_places
                ),
                "crosses": against["crosses"],
                "shots": against["shots"],
                "shots_in_box": against["shots_in_box"],
                **self._expected_goals_columns(against, has_expected_goals),
                "pass_share_while_leading": self._divided_or_left_empty(
                    against["passes_while_leading"], passes_per_score_line, share_places
                ),
                "pass_share_while_level": self._divided_or_left_empty(
                    against["passes_while_level"], passes_per_score_line, share_places
                ),
                "pass_share_while_trailing": self._divided_or_left_empty(
                    against["passes_while_trailing"],
                    passes_per_score_line,
                    share_places,
                ),
            }
        )

    def _expected_goals_columns(
        self, against: pd.DataFrame, has_expected_goals: bool
    ) -> dict[str, Any]:
        """Build the seven expected goals columns, or leave them all empty.

        What a team conceded is what the other side created, so it is never
        counted twice, only carried across from the opponent.
        """
        if not has_expected_goals:
            return {
                name: ""
                for name in (
                    "expected_goals",
                    "non_penalty_expected_goals",
                    "expected_goals_per_shot",
                    "set_piece_expected_goals_share",
                    "expected_goals_against",
                    "non_penalty_expected_goals_against",
                    "expected_goals_against_per_shot",
                )
            }

        places = MatchStyleFeature.SHARE_DECIMAL_PLACES
        rounder = DecimalRounder(places)
        created = against["expected_goals"]
        conceded = against["expected_goals_of_the_opponent"]
        return {
            "expected_goals": rounder.round_every_value(created),
            "non_penalty_expected_goals": rounder.round_every_value(
                against["non_penalty_expected_goals"]
            ),
            "expected_goals_per_shot": self._divided_or_left_empty(
                created, against["shots"], places
            ),
            "set_piece_expected_goals_share": self._divided_or_left_empty(
                against["set_piece_expected_goals"], created, places
            ).replace("", 0.0),
            "expected_goals_against": rounder.round_every_value(conceded),
            "non_penalty_expected_goals_against": rounder.round_every_value(
                against["non_penalty_expected_goals_of_the_opponent"]
            ),
            "expected_goals_against_per_shot": self._divided_or_left_empty(
                conceded, against["shots_of_the_opponent"], places
            ),
        }

    def _divided_or_left_empty(
        self, numerator: pd.Series, denominator: pd.Series, places: int
    ) -> pd.Series:
        """Divide a whole column, leaving a cell empty where nothing divides.

        Returns:
            The rounded quotient per row, or an empty cell. A zero would
            claim a team pressed nobody when in truth it never had the
            chance.
        """
        can_be_divided = denominator != 0
        quotient = numerator / denominator.where(can_be_divided)
        return (
            DecimalRounder(places).round_every_value(quotient).where(can_be_divided, "")
        )


class PassingLaneCounter:
    """The passes between two players, counted and turned into rows.

    Both event sources produce the same edge of the same network, they only
    find the receiver differently, so the counting stands here once. What each
    of them hands over is a table of the completed passes of every match, with
    the passer, the receiver and where the pass ran from and to.
    """

    LANE_KEYS = ["game_identifier", "team_name", "passer_name", "receiver_name"]

    def count_every_lane(self, completed_passes: pd.DataFrame) -> pd.DataFrame:
        """Add the passes between each pair of players of a match up.

        Returns:
            One row per lane, in the order the lanes were first played, with
            the two sums the means are worked out of still in it.
        """
        went_forward = (
            completed_passes["end_x_in_metres"] - completed_passes["start_x_in_metres"]
        ) > PassingLaneFeature.FORWARD_MINIMUM_METRES
        return (
            completed_passes.assign(went_forward=went_forward)
            .groupby(self.LANE_KEYS, sort=False)
            .agg(
                passes=("went_forward", "size"),
                forward_passes=("went_forward", "sum"),
                start_x_sum=("start_x_in_metres", "sum"),
                end_x_sum=("end_x_in_metres", "sum"),
            )
            .reset_index()
        )

    def build_the_rows_of_every_lane(
        self,
        lanes: pd.DataFrame,
        identities: pd.DataFrame,
        source_name: str,
    ) -> pd.DataFrame:
        """Turn the counted lanes into one row per pair of players.

        Args:
            lanes: What every pair of players played, already counted.
            identities: One row per match, which says which competition,
                season and day a lane belongs to.
            source_name: Which of the two event sources these lanes came out
                of, written into the source column.
        """
        rounder = DecimalRounder(PassingLaneFeature.MEAN_DECIMAL_PLACES)
        of_named_matches = lanes.merge(identities, on="game_identifier")
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: source_name,
                "game_id": of_named_matches["game_identifier"],
                "competition": of_named_matches["competition_name"],
                "season": of_named_matches["season_name"],
                "date": of_named_matches["match_date"],
                "team": of_named_matches["team_name"],
                "passer": of_named_matches["passer_name"],
                "receiver": of_named_matches["receiver_name"],
                "passes": of_named_matches["passes"],
                "forward_passes": of_named_matches["forward_passes"],
                "mean_start_x": rounder.round_every_value(
                    of_named_matches["start_x_sum"] / of_named_matches["passes"]
                ),
                "mean_end_x": rounder.round_every_value(
                    of_named_matches["end_x_sum"] / of_named_matches["passes"]
                ),
            }
        )


class PassingNetworkCalculator:
    """The passing network of every team and match, summarised as one row each.

    Both event sources hand the same table over: every open play pass of every
    match, with the passer, the receiver and where the pass ran from and to.
    A team that played no pass at all gets no row.
    """

    TEAM_KEYS = ["game_identifier", "team_name"]

    def summarise_every_team(self, passes: pd.DataFrame) -> pd.DataFrame:
        """Turn the passes of every team of every match into its row.

        Returns:
            One row per team that played a pass, without the columns that say
            which match it was.
        """
        marked = self._marked_up(passes)
        of_the_team = marked.groupby(self.TEAM_KEYS, sort=False)
        pass_count = of_the_team.size()
        per_player = self._count_per_player(marked)
        lanes = self._count_per_lane(marked)
        player_count = per_player.groupby(self.TEAM_KEYS, sort=False).size()
        lane_count = self._lane_count_of_every_team(lanes, pass_count.index)
        rounded_rate = DecimalRounder(PassingNetworkFeature.RATE_DECIMAL_PLACES)
        rounded_length = DecimalRounder(PassingNetworkFeature.LENGTH_DECIMAL_PLACES)
        return pd.DataFrame(
            {
                "passes": pass_count,
                "pass_success_rate": rounded_rate.round_every_value(
                    of_the_team["was_successful"].sum() / pass_count
                ),
                "forward_pass_share": rounded_rate.round_every_value(
                    of_the_team["went_forward"].sum() / pass_count
                ),
                "mean_pass_length_in_metres": rounded_length.round_every_value(
                    of_the_team["how_far_the_ball_travelled"].sum() / pass_count
                ),
                "mean_forward_gain_in_metres": rounded_length.round_every_value(
                    of_the_team["forward_gain_in_metres"].sum() / pass_count
                ),
                "players_involved": player_count,
                "distinct_lanes": lane_count,
                "unused_lane_share": self._unused_lane_share(
                    player_count, lane_count, rounded_rate
                ),
                "pass_concentration": rounded_rate.round_every_value(
                    self._how_much_went_through_few_players(per_player, pass_count)
                ),
                "top_player_share": rounded_rate.round_every_value(
                    per_player.groupby(self.TEAM_KEYS, sort=False)["passes"].max()
                    / pass_count
                ),
                **self._busiest_lane_of_every_team(lanes, pass_count.index),
            }
        ).reset_index()

    def _marked_up(self, passes: pd.DataFrame) -> pd.DataFrame:
        """Say of every single pass how far it went and whether it formed a lane."""
        forward_gain = passes["end_x_in_metres"] - passes["start_x_in_metres"]
        return passes.assign(
            forward_gain_in_metres=forward_gain,
            went_forward=forward_gain > PassingNetworkFeature.FORWARD_MINIMUM_METRES,
            how_far_the_ball_travelled=np.hypot(
                forward_gain, passes["end_y_in_metres"] - passes["start_y_in_metres"]
            ),
            has_reached_somebody_else=passes["was_successful"]
            & (passes["receiver_name"] != "")
            & (passes["receiver_name"] != passes["passer_name"]),
        )

    def _count_per_player(self, marked: pd.DataFrame) -> pd.DataFrame:
        """Count how many passes each player of each team played."""
        return (
            marked.groupby([*self.TEAM_KEYS, "passer_name"], sort=False)
            .size()
            .reset_index(name="passes")
        )

    def _count_per_lane(self, marked: pd.DataFrame) -> pd.DataFrame:
        """Count how often the ball went from one player to another.

        Returns:
            One row per lane, in the order the lanes were first played, so the
            busiest of them is decided the way a walk decided it.
        """
        return (
            marked[marked["has_reached_somebody_else"]]
            .groupby([*self.TEAM_KEYS, "passer_name", "receiver_name"], sort=False)
            .size()
            .reset_index(name="passes")
        )

    def _lane_count_of_every_team(
        self, lanes: pd.DataFrame, every_team: pd.Index
    ) -> pd.Series:
        """Count the distinct lanes of every team, zero where it formed none."""
        return (
            lanes.groupby(self.TEAM_KEYS, sort=False)
            .size()
            .reindex(every_team)
            .fillna(0)
            .astype(int)
        )

    def _unused_lane_share(
        self, player_count: pd.Series, lane_count: pd.Series, rounder: DecimalRounder
    ) -> pd.Series:
        """How many of the possible connections between players never happened.

        Returns:
            The share per team, or an empty cell where a single player played
            every pass, because then there is no connection to miss.
        """
        possible_lanes = player_count * (player_count - 1)
        can_be_divided = possible_lanes != 0
        share = 1.0 - lane_count / possible_lanes.where(can_be_divided)
        return rounder.round_every_value(share.clip(lower=0.0)).where(
            can_be_divided, ""
        )

    def _how_much_went_through_few_players(
        self, per_player: pd.DataFrame, pass_count: pd.Series
    ) -> pd.Series:
        """How much of the passing went through few players.

        The squared shares added up, the Herfindahl-Hirschman index. One
        player playing everything gives 1, eleven equal players give 1/11.
        """
        beside_the_team = per_player.join(
            pass_count.rename("of_the_whole_team"), on=self.TEAM_KEYS
        )
        share = beside_the_team["passes"] / beside_the_team["of_the_whole_team"]
        return (
            (share**2)
            .groupby([per_player[name] for name in self.TEAM_KEYS], sort=False)
            .sum()
            .reindex(pass_count.index)
        )

    def _busiest_lane_of_every_team(
        self, lanes: pd.DataFrame, every_team: pd.Index
    ) -> dict[str, pd.Series]:
        """Name the connection the ball took most often, and how often.

        Returns:
            The two players and the count per team, an empty name and a zero
            where no pass of the team ever reached a team mate.
        """
        busiest = lanes.loc[
            lanes.groupby(self.TEAM_KEYS, sort=False)["passes"].idxmax()
        ].set_index(self.TEAM_KEYS)
        named = (
            busiest["passer_name"]
            + PassingNetworkFeature.LANE_SEPARATOR
            + busiest["receiver_name"]
        )
        return {
            "top_lane": named.reindex(every_team).fillna(""),
            "top_lane_count": busiest["passes"]
            .reindex(every_team)
            .fillna(0)
            .astype(int),
        }


class PlayerMatchMetricCalculator:
    """What one player did in one match, counted and built into their row.

    Both event sources are read into the same actions first, so what counts
    as a progressive pass or a high recovery is decided here once. What each
    of them hands over is the action table with an is_goalkeeper column saying
    whether the player who made an action keeps goal.
    """

    PLAYER_KEYS = ["player_identifier", "game_identifier"]
    COUNTED_NAMES = (
        "passes",
        "completed_passes",
        "progressive_passes",
        "passes_into_box",
        "deep_completions",
        "progression_value",
        "defensive_actions",
        "defensive_height_sum",
        "high_ball_recoveries",
        "take_ons",
        "take_ons_won",
        "shots",
        "shots_in_box",
        "goalkeeper_actions",
        "goalkeeper_actions_outside_box",
        "goalkeeper_height_sum",
        "goalkeeper_passes",
        "goalkeeper_long_passes",
    )

    def count_every_player(self, actions: pd.DataFrame) -> pd.DataFrame:
        """Add up what every player did in every match they touched the ball in.

        Returns:
            One row per player and match, with the two height sums the means
            are worked out of still in it. An action the source left to
            nobody counts towards nothing.
        """
        of_a_named_player = actions[actions["player_identifier"] != ""]
        marked = self._marked_up(of_a_named_player)
        return (
            marked.groupby(self.PLAYER_KEYS, sort=False)[list(self.COUNTED_NAMES)]
            .sum()
            .reset_index()
        )

    def build_the_columns_of_every_player(
        self, counts: pd.DataFrame, is_goalkeeper: pd.Series
    ) -> dict[str, pd.Series]:
        """Turn the counts of every player into the columns of their row.

        Args:
            counts: One row per row of the output, already lined up with it.
            is_goalkeeper: Whether each of those rows belongs to a keeper.

        Returns:
            Everything but the columns that say who the player is and which
            match it was. The goalkeeper columns stay empty for an outfield
            player rather than holding a zero, because a zero would read as
            a keeper who did nothing.
        """
        as_a_whole_number = {
            name: counts[name].astype(int)
            for name in (
                "passes",
                "completed_passes",
                "progressive_passes",
                "passes_into_box",
                "deep_completions",
                "defensive_actions",
                "high_ball_recoveries",
                "take_ons",
                "take_ons_won",
                "shots",
                "shots_in_box",
            )
        }
        return {
            **as_a_whole_number,
            "progression_value": DecimalRounder(
                PlayerMatchMetricFeature.PROGRESSION_DECIMAL_PLACES
            ).round_every_value(counts["progression_value"]),
            "defensive_action_height_in_metres": self._how_far_up_the_pitch_on_average(
                counts["defensive_height_sum"], counts["defensive_actions"]
            ),
            **self._goalkeeper_columns(counts, is_goalkeeper),
        }

    def _marked_up(self, actions: pd.DataFrame) -> pd.DataFrame:
        """Say of every single action what it counts towards.

        Every column here answers one question about one action, so all the
        counting afterwards is a sum over each of them.
        """
        kind = actions["kind"]
        start_x = actions["start_x_in_metres"]
        end_x = actions["end_x_in_metres"]
        gained = end_x - start_x
        is_goalkeeper = actions["is_goalkeeper"]
        is_a_pass = kind.isin(MatchStyleFeature.EVERY_PASS_KIND)
        was_completed = is_a_pass & actions["was_successful"]
        is_on_the_defensive_line = kind.isin(MatchStyleFeature.DEFENSIVE_LINE_KINDS)
        is_a_take_on = kind == MatchStyleFeature.TAKE_ON_KIND
        is_a_shot = kind.isin(MatchStyleFeature.SHOT_KINDS)
        return actions.assign(
            passes=is_a_pass,
            completed_passes=was_completed,
            progressive_passes=was_completed
            & (gained >= PlayerMatchMetricFeature.PROGRESSIVE_PASS_MINIMUM_METRES)
            & (end_x >= MatchStyleFeature.FINAL_THIRD_START_X),
            passes_into_box=was_completed
            & self._lies_in_the_box(end_x, actions["end_y_in_metres"]),
            deep_completions=was_completed
            & (end_x >= PlayerMatchMetricFeature.DEEP_COMPLETION_START_X),
            progression_value=self._progression_value_of(gained, end_x).where(
                was_completed, 0.0
            ),
            defensive_actions=is_on_the_defensive_line,
            defensive_height_sum=start_x.where(is_on_the_defensive_line, 0.0),
            high_ball_recoveries=is_on_the_defensive_line
            & (start_x >= PlayerMatchMetricFeature.HIGH_RECOVERY_START_X),
            take_ons=is_a_take_on,
            take_ons_won=is_a_take_on & actions["was_successful"],
            shots=is_a_shot,
            shots_in_box=is_a_shot
            & self._lies_in_the_box(start_x, actions["start_y_in_metres"]),
            goalkeeper_actions=is_goalkeeper,
            goalkeeper_actions_outside_box=is_goalkeeper
            & (start_x > PlayerMatchMetricFeature.PENALTY_AREA_LENGTH_IN_METRES),
            goalkeeper_height_sum=start_x.where(is_goalkeeper, 0.0),
            goalkeeper_passes=is_goalkeeper & is_a_pass,
            goalkeeper_long_passes=is_goalkeeper
            & is_a_pass
            & (gained > PlayerMatchMetricFeature.LONG_PASS_MINIMUM_METRES),
        )

    def _progression_value_of(self, gained: pd.Series, end_x: pd.Series) -> pd.Series:
        """Weigh the ground a pass won by how near the goal it ended.

        Ten metres won in front of the other box are worth more than ten
        metres won in front of your own, so the gain is multiplied by the
        square of how far up the pitch the ball came to rest.
        """
        share_of_the_pitch = end_x / PitchGeometry.LENGTH_IN_METRES
        return gained.clip(lower=0.0) * share_of_the_pitch**2

    def _lies_in_the_box(
        self, x_in_metres: pd.Series, y_in_metres: pd.Series
    ) -> pd.Series:
        """Return True where a point lies inside the penalty area being attacked."""
        return (
            (x_in_metres >= MatchStyleFeature.BOX_START_X)
            & (y_in_metres >= MatchStyleFeature.BOX_MINIMUM_Y)
            & (y_in_metres <= MatchStyleFeature.BOX_MAXIMUM_Y)
        )

    def _goalkeeper_columns(
        self, counts: pd.DataFrame, is_goalkeeper: pd.Series
    ) -> dict[str, pd.Series]:
        """Build the five keeper columns, and leave them empty for anybody else."""
        of_a_keeper = {
            "goalkeeper_actions": counts["goalkeeper_actions"].astype(int),
            "goalkeeper_actions_outside_box": counts[
                "goalkeeper_actions_outside_box"
            ].astype(int),
            "goalkeeper_action_height_in_metres": (
                self._how_far_up_the_pitch_on_average(
                    counts["goalkeeper_height_sum"], counts["goalkeeper_actions"]
                )
            ),
            "goalkeeper_long_passes": counts["goalkeeper_long_passes"].astype(int),
            "goalkeeper_passes": counts["goalkeeper_passes"].astype(int),
        }
        return {
            name: column.where(is_goalkeeper, "")
            for name, column in of_a_keeper.items()
        }

    def _how_far_up_the_pitch_on_average(
        self, height_sum: pd.Series, action_count: pd.Series
    ) -> pd.Series:
        """How far up the pitch somebody acted on average.

        Returns:
            The mean per row, or an empty cell where there was no such action
            at all, because a zero would claim they acted on their own goal
            line.
        """
        acted_at_all = action_count != 0
        mean_height = height_sum / action_count.where(acted_at_all)
        return (
            DecimalRounder(PlayerMatchMetricFeature.HEIGHT_DECIMAL_PLACES)
            .round_every_value(mean_height)
            .where(acted_at_all, "")
        )


class ExpectedThreatGrid:
    """The value of every place on the pitch, and what a move is worth.

    A cell is worth how likely a goal follows from it. Moving the ball from
    one cell to another is worth the difference between the two, which is
    what makes a pass into the box count for more than a pass along the
    halfway line.
    """

    def __init__(self, values: list[float]) -> None:
        self._values = values

    @property
    def values(self) -> list[float]:
        """The value of every cell, in one long row rather than a square."""
        return self._values

    def which_cell_the_place_falls_into(
        self, x_in_metres: float, y_in_metres: float
    ) -> int:
        """Say which cell a place on the pitch falls into.

        Args:
            x_in_metres: Counted towards the goal being attacked.
            y_in_metres: Counted across the pitch.

        Returns:
            The cell, kept inside the grid even for a coordinate the source
            put slightly off the pitch.
        """
        column = self._kept_inside_the_grid(
            int(
                x_in_metres
                / PitchGeometry.LENGTH_IN_METRES
                * ExpectedThreatFeature.COLUMN_COUNT
            ),
            ExpectedThreatFeature.COLUMN_COUNT,
        )
        row = self._kept_inside_the_grid(
            int(
                y_in_metres
                / PitchGeometry.WIDTH_IN_METRES
                * ExpectedThreatFeature.ROW_COUNT
            ),
            ExpectedThreatFeature.ROW_COUNT,
        )
        return row * ExpectedThreatFeature.COLUMN_COUNT + column

    def which_cell_every_place_falls_into(
        self, x_in_metres: pd.Series, y_in_metres: pd.Series
    ) -> pd.Series:
        """Say of a whole column of places which cell each falls into.

        Args:
            x_in_metres: Counted towards the goal being attacked.
            y_in_metres: Counted across the pitch.

        Returns:
            The cell of every row, each kept inside the grid even for a
            coordinate the source put slightly off the pitch.
        """
        column = self._kept_inside_every_grid(
            x_in_metres
            / PitchGeometry.LENGTH_IN_METRES
            * ExpectedThreatFeature.COLUMN_COUNT,
            ExpectedThreatFeature.COLUMN_COUNT,
        )
        row = self._kept_inside_every_grid(
            y_in_metres
            / PitchGeometry.WIDTH_IN_METRES
            * ExpectedThreatFeature.ROW_COUNT,
            ExpectedThreatFeature.ROW_COUNT,
        )
        return row * ExpectedThreatFeature.COLUMN_COUNT + column

    def gain_between(self, start_cell: int, end_cell: int) -> float:
        """What moving the ball from one cell to another was worth."""
        return self._values[end_cell] - self._values[start_cell]

    def gain_of_every_move(
        self, start_cells: pd.Series, end_cells: pd.Series
    ) -> pd.Series:
        """What moving the ball was worth, for a whole column of moves."""
        values = np.array(self._values)
        return pd.Series(
            values[end_cells.to_numpy()] - values[start_cells.to_numpy()],
            index=start_cells.index,
        )

    def to_rows(self) -> list[dict[str, Any]]:
        """Build one row per cell, so the grid can be written down."""
        return [
            {
                "grid_column": cell % ExpectedThreatFeature.COLUMN_COUNT,
                "grid_row": cell // ExpectedThreatFeature.COLUMN_COUNT,
                "expected_threat": round(
                    value, ExpectedThreatFeature.GRID_DECIMAL_PLACES
                ),
            }
            for cell, value in enumerate(self._values)
        ]

    def describe_the_best_cell(self) -> str:
        """Say where on the pitch the ball is worth the most, for the log."""
        best_cell = max(range(len(self._values)), key=lambda one: self._values[one])
        return (
            f"highest {max(self._values):.4f} in column "
            f"{best_cell % ExpectedThreatFeature.COLUMN_COUNT} "
            f"row {best_cell // ExpectedThreatFeature.COLUMN_COUNT}"
        )

    def _kept_inside_the_grid(self, position: int, count: int) -> int:
        """Keep a column or a row inside the grid."""
        return min(count - 1, max(0, position))

    def _kept_inside_every_grid(self, position: pd.Series, count: int) -> pd.Series:
        """Keep a whole column of columns or rows inside the grid.

        The place is cut towards zero rather than rounded, the way the walk
        this replaces cut it, so a point at 0.9 of a cell still lies in it.
        """
        return position.astype(int).clip(lower=0, upper=count - 1)


class ExpectedThreatGridFile:
    """The grid on disk, so both event sources value a move the same way."""

    def __init__(self, csv_file: CsvFile) -> None:
        self._csv_file = csv_file

    def read(self) -> ExpectedThreatGrid:
        """Read the grid that was learned earlier.

        Raises:
            SystemExit: When the file is not there, because applying a grid
                that was never learned would value every move at zero.
        """
        if not self._csv_file.path.exists():
            raise SystemExit(
                f"No expected threat grid at {self._csv_file.path}. "
                "Run the Wyscout builder first, it learns and writes it."
            )
        written = self._csv_file.read_table()
        of_the_cell = pd.Series(
            ExactNumberReader().read_every_number(written["expected_threat"]).values,
            index=written["grid_row"].astype(int) * ExpectedThreatFeature.COLUMN_COUNT
            + written["grid_column"].astype(int),
        )
        cell_count = (
            ExpectedThreatFeature.COLUMN_COUNT * ExpectedThreatFeature.ROW_COUNT
        )
        return ExpectedThreatGrid(
            list(of_the_cell.reindex(range(cell_count)).fillna(0.0))
        )

    def write(self, grid: ExpectedThreatGrid) -> None:
        """Write the grid down for the other source to pick up."""
        self._csv_file.write_dict_rows(grid.to_rows())


class PreMatchRollingAverage:
    """The smoothed form of every team, as it stood before the current match.

    A rolling average is only worth anything if it never saw the match it is
    used to predict. Every value is therefore shifted by one row inside its
    own team, so a row carries what the team had behind it and never its own
    match.

    Two averages come out of it, one that fades older matches out gradually
    and one over a fixed number of the most recent ones.
    """

    def __init__(self, fading_weight: float, window_length: int) -> None:
        self._fading_weight = fading_weight
        self._window_length = window_length

    def what_every_team_brought_into_its_match(
        self, team_names: pd.Series, what_the_team_did: pd.Series
    ) -> pd.DataFrame:
        """Sum up the past of every team without letting its own match in.

        Args:
            team_names: Whose match each row is. The rows must already be in
                the order the matches were played.
            what_the_team_did: The value to average, in the same order.

        Returns:
            The faded average, the average over the window, and how many
            matches the team had behind it. A team that has never played
            comes back at zero, which reads as no form either way.
        """
        played_before = what_the_team_did.groupby(team_names, sort=False)
        return pd.DataFrame(
            {
                "faded_average": played_before.transform(
                    self._fade_the_matches_before_this_one
                ),
                "mean_of_the_window": played_before.transform(
                    self._average_the_matches_before_this_one
                ),
                "matches_played_before": played_before.cumcount(),
            }
        )

    def _fade_the_matches_before_this_one(self, values: pd.Series) -> pd.Series:
        """Fade the matches of one team out, up to but not including each row."""
        return (
            values.ewm(alpha=self._fading_weight, adjust=False)
            .mean()
            .shift(1)
            .fillna(0.0)
        )

    def _average_the_matches_before_this_one(self, values: pd.Series) -> pd.Series:
        """Average the last few matches of one team, its own one left out.

        Adding nothing at the end turns a negative zero back into a plain
        one, the way summing a list of values in Python does.
        """
        return (
            values.rolling(self._window_length, min_periods=1)
            .mean()
            .shift(1)
            .fillna(0.0)
            + 0.0
        )


class ZipArchiveExtractor:
    """A ZIP archive that is held in memory as bytes, unpacked.

    Kaggle hands out its datasets as ZIP archives. Some downloaders want the
    whole archive on disk, others want exactly one file out of it.
    """

    def looks_like_zip_archive(self, payload: bytes) -> bool:
        """Return True when the payload starts with the two bytes every ZIP has.

        Kaggle answers with a plain file for a small download and with an
        archive for a large one, so a caller has to ask before unpacking.

        Args:
            payload: The bytes that came back from the server.

        Returns:
            True when the bytes are an archive.
        """
        return payload.startswith(KaggleSetting.ZIP_ARCHIVE_FIRST_BYTES)

    def extract_all_files(self, payload: bytes, target_folder: Path) -> int:
        """Unpack the whole archive into a folder.

        Args:
            payload: The archive as it came off the server.
            target_folder: Where the files land. Created when missing.

        Returns:
            How many files the archive held.

        Raises:
            zipfile.BadZipFile: When the payload is not an archive. Ask
                looks_like_zip_archive first.
        """
        target_folder.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(target_folder)
            return len(archive.namelist())

    def extract_one_file(
        self, payload: bytes, name_inside_archive: str, target_file: Path
    ) -> bool:
        """Return True when the named file was found and written.

        Args:
            payload: The archive as it came off the server.
            name_inside_archive: The path the file has inside the archive,
                which is not always the name it should have on disk.
            target_file: Where it lands. The folder is created when missing.

        Returns:
            True when the file was written, False when the archive does not
            hold that name at all.

        Raises:
            zipfile.BadZipFile: When the payload is not an archive.
        """
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if name_inside_archive not in archive.namelist():
                return False
            with archive.open(name_inside_archive) as file_inside_archive:
                target_file.write_bytes(file_inside_archive.read())
        return True


class StadiumLocator:
    """The city and the coordinates that belong to a stadium name.

    The sources write a stadium name in many ways, so the mapping table is
    matched by part of the name. The order of the table matters, the more
    specific key has to come first.
    """

    def __init__(self, text_normalizer: TextNormalizer) -> None:
        self._text_normalizer = text_normalizer

    def find_place(self, stadium_name: str) -> tuple[str, float, float] | None:
        """Find the place a stadium stands in.

        Args:
            stadium_name: The name as the source writes it, accents and all.

        Returns:
            City, latitude and longitude, or None when the mapping table does
            not know this stadium. A caller should collect the unknown names
            and report them, so the table can be filled in.
        """
        comparable_name = self._text_normalizer.to_comparable_text(stadium_name)
        for name_part, place in MatchWeatherSource.PLACE_OF_STADIUM_NAME_PART.items():
            if name_part in comparable_name:
                return place
        return None

    def find_the_place_of_every_stadium(self, stadium_names: pd.Series) -> pd.DataFrame:
        """Find the place behind a whole column of stadium names.

        Only the spellings that really occur are matched, so the work is done
        once per stadium and not once per match.

        Returns:
            A city, a latitude and a longitude column, all three empty in a
            row whose stadium the mapping table does not know.
        """
        every_spelling = pd.Series(stadium_names.unique())
        found = pd.DataFrame(
            every_spelling.map(self.find_place).tolist(),
            columns=["city", "latitude", "longitude"],
            index=every_spelling,
        )
        return found.reindex(stadium_names).set_index(stadium_names.index)


class WebFileDownloader:
    """One file over HTTP, fetched politely and retried once if asked to.

    Every downloader and fetcher gets one of these handed in, so all of them
    behave the same and can be replaced by a stub in a test. One object serves
    one source, because the user agent, the patience and the waiting time
    belong to that source.

    Attributes:
        headers_of_the_last_answer: What the server sent back last, for an
            endpoint that reports its remaining quota only in a header.
    """

    def __init__(
        self,
        user_agent: str = WebRequestSetting.RESEARCH_USER_AGENT,
        timeout_in_seconds: int = WebRequestSetting.STANDARD_TIMEOUT_IN_SECONDS,
        polite_delay_in_seconds: float = (
            WebRequestSetting.STANDARD_POLITE_DELAY_IN_SECONDS
        ),
        attempt_count: int = WebRequestSetting.SINGLE_ATTEMPT,
    ) -> None:
        self._user_agent = user_agent
        self._timeout_in_seconds = timeout_in_seconds
        self._polite_delay_in_seconds = polite_delay_in_seconds
        self._attempt_count = attempt_count
        self._headers_of_the_last_answer: dict[str, str] = {}

    @property
    def headers_of_the_last_answer(self) -> dict[str, str]:
        """The headers the server sent last.

        Some endpoints report how many requests are left there, and nowhere
        else, so a caller reads this straight after a download.
        """
        return dict(self._headers_of_the_last_answer)

    def download_bytes(
        self,
        url: str,
        timeout_in_seconds: int | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> bytes | None:
        """Fetch one file and wait politely afterwards.

        Args:
            url: The full address of the file.
            timeout_in_seconds: How long to wait for this one request. A very
                large file needs more patience than the default this object
                was built with. Left out to use that default.
            extra_headers: Further headers, for an endpoint that wants an API
                key in one.

        Returns:
            The file content, or None when the server answered 404, kept
            failing, or could not be reached at all.
        """
        payload = self._try_to_download(url, timeout_in_seconds, extra_headers)
        self._wait_politely()
        return payload

    def download_json(
        self,
        url: str,
        timeout_in_seconds: int | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        """Fetch one file and read it as JSON.

        Args:
            url: The full address of the file.
            timeout_in_seconds: How long to wait for this one request.
            extra_headers: Further headers, for an endpoint that wants an API
                key in one.

        Returns:
            Whatever the JSON holds, usually a list or a dictionary, or None
            when the file could not be loaded or is not JSON at all. A caller
            has to check the shape before using it.
        """
        payload = self.download_bytes(url, timeout_in_seconds, extra_headers)
        if payload is None:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def _try_to_download(
        self,
        url: str,
        timeout_in_seconds: int | None,
        extra_headers: dict[str, str] | None,
    ) -> bytes | None:
        """Ask the server, and try again once when the failure looks temporary.

        A file that is really not there answers 404, and asking again cannot
        change that. Any other failure is a network hiccup and is worth another
        attempt.
        """
        patience_in_seconds = timeout_in_seconds or self._timeout_in_seconds
        headers = {"User-Agent": self._user_agent}
        headers.update(extra_headers or {})
        request = urllib.request.Request(url, headers=headers)
        for attempt_number in range(self._attempt_count):
            try:
                with urllib.request.urlopen(
                    request, timeout=patience_in_seconds
                ) as response:
                    self._headers_of_the_last_answer = dict(response.headers)
                    return response.read()
            except urllib.error.HTTPError as http_error:
                file_is_really_absent = (
                    http_error.code == WebRequestSetting.PAGE_NOT_FOUND_STATUS_CODE
                )
                if file_is_really_absent:
                    return None
            except (OSError, http.client.HTTPException):
                pass
            if attempt_number + 1 < self._attempt_count:
                time.sleep(WebRequestSetting.BACKOFF_BEFORE_RETRY_IN_SECONDS)
        return None

    def wait_for(self, seconds_to_wait: float) -> None:
        """Wait longer than usual, for a source that throttles a heavy query."""
        if seconds_to_wait > 0:
            time.sleep(seconds_to_wait)

    def _wait_politely(self) -> None:
        """Leave a gap between two requests so we do not hammer the server."""
        self.wait_for(self._polite_delay_in_seconds)


class WikipediaPageReader:
    """The raw wikitext of one Wikipedia page.

    Four callers need it: the tournament squads, the 2026 base camps, the
    tournament coaches and the pageview fetcher. All of them read the same
    parse endpoint, so the request lives here.
    """

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def read_wikitext(self, page_title: str) -> str | None:
        """Read the raw wikitext of one page.

        Args:
            page_title: The title as it stands in the address of the page,
                spaces and all. It gets escaped here.

        Returns:
            The wikitext, or None when the page could not be loaded or does
            not exist. Wikipedia throttles, so None can also mean "try again
            in a moment".
        """
        url = WikipediaSource.API_BASE_URL + urllib.parse.quote(page_title)
        answer = self._web_file_downloader.download_json(
            url, timeout_in_seconds=WikipediaSource.TIMEOUT_IN_SECONDS
        )
        return self._read_wikitext_out_of_answer(answer)

    def _read_wikitext_out_of_answer(self, answer: Any) -> str | None:
        """Dig the wikitext out of the nested answer, or give up quietly."""
        if not isinstance(answer, dict):
            return None
        parsed_page = answer.get("parse")
        if not isinstance(parsed_page, dict):
            return None
        wikitext = parsed_page.get("wikitext")
        return wikitext if isinstance(wikitext, str) else None


class WyscoutDataReader:
    """The lookup tables and the actions of the Wyscout event dataset.

    Every Wyscout builder needs the same four tables to turn an identifier
    into a readable name, and every one of them has to mirror the coordinates
    and decode the escaped characters the same way.
    """

    def __init__(self, text_normalizer: TextNormalizer) -> None:
        """Keep the normaliser and the pattern that pulls numbers out of a cell."""
        self._text_normalizer = text_normalizer
        self._number_pattern = re.compile(WyscoutEventFile.NUMBER_PATTERN)

    def read_team_names(self) -> dict[str, str]:
        """Read the readable name of every team, by identifier."""
        return self._read_readable_lookup(
            WyscoutEventFile.TEAM_FILE_NAME, WyscoutEventFile.NAME_COLUMN
        )

    def read_referee_names(self) -> dict[str, str]:
        """Read the short name of every referee, by identifier."""
        return self._read_readable_lookup(
            WyscoutEventFile.REFEREE_FILE_NAME, WyscoutEventFile.SHORT_NAME_COLUMN
        )

    def read_player_names(self) -> dict[str, str]:
        """Read the short name of every player, by identifier."""
        return self._read_readable_lookup(
            WyscoutEventFile.PLAYER_FILE_NAME, WyscoutEventFile.SHORT_NAME_COLUMN
        )

    def read_competition_names(self) -> dict[str, str]:
        """Read the name of every competition, by identifier.

        These names carry no escaped characters, so they are taken as they are.
        """
        return self._read_lookup(
            WyscoutEventFile.COMPETITION_FILE_NAME, WyscoutEventFile.NAME_COLUMN
        )

    def read_name_lookups(self) -> WyscoutNameLookups:
        """Read all four name tables at once, for a builder that writes names."""
        return WyscoutNameLookups(
            team_names=self.read_team_names(),
            player_names=self.read_player_names(),
            competition_names=self.read_competition_names(),
            referee_names=self.read_referee_names(),
        )

    def read_match_facts(self) -> dict[str, WyscoutMatchFacts]:
        """Read who played whom, when and under which referee, for every match.

        Returns:
            One entry per match identifier. A builder needs it to name the
            opponent, to say which side was at home and to sort its output.
        """
        facts: dict[str, WyscoutMatchFacts] = {}
        for match_file in sorted(
            WyscoutEventFile.SOURCE_FOLDER.glob(WyscoutEventFile.MATCH_FILE_PATTERN)
        ):
            for match in CsvFile(match_file).read_rows():
                identifier = self.as_identifier(
                    match.get(WyscoutEventFile.IDENTIFIER_COLUMN, "")
                )
                facts[identifier] = self._read_facts_of_one_match(match, identifier)
        return facts

    def _read_facts_of_one_match(
        self, match: dict[str, str], identifier: str
    ) -> WyscoutMatchFacts:
        """Turn one row of a match file into the facts a builder asks for."""
        team_one = self.as_identifier(
            match.get(WyscoutEventFile.TEAM_ONE_IDENTIFIER_COLUMN, "")
        )
        team_two = self.as_identifier(
            match.get(WyscoutEventFile.TEAM_TWO_IDENTIFIER_COLUMN, "")
        )
        team_one_played_at_home = (
            match.get(WyscoutEventFile.TEAM_ONE_SIDE_COLUMN)
            == WyscoutEventFile.HOME_SIDE_NAME
        )
        return WyscoutMatchFacts(
            game_identifier=identifier,
            home_team_identifier=team_one if team_one_played_at_home else team_two,
            away_team_identifier=team_two if team_one_played_at_home else team_one,
            referee_identifier=self.read_main_referee_identifier(match),
            competition_identifier=self.as_identifier(
                match.get(WyscoutEventFile.COMPETITION_IDENTIFIER_COLUMN, "")
            ),
            season_name=match.get(WyscoutEventFile.SEASON_IDENTIFIER_COLUMN, ""),
            match_date=match.get(WyscoutEventFile.MATCH_DATE_COLUMN, "")[
                : StatsBombOpenDataSource.DATE_LENGTH
            ],
        )

    def read_the_identity_of_every_match(
        self, lookups: WyscoutNameLookups
    ) -> pd.DataFrame:
        """Say of every match which competition, which two teams and which referee.

        Returns:
            One row per match, in the shape every calculator joins its actions
            onto. The two team identifiers come along beside the names,
            because the raw events name a team by its identifier only.
        """
        facts_of_match = self.read_match_facts()
        facts = pd.DataFrame(
            [
                {
                    "game_identifier": one.game_identifier,
                    "competition_identifier": one.competition_identifier,
                    "season_name": one.season_name,
                    "match_date": one.match_date,
                    "home_team_identifier": one.home_team_identifier,
                    "away_team_identifier": one.away_team_identifier,
                    "referee_identifier": one.referee_identifier,
                }
                for one in facts_of_match.values()
            ]
        )
        return pd.DataFrame(
            {
                "game_identifier": facts["game_identifier"],
                "competition_name": facts["competition_identifier"]
                .map(lookups.competition_names)
                .fillna(""),
                "season_name": facts["season_name"],
                "match_date": facts["match_date"],
                "home_team_name": facts["home_team_identifier"]
                .map(lookups.team_names)
                .fillna(facts["home_team_identifier"]),
                "away_team_name": facts["away_team_identifier"]
                .map(lookups.team_names)
                .fillna(facts["away_team_identifier"]),
                "referee_name": facts["referee_identifier"]
                .map(lookups.referee_names)
                .fillna(facts["referee_identifier"]),
                "home_team_identifier": facts["home_team_identifier"],
                "away_team_identifier": facts["away_team_identifier"],
            }
        )

    def read_every_action(self, lookups: WyscoutNameLookups) -> pd.DataFrame:
        """Read the whole action file as one table, in the shape both sources use.

        The file holds every action of every match in one stream and is close
        to three hundred megabytes, but it is one table and every builder
        that reads it groups over it, so it is read once and whole rather
        than walked match by match.

        The coordinates come back in metres with the acting team attacking
        towards x=105, the way StatsBomb is read too, so the two sources can
        be compared at all.

        Returns:
            One row per action the source could place on the pitch. A row
            without a coordinate or a time drops out, which is what happens
            to the ones the conversion could not place.
        """
        raw_actions = pd.read_csv(
            WyscoutEventFile.SOURCE_FOLDER / WyscoutEventFile.ACTION_FILE_NAME,
            usecols=list(WyscoutEventFile.ACTION_COLUMNS_TO_READ),
            dtype=str,
            keep_default_na=False,
            encoding=CsvFileSetting.ENCODING,
            encoding_errors=CsvFileSetting.IGNORE_BROKEN_CHARACTERS,
        )
        placed = self._only_the_actions_that_sit_on_the_pitch(raw_actions)
        return self._named_and_turned_around(placed, lookups)

    def _only_the_actions_that_sit_on_the_pitch(
        self, raw_actions: pd.DataFrame
    ) -> pd.DataFrame:
        """Keep the actions that carry a full coordinate and a time."""
        numbers = {
            "start_x": WyscoutEventFile.ACTION_START_X_COLUMN,
            "start_y": WyscoutEventFile.ACTION_START_Y_COLUMN,
            "end_x": WyscoutEventFile.ACTION_END_X_COLUMN,
            "end_y": WyscoutEventFile.ACTION_END_Y_COLUMN,
            "period": WyscoutEventFile.ACTION_PERIOD_COLUMN,
            "second": WyscoutEventFile.ACTION_SECOND_COLUMN,
        }
        exact_reader = ExactNumberReader()
        read_as_numbers = raw_actions.assign(
            **{
                name: exact_reader.read_every_number(raw_actions[column])
                for name, column in numbers.items()
            }
        )
        return read_as_numbers.dropna(subset=list(numbers))

    def _named_and_turned_around(
        self, placed: pd.DataFrame, lookups: WyscoutNameLookups
    ) -> pd.DataFrame:
        """Name the team and the player, and turn the pitch the right way round."""
        team_identifier = self.identifier_of_every_row(
            placed[WyscoutEventFile.ACTION_TEAM_COLUMN]
        )
        player_identifier = self.identifier_of_every_row(
            placed[WyscoutEventFile.ACTION_PLAYER_COLUMN]
        )
        kind = (
            placed[WyscoutEventFile.ACTION_TYPE_COLUMN]
            .map(MatchStyleFeature.KIND_OF_SPADL_TYPE)
            .fillna(MatchStyleFeature.OTHER_KIND)
        )
        result_name = placed[WyscoutEventFile.ACTION_RESULT_COLUMN]

        return pd.DataFrame(
            {
                "game_identifier": self.identifier_of_every_row(
                    placed[WyscoutEventFile.ACTION_GAME_COLUMN]
                ),
                "team_name": team_identifier.map(lookups.team_names).fillna(
                    team_identifier
                ),
                "kind": kind,
                "was_successful": result_name
                == WyscoutEventFile.SUCCESSFUL_RESULT_NAME,
                "start_x_in_metres": self.mirror_along_the_pitch(placed["start_x"]),
                "start_y_in_metres": placed["start_y"],
                "end_x_in_metres": self.mirror_along_the_pitch(placed["end_x"]),
                "end_y_in_metres": placed["end_y"],
                "scoring_team": self._who_every_goal_counted_for(kind, result_name),
                "expected_goals": np.nan,
                "was_after_a_set_piece": False,
                "period_number": placed["period"].astype(int),
                "second_in_period": placed["second"],
                "player_name": player_identifier.map(lookups.player_names).fillna(
                    player_identifier
                ),
                "player_identifier": player_identifier,
            }
        ).reset_index(drop=True)

    def _who_every_goal_counted_for(
        self, kind: pd.Series, result_name: pd.Series
    ) -> pd.Series:
        """Say who each goal counted for, and nothing where it was no goal."""
        return pd.Series(
            np.select(
                [
                    kind.isin(MatchStyleFeature.SHOT_KINDS)
                    & (result_name == WyscoutEventFile.SUCCESSFUL_RESULT_NAME),
                    result_name == WyscoutEventFile.OWN_GOAL_RESULT_NAME,
                ],
                [
                    MatchStyleFeature.SCORED_FOR_THE_ACTING_TEAM,
                    MatchStyleFeature.SCORED_FOR_THE_OTHER_TEAM,
                ],
                default=None,
            ),
            index=kind.index,
        )

    def identifier_of_every_row(self, raw_values: pd.Series) -> pd.Series:
        """Turn a whole column of identifiers into the form joins are made on.

        One table writes 12345 and another writes 12345.0 for the very same
        team, so the decimal tail comes off. Text that is no number at all
        comes back trimmed, so a join still has something to match.
        """
        as_number = pd.to_numeric(raw_values, errors="coerce")
        return pd.Series(
            np.where(
                as_number.notna(),
                as_number.fillna(0).astype("int64").astype(str),
                raw_values.str.strip(),
            ),
            index=raw_values.index,
        )

    def as_identifier(self, raw_value: str) -> str:
        """Turn an identifier into the one form every table can be joined on.

        Args:
            raw_value: The cell as the source wrote it. One table writes
                12345, another writes 12345.0 for the very same team.

        Returns:
            The identifier without a decimal tail. Text that is no number at
            all comes back trimmed, so a join still has something to match.
        """
        try:
            return str(int(float(raw_value)))
        except (TypeError, ValueError):
            return raw_value.strip()

    def read_every_substitution(self) -> pd.DataFrame:
        """Read every substitution of every match out of the match files.

        Wyscout writes the substitutions of a team as a Python literal inside
        a single cell, so that cell is parsed one at a time. Everything after
        that is table work.

        Returns:
            One row per substitution, the two teams still named by identifier,
            with the raw player identifiers and the minute as the source wrote
            them. The rows come in the order the match files list them, both
            sides of a match together.
        """
        of_every_file = [
            self._read_the_substitutions_of_one_file(match_file)
            for match_file in sorted(
                WyscoutEventFile.SOURCE_FOLDER.glob(WyscoutEventFile.MATCH_FILE_PATTERN)
            )
        ]
        return pd.concat(of_every_file, ignore_index=True)

    def _read_the_substitutions_of_one_file(self, match_file: Path) -> pd.DataFrame:
        """Read the substitutions of both sides of every match of one file."""
        matches = CsvFile(match_file).read_table()
        of_both_sides = pd.concat(
            [
                self._read_the_substitutions_of_one_side(matches, side, side_number)
                for side_number, side in enumerate(SubstitutionFeature.TEAM_SIDES)
            ]
        )
        in_the_order_of_the_file = of_both_sides.assign(
            row_in_the_file=of_both_sides.index
        ).sort_values(["row_in_the_file", "side_number"], kind="stable")
        return in_the_order_of_the_file.drop(
            columns=["row_in_the_file", "side_number"]
        ).reset_index(drop=True)

    def _read_the_substitutions_of_one_side(
        self, matches: pd.DataFrame, side: tuple[str, str, str], side_number: int
    ) -> pd.DataFrame:
        """Read the substitutions one side of every match of one file made."""
        team_column, list_column, opponent_column = side
        of_the_side = (
            matches.assign(
                substitution=matches[list_column].map(self.read_list_out_of_one_cell)
            )
            .explode("substitution")
            .dropna(subset=["substitution"])
        )
        one_substitution = of_the_side["substitution"]
        return pd.DataFrame(
            {
                "game_identifier": self.identifier_of_every_row(
                    of_the_side[WyscoutEventFile.IDENTIFIER_COLUMN]
                ),
                "competition_identifier": self.identifier_of_every_row(
                    of_the_side[WyscoutEventFile.COMPETITION_IDENTIFIER_COLUMN]
                ),
                "season_name": of_the_side[WyscoutEventFile.SEASON_IDENTIFIER_COLUMN],
                "match_date": of_the_side[WyscoutEventFile.MATCH_DATE_COLUMN].str[
                    : StatsBombOpenDataSource.DATE_LENGTH
                ],
                "team_identifier": self.identifier_of_every_row(
                    of_the_side[team_column]
                ),
                "opponent_identifier": self.identifier_of_every_row(
                    of_the_side[opponent_column]
                ),
                "player_out": one_substitution.str.get(
                    SubstitutionFeature.PLAYER_OUT_FIELD
                ),
                "player_in": one_substitution.str.get(
                    SubstitutionFeature.PLAYER_IN_FIELD
                ),
                "minute": one_substitution.str.get(SubstitutionFeature.MINUTE_FIELD),
                "side_number": side_number,
            }
        )

    def name_every_substituted_player(self, raw_identifiers: pd.Series) -> pd.Series:
        """Name every player of a substitution, keeping the raw value if unknown."""
        looked_up = self.identifier_of_every_row(raw_identifiers.astype(str)).map(
            self.read_player_names()
        )
        return looked_up.where(looked_up.notna(), raw_identifiers)

    def read_the_role_of_every_player(self) -> pd.DataFrame:
        """Read the position of every player, out of the player table.

        Returns:
            One row per player, with the two letter code GK, DF, MF or FW. A
            player whose cell holds no code comes back with an empty role.
        """
        players = CsvFile(
            WyscoutEventFile.SOURCE_FOLDER / WyscoutEventFile.PLAYER_FILE_NAME
        ).read_table()
        return pd.DataFrame(
            {
                "player_identifier": self.identifier_of_every_row(
                    players[WyscoutEventFile.IDENTIFIER_COLUMN]
                ),
                "role": players[PlayerMatchMetricFeature.ROLE_COLUMN]
                .str.extract(PlayerMatchMetricFeature.ROLE_CODE_PATTERN, expand=False)
                .fillna(""),
            }
        )

    def read_every_appearance(self) -> pd.DataFrame:
        """Read who played in which match, and for how many minutes.

        Returns:
            One row per player and match. Somebody who stayed on the bench is
            left out, because a row of zeros over zero minutes says nothing.
        """
        played = CsvFile(
            WyscoutEventFile.SOURCE_FOLDER
            / PlayerMatchMetricFeature.APPEARANCE_FILE_NAME
        ).read_table()
        minutes_played = (
            pd.to_numeric(
                played[PlayerMatchMetricFeature.MINUTES_COLUMN], errors="coerce"
            )
            .fillna(0)
            .astype(int)
        )
        appearances = pd.DataFrame(
            {
                "player_identifier": self.identifier_of_every_row(
                    played[WyscoutEventFile.ACTION_PLAYER_COLUMN]
                ),
                "game_identifier": self.identifier_of_every_row(
                    played[WyscoutEventFile.ACTION_GAME_COLUMN]
                ),
                "team_identifier": self.identifier_of_every_row(
                    played[WyscoutEventFile.ACTION_TEAM_COLUMN]
                ),
                "player_name": played[PlayerMatchMetricFeature.PLAYER_NAME_COLUMN],
                "minutes_played": minutes_played,
            }
        )
        return appearances[minutes_played > 0].reset_index(drop=True)

    def read_list_out_of_one_cell(self, cell: str) -> list[Any]:
        """Read a list the source squeezed into a single cell.

        Args:
            cell: The cell as the source wrote it, a Python literal rather
                than JSON.

        Returns:
            The entries, or an empty list when the cell is empty or cannot be
            read. A single broken cell must not stop a run over thousands of
            matches.
        """
        try:
            value = ast.literal_eval(cell)
        except (ValueError, SyntaxError):
            return []
        return value if isinstance(value, list) else []

    def read_main_referee_identifier(self, match: dict[str, str]) -> str:
        """Read who blew the whistle in one match.

        Returns:
            The identifier of the main referee, or an empty string when the
            match names none. The cell lists the assistants as well, and they
            are of no interest here.
        """
        officials = self.read_list_out_of_one_cell(
            match.get(WyscoutEventFile.OFFICIAL_LIST_COLUMN, "")
        )
        for official in officials:
            if (
                official.get(WyscoutEventFile.OFFICIAL_ROLE_FIELD)
                == WyscoutEventFile.MAIN_REFEREE_ROLE
            ):
                return self.as_identifier(
                    str(official.get(WyscoutEventFile.OFFICIAL_IDENTIFIER_FIELD))
                )
        return ""

    def name_every_counted_player(
        self, per_player: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Put the match around every counted player, with names for the numbers.

        Args:
            per_player: One row per player of a match, keyed by game, player
                and team identifier, with whatever was counted alongside.
            identities: The prepared match table, which names both teams and
                says which of them played at home.

        Returns:
            The counts with the columns of their match beside them and a
            team_name, opponent_name and player_name added. A player whose
            match is in no match file drops out: the row could name neither
            the opponent nor the day it was played.
        """
        of_named_matches = per_player.merge(identities, on="game_identifier")
        plays_at_home = (
            of_named_matches["team_identifier"]
            == of_named_matches["home_team_identifier"]
        )
        team_names = self.read_team_names()
        return of_named_matches.assign(
            team_name=self.name_every_identifier(
                of_named_matches["team_identifier"], team_names
            ),
            opponent_name=self.name_every_identifier(
                of_named_matches["away_team_identifier"].where(
                    plays_at_home, of_named_matches["home_team_identifier"]
                ),
                team_names,
            ),
            player_name=self.name_every_identifier(
                of_named_matches["player_identifier"], self.read_player_names()
            ),
        )

    def name_every_identifier(
        self, identifiers: pd.Series, names: dict[str, str]
    ) -> pd.Series:
        """Look every identifier up, and leave the identifier where none is known."""
        return identifiers.map(names).fillna(identifiers)

    def read_the_card_of_every_event(self, tag_lists: pd.Series) -> pd.DataFrame:
        """Say of a whole column of tag cells which cards each one carries.

        A tag cell holds numbers among other text, and a card tag has to be
        matched as a whole number: 1702 is a yellow, but a cell holding 17020
        carries no card at all.

        Returns:
            One boolean column per kind of card, in the order the cards are
            counted in.
        """
        return pd.DataFrame(
            {
                card_name: tag_lists.str.contains(
                    WyscoutEventFile.EXACT_NUMBER_PATTERN.format(number=tag),
                    regex=True,
                )
                for tag, card_name in WyscoutEventFile.CARD_OF_TAG.items()
            },
            index=tag_lists.index,
        )

    def read_every_card_and_foul(self) -> pd.DataFrame:
        """Read every foul and every carded event out of the raw event files.

        The seven event files hold half a gigabyte between them, but each one
        is a table and everything counted over them is a group by, so they are
        read whole rather than streamed row by row.

        Returns:
            One row per event that was a foul or carried a card, with a one or
            a zero under each of the counted names. An event that names no
            player is kept: a card of a whole bench belongs to no player but
            still counts towards the team.
        """
        of_every_file = [
            self._read_the_cards_and_fouls_of_one_file(event_file)
            for event_file in sorted(
                WyscoutEventFile.SOURCE_FOLDER.glob(WyscoutEventFile.EVENT_FILE_PATTERN)
            )
        ]
        return pd.concat(of_every_file, ignore_index=True)

    def _read_the_cards_and_fouls_of_one_file(self, event_file: Path) -> pd.DataFrame:
        """Read the fouls and cards out of the events of one competition."""
        raw_events = pd.read_csv(
            event_file,
            usecols=list(WyscoutEventFile.EVENT_COLUMNS_TO_READ),
            dtype=str,
            keep_default_na=False,
            encoding=CsvFileSetting.ENCODING,
            encoding_errors=CsvFileSetting.IGNORE_BROKEN_CHARACTERS,
        )
        cards = self.read_the_card_of_every_event(
            raw_events[WyscoutEventFile.TAG_LIST_COLUMN]
        )
        player_identifier = self.identifier_of_every_row(
            raw_events[WyscoutEventFile.PLAYER_IDENTIFIER_COLUMN]
        )
        is_a_foul = (
            raw_events[WyscoutEventFile.EVENT_NAME_COLUMN]
            == WyscoutEventFile.FOUL_EVENT_NAME
        )
        marked = pd.DataFrame(
            {
                "game_identifier": self.identifier_of_every_row(
                    raw_events[WyscoutEventFile.MATCH_IDENTIFIER_COLUMN]
                ),
                "team_identifier": self.identifier_of_every_row(
                    raw_events[WyscoutEventFile.TEAM_IDENTIFIER_COLUMN]
                ),
                "player_identifier": player_identifier,
                EventSourceSetting.FOUL_NAME: is_a_foul.astype(int),
                **{name: cards[name].astype(int) for name in cards.columns},
            }
        )
        counts_towards_anything = is_a_foul.astype(bool) | cards.any(axis="columns")
        return marked[counts_towards_anything]

    def mirror_along_the_pitch(self, distance_from_the_goal: float) -> float:
        """Mirror a coordinate, because Wyscout attacks the other way.

        Args:
            distance_from_the_goal: The x value as SPADL stores it, counted
                from the goal the team attacks.

        Returns:
            The x value counted the way the rest of the project counts it.
        """
        return WyscoutEventFile.PITCH_LENGTH_IN_METRES - distance_from_the_goal

    def _read_readable_lookup(
        self, file_name: str, value_column: str
    ) -> dict[str, str]:
        """Read a lookup and turn its escaped characters into real ones."""
        return {
            identifier: self._text_normalizer.decode_escaped_characters(value)
            for identifier, value in self._read_lookup(file_name, value_column).items()
        }

    def _read_lookup(self, file_name: str, value_column: str) -> dict[str, str]:
        """Read one identifier to value table of the dataset."""
        source_file = CsvFile(WyscoutEventFile.SOURCE_FOLDER / file_name)
        return {
            self.as_identifier(row[WyscoutEventFile.IDENTIFIER_COLUMN]): row[
                value_column
            ]
            for row in source_file.read_rows()
        }


class StatsBombOpenDataReader:
    """The competitions, matches and events of the StatsBomb open data.

    Nine builders walk the same path: ask which competitions exist, keep the
    men's ones, fetch the matches of a season, then stream the events of every
    match. The events are never kept on disk, they can be fetched again.
    """

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def read_open_competitions(
        self, finished_keys: set[tuple[str, str]]
    ) -> list[StatsBombCompetition]:
        """Read the men's competitions that still have to be done.

        Args:
            finished_keys: Competition and season name pairs a earlier run
                already wrote, usually read back out of the output file.

        Returns:
            One entry per season that is still open, in the order the source
            lists them.

        Raises:
            SystemExit: When the competition list could not be loaded, because
                without it there is nothing to walk.
        """
        answer = self._web_file_downloader.download_json(
            f"{StatsBombOpenDataSource.BASE_URL}/"
            f"{StatsBombOpenDataSource.COMPETITION_FILE_NAME}",
            timeout_in_seconds=StatsBombOpenDataSource.TIMEOUT_IN_SECONDS,
        )
        if not isinstance(answer, list):
            raise SystemExit("The StatsBomb competition list could not be loaded.")
        return [
            competition
            for competition in self._read_competitions(answer)
            if competition.finished_key not in finished_keys
        ]

    def read_matches(self, competition: StatsBombCompetition) -> list[dict[str, Any]]:
        """Read every match of one season, in date order.

        Returns:
            The matches, or an empty list when the season could not be
            loaded. A season that fails is skipped, not fatal.
        """
        answer = self._web_file_downloader.download_json(
            f"{StatsBombOpenDataSource.BASE_URL}/matches/"
            f"{competition.competition_identifier}/"
            f"{competition.season_identifier}.json",
            timeout_in_seconds=StatsBombOpenDataSource.TIMEOUT_IN_SECONDS,
        )
        if not isinstance(answer, list):
            return []
        return sorted(
            answer,
            key=lambda match: str(match.get(StatsBombOpenDataSource.MATCH_DATE_FIELD)),
        )

    def read_events(self, match: dict[str, Any]) -> list[dict[str, Any]]:
        """Read every event of one match.

        Returns:
            The events, or an empty list when the file could not be loaded.
            One missing match must not stop a whole competition.
        """
        answer = self._web_file_downloader.download_json(
            f"{StatsBombOpenDataSource.BASE_URL}/events/{match['match_id']}.json",
            timeout_in_seconds=StatsBombOpenDataSource.TIMEOUT_IN_SECONDS,
        )
        return answer if isinstance(answer, list) else []

    def read_the_day_a_match_was_played(self, match: dict[str, Any]) -> str:
        """Read the day a match was played, without the time part."""
        return str(match.get(StatsBombOpenDataSource.MATCH_DATE_FIELD, ""))[
            : StatsBombOpenDataSource.DATE_LENGTH
        ]

    def read_card_name_of(self, event: dict[str, Any]) -> str | None:
        """Read which card an event carries.

        Returns:
            The name of the card, or None when the event carries none. A card
            shown without a foul sits on a Bad Behaviour event, so both event
            types have to be looked at.
        """
        event_name = event.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        if event_name == StatsBombOpenDataSource.FOUL_EVENT_NAME:
            shown = event.get(StatsBombOpenDataSource.FOUL_FIELD, {})
        elif event_name == StatsBombOpenDataSource.BAD_BEHAVIOUR_EVENT_NAME:
            shown = event.get(StatsBombOpenDataSource.BAD_BEHAVIOUR_FIELD, {})
        else:
            return None
        card_name = shown.get(StatsBombOpenDataSource.CARD_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        return StatsBombOpenDataSource.CARD_OF_NAME.get(card_name or "")

    def read_the_actions_of_one_match(self, match: dict[str, Any]) -> pd.DataFrame:
        """Read the events of one match as the action table every builder groups."""
        return self.read_the_actions_out_of(self.read_events(match), match)

    def read_the_actions_out_of(
        self, events: list[dict[str, Any]], match: dict[str, Any]
    ) -> pd.DataFrame:
        """Turn the events already fetched into the action table.

        StatsBomb hands its events over as JSON documents, one file per match,
        so the step that turns a document into an action is still a walk over
        the events. Everything that comes after it is table work.

        Args:
            events: The events of the match, so a caller that wants more than
                one table out of them pays for the download only once.
            match: The match document those events belong to, for its
                identifier.

        Returns:
            One row per event the reader could place on the pitch, in the
            same shape the Wyscout half is read into.
        """
        actions = [
            action
            for action in (self.read_one_action(event) for event in events)
            if action is not None
        ]
        return pd.DataFrame(
            [
                {
                    "game_identifier": str(
                        match[StatsBombOpenDataSource.MATCH_IDENTIFIER_FIELD]
                    ),
                    **vars(action),
                }
                for action in actions
            ],
            columns=[
                "game_identifier",
                "team_name",
                "kind",
                "was_successful",
                "start_x_in_metres",
                "start_y_in_metres",
                "end_x_in_metres",
                "end_y_in_metres",
                "scoring_team",
                "expected_goals",
                "was_after_a_set_piece",
                "period_number",
                "second_in_period",
                "player_name",
                "player_identifier",
            ],
        )

    def read_the_events_out_of(
        self, events: list[dict[str, Any]], match: dict[str, Any]
    ) -> pd.DataFrame:
        """Turn the events already fetched into one row each.

        The action table throws away everything that says nothing about how a
        team played, and six builders need exactly that: the card that was
        shown, the pressure the ball was under, who received a pass and who
        came on for whom. Those live here instead.

        Returns:
            One row per event, in the order the source lists them.
        """
        return pd.DataFrame(
            [
                {
                    "game_identifier": str(
                        match[StatsBombOpenDataSource.MATCH_IDENTIFIER_FIELD]
                    ),
                    **self._read_one_event_row(event),
                }
                for event in events
            ],
            columns=StatsBombPreparedTable.EVENT_COLUMN_NAMES,
        )

    def _read_one_event_row(self, event: dict[str, Any]) -> dict[str, Any]:
        """Read the one row of the prepared event table that one event fills."""
        pass_details = event.get(StatsBombOpenDataSource.PASS_FIELD, {})
        start_point = self._point_or_nowhere(
            event.get(StatsBombOpenDataSource.LOCATION_FIELD)
        )
        end_point = self._point_or_nowhere(
            self._where_a_move_ended(event, pass_details)
        )
        return {
            "event_name": self._name_of(event, StatsBombOpenDataSource.TYPE_FIELD),
            "team_name": self._name_of(event, StatsBombOpenDataSource.TEAM_FIELD),
            "player_name": self._name_of(event, StatsBombOpenDataSource.PLAYER_FIELD),
            "player_identifier": self._identifier_of(
                event.get(StatsBombOpenDataSource.PLAYER_FIELD, {})
            ),
            "minute_in_match": int(
                event.get(StatsBombOpenDataSource.MINUTE_FIELD) or 0
            ),
            "was_under_pressure": bool(
                event.get(PressResistanceFeature.UNDER_PRESSURE_FIELD)
            ),
            "card_name": self.read_card_name_of(event) or "",
            "start_x_in_metres": start_point[0],
            "start_y_in_metres": start_point[1],
            "end_x_in_metres": end_point[0],
            "end_y_in_metres": end_point[1],
            "pass_type_name": self._name_of(
                pass_details, StatsBombOpenDataSource.TYPE_FIELD
            ),
            "was_a_cross": bool(pass_details.get(StatsBombOpenDataSource.CROSS_FIELD)),
            "was_a_completed_pass": bool(pass_details)
            and StatsBombOpenDataSource.OUTCOME_FIELD not in pass_details,
            "receiver_name": self._name_of(
                pass_details, StatsBombOpenDataSource.RECIPIENT_FIELD
            ),
            "was_a_completed_take_on": self._has_come_out_on_top(
                event, MatchStyleFeature.DRIBBLE_EVENT_NAME
            ),
            "replacement_player_name": self._name_of(
                event.get(SubstitutionFeature.SUBSTITUTION_FIELD, {}),
                SubstitutionFeature.REPLACEMENT_FIELD,
            ),
            "replacement_player_identifier": self._identifier_of(
                event.get(SubstitutionFeature.SUBSTITUTION_FIELD, {}).get(
                    SubstitutionFeature.REPLACEMENT_FIELD, {}
                )
            ),
        }

    def _where_a_move_ended(
        self, event: dict[str, Any], pass_details: dict[str, Any]
    ) -> list[float] | None:
        """Read where a pass or a carry ended, and nowhere for anything else."""
        if pass_details:
            return pass_details.get(StatsBombOpenDataSource.END_LOCATION_FIELD)
        return event.get(ExpectedThreatFeature.CARRY_FIELD, {}).get(
            StatsBombOpenDataSource.END_LOCATION_FIELD
        )

    def _point_or_nowhere(self, point: list[float] | None) -> tuple[float, float]:
        """Convert a point onto our pitch, or say it lies nowhere at all."""
        if not point:
            return (float("nan"), float("nan"))
        return self.point_on_our_pitch_in_metres(point)

    def _name_of(self, holder: dict[str, Any], field_name: str) -> str:
        """Read the name out of a nested field, empty where the field is missing."""
        return (holder.get(field_name) or {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        ) or ""

    def _identifier_of(self, player: dict[str, Any]) -> str:
        """Read the identifier of a player, empty where none is named."""
        identifier = player.get(PlayerMatchMetricFeature.IDENTIFIER_FIELD)
        return "" if identifier is None else str(identifier)

    def read_the_starting_line_ups_out_of(
        self, events: list[dict[str, Any]], match: dict[str, Any]
    ) -> pd.DataFrame:
        """Turn the two starting line up events into one row per player.

        StatsBomb writes a whole line up as a single event holding eleven
        players, so it cannot live in a table of one row per event.

        Returns:
            One row per player who started, with the position they held.
        """
        return pd.DataFrame(
            [
                {
                    "game_identifier": str(
                        match[StatsBombOpenDataSource.MATCH_IDENTIFIER_FIELD]
                    ),
                    "team_name": self._name_of(
                        event, StatsBombOpenDataSource.TEAM_FIELD
                    ),
                    "player_identifier": self._identifier_of(
                        entry.get(StatsBombOpenDataSource.PLAYER_FIELD, {})
                    ),
                    "player_name": self._name_of(
                        entry, StatsBombOpenDataSource.PLAYER_FIELD
                    ),
                    "position_name": self._name_of(
                        entry, PlayerMatchMetricFeature.POSITION_FIELD
                    ),
                }
                for event in events
                if self._name_of(event, StatsBombOpenDataSource.TYPE_FIELD)
                == PlayerMatchMetricFeature.STARTING_LINE_UP_EVENT_NAME
                for entry in event.get(PlayerMatchMetricFeature.TACTICS_FIELD, {}).get(
                    PlayerMatchMetricFeature.LINE_UP_FIELD, []
                )
            ],
            columns=StatsBombPreparedTable.LINE_UP_COLUMN_NAMES,
        )

    def read_the_identity_of_one_match(
        self, match: dict[str, Any], competition: StatsBombCompetition
    ) -> dict[str, Any]:
        """Say which match this is, in the words every calculator joins on."""
        return {
            "game_identifier": str(
                match[StatsBombOpenDataSource.MATCH_IDENTIFIER_FIELD]
            ),
            "competition_name": competition.competition_name,
            "season_name": competition.season_name,
            "match_date": self.read_the_day_a_match_was_played(match),
            "home_team_name": match[StatsBombOpenDataSource.HOME_TEAM_FIELD][
                StatsBombOpenDataSource.HOME_TEAM_NAME_FIELD
            ],
            "away_team_name": match[StatsBombOpenDataSource.AWAY_TEAM_FIELD][
                StatsBombOpenDataSource.AWAY_TEAM_NAME_FIELD
            ],
            "referee_name": self._name_of(match, StatsBombOpenDataSource.REFEREE_FIELD),
        }

    def read_one_action(self, event: dict[str, Any]) -> MatchAction | None:
        """Read one event into the action shape both sources are counted in.

        Returns:
            The action with its coordinates in metres, or None for an event
            that says nothing about how a team played, and for one the source
            placed nowhere on the pitch.
        """
        event_name = event.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        team_name = event.get(StatsBombOpenDataSource.TEAM_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        if not team_name:
            return None
        if event_name == MatchStyleFeature.OWN_GOAL_FOR_EVENT_NAME:
            return self._build_the_action_of_an_own_goal(event, team_name)
        location = event.get(StatsBombOpenDataSource.LOCATION_FIELD)
        if not location:
            return None
        if event_name == MatchStyleFeature.PASS_EVENT_NAME:
            return self._build_the_action_of_a_pass(event, team_name, location)
        if event_name == MatchStyleFeature.SHOT_EVENT_NAME:
            return self._shot_action(event, team_name, location)
        return self._build_the_action_of_a_defensive_move(
            event, event_name, team_name, location
        )

    def _build_the_action_of_an_own_goal(
        self, event: dict[str, Any], team_name: str
    ) -> MatchAction:
        """Build the action of a goal the other side put into its own net."""
        return self._put_one_action_together(
            event,
            team_name,
            MatchStyleFeature.OTHER_KIND,
            was_successful=False,
            start_point=(0.0, 0.0),
            end_point=(0.0, 0.0),
            scoring_team=MatchStyleFeature.SCORED_FOR_THE_ACTING_TEAM,
        )

    def _build_the_action_of_a_pass(
        self, event: dict[str, Any], team_name: str, location: list[float]
    ) -> MatchAction | None:
        """Build the action of a pass, or None when it ends nowhere."""
        pass_details = event.get(StatsBombOpenDataSource.PASS_FIELD, {})
        end_location = pass_details.get(StatsBombOpenDataSource.END_LOCATION_FIELD)
        if not end_location:
            return None
        return self._put_one_action_together(
            event,
            team_name,
            self._pass_kind_of(pass_details),
            was_successful=StatsBombOpenDataSource.OUTCOME_FIELD not in pass_details,
            start_point=self.point_on_our_pitch_in_metres(location),
            end_point=self.point_on_our_pitch_in_metres(end_location),
            scoring_team=None,
        )

    def _pass_kind_of(self, pass_details: dict[str, Any]) -> str:
        """Say whether a pass came from a set piece, was a cross, or neither."""
        pass_type = pass_details.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        if pass_type in MatchStyleFeature.SET_PIECE_PASS_NAMES:
            return MatchStyleFeature.SET_PIECE_PASS_KIND
        if pass_details.get(StatsBombOpenDataSource.CROSS_FIELD):
            return MatchStyleFeature.CROSS_KIND
        return MatchStyleFeature.OPEN_PASS_KIND

    def _shot_action(
        self, event: dict[str, Any], team_name: str, location: list[float]
    ) -> MatchAction:
        """Build the action of a shot, with its expected goals."""
        shot_details = event.get(StatsBombOpenDataSource.SHOT_FIELD, {})
        shot_type = shot_details.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        was_a_goal = (
            shot_details.get(StatsBombOpenDataSource.OUTCOME_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            == MatchStyleFeature.GOAL_OUTCOME_NAME
        )
        play_pattern = event.get(StatsBombOpenDataSource.PLAY_PATTERN_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        point = self.point_on_our_pitch_in_metres(location)
        return self._put_one_action_together(
            event,
            team_name,
            (
                MatchStyleFeature.PENALTY_SHOT_KIND
                if shot_type == MatchStyleFeature.PENALTY_SHOT_NAME
                else MatchStyleFeature.SHOT_KIND
            ),
            was_successful=was_a_goal,
            start_point=point,
            end_point=point,
            scoring_team=(
                MatchStyleFeature.SCORED_FOR_THE_ACTING_TEAM if was_a_goal else None
            ),
            expected_goals=self._expected_goals_of(shot_details),
            was_after_a_set_piece=(
                play_pattern in MatchStyleFeature.SET_PIECE_SHOT_PATTERNS
            ),
        )

    def _expected_goals_of(self, shot_details: dict[str, Any]) -> float | None:
        """Read the expected goals of a shot, or None when the source gives none."""
        value = shot_details.get(MatchStyleFeature.EXPECTED_GOALS_FIELD)
        return float(value) if value is not None else None

    def _build_the_action_of_a_defensive_move(
        self,
        event: dict[str, Any],
        event_name: str,
        team_name: str,
        location: list[float],
    ) -> MatchAction | None:
        """Build a tackle, an interception, a foul, a clearance or a take on."""
        kind = self._defensive_kind_of(event, event_name)
        if kind is None:
            return None
        point = self.point_on_our_pitch_in_metres(location)
        return self._put_one_action_together(
            event,
            team_name,
            kind,
            was_successful=self._has_come_out_on_top(event, event_name),
            start_point=point,
            end_point=point,
            scoring_team=None,
        )

    def _defensive_kind_of(self, event: dict[str, Any], event_name: str) -> str | None:
        """Name the kind of an event, or None when it says nothing about style."""
        if event_name == MatchStyleFeature.DUEL_EVENT_NAME:
            duel_type = (
                event.get(StatsBombOpenDataSource.DUEL_FIELD, {})
                .get(StatsBombOpenDataSource.TYPE_FIELD, {})
                .get(StatsBombOpenDataSource.NAME_FIELD)
            )
            if duel_type == MatchStyleFeature.TACKLE_DUEL_NAME:
                return MatchStyleFeature.TACKLE_KIND
            return None
        return MatchStyleFeature.KIND_OF_STATSBOMB_EVENT.get(event_name)

    def _has_come_out_on_top(self, event: dict[str, Any], event_name: str) -> bool:
        """Return True when the player came out of the action on top.

        Only a take on can be lost in a way that matters here, so everything
        else counts as won.
        """
        if event_name != MatchStyleFeature.DRIBBLE_EVENT_NAME:
            return True
        outcome = event.get(StatsBombOpenDataSource.DRIBBLE_FIELD, {}).get(
            StatsBombOpenDataSource.OUTCOME_FIELD, {}
        )
        return (
            outcome.get(StatsBombOpenDataSource.NAME_FIELD)
            == MatchStyleFeature.COMPLETED_DRIBBLE_NAME
        )

    def _put_one_action_together(
        self,
        event: dict[str, Any],
        team_name: str,
        kind: str,
        was_successful: bool,
        start_point: tuple[float, float],
        end_point: tuple[float, float],
        scoring_team: str | None,
        expected_goals: float | None = None,
        was_after_a_set_piece: bool = False,
    ) -> MatchAction:
        """Put the parts of one action together, with the time it happened."""
        return MatchAction(
            team_name=team_name,
            kind=kind,
            was_successful=was_successful,
            start_x_in_metres=start_point[0],
            start_y_in_metres=start_point[1],
            end_x_in_metres=end_point[0],
            end_y_in_metres=end_point[1],
            scoring_team=scoring_team,
            expected_goals=expected_goals,
            was_after_a_set_piece=was_after_a_set_piece,
            period_number=int(event.get(StatsBombOpenDataSource.PERIOD_FIELD) or 1),
            second_in_period=(
                (event.get(StatsBombOpenDataSource.MINUTE_FIELD) or 0)
                * MatchStyleFeature.SECONDS_PER_MINUTE
                + (event.get(StatsBombOpenDataSource.SECOND_FIELD) or 0)
            ),
            player_name=event.get(StatsBombOpenDataSource.PLAYER_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            or "",
            player_identifier=str(
                event.get(StatsBombOpenDataSource.PLAYER_FIELD, {}).get(
                    PlayerMatchMetricFeature.IDENTIFIER_FIELD, ""
                )
            ),
        )

    def point_on_our_pitch_in_metres(self, point: list[float]) -> tuple[float, float]:
        """Convert a point off the StatsBomb pitch onto the one used everywhere.

        StatsBomb counts on 120 by 80, everything else in this project counts
        in metres on 105 by 68.
        """
        return (
            point[0]
            / StatsBombOpenDataSource.PITCH_LENGTH
            * PitchGeometry.LENGTH_IN_METRES,
            point[1]
            / StatsBombOpenDataSource.PITCH_WIDTH
            * PitchGeometry.WIDTH_IN_METRES,
        )

    def _read_competitions(self, answer: list[Any]) -> list[StatsBombCompetition]:
        """Turn the answer into competitions, keeping the men's ones."""
        return [
            StatsBombCompetition(
                competition_identifier=entry[
                    StatsBombOpenDataSource.COMPETITION_IDENTIFIER_FIELD
                ],
                season_identifier=entry[
                    StatsBombOpenDataSource.SEASON_IDENTIFIER_FIELD
                ],
                competition_name=entry.get(
                    StatsBombOpenDataSource.COMPETITION_NAME_FIELD, ""
                ),
                season_name=str(
                    entry.get(StatsBombOpenDataSource.SEASON_NAME_FIELD, "")
                ),
            )
            for entry in answer
            if entry.get(StatsBombOpenDataSource.GENDER_FIELD)
            == StatsBombOpenDataSource.WANTED_GENDER
        ]


class WorldCupTeamNameReader:
    """The team names of the 2026 World Cup, in a usable form.

    Three fetchers need the same list. All of them have to take the FootyStats
    suffix off the name before they can use it in a search query or an article
    title.
    """

    def read_team_names(self) -> list[str]:
        """Read every team name once, sorted, without the FootyStats suffix.

        Returns:
            The 48 names, ready to be used in a search query or an article
            title. An empty list when the team file has not been downloaded
            yet.
        """
        source_file = CsvFile(WorldCupTeamListSource.TEAM_FILE)
        return sorted(
            {
                self.take_the_suffix_off(row[WorldCupTeamListSource.TEAM_NAME_COLUMN])
                for row in source_file.read_rows()
            }
        )

    def take_the_suffix_off(self, raw_team_name: str) -> str:
        """Cut the FootyStats suffix off, so Turkey National Team becomes Turkey.

        Args:
            raw_team_name: The name as the team file writes it.

        Returns:
            The plain country name, trimmed. A name that never carried the
            suffix comes back unchanged.
        """
        return re.sub(
            WorldCupTeamListSource.NATIONAL_TEAM_SUFFIX_PATTERN,
            "",
            raw_team_name.strip(),
            flags=re.IGNORECASE,
        )
