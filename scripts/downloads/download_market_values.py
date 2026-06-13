"""Lädt Transfermarkt-Spielermarktwerte (Kaggle player-scores, anonym).

Kaggle erlaubt für öffentliche Datensätze anonyme Einzeldatei-Downloads
über den v1-API-Endpoint (kein Account/Token nötig). Geladen werden die
zwei für das Nationalkader-Marktwert-Feature benötigten Dateien des
Datensatzes davidcariboo/player-scores. Reine Standardbibliothek.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path


class MarketValueConfig:
    """Quelle und Zielpfade für den player-scores-Download."""

    BASE_URL: str = (
        "https://www.kaggle.com/api/v1/datasets/download/davidcariboo/player-scores"
    )
    USER_AGENT: str = "Mozilla/5.0 (research; market-value downloader)"
    TIMEOUT_SECONDS: int = 300
    POLITE_DELAY_SECONDS: float = 1.0
    OUTPUT_DIR: str = "Data/Transfermarkt Market Values (player-scores)"
    # appearances: Minuten je Spieler/Vereinsspiel (Belastung);
    # transfers: Wechsel inkl. Datum/Abloese (Kader-Unruhe vor Turnieren);
    # games: Vereinsspiele inkl. Tabellenposition;
    # game_lineups: Aufstellungen seit ~2012 inkl. Kapitaens-Flag.
    FILES: tuple[str, ...] = (
        "player_valuations.csv", "players.csv", "appearances.csv",
        "transfers.csv", "games.csv", "game_lineups.csv",
    )


def fetch_file(file_name: str, config: MarketValueConfig) -> bytes | None:
    """Lade eine Einzeldatei des Datensatzes; None bei Fehler."""
    request = urllib.request.Request(
        f"{config.BASE_URL}/{file_name}",
        headers={"User-Agent": config.USER_AGENT},
    )
    try:
        with urllib.request.urlopen(
            request, timeout=config.TIMEOUT_SECONDS
        ) as response:
            return response.read()
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None


def main() -> None:
    """Lade alle konfigurierten Dateien (vorhandene werden übersprungen)."""
    config = MarketValueConfig()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    for file_name in config.FILES:
        target = output_dir / file_name
        if target.exists():
            print(f"  SKIP  {file_name} (bereits vorhanden)")
            continue
        payload = fetch_file(file_name, config)
        time.sleep(config.POLITE_DELAY_SECONDS)
        if payload is None or not payload.lstrip()[:200].count(b","):
            print(f"  FAIL  {file_name}")
            continue
        target.write_bytes(payload)
        print(f"  OK    {file_name} ({len(payload) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
