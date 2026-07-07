"""Extrahiert die Cheftrainer aller Turnier-Kader von Wikipedia.

Die ``...squads``-Seiten nennen je Team den Cheftrainer inklusive
Nationalitäts-Flagge -- Basis für Trainer-Features (ausländischer
Trainer, Trainer-Kontinuität über Turniere). Nutzt die Seiten- und
Fetch-Logik des Kader-Downloaders. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import re
import time
from pathlib import Path

from src.scripts.downloads.download_wikipedia_squads import WikiSquadsConfig, fetch_wikitext, strip_link


class CoachConfig:
    """Zielpfad (Quellen kommen aus WikiSquadsConfig)."""

    OUTPUT_FILE: str = "Data/Tournament Squads (Wikipedia)/coaches.csv"


def parse_coaches(wikitext: str) -> list[tuple[str, str, str]]:
    """Sammle (team, coach, coach_country) aus einem Squads-Wikitext."""
    rows: list[tuple[str, str, str]] = []
    team = ""
    for line in wikitext.splitlines():
        team_match = re.match(r"^===\s*([^=]+?)\s*===\s*$", line)
        if team_match:
            team = team_match.group(1)
            continue
        # Nur Zeilen, die mit "(Head) Coach:" oder "Manager:" BEGINNEN
        # (Wiki-Markup wie ";" oder "'''" davor erlaubt) -- WM-Seiten
        # nutzen "Coach:", EM-Seiten "Manager:"; schliesst Fliesstext-
        # Treffer und Verbands-/Quellen-Links aus.
        coach_match = re.match(
            r"^[;:'*\s]*(?:Head\s+)?(?:[Cc]oach|[Mm]anager)\s*:\s*(.+)$", line
        )
        if coach_match is None or not team:
            continue
        tail = coach_match.group(1)
        country_match = re.search(r"\{\{(?:flagicon|fb)\|([A-Za-z ]{2,20})\}\}", tail)
        link_match = re.search(r"\[\[[^\]]+\]\]", tail)
        if link_match:
            rows.append(
                (team, strip_link(link_match.group(0)),
                 country_match.group(1) if country_match else "")
            )
    return rows


def main() -> None:
    """Extrahiere die Trainer aller konfigurierten Turniere."""
    squads_config = WikiSquadsConfig()
    target = Path(CoachConfig.OUTPUT_FILE)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tournament", "team", "coach", "coach_country",
                         "foreign_coach"])
        for label, page in squads_config.PAGES.items():
            wikitext = fetch_wikitext(page, squads_config)
            time.sleep(squads_config.POLITE_DELAY_SECONDS)
            if wikitext is None:
                print(f"  FAIL  {label}")
                continue
            coaches = parse_coaches(wikitext)
            for team, coach, country in coaches:
                foreign = bool(country) and country.lower() != team.lower()
                writer.writerow([label, team, coach, country, int(foreign)])
            print(f"  OK    {label}: {len(coaches)} Trainer")
    print(f"-> {target}")


if __name__ == "__main__":
    main()
