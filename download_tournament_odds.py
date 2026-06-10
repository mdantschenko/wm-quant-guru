"""Lädt Turnierquoten (1X2 + Over/Under) von FootyStats.

Schließt das Quoten-Gap der jüngeren Turniere (2016--2024), das weder
football-data.co.uk (nur Vereinsligen) noch der Beat-The-Bookie-Datensatz
(endet Mitte 2015) abdeckt. FootyStats liefert pro Turnier eine Match-CSV
mit Vorab-Quoten über die URL /c-dl.php?type=matches&comp=<ID>; die hier
hinterlegten Wettbewerbs-IDs sind ohne Login abrufbar.

Reine Standardbibliothek.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path


class TournamentOddsConfig:
    """Quelle, Wettbewerbs-IDs und Zielpfad."""

    BASE_URL: str = "https://footystats.org/c-dl.php?type=matches&comp="
    USER_AGENT: str = "Mozilla/5.0 (research; tournament-odds downloader)"
    TIMEOUT_SECONDS: int = 40
    POLITE_DELAY_SECONDS: float = 1.0
    OUTPUT_DIR: str = "Tournament Odds (FootyStats)"
    ODDS_HEADER_MARKER: str = "odds_ft_home_team_win"

    # Beschrifteter Dateiname -> FootyStats-Wettbewerbs-ID.
    # Bestätigt (ohne Login abrufbar):
    #   World Cup 2018 = 1425, World Cup 2022 = 7432, Copa America 2024 = 12076
    # Euro-IDs (2016/2020/2024): von der FootyStats-Euro-Datasets-Seite im
    # Browser ablesen und unten eintragen (None => wird übersprungen).
    COMPETITIONS: dict[str, int | None] = {
        "World Cup 2018": 1425,
        "World Cup 2022": 7432,
        "Copa America 2024": 12076,
        "Euro 2016": None,
        "Euro 2020 (EM 2021)": None,
        "Euro 2024": None,
    }


def fetch_csv(comp_id: int, config: TournamentOddsConfig) -> bytes | None:
    """Lade die Match-CSV eines Wettbewerbs; None bei Fehler."""
    url = f"{config.BASE_URL}{comp_id}"
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(
            request, timeout=config.TIMEOUT_SECONDS
        ) as response:
            return response.read()
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None


def has_odds(payload: bytes, config: TournamentOddsConfig) -> bool:
    """Plausibilitätscheck: CSV enthält die 1X2-Quotenspalte."""
    head = payload[:2000].decode("utf-8", errors="replace")
    return config.ODDS_HEADER_MARKER in head


def download_all(config: TournamentOddsConfig) -> int:
    """Lade alle Wettbewerbe mit hinterlegter ID. Gibt Dateianzahl zurück."""
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for label, comp_id in config.COMPETITIONS.items():
        if comp_id is None:
            print(f"  SKIP  {label} (keine comp-ID hinterlegt)")
            continue
        payload = fetch_csv(comp_id, config)
        time.sleep(config.POLITE_DELAY_SECONDS)
        if payload is None or not has_odds(payload, config):
            print(f"  FAIL  {label} (comp={comp_id}, keine gültige Quoten-CSV)")
            continue
        rows = payload.count(b"\n")
        (output_dir / f"{label}.csv").write_bytes(payload)
        written += 1
        print(f"  OK    {label}.csv ({rows} Zeilen)")
    return written


def main() -> None:
    """Lade alle konfigurierten Turnierquoten."""
    config = TournamentOddsConfig()
    print("Lade Turnierquoten (FootyStats) ...")
    count = download_all(config)
    print(f"\nFertig: {count} Turnier-CSVs in '{config.OUTPUT_DIR}'.")


if __name__ == "__main__":
    main()
