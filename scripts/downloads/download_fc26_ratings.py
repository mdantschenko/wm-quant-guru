"""Lädt EA-FC-26-Spielerratings (Kaggle justdhia, anonym, ~2,7 MB ZIP).

Aktueller Scouting-Stand für die WM 2026: 16.000+ Spieler mit
pac/sho/pas/dri/def/phy, Nationalität, Verein und Liga. Ergänzt die
historischen Versionen FIFA 15--FC 24. Reine Standardbibliothek.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path


class Fc26Config:
    """Quelle und Zielpfad."""

    URL: str = (
        "https://www.kaggle.com/api/v1/datasets/download/"
        "justdhia/ea-sports-fc-26-player-ratings"
    )
    USER_AGENT: str = "Mozilla/5.0 (research)"
    TIMEOUT_SECONDS: int = 120
    OUTPUT_DIR: str = "Data/EA Sports FC Ratings (FIFA 15-24)/FC26"


def main() -> None:
    """Lade das ZIP und entpacke alle CSVs."""
    config = Fc26Config()
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
