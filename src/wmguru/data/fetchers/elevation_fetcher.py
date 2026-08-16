"""The elevation of every venue and of every country reference place.

Elevation is a physiology factor the market hardly prices. Estadio Azteca sits
at 2240 metres. A team from the lowlands measurably loses performance there,
while a team used to altitude, such as Bolivia, Ecuador or Mexico, gains. The
feature is the elevation difference between the venue and home.

Three groups of places go in: the stadiums of the historical tournaments out of
the weather mapping table, the 16 stadiums of the 2026 World Cup, and the
reference place of every country out of the climate file.
"""

import csv
from typing import Any

from wmguru.helpers.constant import (
    ComputedFeaturePath,
    CsvFileSetting,
    ElevationSource,
    MatchWeatherSource,
    OpenMeteoSource,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
)


class ElevationFetcher:
    """One row per place, with its elevation in metres."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def fetch_every_place(self) -> int:
        """Write the file and return how many places it holds."""
        places = self._collect_places()
        elevations = self._read_elevations(
            [(latitude, longitude) for *_, latitude, longitude in places]
        )

        with CsvFile(
            ElevationSource.OUTPUT_FILE, ElevationSource.COLUMN_NAMES
        ).writing_writer() as writer:
            for (kind, name, place, latitude, longitude), elevation in zip(
                places, elevations, strict=True
            ):
                writer.writerow(
                    [kind, name, place, latitude, longitude, round(elevation)]
                )
        print(f"{len(places)} places with elevation -> {ElevationSource.OUTPUT_FILE}")
        return len(places)

    def _collect_places(self) -> list[tuple[str, str, str, float, float]]:
        """Collect every place whose elevation is needed, with its coordinates."""
        places: list[tuple[str, str, str, float, float]] = []
        for name, (
            city,
            latitude,
            longitude,
        ) in ElevationSource.PLACE_OF_WORLD_CUP_2026_VENUE.items():
            places.append(
                (ElevationSource.WORLD_CUP_VENUE_KIND, name, city, latitude, longitude)
            )
        for name, (
            city,
            latitude,
            longitude,
        ) in MatchWeatherSource.PLACE_OF_STADIUM_NAME_PART.items():
            places.append(
                (ElevationSource.HISTORICAL_VENUE_KIND, name, city, latitude, longitude)
            )
        places.extend(self._read_country_reference_places())
        return places

    def _read_country_reference_places(
        self,
    ) -> list[tuple[str, str, str, float, float]]:
        """Read the reference place of every country out of the climate file."""
        places: list[tuple[str, str, str, float, float]] = []
        with ComputedFeaturePath.COUNTRY_CLIMATE_FILE.open(
            encoding=CsvFileSetting.ENCODING, newline=CsvFileSetting.NEW_LINE
        ) as file_handle:
            for row in csv.DictReader(file_handle):
                places.append(
                    (
                        ElevationSource.COUNTRY_REFERENCE_KIND,
                        row["country"],
                        row["reference_place"],
                        float(row["latitude"]),
                        float(row["longitude"]),
                    )
                )
        return places

    def _read_elevations(self, points: list[tuple[float, float]]) -> list[float]:
        """Read the elevation of every point, asking the endpoint in batches."""
        elevations: list[float] = []
        for start in range(0, len(points), ElevationSource.BATCH_SIZE):
            batch = points[start : start + ElevationSource.BATCH_SIZE]
            answer = self._web_file_downloader.download_json(
                self._build_url(batch),
                timeout_in_seconds=OpenMeteoSource.TIMEOUT_IN_SECONDS,
            )
            elevations.extend(self._read_batch_answer(answer, len(batch)))
        return elevations

    def _build_url(self, batch: list[tuple[float, float]]) -> str:
        """Build the address of one request."""
        latitudes = ",".join(f"{latitude}" for latitude, _ in batch)
        longitudes = ",".join(f"{longitude}" for _, longitude in batch)
        return (
            f"{OpenMeteoSource.ELEVATION_URL}"
            f"?latitude={latitudes}&longitude={longitudes}"
        )

    def _read_batch_answer(self, answer: Any, batch_size: int) -> list[float]:
        """Read the elevations of one batch, or fall back to zeroes when it failed."""
        if isinstance(answer, dict):
            elevations = answer.get("elevation")
            if isinstance(elevations, list) and len(elevations) == batch_size:
                return elevations
        print(f"  FAIL  a batch of {batch_size} places came back unusable")
        return [0.0] * batch_size


if __name__ == "__main__":
    ElevationFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=OpenMeteoSource.POLITE_DELAY_IN_SECONDS,
        )
    ).fetch_every_place()
