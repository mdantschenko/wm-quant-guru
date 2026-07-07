"""Lädt die Fjelstul World Cup Database (Kaggle, anonym, ~1,3 MB).

Akademisch kuratierte, normalisierte Datenbank ALLER Weltmeisterschaften
1930--2022 (J. Fjelstul): 25+ Tabellen mit minutengenauen Toren, Karten,
Auswechslungen, Elfmetern, Kadern, Trainer- und Schiedsrichter-
Einsätzen, Stadien und Gruppentabellen. Referenzquelle für historische
Validierung und Langzeit-Features (Bank-Nutzung, Trainer- und
Schiri-Historie weit vor 2014). Reine Standardbibliothek.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path


class WcdbConfig:
    """Quelle und Zielpfad."""

    URL: str = (
        "https://www.kaggle.com/api/v1/datasets/download/"
        "joshfjelstul/world-cup-database"
    )
    USER_AGENT: str = "Mozilla/5.0 (research)"
    TIMEOUT_SECONDS: int = 300
    OUTPUT_DIR: str = "Data/World Cup Database (Fjelstul, 1930-2022)"


def main() -> None:
    """Lade das ZIP und entpacke alle Tabellen."""
    config = WcdbConfig()
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
    print(f"OK    {len(list(output_dir.glob('*.csv')))} Tabellen -> {output_dir}")


if __name__ == "__main__":
    main()
