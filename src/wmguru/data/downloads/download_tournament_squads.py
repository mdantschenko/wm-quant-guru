"""Lädt Turnier-Kaderlisten (Spieler-CSVs) von FootyStats.

Pro Turnier eine CSV mit allen eingesetzten Spielern inkl. Verein
(``Current Club``), Nationalität, Einsatzminuten und FootyStats-Matchrating
(``average_rating_overall``). Grundlage für Kader-Features wie
Club-Chemistry (Herfindahl-Index über Vereinszugehörigkeit),
Legionärs-Anteile und aggregierte Form-Ratings. Nutzt dieselben
verifizierten comp-IDs wie download_tournament_odds.py.
Reine Standardbibliothek.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path


class SquadsConfig:
    """Quelle, Wettbewerbs-IDs und Zielpfad."""

    BASE_URL: str = "https://footystats.org/c-dl.php?type=players&comp="
    USER_AGENT: str = "Mozilla/5.0 (research; squads downloader)"
    TIMEOUT_SECONDS: int = 40
    POLITE_DELAY_SECONDS: float = 1.0
    OUTPUT_DIR: str = "Data/Tournament Squads (FootyStats)"
    HEADER_MARKER: str = "full_name"

    COMPETITIONS: dict[str, int] = {
        "World Cup 2014": 1384,
        "World Cup 2018": 1425,
        "World Cup 2022": 7432,
        "Euro 2016": 1400,
        "Euro 2020 (EM 2021)": 5635,
        "Euro 2024": 11084,
        "Copa America 2019": 1956,
        "Copa America 2021": 5862,
        "Copa America 2024": 12076,
    }


def fetch_csv(comp_id: int, config: SquadsConfig) -> bytes | None:
    """Lade die Spieler-CSV eines Wettbewerbs; None bei Fehler."""
    request = urllib.request.Request(
        f"{config.BASE_URL}{comp_id}", headers={"User-Agent": config.USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return response.read()
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None


def main() -> None:
    """Lade alle Kaderlisten (vorhandene werden übersprungen)."""
    config = SquadsConfig()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    for label, comp_id in config.COMPETITIONS.items():
        target = output_dir / f"{label}.csv"
        if target.exists():
            print(f"  SKIP  {label}")
            continue
        payload = fetch_csv(comp_id, config)
        time.sleep(config.POLITE_DELAY_SECONDS)
        if payload is None or config.HEADER_MARKER.encode() not in payload[:500]:
            print(f"  FAIL  {label} (comp={comp_id})")
            continue
        target.write_bytes(payload)
        line_count = payload.count(b"\n")
        print(f"  OK    {label}.csv ({line_count} Zeilen)")


if __name__ == "__main__":
    main()
