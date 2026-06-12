"""Baut Schiedsrichter-Profile aus den Turnier-Match-CSVs (FootyStats).

Pro Schiedsrichter werden über alle abgeschlossenen Turnierspiele
Karten- und Foul-Raten aggregiert -- Basis für das Regulierungs-Feature
(kleinliche vs. laufenlassende Schiedsrichter). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from pathlib import Path


class RefereeConfig:
    """Quellen und Zielpfad."""

    SOURCE_DIR: str = "Data/Tournament Odds (FootyStats)"
    OUTPUT_FILE: str = "Data/Computed Features/referee_profiles.csv"


def to_int(value: str | None) -> int:
    """Robuste Ganzzahl-Konvertierung (leere/N/A-Felder -> 0)."""
    try:
        return int(value or 0)
    except ValueError:
        return 0


def main() -> None:
    """Aggregiere Karten/Fouls je Schiedsrichter über alle Turniere."""
    config = RefereeConfig()
    stats: dict[str, dict[str, object]] = {}
    for path in sorted(Path(config.SOURCE_DIR).glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                referee = (row.get("referee") or "").strip()
                if row.get("status") != "complete" or referee in ("", "N/A"):
                    continue
                entry = stats.setdefault(
                    referee,
                    {"matches": 0, "yellows": 0, "reds": 0, "fouls": 0,
                     "tournaments": set()},
                )
                entry["matches"] += 1
                entry["yellows"] += to_int(row.get("home_team_yellow_cards"))
                entry["yellows"] += to_int(row.get("away_team_yellow_cards"))
                entry["reds"] += to_int(row.get("home_team_red_cards"))
                entry["reds"] += to_int(row.get("away_team_red_cards"))
                entry["fouls"] += to_int(row.get("home_team_fouls"))
                entry["fouls"] += to_int(row.get("away_team_fouls"))
                entry["tournaments"].add(path.stem)
    target = Path(config.OUTPUT_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["referee", "n_matches", "avg_yellow_cards",
                         "avg_red_cards", "avg_fouls", "tournaments"])
        for referee, entry in sorted(
            stats.items(), key=lambda kv: -int(kv[1]["matches"])
        ):
            matches = int(entry["matches"])
            writer.writerow(
                [referee, matches,
                 round(int(entry["yellows"]) / matches, 2),
                 round(int(entry["reds"]) / matches, 3),
                 round(int(entry["fouls"]) / matches, 1),
                 "; ".join(sorted(entry["tournaments"]))]
            )
    print(f"{len(stats)} Schiedsrichter-Profile -> {target}")


if __name__ == "__main__":
    main()
