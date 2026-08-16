"""How far every team travelled during a historical tournament.

Out of the venues of the StatsBomb match files the chronological venue chain of
every team is built. Out of that come the great circle kilometres since the
last match, the running total, and the time zone shifts as a stand in for the
body clock.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from wmguru.helpers.constant import TravelLoadCalculation
from wmguru.helpers.utils import (
    CsvFile,
    GeographyCalculator,
    StadiumLocator,
    TextNormalizer,
)

TEAM_KEYS = ["tournament", "team"]


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
        every_tournament = pd.concat(
            [
                self.calculate_one_tournament(match_file)
                for match_file in sorted(
                    TravelLoadCalculation.SOURCE_FOLDER.glob("*.csv")
                )
            ],
            ignore_index=True,
        )
        output_file = CsvFile(
            TravelLoadCalculation.OUTPUT_FILE, TravelLoadCalculation.COLUMN_NAMES
        )
        output_file.write_table(every_tournament)
        print(f"{len(every_tournament)} team and match rows -> {output_file.path}")
        return len(every_tournament)

    def calculate_one_tournament(self, match_file: Path) -> pd.DataFrame:
        """Calculate one row per team and match of one tournament."""
        return self._add_the_legs_up(self._build_venue_chains(match_file))

    def _build_venue_chains(self, match_file: Path) -> pd.DataFrame:
        """Build the chain of venues every team passes through, in time order.

        A match whose stadium the mapping table does not know drops out of
        the chain, so the leg before and the leg after it are joined into one
        rather than counted as no travel at all.

        Other builders write their own files into the same folder, so a file
        that names no stadium at all is no match list and is skipped.
        """
        matches = CsvFile(match_file).read_table()
        if TravelLoadCalculation.STADIUM_COLUMN not in matches.columns:
            return pd.DataFrame(
                columns=[*TEAM_KEYS, "match_date", "city", "latitude", "longitude"],
                dtype=float,
            )
        located = matches.join(
            self._stadium_locator.find_the_place_of_every_stadium(
                matches[TravelLoadCalculation.STADIUM_COLUMN]
            )
        ).dropna(subset=["city"])

        both_teams = pd.concat(
            [
                located.assign(team=located["home_team"]),
                located.assign(team=located["away_team"]),
            ]
        )
        return (
            both_teams.assign(tournament=match_file.stem)
            .sort_values([*TEAM_KEYS, "match_date"], kind="stable")
            .reset_index(drop=True)
        )

    def _add_the_legs_up(self, venue_chains: pd.DataFrame) -> pd.DataFrame:
        """Measure every leg and carry the running totals along the chain."""
        walked_so_far = venue_chains.groupby(TEAM_KEYS, sort=False)
        came_from_latitude = walked_so_far["latitude"].shift(1)
        came_from_longitude = walked_so_far["longitude"].shift(1)

        kilometres = np.round(
            self._geography_calculator.distance_of_every_leg(
                came_from_latitude,
                came_from_longitude,
                venue_chains["latitude"],
                venue_chains["longitude"],
            ).fillna(0.0)
        ).astype(int)
        time_zone_shift = (
            self._geography_calculator.time_zone_shift_of_every_leg(
                came_from_longitude, venue_chains["longitude"]
            )
            .fillna(0.0)
            .astype(int)
        )
        with_the_legs = venue_chains.assign(
            kilometres_since_last_match=kilometres,
            time_zone_shift_since_last_match=time_zone_shift,
        )
        running = with_the_legs.groupby(TEAM_KEYS, sort=False)
        return with_the_legs.assign(
            total_kilometres=running["kilometres_since_last_match"].cumsum(),
            total_time_zone_shifts=running["time_zone_shift_since_last_match"].cumsum(),
        )


if __name__ == "__main__":
    TravelLoadCalculator(
        StadiumLocator(TextNormalizer()), GeographyCalculator()
    ).calculate_every_tournament()
