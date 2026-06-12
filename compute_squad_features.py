"""Berechnet Kader-Features: Club-Chemistry (HHI) und Legionärs-Anteile.

Club-Chemistry: Herfindahl-Hirschman-Index über die Vereinszugehörigkeit
eines Nationalkaders (Blockbildung, z. B. Bayern-Block 2014). Quelle sind
die Wikipedia-Kaderlisten aller Turniere (echter Verein + Verbandsland
des Vereins); die FootyStats-Kaderlisten sind hierfür unbrauchbar, da
ihr \"Current Club\" das Nationalteam selbst ist. Zusätzlich je Kader der
Anteil der Spieler in Top-5-Ligen (Verbandsland ENG/ESP/GER/ITA/FRA).
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


class SquadFeatureConfig:
    """Quelle, Zielpfad und Parameter."""

    SQUADS_DIR: str = "Tournament Squads (Wikipedia)"
    OUTPUT_FILE: str = "Computed Features/club_chemistry_hhi.csv"
    TOP5_CODES: frozenset[str] = frozenset({"ENG", "ESP", "GER", "ITA", "FRA"})
    MIN_SQUAD: int = 15


def squad_rows(path: Path, config: SquadFeatureConfig) -> list[list[object]]:
    """HHI- und Top-5-Zeilen für alle Teams einer Turnier-Kaderdatei."""
    clubs_by_team: dict[str, list[str]] = {}
    top5_by_team: dict[str, list[bool]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for player in csv.DictReader(handle):
            team = player["team"].strip()
            club = player["club"].strip()
            if not team or not club:
                continue
            clubs_by_team.setdefault(team, []).append(club)
            top5_by_team.setdefault(team, []).append(
                player["club_country"].upper() in config.TOP5_CODES
            )
    rows: list[list[object]] = []
    for team, clubs in sorted(clubs_by_team.items()):
        if len(clubs) < config.MIN_SQUAD:
            continue
        counts = Counter(clubs)
        total = sum(counts.values())
        hhi = round(sum((n / total) ** 2 for n in counts.values()), 4)
        top_club, top_n = counts.most_common(1)[0]
        top5_share = sum(top5_by_team[team]) / len(top5_by_team[team])
        rows.append(
            [path.stem, team, total, len(counts), hhi, top_club,
             round(top_n / total, 3), round(top5_share, 3)]
        )
    return rows


def main() -> None:
    """Berechne und schreibe die Kader-Features aller Turniere."""
    config = SquadFeatureConfig()
    rows: list[list[object]] = []
    for path in sorted(Path(config.SQUADS_DIR).glob("*.csv")):
        rows.extend(squad_rows(path, config))
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
