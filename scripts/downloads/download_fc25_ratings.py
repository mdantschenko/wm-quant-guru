"""Lädt EA-FC-25-Spielerratings (Kaggle nyagami, anonym, ~3,4 MB ZIP).

Schließt die Versionslücke zwischen FC 24 und FC 26: vollständige
Spielerdatenbank (männlich/weiblich) mit pac/sho/def/phy-Attributen,
Nation, Verein und Liga. Reine Standardbibliothek.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path


class Fc25Config:
    """Quelle und Zielpfad."""

    URL: str = (
        "https://www.kaggle.com/api/v1/datasets/download/"
        "nyagami/ea-sports-fc-25-database-ratings-and-stats"
    )
    USER_AGENT: str = "Mozilla/5.0 (research)"
    TIMEOUT_SECONDS: int = 120
    OUTPUT_DIR: str = "Data/EA Sports FC Ratings (FIFA 15-24)/FC25"


def main() -> None:
    """Lade das ZIP und entpacke alle CSVs."""
    config = Fc25Config()
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
