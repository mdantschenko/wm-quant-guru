"""Holt den aktuellen Elo-Stand aller Nationalteams von eloratings.net.

Betriebsskript für die WM 2026: Der historische Datensatz endet 2025;
dieses Skript zieht die Live-Tabelle (World.tsv) samt Team-Namen-Mapping
(en.teams.tsv) und schreibt einen datumsgestempelten Snapshot --
zeitkausal ablegbar vor jedem Spieltag. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import urllib.request
from datetime import date
from pathlib import Path


class EloConfig:
    """Endpunkte und Zielpfad."""

    WORLD_URL: str = "https://eloratings.net/World.tsv"
    TEAMS_URL: str = "https://eloratings.net/en.teams.tsv"
    USER_AGENT: str = "Mozilla/5.0 (research)"
    TIMEOUT_SECONDS: int = 30
    OUTPUT_DIR: str = "International Football Elo Ratings (1872-2025)/current"


def fetch_lines(url: str, config: EloConfig) -> list[str]:
    """Lade eine TSV-Datei als Zeilenliste."""
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8").splitlines()


def main() -> None:
    """Lade Live-Elo + Namen und schreibe einen Tages-Snapshot."""
    config = EloConfig()
    names = {
        parts[0]: parts[1]
        for line in fetch_lines(config.TEAMS_URL, config)
        if len(parts := line.split("\t")) >= 2
    }
    target = Path(config.OUTPUT_DIR) / f"elo_{date.today().isoformat()}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "team_code", "team_name", "elo"])
        for line in fetch_lines(config.WORLD_URL, config):
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            code = parts[2]
            writer.writerow([parts[0], code, names.get(code, code), parts[3]])
            written += 1
    print(f"{written} Teams (Live-Elo) -> {target}")


if __name__ == "__main__":
    main()
