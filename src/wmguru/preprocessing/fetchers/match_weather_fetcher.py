"""The kick off weather of every tournament match, from the Open-Meteo archive.

It reads the match files of the StatsBomb folder, which carry stadium, date and
kick off time, finds the coordinates of the stadium through a mapping table and
pulls temperature, apparent temperature and humidity for the kick off hour in
local time. That is the base for the climate features, that is heat and
humidity load and the climate distance of the teams.
"""

import csv
from typing import Any

from wmguru.helpers.constant import (
    CsvFileSetting,
    MatchWeatherSource,
    OpenMeteoSource,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    CsvFile,
    StadiumLocator,
    TextNormalizer,
    WebFileDownloader,
)


class MatchWeatherFetcher:
    """One row per tournament match, with the weather at kick off."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        stadium_locator: StadiumLocator,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._stadium_locator = stadium_locator
        self._weather_of_the_day: dict[tuple[float, float, str], Any] = {}
        self._unknown_stadiums: set[str] = set()

    def fetch_every_match(self) -> int:
        """Write the file and return how many matches carry weather."""
        MatchWeatherSource.OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        written_count = 0
        with CsvFile(
            MatchWeatherSource.OUTPUT_FILE, MatchWeatherSource.COLUMN_NAMES
        ).writing_writer() as writer:
            for match_file in sorted(MatchWeatherSource.SOURCE_FOLDER.glob("*.csv")):
                written_count += self._write_one_tournament(writer, match_file)
        print(
            f"{written_count} matches with kick off weather "
            f"-> {MatchWeatherSource.OUTPUT_FILE}"
        )
        self._report_unknown_stadiums()
        return written_count

    def _write_one_tournament(self, writer: Any, match_file: Any) -> int:
        """Walk the matches of one tournament file and return the row count."""
        tournament_name = match_file.stem
        written_count = 0
        with match_file.open(
            encoding=CsvFileSetting.ENCODING, newline=CsvFileSetting.NEW_LINE
        ) as file_handle:
            for match in csv.DictReader(file_handle):
                row = self._build_the_row_of_one_match(tournament_name, match)
                if row is None:
                    continue
                writer.writerow(row)
                written_count += 1
        return written_count

    def _build_the_row_of_one_match(
        self, tournament_name: str, match: dict[str, str]
    ) -> list[Any] | None:
        """Build one output row."""
        place = self._stadium_locator.find_place(match["stadium"])
        if place is None:
            self._unknown_stadiums.add(match["stadium"])
            return None

        city, latitude, longitude = place
        weather = self._read_weather_of_the_day(
            latitude, longitude, match["match_date"]
        )
        if weather is None:
            return None

        hour = self._kick_off_hour(match["kick_off"])
        hourly_values = weather.get("hourly", {})
        return [
            tournament_name,
            match["match_id"],
            match["match_date"],
            match["kick_off"],
            match["stadium"],
            city,
            latitude,
            longitude,
            self._the_value_of_that_hour(
                hourly_values, MatchWeatherSource.TEMPERATURE_VARIABLE, hour
            ),
            self._the_value_of_that_hour(
                hourly_values, MatchWeatherSource.APPARENT_TEMPERATURE_VARIABLE, hour
            ),
            self._the_value_of_that_hour(
                hourly_values, MatchWeatherSource.HUMIDITY_VARIABLE, hour
            ),
        ]

    def _read_weather_of_the_day(
        self, latitude: float, longitude: float, day: str
    ) -> Any:
        """Ask for the hourly values of one day, and remember the answer."""
        cache_key = (latitude, longitude, day)
        if cache_key not in self._weather_of_the_day:
            url = (
                f"{OpenMeteoSource.WEATHER_ARCHIVE_URL}"
                f"?latitude={latitude}&longitude={longitude}"
                f"&start_date={day}&end_date={day}"
                f"&hourly={MatchWeatherSource.HOURLY_VARIABLES}&timezone=auto"
            )
            self._weather_of_the_day[cache_key] = (
                self._web_file_downloader.download_json(
                    url, timeout_in_seconds=OpenMeteoSource.TIMEOUT_IN_SECONDS
                )
            )
        return self._weather_of_the_day[cache_key]

    def _kick_off_hour(self, kick_off_time: str) -> int:
        """Read the hour out of HH:MM:SS.mmm, falling back to the afternoon."""
        try:
            hour = int(kick_off_time.split(":")[0])
        except (ValueError, IndexError):
            return MatchWeatherSource.FALLBACK_KICK_OFF_HOUR
        return max(
            MatchWeatherSource.FIRST_HOUR_OF_DAY,
            min(MatchWeatherSource.LAST_HOUR_OF_DAY, hour),
        )

    def _the_value_of_that_hour(
        self, hourly_values: dict[str, Any], variable_name: str, hour: int
    ) -> Any:
        """Read one hourly value, or nothing when the endpoint left the day out."""
        values = hourly_values.get(
            variable_name, [None] * MatchWeatherSource.HOURS_PER_DAY
        )
        return values[hour] if hour < len(values) else None

    def _report_unknown_stadiums(self) -> None:
        """Name the stadiums that are missing from the mapping table."""
        if not self._unknown_stadiums:
            return
        print("Unknown stadiums, please add them to the mapping table:")
        for stadium_name in sorted(self._unknown_stadiums):
            print(f"  {stadium_name.encode('ascii', 'replace').decode()}")


if __name__ == "__main__":
    MatchWeatherFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=OpenMeteoSource.POLITE_DELAY_IN_SECONDS,
        ),
        StadiumLocator(TextNormalizer()),
    ).fetch_every_match()
