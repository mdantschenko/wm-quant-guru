"""Lädt vorab aufbereitete Club-Match-Daten + UEFA-Historie (Kaggle, anonym).

Zwei kompakte, sofort nutzbare Datensätze:
  1) adamgbor/club-football-match-data-2000-2025: 230k Spiele aus 38
     Divisionen mit Elo, Form, Vollstatistik und Quoten je Spiel +
     245k Klub-Tag-Elo-Zeilen.
  2) rtx666x3/all-time-uefa-competitions-results: 28k UEFA-Klubspiele
     1955-2026 (CL/EL/UEFA-Cup/CWC/...) plus Klub-Koordinaten.
Reine Standardbibliothek.
"""
from __future__ import annotations

import io
import time
import urllib.request
import zipfile
from pathlib import Path


class ClubDataConfig:
    """Kaggle-Datensätze und Zielordner."""

    BASE_URL: str = "https://www.kaggle.com/api/v1/datasets/download/"
    USER_AGENT: str = "Mozilla/5.0 (research)"
    TIMEOUT_SECONDS: int = 300
    POLITE_DELAY_SECONDS: float = 1.0

    # Kaggle-Ref -> Zielordner.
    PACKAGES: dict[str, str] = {
        "adamgbor/club-football-match-data-2000-2025":
            "Data/Club Football Engineered (2000-2025)",
        "rtx666x3/all-time-uefa-competitions-results":
            "Data/UEFA Club Competitions (Beat The Bookie)/all_time_results",
    }


def main() -> None:
    """Lade beide Pakete (skip, falls Ordner schon CSVs enthält)."""
    config = ClubDataConfig()
    for ref, out in config.PACKAGES.items():
        output_dir = Path(out)
        if output_dir.exists() and any(output_dir.glob("*.csv")):
            print(f"  SKIP  {ref}")
            continue
        request = urllib.request.Request(
            config.BASE_URL + ref, headers={"User-Agent": config.USER_AGENT}
        )
        try:
            with urllib.request.urlopen(
                request, timeout=config.TIMEOUT_SECONDS
            ) as response:
                payload = response.read()
        except Exception as error:
            print(f"  FAIL  {ref}: {error}")
            continue
        time.sleep(config.POLITE_DELAY_SECONDS)
        output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(output_dir)
        print(f"  OK    {ref} -> {output_dir}")


if __name__ == "__main__":
    main()
