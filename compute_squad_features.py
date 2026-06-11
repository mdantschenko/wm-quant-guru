"""Berechnet Kader-Features: Club-Chemistry (HHI) und Legionärs-Anteile.

Club-Chemistry: Herfindahl-Hirschman-Index über die Vereinszugehörigkeit
eines Nationalkaders (Blockbildung, z. B. Bayern-Block 2014). Quellen:
FootyStats-Kaderlisten (9 historische Turniere, Team = Nationalität)
und die Wikipedia-Kader der WM 2026. Für die WM 2026 zusätzlich der
Anteil der Spieler in Top-5-Ligen (Verbandsland des Vereins).
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


class SquadFeatureConfig:
    """Quellen, Zielpfad und Parameter."""

    FOOTYSTATS_DIR: str = "Tournament Squads (FootyStats)"
    WC2026_FILE: str = "World Cup 2026 Squads (Wikipedia)/wc2026_squads.csv"
    OUTPUT_FILE: str = "Computed Features/club_chemistry_hhi.csv"
    TOP5_CODES: frozenset[str] = frozenset({"ENG", "ESP", "GER", "ITA", "FRA"})
    MIN_SQUAD: int = 15  # FootyStats listet teils Randspieler; Minimum je Team


def hhi_row(
    tournament: str, team: str, clubs: list[str], top5_share: str
) -> list[object]:
    """Bilde eine Ergebniszeile aus der Vereinsliste eines Kaders."""
    counts = Counter(clubs)
    total = sum(counts.values())
    hhi = round(sum((n / total) ** 2 for n in counts.values()), 4)
    top_club, top_n = counts.most_common(1)[0]
    return [tournament, team, total, len(counts), hhi, top_club,
            round(top_n / total, 3), top5_share]


def footystats_rows(config: SquadFeatureConfig) -> list[list[object]]:
    """HHI je Team für alle FootyStats-Turnier-Kaderlisten."""
    rows: list[list[object]] = []
    for path in sorted(Path(config.FOOTYSTATS_DIR).glob("*.csv")):
        clubs_by_team: dict[str, list[str]] = {}
        with path.open(encoding="utf-8", newline="") as handle:
            for player in csv.DictReader(handle):
                club = (player.get("Current Club") or "").strip()
                team = (player.get("nationality") or "").strip()
                if club and club.upper() != "N/A" and team:
                    clubs_by_team.setdefault(team, []).append(club)
        for team, clubs in sorted(clubs_by_team.items()):
            if len(clubs) < config.MIN_SQUAD:
                continue
            # Datendefekt mancher FootyStats-Dateien (z. B. Copa 2019):
            # "Current Club" enthaelt das Nationalteam statt des Vereins.
            if clubs.count(team) / len(clubs) > 0.5:
                continue
            rows.append(hhi_row(path.stem, team, clubs, ""))
    return rows


def wc2026_rows(config: SquadFeatureConfig) -> list[list[object]]:
    """HHI + Top-5-Liga-Anteil je Team für die WM-2026-Kader."""
    clubs_by_team: dict[str, list[str]] = {}
    top5_by_team: dict[str, list[bool]] = {}
    with Path(config.WC2026_FILE).open(encoding="utf-8", newline="") as handle:
        for player in csv.DictReader(handle):
            team = player["team"].strip()
            clubs_by_team.setdefault(team, []).append(player["club"].strip())
            top5_by_team.setdefault(team, []).append(
                player["club_country"].upper() in config.TOP5_CODES
            )
    rows: list[list[object]] = []
    for team, clubs in sorted(clubs_by_team.items()):
        share = sum(top5_by_team[team]) / len(top5_by_team[team])
        rows.append(hhi_row("World Cup 2026", team, clubs, f"{share:.3f}"))
    return rows


def main() -> None:
    """Berechne und schreibe alle Kader-Features."""
    config = SquadFeatureConfig()
    rows = footystats_rows(config) + wc2026_rows(config)
    target = Path(config.OUTPUT_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tournament", "team", "n_players", "n_clubs", "hhi",
                         "top_club", "top_club_share", "top5_league_share"])
        writer.writerows(rows)
    print(f"{len(rows)} Team-Turnier-Zeilen -> {target}")


if __name__ == "__main__":
    main()
