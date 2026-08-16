"""All shared helper classes of the whole project live in this file.

Anything more than one class needs belongs here, never copied into a second
place. Together with constant.py and data_class.py these are the three files
that hold many small classes on purpose.

The classes are sorted so that a class only ever uses one above it:
   1. TextNormalizer           compare two spellings of the same name
   2. DateNormalizer           one date format out of the many sources use
   3. ConfederationLookup      which confederation a national team is in
   4. ApiKeyReader             get a key without putting it into the code
   5. GeographyCalculator      distance and time zone between two places
   6. CsvFile                  read and write a CSV file, resumable
   7. SharedFeatureFile        one file that both event sources write into
   8. MatchDisciplineCounter   fouls and cards, counted the same way by both
   9. MatchStyleCalculator     the actions of a match to two style rows
  10. PassingLaneCounter       the passes between two players of a team
  11. PassingNetworkCalculator the passing network of a team, summarised
  12. PlayerMatchMetricCalculator what one player did in one match
  13. ExpectedThreatGrid       what a place on the pitch is worth
  14. ExpectedThreatGridFile   that grid on disk, for both sources
  15. PreMatchRollingAverage  the form of a team before its next match
  16. ZipArchiveExtractor      unpack an archive that was downloaded
  17. StadiumLocator           stadium name to city and coordinates
  18. WebFileDownloader        fetch a file over HTTP
  19. WikipediaPageReader      read the raw wikitext of a page
  20. WyscoutDataReader        the lookup tables of the Wyscout dataset
  21. StatsBombOpenDataReader  competitions, matches and events of StatsBomb
  22. WorldCupTeamNameReader   the 48 team names of the 2026 World Cup
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
    StatsBombOpenDataSource,
    TimeStampFormat,
    WebRequestSetting,
    WikipediaSource,
    WorldCupTeamListSource,
    WyscoutEventFile,
)
from wmguru.helpers.data_class import (
    MatchAction,
    MatchIdentity,
    PlayerAppearance,
    StatsBombCompetition,
    TeamPass,
    WyscoutMatchFacts,
    WyscoutNameLookups,
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
        return self._as_iso(self._full_year(year), month, day)

    def _read_a_named_month_date(self, text: str) -> str:
        """Read a date whose month is spelled out, with a time behind it."""
        tokens = text.replace(TimeStampFormat.DASH, " ").split()
        if len(tokens) < 3:
            return ""
        month = TimeStampFormat.MONTH_OF_ABBREVIATION.get(tokens[0][:3].lower())
        if month is None:
            return ""
        try:
            return self._as_iso(int(tokens[2]), month, int(tokens[1]))
        except ValueError:
            return ""

    def _full_year(self, year: int) -> int:
        """Turn a two digit year into a full one.

        The odds files reach back to 1993, so a year of 90 or more belongs to
        the last century and anything below it to this one.
        """
        if year >= 100:
            return year
        if year >= TimeStampFormat.LAST_CENTURY_FROM:
            return 1900 + year
        return 2000 + year

    def _as_iso(self, year: int, month: int, day: int) -> str:
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

    def stream_rows(self) -> Iterator[dict[str, str]]:
        """Walk the file row by row without holding it in memory.

        The Wyscout event files are gigabytes once unpacked, so anything that
        reads them has to stream. Use read_rows only for a file that comfortably
        fits in memory, such as a lookup table.

        Yields:
            One dictionary per data row, keyed by the header line. Nothing at
            all when the file does not exist yet.
        """
        if not self._target_file.exists():
            return
        with self._target_file.open(
            encoding=CsvFileSetting.ENCODING,
            newline=CsvFileSetting.NEW_LINE,
            errors=CsvFileSetting.IGNORE_BROKEN_CHARACTERS,
        ) as file_handle:
            yield from csv.DictReader(file_handle)

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
        with self._open(CsvFileSetting.WRITE_MODE) as writer:
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
        with self._open(CsvFileSetting.APPEND_MODE, write_header=file_is_new) as writer:
            yield writer

    @contextlib.contextmanager
    def _open(self, mode: str, write_header: bool = True) -> Iterator[Any]:
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

    def read_own_rows(self) -> list[dict[str, Any]]:
        """Read what this source wrote in an earlier run."""
        return [
            row
            for row in self._csv_file.read_rows()
            if row.get(EventSourceSetting.SOURCE_COLUMN) == self._source_name
        ]

    def read_rows_of_the_other_source(self) -> list[dict[str, Any]]:
        """Read what the other source wrote, so this run does not lose it.

        Returns:
            Every row another source is responsible for. An empty list when
            the file does not exist yet.
        """
        return [
            row
            for row in self._csv_file.read_rows()
            if row.get(EventSourceSetting.SOURCE_COLUMN) != self._source_name
        ]

    def read_finished_keys(self) -> set[tuple[str, str]]:
        """Read which competition and season this source already covered.

        Returns:
            One competition and season pair per finished season, so a stopped
            run knows what to skip. Only rows of this source count; what the
            other half did is none of its business, otherwise it would skip a
            season it never touched.
        """
        return {
            (
                str(row.get(EventSourceSetting.COMPETITION_COLUMN)),
                str(row.get(EventSourceSetting.SEASON_COLUMN)),
            )
            for row in self.read_own_rows()
        }

    def write_keeping_the_other_source(self, own_rows: list[dict[str, Any]]) -> int:
        """Write this source's rows without dropping the other source's.

        Args:
            own_rows: Everything this source produced. It replaces whatever
                this source wrote before, and nothing else.

        Returns:
            How many rows the file holds afterwards, both sources counted.
        """
        all_rows = own_rows + self.read_rows_of_the_other_source()
        self._csv_file.write_dict_rows(self._in_a_fixed_order(all_rows))
        return len(all_rows)

    def _in_a_fixed_order(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort the rows the one way this file is always sorted.

        Two runs over the same data then give two identical files, so a diff
        between them means something.
        """
        return sorted(
            rows,
            key=lambda row: tuple(str(row.get(name)) for name in self._sort_key_names),
        )


