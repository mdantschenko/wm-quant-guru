"""Geokodiert alle Spielorte aus results.csv (Open-Meteo, frei ohne Key).

~2.200 einzigartige (Stadt, Land)-Paare aus 49.400 Länderspielen werden
zu Koordinaten + ZEITZONE aufgelöst -- damit lassen sich Reisedistanz,
Zeitzonenwechsel, Höhe und Klima für den GESAMTEN Trainingsdatensatz
berechnen (Konzept-P1-Feature), nicht nur für die Turnierspiele.
Bevorzugt wird der Geocoding-Treffer, dessen Land zum results-Land
passt. Resumierbar (vorhandene Paare werden übersprungen).
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path


class GeocodeConfig:
    """Quelle, Endpunkt und Zielpfad."""

    RESULTS_FILE: str = (
        "Data/International football results from 1872 to 2026/results.csv"
    )
    API_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
    TIMEOUT_SECONDS: int = 30
    POLITE_DELAY_SECONDS: float = 0.15
    OUTPUT_FILE: str = "Data/Computed Features/match_city_geocodes.csv"


def normalize(text: str) -> str:
    """Kleinschreibung + Akzente entfernen (für Ländervergleich)."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def geocode(city: str, country: str, config: GeocodeConfig) -> dict | None:
    """Geokodiere eine Stadt; bevorzuge Treffer im passenden Land."""
    url = (
        f"{config.API_URL}?name={urllib.parse.quote(city)}&count=5"
        "&language=en&format=json"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "wm-quant-guru"})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            results = json.loads(response.read()).get("results") or []
    except Exception:
        return None
    if not results:
        return None
    want = normalize(country)
    for candidate in results:
        if normalize(candidate.get("country", "")) == want:
            return candidate
    for candidate in results:
        if want in normalize(candidate.get("country", "")) or \
                normalize(candidate.get("country", "")) in want:
            return candidate
    return results[0]


def main() -> None:
    """Geokodiere alle einzigartigen Spielorte (resumierbar)."""
    config = GeocodeConfig()
    pairs: set[tuple[str, str]] = set()
    with Path(config.RESULTS_FILE).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            city = row["city"].strip()
            country = row["country"].strip()
            if city and country:
                pairs.add((city, country))
    target = Path(config.OUTPUT_FILE)
    done: set[tuple[str, str]] = set()
    if target.exists():
        with target.open(encoding="utf-8", newline="") as handle:
            done = {(r["city"], r["country"]) for r in csv.DictReader(handle)}
    is_new = not target.exists()
    written = failed = 0
    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(["city", "country", "latitude", "longitude",
                             "timezone", "resolved_name", "resolved_country"])
        for city, country in sorted(pairs - done):
            hit = geocode(city, country, config)
            time.sleep(config.POLITE_DELAY_SECONDS)
            if hit is None:
                failed += 1
                continue
            writer.writerow(
                [city, country, hit.get("latitude"), hit.get("longitude"),
                 hit.get("timezone", ""), hit.get("name", ""),
                 hit.get("country", "")]
            )
            written += 1
            if written % 250 == 0:
                print(f"  ... {written} geokodiert", flush=True)
    print(f"+{written} geokodiert ({failed} ohne Treffer, "
          f"{len(done)} bereits vorhanden) -> {target}")


if __name__ == "__main__":
    main()
