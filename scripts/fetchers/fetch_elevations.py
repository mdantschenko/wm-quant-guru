"""Holt Höhenlagen aller Turnier-Venues und Team-Referenzorte (Open-Meteo).

Höhe ist ein kaum eingepreister Physiologie-Faktor: Estadio Azteca
liegt auf 2.240 m -- Tiefland-Teams verlieren dort messbar Leistung,
während höhenadaptierte Teams (Bolivien, Ecuador, Mexiko) profitieren.
Das Feature ist die Höhen-DIFFERENZ zwischen Spielort und Heimat.
Quellen: Stadion-Mapping des Wetter-Skripts (historische Turniere),
fest hinterlegte WM-2026-Venues, Länder-Referenzorte aus dem
Klima-Artefakt. Die Elevation-API verarbeitet Koordinaten in Batches.
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import urllib.request
from pathlib import Path

from scripts.fetchers.fetch_match_weather import WeatherConfig


class ElevationConfig:
    """Endpunkt, WM-2026-Venues und Zielpfad."""

    API_URL: str = "https://api.open-meteo.com/v1/elevation"
    TIMEOUT_SECONDS: int = 30
    BATCH_SIZE: int = 90
    CLIMATE_FILE: str = "Data/Computed Features/country_climate.csv"
    OUTPUT_FILE: str = "Data/Computed Features/venue_country_elevations.csv"

    # Die 16 offiziellen WM-2026-Stadien (Stadt, Lat, Lon).
    WC2026_VENUES: dict[str, tuple[str, float, float]] = {
        "MetLife Stadium": ("East Rutherford", 40.81, -74.07),
        "AT&T Stadium": ("Arlington TX", 32.75, -97.09),
        "Arrowhead Stadium": ("Kansas City", 39.05, -94.48),
        "NRG Stadium": ("Houston", 29.68, -95.41),
        "Mercedes-Benz Stadium": ("Atlanta", 33.76, -84.40),
        "Hard Rock Stadium": ("Miami", 25.96, -80.24),
        "Lincoln Financial Field": ("Philadelphia", 39.90, -75.17),
        "Lumen Field": ("Seattle", 47.60, -122.33),
        "Levi's Stadium": ("Santa Clara", 37.40, -121.97),
        "SoFi Stadium": ("Inglewood", 33.95, -118.34),
        "Gillette Stadium": ("Foxborough", 42.09, -71.26),
        "BMO Field": ("Toronto", 43.63, -79.42),
        "BC Place Stadium": ("Vancouver", 49.28, -123.11),
        "Estadio Azteca": ("Mexico City", 19.30, -99.15),
        "Estadio AKRON": ("Guadalajara", 20.68, -103.46),
        "Estadio BBVA Bancomer": ("Monterrey", 25.67, -100.24),
    }


def elevations_for(
    coordinates: list[tuple[float, float]], config: ElevationConfig
) -> list[float]:
    """Hole Höhen (Meter) für eine Koordinatenliste in Batches."""
    results: list[float] = []
    for start in range(0, len(coordinates), config.BATCH_SIZE):
        batch = coordinates[start:start + config.BATCH_SIZE]
        url = (
            f"{config.API_URL}?latitude="
            + ",".join(f"{lat}" for lat, _ in batch)
            + "&longitude="
            + ",".join(f"{lon}" for _, lon in batch)
        )
        request = urllib.request.Request(url, headers={"User-Agent": "wm-quant-guru"})
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            results.extend(json.loads(response.read())["elevation"])
    return results


def main() -> None:
    """Sammle alle Orte, hole Höhen und schreibe eine kombinierte CSV."""
    config = ElevationConfig()
    weather_config = WeatherConfig()
    entries: list[tuple[str, str, str, float, float]] = []
    for name, (city, lat, lon) in config.WC2026_VENUES.items():
        entries.append(("venue_wc2026", name, city, lat, lon))
    for key, (city, lat, lon) in weather_config.STADIUM_LOCATIONS.items():
        entries.append(("venue_historical", key, city, lat, lon))
    with Path(config.CLIMATE_FILE).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            entries.append(
                ("country_reference", row["country"], row["reference_place"],
                 float(row["latitude"]), float(row["longitude"]))
            )
    heights = elevations_for([(lat, lon) for *_, lat, lon in entries], config)
    target = Path(config.OUTPUT_FILE)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["kind", "name", "place", "latitude", "longitude",
                         "elevation_m"])
        for (kind, name, place, lat, lon), height in zip(entries, heights):
            writer.writerow([kind, name, place, lat, lon, round(height)])
    print(f"{len(entries)} Orte mit Höhenlage -> {target}")


if __name__ == "__main__":
    main()
