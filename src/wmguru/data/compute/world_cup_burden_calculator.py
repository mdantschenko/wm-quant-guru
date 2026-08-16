"""Travel, time zone and altitude load per team for the 2026 group stage.

TravelLoadCalculator only covers the historical tournaments and knows nothing
about altitude. This one builds the chain of the 72 group matches, whose teams
and venues are fixed after the draw, and adds:
  - great circle kilometres since the last match and in total,
  - the time zone shift as a stand in for the body clock,
  - the altitude of the venue and the altitude gained since the last match,
  - the rest days between two matches.

That makes the hidden unfairness of the schedule visible: which team crosses
the continent, and which one plays in Mexico City at 2254 metres.

It writes two files, one row per team and match, and one summary row per team.
"""

from datetime import date
from typing import Any

from wmguru.helpers.constant import (
    CityGeocodeSource,
    ElevationSource,
    InternationalResultSource,
    WorldCupBurdenCalculation,
)
from wmguru.helpers.utils import CsvFile, GeographyCalculator


class WorldCupBurdenCalculator:
    """The leg file and the summary file of the 2026 group stage."""

    def __init__(self, geography_calculator: GeographyCalculator) -> None:
        self._geography_calculator = geography_calculator

    def calculate_every_team(self) -> tuple[int, int]:
        """Write both files and return how many legs and teams they hold."""
        venue_chains = self._build_venue_chains()
        legs = self._build_legs(venue_chains)
        summary = self._build_summary(legs)

        CsvFile(
            WorldCupBurdenCalculation.OUTPUT_FOLDER
            / WorldCupBurdenCalculation.LEG_FILE_NAME,
            WorldCupBurdenCalculation.LEG_COLUMN_NAMES,
        ).write_dict_rows(legs)
        CsvFile(
            WorldCupBurdenCalculation.OUTPUT_FOLDER
            / WorldCupBurdenCalculation.SUMMARY_FILE_NAME,
            WorldCupBurdenCalculation.SUMMARY_COLUMN_NAMES,
        ).write_dict_rows(summary)

        print(f"  OK    {len(legs)} team and match rows, {len(summary)} teams")
        return len(legs), len(summary)

    def _read_places(self) -> dict[str, tuple[float, float, str]]:
        """Read the coordinates and the time zone of every city."""
        return {
            row["city"]: (
                float(row["latitude"]),
                float(row["longitude"]),
                row["timezone"],
            )
            for row in CsvFile(CityGeocodeSource.OUTPUT_FILE).read_rows()
        }

    def _read_venues(self) -> list[tuple[float, float, float]]:
        """Read the 2026 stadiums as latitude, longitude and altitude."""
        return [
            (
                float(row["latitude"]),
                float(row["longitude"]),
                float(row["elevation_m"]),
            )
            for row in CsvFile(ElevationSource.OUTPUT_FILE).read_rows()
            if row["kind"] == ElevationSource.WORLD_CUP_VENUE_KIND
        ]

    def _altitude_of_the_nearest_venue(
        self,
        latitude: float,
        longitude: float,
        venues: list[tuple[float, float, float]],
    ) -> float:
        """Read the altitude of the stadium closest to a city."""
        return min(
            venues,
            key=lambda venue: self._geography_calculator.distance_in_kilometres(
                latitude, longitude, venue[0], venue[1]
            ),
        )[2]

    def _build_venue_chains(self) -> dict[str, list[dict[str, Any]]]:
        """Build the chain of venues every team passes through."""
        places = self._read_places()
        venues = self._read_venues()
        venue_chains: dict[str, list[dict[str, Any]]] = {}
        for match in CsvFile(InternationalResultSource.RESULT_FILE).read_rows():
            if not self._is_a_group_match_of_2026(match):
                continue
            latitude, longitude, time_zone = places[
                match[InternationalResultSource.CITY_COLUMN]
            ]
            altitude = self._altitude_of_the_nearest_venue(latitude, longitude, venues)
            for team_name, opponent_name in self._both_sides_of(match):
                venue_chains.setdefault(team_name, []).append(
                    {
                        "date": match[InternationalResultSource.DATE_COLUMN],
                        "opponent": opponent_name,
                        "city": match[InternationalResultSource.CITY_COLUMN],
                        "is_host": int(self._is_the_host(match, team_name)),
                        "latitude": latitude,
                        "longitude": longitude,
                        "timezone": time_zone,
                        "altitude": altitude,
                    }
                )
        for matches in venue_chains.values():
            matches.sort(key=lambda match: match["date"])
        return venue_chains

    def _is_a_group_match_of_2026(self, match: dict[str, str]) -> bool:
        """Return True when the row is a 2026 World Cup match the list already has."""
        if (
            match[InternationalResultSource.TOURNAMENT_COLUMN]
            != WorldCupBurdenCalculation.TOURNAMENT_NAME
        ):
            return False
        return match[InternationalResultSource.DATE_COLUMN].startswith(
            WorldCupBurdenCalculation.SEASON_PREFIX
        )

    def _both_sides_of(self, match: dict[str, str]) -> tuple[tuple[str, str], ...]:
        """Build both sides of one match, each team with the other as opponent."""
        home_team = match[InternationalResultSource.HOME_TEAM_COLUMN]
        away_team = match[InternationalResultSource.AWAY_TEAM_COLUMN]
        return ((home_team, away_team), (away_team, home_team))

    def _is_the_host(self, match: dict[str, str], team_name: str) -> bool:
        """Return True when the venue is not neutral and the team is named first."""
        venue_is_neutral = (
            match[InternationalResultSource.NEUTRAL_VENUE_COLUMN].strip().upper()
            != InternationalResultSource.NOT_NEUTRAL_TEXT
        )
        if venue_is_neutral:
            return False
        return team_name == match[InternationalResultSource.HOME_TEAM_COLUMN]

    def _build_legs(
        self, venue_chains: dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Build one row per team and match, with the leg since the match before it."""
        legs: list[dict[str, Any]] = []
        for team_name, matches in sorted(venue_chains.items()):
            total_kilometres = 0.0
            total_time_zone_shifts = 0
            previous_match: dict[str, Any] | None = None
            for match_number, match in enumerate(matches, start=1):
                leg = self._build_one_leg(match, previous_match)
                total_kilometres += leg["kilometres"]
                total_time_zone_shifts += leg["time_zone_shift"]
                legs.append(
                    {
                        "team": team_name,
                        "match_number": match_number,
                        "date": match["date"],
                        "opponent": match["opponent"],
                        "city": match["city"],
                        "is_host": match["is_host"],
                        "timezone": match["timezone"],
                        "altitude_m": round(match["altitude"]),
                        "altitude_gain_since_last": round(leg["altitude_gain"]),
                        "km_since_last": round(leg["kilometres"]),
                        "cumulative_km": round(total_kilometres),
                        "tz_shift_since_last": leg["time_zone_shift"],
                        "cumulative_tz_shifts": total_time_zone_shifts,
                        "days_rest": leg["rest_days"],
                    }
                )
                previous_match = match
        return legs

    def _build_one_leg(
        self, match: dict[str, Any], previous_match: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Work out what changed since the match before, zero for the first one."""
        if previous_match is None:
            return {
                "kilometres": 0.0,
                "time_zone_shift": 0,
                "altitude_gain": 0.0,
                "rest_days": WorldCupBurdenCalculation.NO_REST_DAYS_YET,
            }
        return {
            "kilometres": self._geography_calculator.distance_in_kilometres(
                previous_match["latitude"],
                previous_match["longitude"],
                match["latitude"],
                match["longitude"],
            ),
            "time_zone_shift": self._geography_calculator.time_zone_shift(
                previous_match["longitude"], match["longitude"]
            ),
            "altitude_gain": self._altitude_gained(previous_match, match),
            "rest_days": (
                date.fromisoformat(match["date"])
                - date.fromisoformat(previous_match["date"])
            ).days,
        }

    def _altitude_gained(
        self, previous_match: dict[str, Any], match: dict[str, Any]
    ) -> float:
        """Measure how much higher the venue is than the one before it.

        Only going up costs a team anything, coming down is no burden, so a
        descent counts as zero.
        """
        return max(0.0, match["altitude"] - previous_match["altitude"])

    def _build_summary(self, legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build one row per team, the hardest travelled team first."""
        legs_of_team: dict[str, list[dict[str, Any]]] = {}
        for leg in legs:
            legs_of_team.setdefault(leg["team"], []).append(leg)

        summary = [
            {
                "team": team_name,
                "group_matches": len(team_legs),
                "total_km": team_legs[-1]["cumulative_km"],
                "total_tz_shifts": team_legs[-1]["cumulative_tz_shifts"],
                "max_altitude_m": max(leg["altitude_m"] for leg in team_legs),
                "high_altitude_matches": sum(
                    1
                    for leg in team_legs
                    if leg["altitude_m"]
                    >= WorldCupBurdenCalculation.HIGH_ALTITUDE_IN_METRES
                ),
                "first_city": team_legs[0]["city"],
                "last_city": team_legs[-1]["city"],
            }
            for team_name, team_legs in sorted(legs_of_team.items())
        ]
        summary.sort(key=lambda row: row["total_km"], reverse=True)
        return summary


if __name__ == "__main__":
    WorldCupBurdenCalculator(GeographyCalculator()).calculate_every_team()
