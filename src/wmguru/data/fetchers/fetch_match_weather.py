"""Holt Spieltag-Wetter (Open-Meteo Archiv, frei ohne Key) je Turnierspiel.

Liest die Match-CSVs aus dem StatsBomb-xG-Ordner (Stadion, Datum,
Anstoßzeit), ordnet jedem Stadion via Mapping-Tabelle Stadt/Koordinaten
zu und zieht Temperatur, gefühlte Temperatur und Luftfeuchte zur
Anstoßstunde (lokale Zeit) aus dem Open-Meteo-Archiv. Grundlage für
Klima-Features (Hitze-/Feuchte-Belastung, Klima-Distanz der Teams).
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path


class WeatherConfig:
    """Quelle, Stadion-Koordinaten und Zielpfad."""

    SOURCE_DIR: str = "Data/xG Tournament Data (StatsBomb Open Data)"
    OUTPUT_DIR: str = "Data/Match Weather (Open-Meteo)"
    OUTPUT_FILE: str = "tournament_match_weather.csv"
    API_URL: str = "https://archive-api.open-meteo.com/v1/archive"
    HOURLY_VARS: str = "temperature_2m,relative_humidity_2m,apparent_temperature"
    TIMEOUT_SECONDS: int = 30
    POLITE_DELAY_SECONDS: float = 0.15

    # Stadion-Erkennungs-Substring (normalisiert) -> (Stadt, Lat, Lon).
    # Reihenfolge relevant: spezifischere Schluessel zuerst.
    STADIUM_LOCATIONS: dict[str, tuple[str, float, float]] = {
        # WM 2022 (Katar -- klimatisch ein Standort)
        "ahmad bin ali": ("Doha", 25.29, 51.53),
        "al bayt": ("Doha", 25.29, 51.53),
        "al janoub": ("Doha", 25.29, 51.53),
        "al thumama": ("Doha", 25.29, 51.53),
        "education city": ("Doha", 25.29, 51.53),
        "khalifa international": ("Doha", 25.29, 51.53),
        "lusail": ("Doha", 25.29, 51.53),
        "stadium 974": ("Doha", 25.29, 51.53),
        # WM 2018 (Russland)
        "ak bars": ("Kazan", 55.80, 49.11),
        "ekaterinburg": ("Yekaterinburg", 56.84, 60.61),
        "mordovia": ("Saransk", 54.18, 45.18),
        "fisht": ("Sochi", 43.60, 39.73),
        "otkritie": ("Moscow", 55.75, 37.62),
        "luzhniki": ("Moscow", 55.75, 37.62),
        "rostec": ("Kaliningrad", 54.71, 20.45),
        "rostov": ("Rostov-on-Don", 47.24, 39.71),
        "saint-petersburg": ("Saint Petersburg", 59.94, 30.31),
        "solidarnost": ("Samara", 53.20, 50.15),
        "nizhny novgorod": ("Nizhny Novgorod", 56.33, 44.00),
        "volgograd": ("Volgograd", 48.71, 44.51),
        # EM 2021 (paneuropaeisch)
        "allianz": ("Munich", 48.14, 11.58),
        "nationala": ("Bucharest", 44.43, 26.10),
        "baki olimpiya": ("Baku", 40.41, 49.87),
        "cartuja": ("Seville", 37.39, -5.99),
        "estadio olimpico": ("Rome", 41.90, 12.50),
        "hampden": ("Glasgow", 55.86, -4.25),
        "cruijff": ("Amsterdam", 52.37, 4.90),
        "parken": ("Copenhagen", 55.68, 12.57),
        "puskas": ("Budapest", 47.50, 19.04),
        "wembley": ("London", 51.51, -0.13),
        # EM 2024 (Deutschland)
        "olympiastadion": ("Berlin", 52.52, 13.40),
        "deutsche bank": ("Frankfurt", 50.11, 8.68),
        "merkur": ("Duesseldorf", 51.23, 6.78),
        "mhparena": ("Stuttgart", 48.78, 9.18),
        "trainingszentrum rb leipzig": ("Leipzig", 51.34, 12.37),
        "red bull arena": ("Leipzig", 51.34, 12.37),
        "rheinenergie": ("Cologne", 50.94, 6.96),
        "signal": ("Dortmund", 51.51, 7.47),
        "veltins": ("Gelsenkirchen", 51.52, 7.10),
        "volksparkstadion": ("Hamburg", 53.55, 9.99),
        # Copa America 2024 (USA)
        "at&t": ("Arlington TX", 32.74, -97.11),
        "allegiant": ("Las Vegas", 36.17, -115.14),
        "arrowhead": ("Kansas City", 39.10, -94.58),
        "mercy park": ("Kansas City", 39.10, -94.58),
        "bank of america": ("Charlotte", 35.23, -80.84),
        "hard rock": ("Miami", 25.96, -80.24),
        "inter&co": ("Orlando", 28.54, -81.38),
        "levi": ("Santa Clara", 37.35, -121.96),
        "mercedes-benz": ("Atlanta", 33.75, -84.39),
        "metlife": ("East Rutherford", 40.81, -74.07),
        "nrg": ("Houston", 29.76, -95.36),
        "q2": ("Austin", 30.27, -97.74),
        "sofi": ("Inglewood", 33.96, -118.34),
        "state farm": ("Glendale AZ", 33.54, -112.19),
    }


def normalize(text: str) -> str:
    """Kleinschreibung + Akzente entfernen (für robustes Substring-Matching).

    Das türkische ı (U+0131) ist kein kombinierender Akzent und wird
    explizit ersetzt (z. B. \"Bakı\" -> \"baki\").
    """
    decomposed = unicodedata.normalize("NFKD", text.lower().replace("ı", "i"))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def locate_stadium(
    stadium: str, config: WeatherConfig
) -> tuple[str, float, float] | None:
    """Finde (Stadt, Lat, Lon) zum Stadionnamen; None falls unbekannt."""
    name = normalize(stadium)
    for key, location in config.STADIUM_LOCATIONS.items():
        if key in name:
            return location
    return None


def fetch_day_weather(
    latitude: float, longitude: float, day: str, config: WeatherConfig
) -> dict | None:
    """Lade die Stundenwerte eines Tages (lokale Zeit); None bei Fehler."""
    url = (
        f"{config.API_URL}?latitude={latitude}&longitude={longitude}"
        f"&start_date={day}&end_date={day}"
        f"&hourly={config.HOURLY_VARS}&timezone=auto"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "wm-quant-guru"})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def kickoff_hour(kick_off: str) -> int:
    """Anstoßstunde aus 'HH:MM:SS.mmm'; 15 Uhr als Fallback."""
    try:
        return max(0, min(23, int(kick_off.split(":")[0])))
    except (ValueError, IndexError):
        return 15


def main() -> None:
    """Hole das Anstoß-Wetter aller Turnierspiele und schreibe eine CSV."""
    config = WeatherConfig()
    output_path = Path(config.OUTPUT_DIR) / config.OUTPUT_FILE
    output_path.parent.mkdir(parents=True, exist_ok=True)
    day_cache: dict[tuple[float, float, str], dict | None] = {}
    written = 0
    unknown: set[str] = set()
    with output_path.open("w", encoding="utf-8", newline="") as sink:
        writer = csv.writer(sink)
        writer.writerow(
            ["tournament", "match_id", "match_date", "kick_off_local", "stadium",
             "city", "latitude", "longitude", "temperature_c",
             "apparent_temperature_c", "relative_humidity_pct"]
        )
        for csv_path in sorted(Path(config.SOURCE_DIR).glob("*.csv")):
            tournament = csv_path.stem
            with csv_path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    location = locate_stadium(row["stadium"], config)
                    if location is None:
                        unknown.add(row["stadium"])
                        continue
                    city, latitude, longitude = location
                    cache_key = (latitude, longitude, row["match_date"])
                    if cache_key not in day_cache:
                        day_cache[cache_key] = fetch_day_weather(
                            latitude, longitude, row["match_date"], config
                        )
                        time.sleep(config.POLITE_DELAY_SECONDS)
                    weather = day_cache[cache_key]
                    if weather is None:
                        continue
                    hour = kickoff_hour(row["kick_off"])
                    hourly = weather.get("hourly", {})
                    writer.writerow(
                        [tournament, row["match_id"], row["match_date"],
                         row["kick_off"], row["stadium"], city, latitude, longitude,
                         hourly.get("temperature_2m", [None] * 24)[hour],
                         hourly.get("apparent_temperature", [None] * 24)[hour],
                         hourly.get("relative_humidity_2m", [None] * 24)[hour]]
                    )
                    written += 1
    print(f"{written} Spiele mit Anstoß-Wetter -> {output_path}")
    if unknown:
        print("Unbekannte Stadien (bitte Mapping ergänzen):")
        for stadium in sorted(unknown):
            print(f"  {stadium.encode('ascii', 'replace').decode()}")


if __name__ == "__main__":
    main()
