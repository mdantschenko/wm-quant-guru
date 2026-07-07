"""Lädt EA-Sports-FC-Spielerratings (FIFA 15 -- FC 24) von Kaggle.

Anonymer Download (kein Token nötig) des Datensatzes
stefanoleone992/ea-sports-fc-24-complete-player-dataset. Die Datei
male_players.csv enthält alle Versionen FIFA 15 bis FC 24 mit
Attributen wie pace/shooting/defending/physic je Spieler und Version --
Basis für zeitkorrekte Kader-Athletik-Features (z. B. Pace-Differenz
Sturm vs. gegnerische Abwehr). Kaggle liefert die Datei als ZIP.
Reine Standardbibliothek.
"""
from __future__ import annotations

import io
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


class RatingsConfig:
    """Quelle und Zielpfade für die EA-FC-Ratings."""

    BASE_URL: str = (
        "https://www.kaggle.com/api/v1/datasets/download/"
        "stefanoleone992/ea-sports-fc-24-complete-player-dataset/"
    )
    USER_AGENT: str = "Mozilla/5.0 (research; ratings downloader)"
    TIMEOUT_SECONDS: int = 300
    OUTPUT_DIR: str = "Data/EA Sports FC Ratings (FIFA 15-24)"
    # male_players: Spieler je Version; male_teams: CLUB-Team-Ratings
    # je Version (keine Nationalteams enthalten).
    FILE_NAMES: tuple[str, ...] = ("male_players.csv", "male_teams.csv")


def download_one(file_name: str, config: RatingsConfig) -> None:
    """Lade eine Datei (ZIP-entpackt, skip falls vorhanden)."""
    target = Path(config.OUTPUT_DIR) / file_name
    if target.exists():
        print(f"SKIP  {target} (bereits vorhanden)")
        return
    request = urllib.request.Request(
        config.BASE_URL + file_name, headers={"User-Agent": config.USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            payload = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError) as error:
        print(f"FAIL  {file_name}: {error}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if payload[:2] == b"PK":  # Kaggle liefert groessere Dateien als ZIP
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extract(file_name, path=target.parent)
    else:
        target.write_bytes(payload)
    print(f"OK    {target} ({target.stat().st_size / 1e6:.0f} MB)")


def main() -> None:
    """Lade alle konfigurierten Dateien."""
    config = RatingsConfig()
    for file_name in config.FILE_NAMES:
        download_one(file_name, config)


if __name__ == "__main__":
    main()
