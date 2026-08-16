"""Every venue of the training data, as coordinates and a timezone.

About 2200 unique city and country pairs come out of 49400 international
matches. With coordinates and timezone the travel distance, the timezone jump,
the elevation and the climate can be computed for the whole training set, not
only for the tournament matches.

The run can be stopped and started again, a pair that is already in the output
file is never asked for a second time.
"""

import csv
import urllib.parse
from typing import Any

from wmguru.helpers.constant import (
    CityGeocodeSource,
    CsvFileSetting,
    InternationalResultSource,
    OpenMeteoSource,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    CsvFile,
    TextNormalizer,
    WebFileDownloader,
)


class CityGeocodeFetcher:
    """The coordinates of every venue in the results file, asked of Open-Meteo."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        text_normalizer: TextNormalizer,
        output_file: CsvFile,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._text_normalizer = text_normalizer
        self._output_file = output_file

    def fetch_every_city(self) -> tuple[int, int]:
        """Return how many cities were resolved and how many were not found."""
        wanted_pairs = self._read_city_and_country_pairs()
        finished_pairs = self._output_file.read_finished_value_pairs(
            InternationalResultSource.CITY_COLUMN,
            InternationalResultSource.COUNTRY_COLUMN,
        )
        resolved_count = 0
        not_found_count = 0
        with self._output_file.appending_writer() as writer:
            for city, country in sorted(wanted_pairs - finished_pairs):
                place = self._find_place(city, country)
                if place is None:
                    not_found_count += 1
                    continue
                writer.writerow(self._build_the_row_of_one_city(city, country, place))
                resolved_count += 1
                self._report_progress(resolved_count)
        print(
            f"+{resolved_count} resolved ({not_found_count} without a hit, "
            f"{len(finished_pairs)} already there) -> {self._output_file.path}"
        )
        return resolved_count, not_found_count

    def _read_city_and_country_pairs(self) -> set[tuple[str, str]]:
        """Read every city and country pair that appears in the results file."""
        pairs: set[tuple[str, str]] = set()
        with InternationalResultSource.RESULT_FILE.open(
            encoding=CsvFileSetting.ENCODING, newline=CsvFileSetting.NEW_LINE
        ) as file_handle:
            for row in csv.DictReader(file_handle):
                city = row[InternationalResultSource.CITY_COLUMN].strip()
                country = row[InternationalResultSource.COUNTRY_COLUMN].strip()
                if city and country:
                    pairs.add((city, country))
        return pairs

    def _find_place(self, city: str, country: str) -> dict[str, Any] | None:
        """Find the best candidate for a city, or return None when there is no hit.

        A city name exists many times in the world, so a candidate whose
        country matches the country of the match is always preferred.
        """
        candidates = self._ask_for_candidates(city)
        if not candidates:
            return None
        exact_hit = self._first_candidate_with_the_same_country(candidates, country)
        return exact_hit if exact_hit is not None else candidates[0]

    def _ask_for_candidates(self, city: str) -> list[dict[str, Any]]:
        """Ask the endpoint for a handful of candidates for one city name."""
        url = (
            f"{OpenMeteoSource.GEOCODING_URL}?name={urllib.parse.quote(city)}"
            f"&count={CityGeocodeSource.CANDIDATE_COUNT}&language=en&format=json"
        )
        answer = self._web_file_downloader.download_json(
            url, timeout_in_seconds=OpenMeteoSource.TIMEOUT_IN_SECONDS
        )
        if not isinstance(answer, dict):
            return []
        candidates = answer.get("results") or []
        return candidates if isinstance(candidates, list) else []

    def _first_candidate_with_the_same_country(
        self, candidates: list[dict[str, Any]], country: str
    ) -> dict[str, Any] | None:
        """Find the candidate whose country matches, first exactly and then loosely."""
        wanted = self._text_normalizer.to_comparable_text(country)
        for candidate in candidates:
            if (
                self._text_normalizer.to_comparable_text(candidate.get("country", ""))
                == wanted
            ):
                return candidate
        for candidate in candidates:
            if self._text_normalizer.mean_the_same_country(
                candidate.get("country", ""), country
            ):
                return candidate
        return None

    def _build_the_row_of_one_city(
        self, city: str, country: str, place: dict[str, Any]
    ) -> list[Any]:
        """Build one output row."""
        return [
            city,
            country,
            place.get("latitude"),
            place.get("longitude"),
            place.get("timezone", ""),
            place.get("name", ""),
            place.get("country", ""),
        ]

    def _report_progress(self, resolved_count: int) -> None:
        """Say something every now and then, the run takes a while."""
        if resolved_count % CityGeocodeSource.PROGRESS_REPORT_EVERY_N_CITIES == 0:
            print(f"  ... {resolved_count} resolved", flush=True)


if __name__ == "__main__":
    CityGeocodeFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=OpenMeteoSource.POLITE_DELAY_IN_SECONDS,
        ),
        TextNormalizer(),
        CsvFile(CityGeocodeSource.OUTPUT_FILE, CityGeocodeSource.COLUMN_NAMES),
    ).fetch_every_city()
