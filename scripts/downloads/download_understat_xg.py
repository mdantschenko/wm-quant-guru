"""Lädt Understat-Club-xG-Datensätze (Kaggle, anonym) -- zwei Pakete.

1) understat-database (mexwell): je Big-5-Liga (+RFPL) Spiel-xG seit
   2014 inklusive Understats eigener Forecast-Wahrscheinlichkeiten
   (w/d/l) -- nutzbar als externes Modell-Benchmark.
2) player-stats-per-game (codytipton): 594k Spieler-Spiel-Zeilen mit
   xG/xA/xGChain/xGBuildup sowie Team-Spiel-Statistiken inkl. PPDA
   (Pressing-Intensität) und Deep Completions -- Metriken, die das
   Konzept fuer Laenderspiele als nicht verfuegbar einstufte; auf
   Vereinsebene sind sie es (Spieler-Form-Features vor Turnieren).
Reine Standardbibliothek.
"""
from __future__ import annotations

import io
import time
import urllib.request
import zipfile
from pathlib import Path


class UnderstatConfig:
    """Quellen und Zielstruktur."""

    USER_AGENT: str = "Mozilla/5.0 (research)"
    TIMEOUT_SECONDS: int = 600
    POLITE_DELAY_SECONDS: float = 1.0
    BASE_URL: str = "https://www.kaggle.com/api/v1/datasets/download/"
    OUTPUT_ROOT: str = "Data/Understat Club xG (2014-)"

    # Unterordner -> Kaggle-Datensatz.
    PACKAGES: dict[str, str] = {
        "league_matches": "mexwell/understat-database",
        "player_per_game": "codytipton/player-stats-per-game-understat",
    }


def main() -> None:
    """Lade beide Pakete (skip, falls Unterordner schon gefüllt)."""
    config = UnderstatConfig()
    for subfolder, ref in config.PACKAGES.items():
        target_dir = Path(config.OUTPUT_ROOT) / subfolder
        if target_dir.exists() and any(target_dir.rglob("*.csv")):
            print(f"  SKIP  {subfolder}")
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
            print(f"  FAIL  {subfolder}: {error}")
            continue
        time.sleep(config.POLITE_DELAY_SECONDS)
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(target_dir)
        csv_count = len(list(target_dir.rglob("*.csv")))
        print(f"  OK    {subfolder}: {csv_count} CSVs ({len(payload)/1e6:.0f} MB)")


if __name__ == "__main__":
    main()