class MatchDisciplineCounter:
    """Fouls and cards, counted per player and folded into one match row.

    Both event sources end up with the same numbers, so both count into the
    same shape and both add the two sides up the same way. Only where the
    fouls and cards are read differs, and that is each source's own business.
    """

    def empty_counter(self) -> dict[str, int]:
        """Build a counter holding a zero for fouls and every kind of card."""
        return {name: 0 for name in MatchDisciplineFeature.COUNTED_NAMES}

    def summarise_both_sides(
        self, home_counter: dict[str, int], away_counter: dict[str, int]
    ) -> dict[str, int]:
        """Turn the two counters of a match into the columns of a match row.

        Returns:
            The fouls and cards of both sides. A red counts a second yellow as
            well, because both end with a player leaving the pitch.
        """
        return {
            "home_fouls": home_counter[EventSourceSetting.FOUL_NAME],
            "away_fouls": away_counter[EventSourceSetting.FOUL_NAME],
            "home_yellow": home_counter[EventSourceSetting.YELLOW_NAME],
            "home_red": self._sendings_off_of(home_counter),
            "away_yellow": away_counter[EventSourceSetting.YELLOW_NAME],
            "away_red": self._sendings_off_of(away_counter),
            "total_cards": sum(
                home_counter[name] + away_counter[name]
                for name in MatchDisciplineFeature.CARD_NAMES
            ),
        }

    def _sendings_off_of(self, counter: dict[str, int]) -> int:
        """Count how many players of one side had to leave the pitch."""
        return (
            counter[EventSourceSetting.RED_NAME]
            + counter[EventSourceSetting.SECOND_YELLOW_NAME]
        )


