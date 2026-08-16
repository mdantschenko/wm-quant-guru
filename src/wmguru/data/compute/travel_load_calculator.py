"""How far every team travelled during a historical tournament.

Out of the venues of the StatsBomb match files the chronological venue chain of
every team is built. Out of that come the great circle kilometres since the
last match, the running total, and the time zone shifts as a stand in for the
body clock.
"""

from pathlib import Path
from typing import Any

from wmguru.helpers.constant import TravelLoadCalculation
from wmguru.helpers.utils import (
    CsvFile,
    GeographyCalculator,
    StadiumLocator,
    TextNormalizer,
)


class TravelLoadCalculator:
    """One row per team and match, with its travel so far."""

    def __init__(
        self,
        stadium_locator: StadiumLocator,
        geography_calculator: GeographyCalculator,
    ) -> None:
        self._stadium_locator = stadium_locator
        self._geography_calculator = geography_calculator

    def calculate_every_tournament(self) -> int:
        """Write the file and return how many team and match rows it holds."""
        rows: list[list[Any]] = []
        for match_file in sorted(TravelLoadCalculation.SOURCE_FOLDER.glob("*.csv")):
            rows.extend(self.calculate_one_tournament(match_file))

        output_file = CsvFile(
            TravelLoadCalculation.OUTPUT_FILE, TravelLoadCalculation.COLUMN_NAMES
        )
        output_file.write_rows(rows)
        print(f"{len(rows)} team and match rows -> {output_file.path}")
        return len(rows)

    def calculate_one_tournament(self, match_file: Path) -> list[list[Any]]:
        """Calculate one row per team of one tournament."""
        venue_chains = self._build_venue_chains(match_file)
        rows: list[list[Any]] = []
        for team_name, venues in sorted(venue_chains.items()):
            venues_in_time_order = sorted(venues, key=self._match_date_of)
            rows.extend(
                self._walk_the_chain(match_file.stem, team_name, venues_in_time_order)
            )
        return rows

    def _match_date_of(self, venue: tuple[str, str, float, float]) -> str:
        """Read the match date, which is the first field of a venue entry."""
        return venue[0]

    def _build_venue_chains(
        self, match_file: Path
    ) -> dict[str, list[tuple[str, str, float, float]]]:
        """Build the chain of venues every team passes through."""
        venue_chains: dict[str, list[tuple[str, str, float, float]]] = {}
        for match in CsvFile(match_file).read_rows():
            place = self._stadium_locator.find_place(match["stadium"])
            if place is None:
                continue
            city, latitude, longitude = place
            for team_name in (match["home_team"], match["away_team"]):
                venue_chains.setdefault(team_name, []).append(
                    (match["match_date"], city, latitude, longitude)
                )
        return venue_chains

    def _walk_the_chain(
        self,
        tournament_name: str,
        team_name: str,
        venues: list[tuple[str, str, float, float]],
    ) -> list[list[Any]]:
        """Build one row per match, with the leg since the match before it."""
        rows: list[list[Any]] = []
        total_kilometres = 0.0
        total_time_zone_shifts = 0
        previous_venue: tuple[str, str, float, float] | None = None
        for match_date, city, latitude, longitude in venues:
            kilometres = 0
            time_zone_shift = 0
            if previous_venue is not None:
                kilometres = round(
                    self._geography_calculator.distance_in_kilometres(
                        previous_venue[2], previous_venue[3], latitude, longitude
                    )
                )
                time_zone_shift = self._geography_calculator.time_zone_shift(
                    previous_venue[3], longitude
                )
            total_kilometres += kilometres
            total_time_zone_shifts += time_zone_shift
            rows.append(
                [
                    tournament_name,
                    team_name,
                    match_date,
                    city,
                    kilometres,
                    round(total_kilometres),
                    time_zone_shift,
                    total_time_zone_shifts,
                ]
            )
            previous_venue = (match_date, city, latitude, longitude)
        return rows


if __name__ == "__main__":
    TravelLoadCalculator(
        StadiumLocator(TextNormalizer()), GeographyCalculator()
    ).calculate_every_tournament()
