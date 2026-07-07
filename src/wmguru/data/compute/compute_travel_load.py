"""Berechnet Reisebelastung (Jetlag-Feature) je Team und Turnierspiel.

Aus den Spielorten der StatsBomb-Turnierdaten wird pro Team die
chronologische Venue-Sequenz gebildet; daraus Großkreis-Kilometer seit
dem letzten Spiel, kumulierte Kilometer und (als zirkadianer Proxy)
Zeitzonen-Verschiebungen (Laengengrad/15). Stadion-Koordinaten kommen
aus der Mapping-Tabelle des Wetter-Skripts. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

from src.scripts.fetchers.fetch_match_weather import WeatherConfig, locate_stadium


class TravelConfig:
    """Quellen und Zielpfad."""

    SOURCE_DIR: str = "Data/xG Tournament Data (StatsBomb Open Data)"
    OUTPUT_FILE: str = "Data/Computed Features/travel_load.csv"


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Großkreisdistanz zweier Koordinaten in Kilometern."""
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))


def timezone_proxy(longitude: float) -> int:
    """Zeitzonen-Proxy aus dem Laengengrad (15 Grad je Stunde)."""
    return round(longitude / 15.0)


def main() -> None:
    """Berechne die Reisekette jedes Teams in jedem Turnier."""
    travel_config = TravelConfig()
    weather_config = WeatherConfig()
    output_rows: list[list[object]] = []
    for path in sorted(Path(travel_config.SOURCE_DIR).glob("*.csv")):
        tournament = path.stem
        legs: dict[str, list[tuple[str, str, float, float]]] = {}
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                location = locate_stadium(row["stadium"], weather_config)
                if location is None:
                    continue
                city, latitude, longitude = location
                for team in (row["home_team"], row["away_team"]):
                    legs.setdefault(team, []).append(
                        (row["match_date"], city, latitude, longitude)
                    )
        for team, matches in sorted(legs.items()):
            matches.sort()
            cumulative_km = 0.0
            cumulative_tz = 0
            previous: tuple[str, str, float, float] | None = None
            for match_date, city, latitude, longitude in matches:
                km = tz = 0
                if previous is not None:
                    km = round(haversine_km(previous[2], previous[3], latitude, longitude))
                    tz = abs(timezone_proxy(longitude) - timezone_proxy(previous[3]))
                cumulative_km += km
                cumulative_tz += tz
                output_rows.append(
                    [tournament, team, match_date, city, km, round(cumulative_km),
                     tz, cumulative_tz]
                )
                previous = (match_date, city, latitude, longitude)
    target = Path(travel_config.OUTPUT_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tournament", "team", "match_date", "city",
                         "km_since_last_match", "cumulative_km",
                         "tz_shift_since_last", "cumulative_tz_shifts"])
        writer.writerows(output_rows)
    print(f"{len(output_rows)} Team-Spiel-Zeilen -> {target}")


if __name__ == "__main__":
    main()