class MatchStyleCalculator:
    """The actions of a match, as two rows, one per team.

    Both event sources are read into the same action first, so the whole
    calculation stands here once. A number that needs the other side, such as
    the share of the passes, is why both teams are counted together.
    """

    def calculate_rows_of_one_match(
        self,
        actions: list[MatchAction],
        identity: MatchIdentity,
        source_name: str,
        has_expected_goals: bool,
    ) -> list[dict[str, Any]]:
        """Build the row of each team of one match.

        Args:
            actions: Every action of the match, both teams together.
            identity: Which match this is, with both teams already named.
            source_name: Which of the two event sources the actions came out
                of, written into the source column.
            has_expected_goals: False for a source that carries none, which
                leaves those columns empty rather than writing a zero.

        Returns:
            Two rows, or fewer when a team has no pass at all, which means
            its half of the match never arrived.
        """
        counts = self._count_both_teams(actions, identity)
        rows: list[dict[str, Any]] = []
        for team_name, opponent_name, is_home in (
            (identity.home_team_name, identity.away_team_name, 1),
            (identity.away_team_name, identity.home_team_name, 0),
        ):
            if not counts[team_name]["passes_any"]:
                continue
            rows.append(
                self._build_row(
                    counts[team_name],
                    counts[opponent_name],
                    team_name,
                    opponent_name,
                    is_home,
                    identity,
                    source_name,
                    has_expected_goals,
                )
            )
        return rows

    def fill_expected_goals_against(
        self, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Copy the expected goals of each row onto the other row of its match.

        What a team conceded is what the other side created, so it is not
        counted again, only carried across.
        """
        rows_of_game: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            rows_of_game.setdefault(str(row.get("game_id")), []).append(row)
        for both_rows in rows_of_game.values():
            for row in both_rows:
                other_row = next(
                    (other for other in both_rows if other is not row), None
                )
                self._write_conceded_columns(row, other_row)
        return rows

    def _write_conceded_columns(
        self, row: dict[str, Any], other_row: dict[str, Any] | None
    ) -> None:
        """Write what one team conceded, out of what the other one created."""
        created = self._as_number(other_row and other_row.get("expected_goals"))
        non_penalty = self._as_number(
            other_row and other_row.get("non_penalty_expected_goals")
        )
        shots = self._as_number(other_row and other_row.get("shots"))
        places = MatchStyleFeature.SHARE_DECIMAL_PLACES
        row["expected_goals_against"] = (
            round(created, places) if created is not None else ""
        )
        row["non_penalty_expected_goals_against"] = (
            round(non_penalty, places) if non_penalty is not None else ""
        )
        row["expected_goals_against_per_shot"] = (
            round(created / shots, places) if created is not None and shots else ""
        )

    def _as_number(self, value: Any) -> float | None:
        """Read a cell back as a number, or None when it holds no number."""
        try:
            return float(value) if value not in (None, "", "None", False) else None
        except (TypeError, ValueError):
            return None

    def _count_both_teams(
        self, actions: list[MatchAction], identity: MatchIdentity
    ) -> dict[str, dict[str, float]]:
        """Count every action of both teams, and their passes per score line."""
        counts = {
            identity.home_team_name: self._empty_count(),
            identity.away_team_name: self._empty_count(),
        }
        for action in actions:
            if action.team_name in counts:
                self._add_one_action(counts[action.team_name], action)
        self._add_the_passes_per_score_line(actions, identity, counts)
        return counts

    def _empty_count(self) -> dict[str, float]:
        """Build a count that holds a zero for everything that is counted."""
        return {
            name: 0.0
            for name in (
                "passes_any",
                "passes_open_play",
                "passes_set_piece",
                "crosses",
                "into_box",
                "forward_metres",
                "passes_in_own_half",
                "final_third",
                "defensive_actions_high",
                "defensive_height_sum",
                "defensive_action_count",
                "take_ons",
                "take_ons_won",
                "shots",
                "shots_in_box",
                "expected_goals",
                "non_penalty_expected_goals",
                "set_piece_expected_goals",
                "passes_while_leading",
                "passes_while_level",
                "passes_while_trailing",
            )
        }

    def _add_one_action(self, count: dict[str, float], action: MatchAction) -> None:
        """Add one action to the count of the team that played it."""
        if action.kind in MatchStyleFeature.EVERY_PASS_KIND:
            count["passes_any"] += 1
        if action.kind in MatchStyleFeature.OPEN_PLAY_PASS_KINDS:
            self._add_one_open_play_pass(count, action)
        elif action.kind == MatchStyleFeature.SET_PIECE_PASS_KIND:
            count["passes_set_piece"] += 1
        elif (
            action.kind in MatchStyleFeature.PRESSING_DEFENCE_KINDS
            and action.start_x_in_metres >= MatchStyleFeature.PRESSING_DEFENCE_MINIMUM_X
        ):
            count["defensive_actions_high"] += 1
        if action.kind in MatchStyleFeature.DEFENSIVE_LINE_KINDS:
            count["defensive_height_sum"] += action.start_x_in_metres
            count["defensive_action_count"] += 1
        if action.kind == MatchStyleFeature.TAKE_ON_KIND:
            count["take_ons"] += 1
            count["take_ons_won"] += 1 if action.was_successful else 0
        if action.kind in MatchStyleFeature.SHOT_KINDS:
            self._add_one_shot(count, action)

    def _add_one_open_play_pass(
        self, count: dict[str, float], action: MatchAction
    ) -> None:
        """Add a pass that was played out of open play rather than a set piece."""
        count["passes_open_play"] += 1
        count["forward_metres"] += action.end_x_in_metres - action.start_x_in_metres
        if self._is_in_the_box(action.end_x_in_metres, action.end_y_in_metres):
            count["into_box"] += 1
        if action.kind == MatchStyleFeature.CROSS_KIND:
            count["crosses"] += 1
        if action.start_x_in_metres <= MatchStyleFeature.PRESSING_PASS_MAXIMUM_X:
            count["passes_in_own_half"] += 1
        if action.start_x_in_metres >= MatchStyleFeature.FINAL_THIRD_START_X:
            count["final_third"] += 1

    def _add_one_shot(self, count: dict[str, float], action: MatchAction) -> None:
        """Add a shot and, when the source carries it, its expected goals."""
        count["shots"] += 1
        if self._is_in_the_box(action.start_x_in_metres, action.start_y_in_metres):
            count["shots_in_box"] += 1
        if action.expected_goals is None:
            return
        count["expected_goals"] += action.expected_goals
        if action.kind != MatchStyleFeature.PENALTY_SHOT_KIND:
            count["non_penalty_expected_goals"] += action.expected_goals
        if action.was_after_a_set_piece:
            count["set_piece_expected_goals"] += action.expected_goals

    def _is_in_the_box(self, x_in_metres: float, y_in_metres: float) -> bool:
        """Return True when a point lies inside the penalty area being attacked."""
        return (
            x_in_metres >= MatchStyleFeature.BOX_START_X
            and MatchStyleFeature.BOX_MINIMUM_Y
            <= y_in_metres
            <= MatchStyleFeature.BOX_MAXIMUM_Y
        )

    def _add_the_passes_per_score_line(
        self,
        actions: list[MatchAction],
        identity: MatchIdentity,
        counts: dict[str, dict[str, float]],
    ) -> None:
        """Count each pass under the score line that stood when it was played.

        A team that is ahead lets the other one have the ball, so the plain
        share of the passes says as much about the score as about the style.
        """
        goals_of_team = {
            identity.home_team_name: 0,
            identity.away_team_name: 0,
        }
        for action in sorted(actions, key=lambda one: one.order_in_the_match):
            if (
                action.team_name in counts
                and action.kind in MatchStyleFeature.OPEN_PLAY_PASS_KINDS
            ):
                counts[action.team_name][
                    self._score_line_name(action.team_name, identity, goals_of_team)
                ] += 1
            self._add_a_goal(action, identity, goals_of_team)

    def _score_line_name(
        self,
        team_name: str,
        identity: MatchIdentity,
        goals_of_team: dict[str, int],
    ) -> str:
        """Say whether a team was ahead, level or behind at this moment."""
        opponent_name = (
            identity.away_team_name
            if team_name == identity.home_team_name
            else identity.home_team_name
        )
        lead = goals_of_team[team_name] - goals_of_team[opponent_name]
        if lead > 0:
            return "passes_while_leading"
        return "passes_while_level" if lead == 0 else "passes_while_trailing"

    def _add_a_goal(
        self,
        action: MatchAction,
        identity: MatchIdentity,
        goals_of_team: dict[str, int],
    ) -> None:
        """Move the score on, if this action was a goal at all."""
        if action.scoring_team is None:
            return
        other_team = (
            identity.away_team_name
            if action.team_name == identity.home_team_name
            else identity.home_team_name
        )
        scorer = (
            action.team_name
            if action.scoring_team == MatchStyleFeature.SCORED_FOR_THE_ACTING_TEAM
            else other_team
        )
        if scorer in goals_of_team:
            goals_of_team[scorer] += 1

    def _build_row(
        self,
        count: dict[str, float],
        opponent_count: dict[str, float],
        team_name: str,
        opponent_name: str,
        is_home: int,
        identity: MatchIdentity,
        source_name: str,
        has_expected_goals: bool,
    ) -> dict[str, Any]:
        """Turn the count of one team into its output row."""
        share_places = MatchStyleFeature.SHARE_DECIMAL_PLACES
        passes_per_score_line = (
            count["passes_while_leading"]
            + count["passes_while_level"]
            + count["passes_while_trailing"]
        )
        return {
            EventSourceSetting.SOURCE_COLUMN: source_name,
            "game_id": identity.game_identifier,
            "competition": identity.competition_name,
            "season": identity.season_name,
            "date": identity.match_date,
            "team": team_name,
            "opponent": opponent_name,
            "is_home": is_home,
            "passes": int(count["passes_any"]),
            "pass_share": self._share(
                count["passes_any"],
                count["passes_any"] + opponent_count["passes_any"],
                share_places,
            ),
            "field_tilt": self._share(
                count["final_third"],
                count["final_third"] + opponent_count["final_third"],
                share_places,
            ),
            "passes_per_defensive_action": self._share(
                opponent_count["passes_in_own_half"],
                count["defensive_actions_high"],
                MatchStyleFeature.PRESSING_DECIMAL_PLACES,
            ),
            "defensive_action_height_in_metres": self._share(
                count["defensive_height_sum"],
                count["defensive_action_count"],
                MatchStyleFeature.HEIGHT_DECIMAL_PLACES,
            ),
            "passes_into_box": int(count["into_box"]),
            "directness_in_metres": self._share(
                count["forward_metres"],
                count["passes_open_play"],
                MatchStyleFeature.PRESSING_DECIMAL_PLACES,
            ),
            "set_piece_pass_share": self._share(
                count["passes_set_piece"], count["passes_any"], share_places
            ),
            "take_on_success_rate": self._share(
                count["take_ons_won"], count["take_ons"], share_places
            ),
            "crosses": int(count["crosses"]),
            "shots": int(count["shots"]),
            "shots_in_box": int(count["shots_in_box"]),
            **self._expected_goals_columns(count, has_expected_goals),
            "expected_goals_against": "",
            "non_penalty_expected_goals_against": "",
            "expected_goals_against_per_shot": "",
            "pass_share_while_leading": self._share(
                count["passes_while_leading"], passes_per_score_line, share_places
            ),
            "pass_share_while_level": self._share(
                count["passes_while_level"], passes_per_score_line, share_places
            ),
            "pass_share_while_trailing": self._share(
                count["passes_while_trailing"], passes_per_score_line, share_places
            ),
        }

    def _expected_goals_columns(
        self, count: dict[str, float], has_expected_goals: bool
    ) -> dict[str, Any]:
        """Build the four expected goals columns, or leave them empty."""
        if not has_expected_goals:
            return {
                "expected_goals": "",
                "non_penalty_expected_goals": "",
                "expected_goals_per_shot": "",
                "set_piece_expected_goals_share": "",
            }
        places = MatchStyleFeature.SHARE_DECIMAL_PLACES
        return {
            "expected_goals": round(count["expected_goals"], places),
            "non_penalty_expected_goals": round(
                count["non_penalty_expected_goals"], places
            ),
            "expected_goals_per_shot": self._share(
                count["expected_goals"], count["shots"], places
            ),
            "set_piece_expected_goals_share": self._share(
                count["set_piece_expected_goals"], count["expected_goals"], places
            )
            or 0.0,
        }

    def _share(self, numerator: float, denominator: float, places: int) -> Any:
        """Divide, or give an empty cell when there is nothing to divide by.

        Returns:
            The rounded quotient, or an empty string. A zero would claim a
            team pressed nobody when in truth it never had the chance.
        """
        return round(numerator / denominator, places) if denominator else ""


class PassingLaneCounter:
    """The passes between two players, counted and turned into rows.

    Both event sources produce the same edge of the same network, they only
    find the receiver differently, so the counting stands here once.
    """

    def add_one_pass(
        self,
        lanes: dict[tuple[str, str, str], dict[str, float]],
        team_name: str,
        passer_name: str,
        receiver_name: str,
        start_x_in_metres: float,
        end_x_in_metres: float,
    ) -> None:
        """Add one completed pass to the lane between two players."""
        lane = lanes.setdefault(
            (team_name, passer_name, receiver_name),
            {
                "passes": 0.0,
                "forward_passes": 0.0,
                "start_x_sum": 0.0,
                "end_x_sum": 0.0,
            },
        )
        lane["passes"] += 1
        if (
            end_x_in_metres - start_x_in_metres
            > PassingLaneFeature.FORWARD_MINIMUM_METRES
        ):
            lane["forward_passes"] += 1
        lane["start_x_sum"] += start_x_in_metres
        lane["end_x_sum"] += end_x_in_metres

    def build_rows(
        self,
        lanes: dict[tuple[str, str, str], dict[str, float]],
        identity: MatchIdentity,
        source_name: str,
    ) -> list[dict[str, Any]]:
        """Turn the lanes of one match into one row per pair of players."""
        places = PassingLaneFeature.MEAN_DECIMAL_PLACES
        return [
            {
                EventSourceSetting.SOURCE_COLUMN: source_name,
                "game_id": identity.game_identifier,
                "competition": identity.competition_name,
                "season": identity.season_name,
                "date": identity.match_date,
                "team": team_name,
                "passer": passer_name,
                "receiver": receiver_name,
                "passes": int(lane["passes"]),
                "forward_passes": int(lane["forward_passes"]),
                "mean_start_x": round(lane["start_x_sum"] / lane["passes"], places),
                "mean_end_x": round(lane["end_x_sum"] / lane["passes"], places),
            }
            for (team_name, passer_name, receiver_name), lane in lanes.items()
        ]


class PassingNetworkCalculator:
    """The passing network of one team in one match, summarised."""

    def summarise(self, passes: list[TeamPass]) -> dict[str, Any]:
        """Turn the passes of one team into the columns of its row.

        Args:
            passes: Every open play pass of the team, in any order. Must not
                be empty, a team without a pass gets no row at all.

        Returns:
            The whole row apart from the columns that say which match it was.
        """
        passes_per_player = self._count_per_player(passes)
        lanes = self._count_per_lane(passes)
        pass_count = len(passes)
        rate_places = PassingNetworkFeature.RATE_DECIMAL_PLACES
        top_lane, top_lane_count = self._busiest_lane(lanes)
        return {
            "passes": pass_count,
            "pass_success_rate": round(
                sum(1 for one in passes if one.was_successful) / pass_count,
                rate_places,
            ),
            "forward_pass_share": round(
                sum(1 for one in passes if self._was_forward(one)) / pass_count,
                rate_places,
            ),
            "mean_pass_length_in_metres": round(
                sum(self._length_of(one) for one in passes) / pass_count,
                PassingNetworkFeature.LENGTH_DECIMAL_PLACES,
            ),
            "mean_forward_gain_in_metres": round(
                sum(one.forward_gain_in_metres for one in passes) / pass_count,
                PassingNetworkFeature.LENGTH_DECIMAL_PLACES,
            ),
            "players_involved": len(passes_per_player),
            "distinct_lanes": len(lanes),
            "unused_lane_share": self._unused_lane_share(
                len(passes_per_player), len(lanes)
            ),
            "pass_concentration": round(
                self._concentration_of(passes_per_player, pass_count), rate_places
            ),
            "top_player_share": round(
                max(passes_per_player.values()) / pass_count, rate_places
            ),
            "top_lane": top_lane,
            "top_lane_count": top_lane_count,
        }

    def _count_per_player(self, passes: list[TeamPass]) -> dict[str, int]:
        """Count how many passes each player of the team played."""
        passes_per_player: dict[str, int] = {}
        for one_pass in passes:
            passes_per_player[one_pass.passer_name] = (
                passes_per_player.get(one_pass.passer_name, 0) + 1
            )
        return passes_per_player

    def _count_per_lane(self, passes: list[TeamPass]) -> dict[tuple[str, str], int]:
        """Count how often the ball went from one player to another."""
        lanes: dict[tuple[str, str], int] = {}
        for one_pass in passes:
            if not one_pass.reached_somebody_else:
                continue
            lane = (one_pass.passer_name, one_pass.receiver_name)
            lanes[lane] = lanes.get(lane, 0) + 1
        return lanes

    def _was_forward(self, one_pass: TeamPass) -> bool:
        """Return True when a pass won enough ground to be called forward."""
        return (
            one_pass.forward_gain_in_metres
            > PassingNetworkFeature.FORWARD_MINIMUM_METRES
        )

    def _length_of(self, one_pass: TeamPass) -> float:
        """How far the ball travelled, across the pitch as well as up it."""
        return math.hypot(
            one_pass.forward_gain_in_metres,
            one_pass.end_y_in_metres - one_pass.start_y_in_metres,
        )

    def _unused_lane_share(self, player_count: int, lane_count: int) -> Any:
        """How many of the possible connections between players never happened.

        Returns:
            The share, or an empty cell when a single player played every
            pass, because then there is no connection to miss.
        """
        possible_lanes = player_count * (player_count - 1)
        if not possible_lanes:
            return ""
        return round(
            max(0.0, 1.0 - lane_count / possible_lanes),
            PassingNetworkFeature.RATE_DECIMAL_PLACES,
        )

    def _concentration_of(
        self, passes_per_player: dict[str, int], pass_count: int
    ) -> float:
        """How much of the passing went through few players.

        The squared shares added up, the Herfindahl-Hirschman index. One
        player playing everything gives 1, eleven equal players give 1/11.
        """
        return sum((count / pass_count) ** 2 for count in passes_per_player.values())

    def _busiest_lane(self, lanes: dict[tuple[str, str], int]) -> tuple[str, Any]:
        """Name the connection the ball took most often, and how often.

        Returns:
            The two players and the count, or an empty name and a zero when
            no pass of the team ever reached a team mate.
        """
        if not lanes:
            return "", 0
        (passer_name, receiver_name), count = max(
            lanes.items(), key=lambda lane: lane[1]
        )
        return (
            f"{passer_name}{PassingNetworkFeature.LANE_SEPARATOR}{receiver_name}",
            count,
        )


class PlayerMatchMetricCalculator:
    """What one player did in one match, counted and built into their row.

    Both event sources are read into the same actions first, so what counts
    as a progressive pass or a high recovery is decided here once.
    """

    def empty_counter(self) -> dict[str, float]:
        """Build a counter that holds a zero for everything that is counted."""
        return {
            name: 0.0
            for name in (
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
        }

    def add_one_action(
        self, counter: dict[str, float], action: MatchAction, is_goalkeeper: bool
    ) -> None:
        """Add one action of one player to their counter."""
        if is_goalkeeper:
            self._add_a_goalkeeper_action(counter, action)
        if action.kind in MatchStyleFeature.EVERY_PASS_KIND:
            self._add_one_pass(counter, action, is_goalkeeper)
        if action.kind in MatchStyleFeature.DEFENSIVE_LINE_KINDS:
            counter["defensive_actions"] += 1
            counter["defensive_height_sum"] += action.start_x_in_metres
            if (
                action.start_x_in_metres
                >= PlayerMatchMetricFeature.HIGH_RECOVERY_START_X
            ):
                counter["high_ball_recoveries"] += 1
        if action.kind == MatchStyleFeature.TAKE_ON_KIND:
            counter["take_ons"] += 1
            counter["take_ons_won"] += 1 if action.was_successful else 0
        if action.kind in MatchStyleFeature.SHOT_KINDS:
            counter["shots"] += 1
            if self._is_in_the_box(action.start_x_in_metres, action.start_y_in_metres):
                counter["shots_in_box"] += 1

    def build_row(
        self, counter: dict[str, float], is_goalkeeper: bool
    ) -> dict[str, Any]:
        """Turn the counter of one player into the columns of their row.

        Returns:
            Everything but the columns that say who the player is and which
            match it was. The goalkeeper columns stay empty for an outfield
            player rather than holding a zero, because a zero would read as
            a keeper who did nothing.
        """
        return {
            "passes": int(counter["passes"]),
            "completed_passes": int(counter["completed_passes"]),
            "progressive_passes": int(counter["progressive_passes"]),
            "passes_into_box": int(counter["passes_into_box"]),
            "deep_completions": int(counter["deep_completions"]),
            "progression_value": round(
                counter["progression_value"],
                PlayerMatchMetricFeature.PROGRESSION_DECIMAL_PLACES,
            ),
            "defensive_actions": int(counter["defensive_actions"]),
            "defensive_action_height_in_metres": self._mean_height(
                counter["defensive_height_sum"], counter["defensive_actions"]
            ),
            "high_ball_recoveries": int(counter["high_ball_recoveries"]),
            "take_ons": int(counter["take_ons"]),
            "take_ons_won": int(counter["take_ons_won"]),
            "shots": int(counter["shots"]),
            "shots_in_box": int(counter["shots_in_box"]),
            **self._goalkeeper_columns(counter, is_goalkeeper),
        }

    def _add_a_goalkeeper_action(
        self, counter: dict[str, float], action: MatchAction
    ) -> None:
        """Add an action of a keeper, and note how far out they played it."""
        counter["goalkeeper_actions"] += 1
        counter["goalkeeper_height_sum"] += action.start_x_in_metres
        if (
            action.start_x_in_metres
            > PlayerMatchMetricFeature.PENALTY_AREA_LENGTH_IN_METRES
        ):
            counter["goalkeeper_actions_outside_box"] += 1

    def _add_one_pass(
        self, counter: dict[str, float], action: MatchAction, is_goalkeeper: bool
    ) -> None:
        """Add a pass, and what it was worth when it arrived."""
        counter["passes"] += 1
        gained = action.end_x_in_metres - action.start_x_in_metres
        if is_goalkeeper:
            counter["goalkeeper_passes"] += 1
            if gained > PlayerMatchMetricFeature.LONG_PASS_MINIMUM_METRES:
                counter["goalkeeper_long_passes"] += 1
        if not action.was_successful:
            return
        counter["completed_passes"] += 1
        counter["progression_value"] += self._progression_value_of(action)
        if (
            gained >= PlayerMatchMetricFeature.PROGRESSIVE_PASS_MINIMUM_METRES
            and action.end_x_in_metres >= MatchStyleFeature.FINAL_THIRD_START_X
        ):
            counter["progressive_passes"] += 1
        if self._is_in_the_box(action.end_x_in_metres, action.end_y_in_metres):
            counter["passes_into_box"] += 1
        if action.end_x_in_metres >= PlayerMatchMetricFeature.DEEP_COMPLETION_START_X:
            counter["deep_completions"] += 1

    def _progression_value_of(self, action: MatchAction) -> float:
        """Weigh the ground a pass won by how near the goal it ended.

        Ten metres won in front of the other box are worth more than ten
        metres won in front of your own, so the gain is multiplied by the
        square of how far up the pitch the ball came to rest.
        """
        gained = max(0.0, action.end_x_in_metres - action.start_x_in_metres)
        share_of_the_pitch = action.end_x_in_metres / PitchGeometry.LENGTH_IN_METRES
        return gained * share_of_the_pitch**2

    def _is_in_the_box(self, x_in_metres: float, y_in_metres: float) -> bool:
        """Return True when a point lies inside the penalty area being attacked."""
        return (
            x_in_metres >= MatchStyleFeature.BOX_START_X
            and MatchStyleFeature.BOX_MINIMUM_Y
            <= y_in_metres
            <= MatchStyleFeature.BOX_MAXIMUM_Y
        )

    def _goalkeeper_columns(
        self, counter: dict[str, float], is_goalkeeper: bool
    ) -> dict[str, Any]:
        """Build the five keeper columns, or leave them empty for anybody else."""
        if not is_goalkeeper:
            return {
                "goalkeeper_actions": "",
                "goalkeeper_actions_outside_box": "",
                "goalkeeper_action_height_in_metres": "",
                "goalkeeper_long_passes": "",
                "goalkeeper_passes": "",
            }
        return {
            "goalkeeper_actions": int(counter["goalkeeper_actions"]),
            "goalkeeper_actions_outside_box": int(
                counter["goalkeeper_actions_outside_box"]
            ),
            "goalkeeper_action_height_in_metres": self._mean_height(
                counter["goalkeeper_height_sum"], counter["goalkeeper_actions"]
            ),
            "goalkeeper_long_passes": int(counter["goalkeeper_long_passes"]),
            "goalkeeper_passes": int(counter["goalkeeper_passes"]),
        }

    def _mean_height(self, height_sum: float, action_count: float) -> Any:
        """How far up the pitch somebody acted on average.

        Returns:
            The mean, or an empty cell when there was no such action at all,
            because a zero would claim they acted on their own goal line.
        """
        if not action_count:
            return ""
        return round(
            height_sum / action_count,
            PlayerMatchMetricFeature.HEIGHT_DECIMAL_PLACES,
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

    def cell_of(self, x_in_metres: float, y_in_metres: float) -> int:
        """Say which cell a place on the pitch falls into.

        Args:
            x_in_metres: Counted towards the goal being attacked.
            y_in_metres: Counted across the pitch.

        Returns:
            The cell, kept inside the grid even for a coordinate the source
            put slightly off the pitch.
        """
        column = self._inside(
            int(
                x_in_metres
                / PitchGeometry.LENGTH_IN_METRES
                * ExpectedThreatFeature.COLUMN_COUNT
            ),
            ExpectedThreatFeature.COLUMN_COUNT,
        )
        row = self._inside(
            int(
                y_in_metres
                / PitchGeometry.WIDTH_IN_METRES
                * ExpectedThreatFeature.ROW_COUNT
            ),
            ExpectedThreatFeature.ROW_COUNT,
        )
        return row * ExpectedThreatFeature.COLUMN_COUNT + column

    def gain_between(self, start_cell: int, end_cell: int) -> float:
        """What moving the ball from one cell to another was worth."""
        return self._values[end_cell] - self._values[start_cell]

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

    def _inside(self, position: int, count: int) -> int:
        """Keep a column or a row inside the grid."""
        return min(count - 1, max(0, position))


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
        values = [0.0] * (
            ExpectedThreatFeature.COLUMN_COUNT * ExpectedThreatFeature.ROW_COUNT
        )
        for row in self._csv_file.read_rows():
            cell = int(row["grid_row"]) * ExpectedThreatFeature.COLUMN_COUNT + int(
                row["grid_column"]
            )
            values[cell] = float(row["expected_threat"])
        return ExpectedThreatGrid(values)

    def write(self, grid: ExpectedThreatGrid) -> None:
        """Write the grid down for the other source to pick up."""
        self._csv_file.write_dict_rows(grid.to_rows())


class PreMatchRollingAverage:
    """The smoothed form of every team, as it stood before the current match.

    A rolling average is only worth anything if it never saw the match it is
    used to predict. This one is therefore asked first and updated second: a
    row carries the state before its own match, and the match only enters the
    state once the row has been written.

    Two averages come out of it, one that fades older matches out gradually
    and one over a fixed number of the most recent ones.
    """

    def __init__(self, fading_weight: float, window_length: int) -> None:
        self._fading_weight = fading_weight
        self._window_length = window_length
        self._faded_average: dict[str, float] = {}
        self._recent_values: dict[str, list[float]] = {}
        self._match_count: dict[str, int] = {}

    def before_the_next_match(self, team_name: str) -> tuple[float, float, int]:
        """Read the state of one team before its next match.

        Returns:
            The faded average, the average over the window, and how many
            matches the team has behind it. A team that has never played
            comes back at zero, which reads as no form either way.
        """
        recent = self._recent_values.get(team_name, [])
        return (
            self._faded_average.get(team_name, 0.0),
            sum(recent) / len(recent) if recent else 0.0,
            self._match_count.get(team_name, 0),
        )

    def add_one_match(self, team_name: str, value: float) -> None:
        """Take one match into the state, after its row has been written."""
        previous = self._faded_average.get(team_name)
        self._faded_average[team_name] = (
            value
            if previous is None
            else self._fading_weight * value + (1.0 - self._fading_weight) * previous
        )
        recent = self._recent_values.setdefault(team_name, [])
        recent.append(value)
        if len(recent) > self._window_length:
            recent.pop(0)
        self._match_count[team_name] = self._match_count.get(team_name, 0) + 1


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

    def stream_actions_of_every_match(
        self, lookups: WyscoutNameLookups
    ) -> Iterator[tuple[str, list[MatchAction]]]:
        """Walk the action file and hand over one match at a time.

        The file holds every action of every match in one stream, sorted by
        match, and is several hundred megabytes. Collecting a match and giving
        it away keeps one match in memory rather than all of them.

        Yields:
            The match identifier and its actions, in the order they were
            played. A match without a single readable action is skipped.
        """
        action_file = CsvFile(
            WyscoutEventFile.SOURCE_FOLDER / WyscoutEventFile.ACTION_FILE_NAME
        )
        current_game = ""
        actions: list[MatchAction] = []
        for row in action_file.stream_rows():
            game_identifier = self.as_identifier(
                row[WyscoutEventFile.ACTION_GAME_COLUMN]
            )
            if game_identifier != current_game:
                if actions:
                    yield current_game, actions
                current_game, actions = game_identifier, []
            action = self.read_one_action(row, lookups)
            if action is not None:
                actions.append(action)
        if actions:
            yield current_game, actions

    def read_one_action(
        self, row: dict[str, str], lookups: WyscoutNameLookups
    ) -> MatchAction | None:
        """Read one row of the action file, in the direction everything else uses.

        Returns:
            The action with its team and player named, or None when a
            coordinate or a time is missing, which happens for the rows the
            conversion could not place on the pitch.
        """
        try:
            start_x = self.mirror_along_the_pitch(
                float(row[WyscoutEventFile.ACTION_START_X_COLUMN])
            )
            end_x = self.mirror_along_the_pitch(
                float(row[WyscoutEventFile.ACTION_END_X_COLUMN])
            )
            start_y = float(row[WyscoutEventFile.ACTION_START_Y_COLUMN])
            end_y = float(row[WyscoutEventFile.ACTION_END_Y_COLUMN])
            period_number = int(float(row[WyscoutEventFile.ACTION_PERIOD_COLUMN]))
            second_in_period = float(row[WyscoutEventFile.ACTION_SECOND_COLUMN])
        except (KeyError, TypeError, ValueError):
            return None

        kind = MatchStyleFeature.KIND_OF_SPADL_TYPE.get(
            row[WyscoutEventFile.ACTION_TYPE_COLUMN], MatchStyleFeature.OTHER_KIND
        )
        result_name = row[WyscoutEventFile.ACTION_RESULT_COLUMN]
        team_identifier = self.as_identifier(row[WyscoutEventFile.ACTION_TEAM_COLUMN])
        player_identifier = self.as_identifier(
            row[WyscoutEventFile.ACTION_PLAYER_COLUMN]
        )
        return MatchAction(
            team_name=lookups.team_names.get(team_identifier, team_identifier),
            kind=kind,
            was_successful=result_name == WyscoutEventFile.SUCCESSFUL_RESULT_NAME,
            start_x_in_metres=start_x,
            start_y_in_metres=start_y,
            end_x_in_metres=end_x,
            end_y_in_metres=end_y,
            scoring_team=self._scoring_team_of(kind, result_name),
            expected_goals=None,
            was_after_a_set_piece=False,
            period_number=period_number,
            second_in_period=second_in_period,
            player_name=lookups.player_names.get(player_identifier, player_identifier),
            player_identifier=player_identifier,
        )

    def _scoring_team_of(self, kind: str, result_name: str) -> str | None:
        """Say who a goal counted for, or None when the action was no goal."""
        if (
            kind in MatchStyleFeature.SHOT_KINDS
            and result_name == WyscoutEventFile.SUCCESSFUL_RESULT_NAME
        ):
            return MatchStyleFeature.SCORED_FOR_THE_ACTING_TEAM
        if result_name == WyscoutEventFile.OWN_GOAL_RESULT_NAME:
            return MatchStyleFeature.SCORED_FOR_THE_OTHER_TEAM
        return None

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

    def read_player_roles(self) -> dict[str, str]:
        """Read the position of every player, by identifier.

        Returns:
            The two letter code of each player, GK, DF, MF or FW. A player
            whose cell holds no code comes back with an empty role.
        """
        role_pattern = re.compile(PlayerMatchMetricFeature.ROLE_CODE_PATTERN)
        source_file = CsvFile(
            WyscoutEventFile.SOURCE_FOLDER / WyscoutEventFile.PLAYER_FILE_NAME
        )
        roles: dict[str, str] = {}
        for row in source_file.read_rows():
            found = role_pattern.search(
                row.get(PlayerMatchMetricFeature.ROLE_COLUMN, "")
            )
            roles[self.as_identifier(row[WyscoutEventFile.IDENTIFIER_COLUMN])] = (
                found.group(1) if found else ""
            )
        return roles

    def read_appearances(self) -> dict[tuple[str, str], PlayerAppearance]:
        """Read who played in which match, and for how many minutes.

        Returns:
            One entry per player and match, keyed by the two identifiers.
            Somebody who stayed on the bench is left out, because a row of
            zeros over zero minutes says nothing.
        """
        source_file = CsvFile(
            WyscoutEventFile.SOURCE_FOLDER
            / PlayerMatchMetricFeature.APPEARANCE_FILE_NAME
        )
        appearances: dict[tuple[str, str], PlayerAppearance] = {}
        for row in source_file.read_rows():
            minutes_played = self._as_whole_number(
                row.get(PlayerMatchMetricFeature.MINUTES_COLUMN)
            )
            if minutes_played <= 0:
                continue
            player_identifier = self.as_identifier(
                row[WyscoutEventFile.ACTION_PLAYER_COLUMN]
            )
            game_identifier = self.as_identifier(
                row[WyscoutEventFile.ACTION_GAME_COLUMN]
            )
            appearances[(player_identifier, game_identifier)] = PlayerAppearance(
                player_name=row.get(
                    PlayerMatchMetricFeature.PLAYER_NAME_COLUMN, player_identifier
                ),
                team_identifier=self.as_identifier(
                    row[WyscoutEventFile.ACTION_TEAM_COLUMN]
                ),
                minutes_played=minutes_played,
            )
        return appearances

    def _as_whole_number(self, value: str | None) -> int:
        """Read a count, or zero when the cell holds no number at all."""
        try:
            return int(float(value or 0))
        except (TypeError, ValueError):
            return 0

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

    def read_card_names_out_of_tag_list(self, tag_list: str) -> list[str]:
        """Read which cards one event carries.

        Args:
            tag_list: The tag cell of one event, numbers among other text.

        Returns:
            One name per card tag found. Empty when the numbers in the cell
            are other tags that merely start with the same digits.
        """
        if WyscoutEventFile.CARD_TAG_PREFIX not in tag_list:
            return []
        return [
            WyscoutEventFile.CARD_OF_TAG[tag]
            for tag in {
                int(number) for number in self._number_pattern.findall(tag_list)
            }
            if tag in WyscoutEventFile.CARD_OF_TAG
        ]

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

    def date_of(self, match: dict[str, Any]) -> str:
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
            return self._own_goal_action(event, team_name)
        location = event.get(StatsBombOpenDataSource.LOCATION_FIELD)
        if not location:
            return None
        if event_name == MatchStyleFeature.PASS_EVENT_NAME:
            return self._pass_action(event, team_name, location)
        if event_name == MatchStyleFeature.SHOT_EVENT_NAME:
            return self._shot_action(event, team_name, location)
        return self._defensive_action(event, event_name, team_name, location)

    def _own_goal_action(self, event: dict[str, Any], team_name: str) -> MatchAction:
        """Build the action of a goal the other side put into its own net."""
        return self._build_action(
            event,
            team_name,
            MatchStyleFeature.OTHER_KIND,
            was_successful=False,
            start_point=(0.0, 0.0),
            end_point=(0.0, 0.0),
            scoring_team=MatchStyleFeature.SCORED_FOR_THE_ACTING_TEAM,
        )

    def _pass_action(
        self, event: dict[str, Any], team_name: str, location: list[float]
    ) -> MatchAction | None:
        """Build the action of a pass, or None when it ends nowhere."""
        pass_details = event.get(StatsBombOpenDataSource.PASS_FIELD, {})
        end_location = pass_details.get(StatsBombOpenDataSource.END_LOCATION_FIELD)
        if not end_location:
            return None
        return self._build_action(
            event,
            team_name,
            self._pass_kind_of(pass_details),
            was_successful=StatsBombOpenDataSource.OUTCOME_FIELD not in pass_details,
            start_point=self.in_metres(location),
            end_point=self.in_metres(end_location),
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
        point = self.in_metres(location)
        return self._build_action(
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

    def _defensive_action(
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
        point = self.in_metres(location)
        return self._build_action(
            event,
            team_name,
            kind,
            was_successful=self._was_won(event, event_name),
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

    def _was_won(self, event: dict[str, Any], event_name: str) -> bool:
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

    def _build_action(
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

    def in_metres(self, point: list[float]) -> tuple[float, float]:
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
