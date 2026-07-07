"""Holt Bevölkerung und BIP je Land (World-Bank-API, frei ohne Key).

Klassische Talent-Pool-Kovariaten der Turnierprognose-Literatur
(Bernard & Busse 2004): Bevölkerungsgröße und Wirtschaftskraft erklären
einen messbaren Teil des Nationalteam-Erfolgs. Geholt werden Jahreswerte
2000--heute für alle Länder (SP.POP.TOTL, NY.GDP.MKTP.CD).
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.request
from pathlib import Path


class WorldBankConfig:
    """Indikatoren, Endpunkt und Zielpfad."""

    API_URL: str = (
        "https://api.worldbank.org/v2/country/all/indicator/{indicator}"
        "?format=json&per_page=20000&date=2000:2026"
    )
    INDICATORS: dict[str, str] = {
        "population": "SP.POP.TOTL",
        "gdp_usd": "NY.GDP.MKTP.CD",
    }
    TIMEOUT_SECONDS: int = 120
    POLITE_DELAY_SECONDS: float = 1.0
    OUTPUT_FILE: str = "Data/Computed Features/worldbank_population_gdp.csv"


def fetch_indicator(code: str, config: WorldBankConfig) -> dict[tuple[str, str], float]:
    """(land, jahr) -> Wert für einen Indikator."""
    request = urllib.request.Request(
        config.API_URL.format(indicator=code),
        headers={"User-Agent": "wm-quant-guru"},
    )
    with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read())
    series: dict[tuple[str, str], float] = {}
    for row in payload[1] or []:
        value = row.get("value")
        if value is None:
            continue
        series[(row["country"]["value"], row["date"])] = float(value)
    return series


def main() -> None:
    """Lade beide Indikatoren und schreibe eine kombinierte CSV."""
    config = WorldBankConfig()
    population = fetch_indicator(config.INDICATORS["population"], config)
    time.sleep(config.POLITE_DELAY_SECONDS)
    gdp = fetch_indicator(config.INDICATORS["gdp_usd"], config)
    target = Path(config.OUTPUT_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted(set(population) | set(gdp))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["country", "year", "population", "gdp_usd"])
        for country, year in keys:
            writer.writerow(
                [country, year,
                 population.get((country, year), ""),
                 gdp.get((country, year), "")]
            )
    print(f"{len(keys)} Land-Jahr-Zeilen -> {target}")


if __name__ == "__main__":
    main()
