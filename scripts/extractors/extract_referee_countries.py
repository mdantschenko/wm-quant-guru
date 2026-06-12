"""Extrahiert Schiedsrichter-Nationalitäten aus StatsBomb Open Data.

Die Match-Listen der Turniere enthalten je Spiel den Schiedsrichter
samt Herkunftsland -- Basis für ein Konföderations-Bias-Feature
(südamerikanische Schiedsrichter lassen statistisch ein anderes Spiel
zu als europäische; Paarung Schiri-Konföderation x Team-Konföderation
ist in kaum einem Modell enthalten). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

from scripts.downloads.download_statsbomb_xg import StatsBombConfig, fetch_json


class RefereeCountryConfig:
    """Zielpfad (Turniere kommen aus StatsBombConfig)."""

    OUTPUT_FILE: str = "Data/Computed Features/referee_countries.csv"


def main() -> None:
    """Sammle (turnier, match, schiri, land) aus allen Match-Listen."""
    statsbomb = StatsBombConfig()
    target = Path(RefereeCountryConfig.OUTPUT_FILE)
    written = 0
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tournament", "match_id", "match_date", "referee",
                         "referee_country"])
        for label, (competition_id, season_id) in statsbomb.TOURNAMENTS.items():
            matches = fetch_json(
                f"{statsbomb.BASE_URL}/matches/{competition_id}/{season_id}.json",
                statsbomb,
            )
            time.sleep(statsbomb.POLITE_DELAY_SECONDS)
            if not isinstance(matches, list):
                print(f"  FAIL  {label}")
                continue
            for match in matches:
                referee = match.get("referee") or {}
                writer.writerow(
                    [label, match.get("match_id"), match.get("match_date"),
                     referee.get("name", ""),
                     (referee.get("country") or {}).get("name", "")]
                )
                written += 1
            print(f"  OK    {label}")
    print(f"{written} Spiele mit Schiri-Land -> {target}")


if __name__ == "__main__":
    main()
