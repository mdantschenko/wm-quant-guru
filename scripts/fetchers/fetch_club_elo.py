"""Holt Club-Elo-Ratings von clubelo.com (offene API, kein Key).

Club-Elo quantifiziert die Vereinsstärke tagesgenau seit den 1940ern --
als Kontext-Feature für Spielerprofile (Qualität des Vereinsumfelds der
Legionäre) und Club-Wettbewerbs-Analysen. Geholt werden Jahres-Snapshots
(1.6. jedes Jahres, ~630 Klubs je Snapshot) plus der aktuelle Stand.
API: http://api.clubelo.com/YYYY-MM-DD (CSV). Reine Standardbibliothek.
"""
from __future__ import annotations

import time
import urllib.request
from datetime import date
from pathlib import Path


class ClubEloConfig:
    """Endpunkt, Zeitraum und Zielpfad."""

    API_URL: str = "http://api.clubelo.com/"
    FIRST_YEAR: int = 2000
    SNAPSHOT_MONTH_DAY: str = "06-01"
    TIMEOUT_SECONDS: int = 40
    POLITE_DELAY_SECONDS: float = 1.0
    OUTPUT_DIR: str = "Data/Club Elo (clubelo.com)"


def fetch_snapshot(day: str, config: ClubEloConfig) -> bytes | None:
    """Lade den Ranking-Snapshot eines Tages; None bei Fehler."""
    request = urllib.request.Request(
        config.API_URL + day, headers={"User-Agent": "wm-quant-guru"}
    )
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return response.read()
    except Exception:
        return None


def main() -> None:
    """Lade Jahres-Snapshots und den aktuellen Stand (resumierbar)."""
    config = ClubEloConfig()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    days = [f"{year}-{config.SNAPSHOT_MONTH_DAY}"
            for year in range(config.FIRST_YEAR, date.today().year + 1)]
    today = date.today().isoformat()
    if today not in days:
        days.append(today)
    for day in days:
        target = output_dir / f"clubelo_{day}.csv"
        if target.exists():
            continue
        payload = fetch_snapshot(day, config)
        time.sleep(config.POLITE_DELAY_SECONDS)
        if payload is None or not payload.startswith(b"Rank,"):
            print(f"  FAIL  {day}")
            continue
        target.write_bytes(payload)
        club_count = payload.count(b"\n") - 1
        print(f"  OK    {day} ({club_count} Klubs)")
    print(f"-> {output_dir}")


if __name__ == "__main__":
    main()
