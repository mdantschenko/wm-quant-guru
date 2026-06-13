"""Lädt das API-Football-Statistikpaket (Kaggle tonygordonjr, anonym).

~115 MB Vereinsfussball-Tiefendaten 2020--2024 (Big-5-Ligen,
Championship, MLS, UEFA Champions League): Spiel-Events, AUFSTELLUNGEN
mit Formation und Trainer, Team-/Spieler-Statistiken je Spiel,
Tabellenstaende, Venues -- und vor allem 80.000+ VERLETZUNGS-Eintraege
(Spieler, Datum, Grund), die zuvor als nicht frei beschaffbar galten.
Reine Standardbibliothek.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path


class MatchStatsConfig:
    """Quelle und Zielpfad."""

    URL: str = (
        "https://www.kaggle.com/api/v1/datasets/download/"
        "tonygordonjr/football-match-statistics-and-more"
    )
    USER_AGENT: str = "Mozilla/5.0 (research)"
    TIMEOUT_SECONDS: int = 1800
    OUTPUT_DIR: str = "Data/Match Statistics & Injuries (API-Football 2020-2024)"


def main() -> None:
    """Lade das ZIP und entpacke alle CSVs."""
    config = MatchStatsConfig()
    output_dir = Path(config.OUTPUT_DIR)
    if any(output_dir.glob("*.csv")):
        print(f"SKIP  {output_dir} (bereits vorhanden)")
        return
    request = urllib.request.Request(
        config.URL, headers={"User-Agent": config.USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
        payload = response.read()
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extractall(output_dir)
    print(f"OK    {sorted(p.name for p in output_dir.glob('*.csv'))} -> {output_dir}")


if __name__ == "__main__":
    main()
