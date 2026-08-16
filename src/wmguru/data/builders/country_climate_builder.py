"""The summer climate of every country, and the distance of every match from it.

A team from a cool country playing at thirty five degrees is at a disadvantage
no rating carries. This measures it: what June and July are normally like at
home, against what it felt like at kick off.

The climate file is resumable, a country already in it is not fetched again,
because the ten year query is heavy and the source throttles it.
"""

import urllib.parse
from typing import Any

from wmguru.helpers.constant import (
    CountryClimateCalculation,
    OpenMeteoSource,
    WebRequestSetting,
)
from wmguru.helpers.utils import CsvFile, WebFileDownloader


class CountryClimateBuilder:
    """The summer normal of every country, and how far a match was from it."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader
        self._climate_file = CsvFile(
            CountryClimateCalculation.OUTPUT_FILE,
            CountryClimateCalculation.COLUMN_NAMES,
        )
        self._distance_file = CsvFile(
            CountryClimateCalculation.DISTANCE_OUTPUT_FILE,
            CountryClimateCalculation.DISTANCE_COLUMN_NAMES,
        )

    def build_every_country(self) -> int:
        """Fetch what is missing, write both files.

        Returns:
            How many matches got a climate distance.
        """
        climate_rows = self._climate_file.read_rows()
        temperature_of_country = {
            row["country"]: float(row["june_july_mean_temperature"])
            for row in climate_rows
        }
        for country in sorted(self._collect_every_country()):
            if country in temperature_of_country:
                continue
            row = self._fetch_one_country(country)
            if row is None:
                continue
            climate_rows.append(row)
            temperature_of_country[country] = float(row["june_july_mean_temperature"])
        self._climate_file.write_dict_rows(climate_rows)
        print(f"{len(climate_rows)} country climates -> {self._climate_file.path}")

        distance_rows = self._build_distance_rows(temperature_of_country)
        self._distance_file.write_dict_rows(distance_rows)
        print(f"{len(distance_rows)} match distances -> {self._distance_file.path}")
        return len(distance_rows)

    def _collect_every_country(self) -> set[str]:
        """Collect every team of the past tournaments and of the 2026 squads."""
        countries: set[str] = set()
        for row in self._read_every_tournament_match():
            countries.update((row["home_team"], row["away_team"]))
        for row in CsvFile(CountryClimateCalculation.WORLD_CUP_SQUAD_FILE).read_rows():
            countries.add(row["team"])
        return countries

    def _read_every_tournament_match(self) -> list[dict[str, str]]:
        """Read the matches of every tournament file in the folder.

        Other builders write their own files into the same folder, the bench
        line ups for one, so a file that names no two teams is skipped rather
        than read as a match list.
        """
        matches: list[dict[str, str]] = []
        for match_file in sorted(
            CountryClimateCalculation.TOURNAMENT_FOLDER.glob(
                CountryClimateCalculation.MATCH_FILE_PATTERN
            )
        ):
            rows = CsvFile(match_file).read_rows()
            if rows and "home_team" in rows[0] and "away_team" in rows[0]:
                matches.extend(rows)
        return matches

    def _fetch_one_country(self, country: str) -> dict[str, Any] | None:
        """Find the country on the map and read its summer normal.

        Returns:
            The row for the climate file, or None when the place cannot be
            found or the archive gives no temperature even after a retry.
        """
        place = self._find_the_place(country)
        if place is None:
            print(f"  SKIP  {country} (no place found)")
            return None
        temperature = self._read_summer_temperature(place)
        if temperature is None:
            print(f"  SKIP  {country} (no climate value)")
            return None
        return {
            "country": country,
            "reference_place": place.get("name"),
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "june_july_mean_temperature": temperature,
        }

    def _find_the_place(self, country: str) -> dict[str, Any] | None:
        """Look the country up, under the name the geocoder knows it by."""
        query = CountryClimateCalculation.PLACE_OF_TEAM_NAME.get(country, country)
        answer = self._web_file_downloader.download_json(
            f"{OpenMeteoSource.GEOCODING_URL}?name={self._quoted(query)}&count=1",
            timeout_in_seconds=OpenMeteoSource.TIMEOUT_IN_SECONDS,
        )
        results = (answer or {}).get("results") or []
        return results[0] if results else None

    def _read_summer_temperature(self, place: dict[str, Any]) -> float | None:
        """Average the June and July days of ten years at one place.

        The archive throttles a query this long, so one retry after a longer
        wait is worth it before the country is given up on.
        """
        temperature = self._ask_the_archive(place)
        if temperature is None:
            self._web_file_downloader.wait_for(
                CountryClimateCalculation.RETRY_WAIT_IN_SECONDS
            )
            temperature = self._ask_the_archive(place)
        self._web_file_downloader.wait_for(
            CountryClimateCalculation.ARCHIVE_DELAY_IN_SECONDS
        )
        return temperature

    def _ask_the_archive(self, place: dict[str, Any]) -> float | None:
        """Ask for the daily temperatures and average the summer days."""
        first = CountryClimateCalculation.FIRST_CLIMATE_YEAR
        last = CountryClimateCalculation.LAST_CLIMATE_YEAR
        answer = self._web_file_downloader.download_json(
            f"{OpenMeteoSource.WEATHER_ARCHIVE_URL}"
            f"?latitude={place['latitude']}&longitude={place['longitude']}"
            f"&start_date={first}-06-01&end_date={last}-07-31"
            f"&daily={CountryClimateCalculation.DAILY_TEMPERATURE_VARIABLE}"
            f"&timezone=UTC",
            timeout_in_seconds=OpenMeteoSource.TIMEOUT_IN_SECONDS,
        )
        if answer is None:
            return None
        daily = answer.get("daily", {})
        summer_values = [
            value
            for day, value in zip(
                daily.get("time", []),
                daily.get(CountryClimateCalculation.DAILY_TEMPERATURE_VARIABLE, []),
                strict=False,
            )
            if value is not None and day[5:7] in CountryClimateCalculation.SUMMER_MONTHS
        ]
        if not summer_values:
            return None
        return round(
            sum(summer_values) / len(summer_values),
            CountryClimateCalculation.TEMPERATURE_DECIMAL_PLACES,
        )

    def _build_distance_rows(
        self, temperature_of_country: dict[str, float]
    ) -> list[dict[str, Any]]:
        """Measure how far every match was from the summer each team knows."""
        teams_of_match = self._read_teams_of_every_match()
        rows: list[dict[str, Any]] = []
        for weather in CsvFile(CountryClimateCalculation.WEATHER_FILE).read_rows():
            teams = teams_of_match.get(weather["match_id"])
            felt_like = weather["apparent_temperature_c"]
            if teams is None or not felt_like:
                continue
            home_team, away_team = teams
            rows.append(
                {
                    "tournament": weather["tournament"],
                    "match_id": weather["match_id"],
                    "match_date": weather["match_date"],
                    "city": weather["city"],
                    "apparent_temperature_c": felt_like,
                    "home_team": home_team,
                    "home_climate_delta_c": self._distance_of(
                        felt_like, home_team, temperature_of_country
                    ),
                    "away_team": away_team,
                    "away_climate_delta_c": self._distance_of(
                        felt_like, away_team, temperature_of_country
                    ),
                }
            )
        return rows

    def _read_teams_of_every_match(self) -> dict[str, tuple[str, str]]:
        """Read which two teams played each tournament match."""
        return {
            row["match_id"]: (row["home_team"], row["away_team"])
            for row in self._read_every_tournament_match()
        }

    def _distance_of(
        self,
        felt_like: str,
        team: str,
        temperature_of_country: dict[str, float],
    ) -> Any:
        """How much warmer the match was than the summer that team knows.

        Returns:
            The difference in degrees, or an empty cell for a team whose
            country never got a climate value.
        """
        if team not in temperature_of_country:
            return ""
        return round(
            float(felt_like) - temperature_of_country[team],
            CountryClimateCalculation.DELTA_DECIMAL_PLACES,
        )

    def _quoted(self, text: str) -> str:
        """Make a name safe to put into a query string."""
        return urllib.parse.quote(text)


if __name__ == "__main__":
    CountryClimateBuilder(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=OpenMeteoSource.POLITE_DELAY_IN_SECONDS,
        )
    ).build_every_country()
