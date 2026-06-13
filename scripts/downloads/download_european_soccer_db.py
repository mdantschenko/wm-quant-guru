"""Lädt die European Soccer Database (Kaggle hugomathien, anonym).

Der klassische Forschungsdatensatz: ~25.000 Spiele aus 11 europäischen
Ligen 2008--2016 als SQLite-Datenbank, inklusive Spieler-Aufstellungen
je Spiel, Buchmacherquoten mehrerer Anbieter und FIFA-Spielerattributen
im Zeitverlauf -- ideale historische Tiefe für Vereins-Features und
Aufstellungs-basierte Analysen. ~300 MB ZIP. Reine Standardbibliothek.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path


class SoccerDbConfig:
    """Quelle und Zielpfad."""

    URL: str = "https://www.kaggle.com/api/v1/datasets/download/hugomathien/soccer"
    USER_AGENT: str = "Mozilla/5.0 (research)"
    TIMEOUT_SECONDS: int = 1800
    OUTPUT_DIR: str = "Data/European Soccer Database (Kaggle)"


def main() -> None:
    """Lade das ZIP und entpacke die SQLite-Datenbank."""
    config = SoccerDbConfig()
    output_dir = Path(config.OUTPUT_DIR)
    if any(output_dir.glob("*.sqlite")):
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
    files = sorted(p.name for p in output_dir.iterdir())
    print(f"OK    {files} -> {output_dir}")


if __name__ == "__main__":
    main()
