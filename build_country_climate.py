"""Baut Länder-Klimanormale und Klima-Distanzen je Turnierspiel.

Schritt 1: Für jedes Teilnehmerland (alle Turniere inkl. WM 2026) die
mittlere Juni/Juli-Tagestemperatur 2015--2024 am bevölkerungsreichsten
Ort (Open-Meteo Geocoding + Archiv, frei ohne Key) -> country_climate.csv.
Schritt 2: Für jedes historische Turnierspiel die Klima-Distanz je Team
(gefühlte Anstoß-Temperatur minus Heimat-Klimanormal)
-> match_climate_distance.csv. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


class ClimateConfig:
    """Quellen, API-Endpunkte und Zielpfade."""

    XG_DIR: str = "xG Tournament Data (StatsBomb Open Data)"
    WC2026_SQUADS: str = "Tournament Squads (Wikipedia)/World Cup 2026.csv"
    WEATHER_FILE: str = "Match Weather (Open-Meteo)/tournament_match_weather.csv"
    CLIMATE_FILE: str = "Computed Features/country_climate.csv"
    DISTANCE_FILE: str = "Computed Features/match_climate_distance.csv"

    GEOCODE_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
    ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
    TIMEOUT_SECONDS: int = 30
    POLITE_DELAY_SECONDS: float = 0.15
    ARCHIVE_DELAY_SECONDS: float = 1.2   # 10-Jahres-Abfragen werden gedrosselt
    RETRY_WAIT_SECONDS: float = 10.0
    CLIMATE_YEARS: tuple[int, int] = (2015, 2024)

    # Nicht-souveraene/uneindeutige Teamnamen -> geokodierbarer Ort.
    GEOCODE_OVERRIDES: dict[str, str] = {
        "England": "London", "Scotland": "Glasgow", "Wales": "Cardiff",
        "Northern Ireland": "Belfast", "South Korea": "Seoul",
        "Korea Republic": "Seoul", "North Korea": "Pyongyang",
        "United States": "Washington", "USA": "Washington",
        "Ivory Coast": "Abidjan", "Cote d'Ivoire": "Abidjan",
        "DR Congo": "Kinshasa", "Czech Republic": "Prague", "Czechia": "Prague",
        "Bosnia and Herzegovina": "Sarajevo", "Curacao": "Willemstad",
        "Cape Verde": "Praia", "New Zealand": "Auckland",
        "Republic of Ireland": "Dublin", "Turkey": "Ankara",
        "China PR": "Beijing", "IR Iran": "Tehran",
    }


def api_json(url: str, config: ClimateConfig) -> dict | None:
    """GET mit JSON-Antwort; None bei Fehler."""
    request = urllib.request.Request(url, headers={"User-Agent": "wm-quant-guru"})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except Exception:
        return None


def collect_countries(config: ClimateConfig) -> set[str]:
    """Alle Teamnamen aus historischen Turnieren und WM-2026-Kadern."""
    countries: set[str] = set()
    for path in Path(config.XG_DIR).glob("*.csv"):
        for row in csv.DictReader(path.open(encoding="utf-8", newline="")):
            countries.update((row["home_team"], row["away_team"]))
    for row in csv.DictReader(
        Path(config.WC2026_SQUADS).open(encoding="utf-8", newline="")
    ):
        countries.add(row["team"])
    return countries


def june_july_mean(latitude: float, longitude: float, config: ClimateConfig) -> float | None:
    """Mittlere Juni/Juli-Tagestemperatur ueber die Klimajahre."""
    first, last = config.CLIMATE_YEARS
    url = (
        f"{config.ARCHIVE_URL}?latitude={latitude}&longitude={longitude}"
        f"&start_date={first}-06-01&end_date={last}-07-31"
        f"&daily=temperature_2m_mean&timezone=UTC"
    )
    data = api_json(url, config)
    if data is None:
        return None
    days = data.get("daily", {}).get("time", [])
    values = data.get("daily", {}).get("temperature_2m_mean", [])
    summer = [v for d, v in zip(days, values)
              if v is not None and d[5:7] in ("06", "07")]
    return round(sum(summer) / len(summer), 2) if summer else None


def build_country_climate(config: ClimateConfig) -> dict[str, float]:
    """Geokodiere alle Laender und schreibe die Klimanormale (resumierbar)."""
    climates: dict[str, float] = {}
    rows: list[list[object]] = []
    target = Path(config.CLIMATE_FILE)
    if target.exists():  # bereits berechnete Laender uebernehmen
        with target.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                climates[row["country"]] = float(row["jun_jul_mean_temp_c"])
                rows.append([row["country"], row["reference_place"],
                             row["latitude"], row["longitude"],
                             row["jun_jul_mean_temp_c"]])
    for country in sorted(collect_countries(config)):
        if country in climates:
            continue
        query = config.GEOCODE_OVERRIDES.get(country, country)
        geo = api_json(
            f"{config.GEOCODE_URL}?name={urllib.parse.quote(query)}&count=1",
            config,
        )
        time.sleep(config.POLITE_DELAY_SECONDS)
        results = (geo or {}).get("results") or []
        if not results:
            print(f"  SKIP  {country} (nicht geokodierbar)")
            continue
        place = results[0]
        mean_temp = june_july_mean(place["latitude"], place["longitude"], config)
        if mean_temp is None:  # einmal nachfassen (Drosselung)
            time.sleep(config.RETRY_WAIT_SECONDS)
            mean_temp = june_july_mean(place["latitude"], place["longitude"], config)
        time.sleep(config.ARCHIVE_DELAY_SECONDS)
        if mean_temp is None:
            print(f"  SKIP  {country} (kein Klimawert)")
            continue
        climates[country] = mean_temp
        rows.append([country, place.get("name"), place["latitude"],
                     place["longitude"], mean_temp])
    target = Path(config.CLIMATE_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["country", "reference_place", "latitude", "longitude",
                         "jun_jul_mean_temp_c"])
        writer.writerows(rows)
    print(f"{len(rows)} Laender-Klimanormale -> {target}")
    return climates


def build_match_distances(climates: dict[str, float], config: ClimateConfig) -> None:
    """Klima-Distanz je historischem Turnierspiel und Team."""
    teams_by_match: dict[str, tuple[str, str]] = {}
    for path in Path(config.XG_DIR).glob("*.csv"):
        for row in csv.DictReader(path.open(encoding="utf-8", newline="")):
            teams_by_match[row["match_id"]] = (row["home_team"], row["away_team"])
    target = Path(config.DISTANCE_FILE)
    written = 0
    with target.open("w", encoding="utf-8", newline="") as sink:
        writer = csv.writer(sink)
        writer.writerow(["tournament", "match_id", "match_date", "city",
                         "apparent_temperature_c", "home_team",
                         "home_climate_delta_c", "away_team",
                         "away_climate_delta_c"])
        for row in csv.DictReader(
            Path(config.WEATHER_FILE).open(encoding="utf-8", newline="")
        ):
            teams = teams_by_match.get(row["match_id"])
            apparent = row["apparent_temperature_c"]
            if teams is None or not apparent:
                continue
            home, away = teams
            deltas = [
                round(float(apparent) - climates[t], 1) if t in climates else ""
                for t in (home, away)
            ]
            writer.writerow([row["tournament"], row["match_id"], row["match_date"],
                             row["city"], apparent, home, deltas[0], away, deltas[1]])
            written += 1
    print(f"{written} Spiel-Klimadistanzen -> {target}")


def main() -> None:
    """Erzeuge Klimanormale und Spiel-Klimadistanzen."""
    config = ClimateConfig()
    climates = build_country_climate(config)
    build_match_distances(climates, config)


if __name__ == "__main__":
    main()
