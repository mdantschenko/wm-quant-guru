"""Berechnet Elo-Ratings für alle Länderspiele (eloratings.net-Methodik).

Der heruntergeladene Elo-Datensatz enthält nur ~400 Snapshot-Stichtage --
das Konzept verlangt aber das Rating ZUM STICHTAG VOR JEDEM SPIEL
(zeitkausal, P0). Diese Engine berechnet die volle Historie selbst aus
results.csv nach der World-Football-Elo-Methodik: K-Faktor je
Wettbewerbstyp, Tordifferenz-Multiplikator, +100 Heimvorteil (entfällt
auf neutralem Platz), Startrating 1500. Ausgabe: eine Zeile je Spiel mit
den PRE-Match-Ratings beider Teams. Validierbar gegen den Live-Snapshot
von eloratings.net. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from pathlib import Path


class EloConfig:
    """Quelle, Methodik-Parameter und Zielpfade."""

    RESULTS_FILE: str = (
        "Data/International football results from 1872 to 2026/results.csv"
    )
    OUTPUT_HISTORY: str = (
        "Data/International Football Elo Ratings (1872-2025)/elo_prematch_history.csv"
    )
    OUTPUT_SNAPSHOT: str = (
        "Data/International Football Elo Ratings (1872-2025)/elo_computed_latest.csv"
    )

    START_RATING: float = 1500.0
    HOME_ADVANTAGE: float = 100.0  # entfaellt bei neutral=TRUE

    # K-Faktoren nach eloratings.net: WM-Endrunde 60; Kontinental-
    # Endrunden & Confed-Cup 50; Qualifikationen & Nations League 40;
    # sonstige Turniere 30; Freundschaftsspiele 20.
    K_WORLD_CUP: float = 60.0
    K_CONTINENTAL: float = 50.0
    K_QUALIFIER: float = 40.0
    K_OTHER: float = 30.0
    K_FRIENDLY: float = 20.0

    CONTINENTAL_FINALS: tuple[str, ...] = (
        "UEFA Euro", "Copa América", "African Cup of Nations",
        "Africa Cup of Nations", "AFC Asian Cup", "CONCACAF Championship",
        "Gold Cup", "Confederations Cup", "Oceania Nations Cup",
    )


def k_factor(tournament: str, config: EloConfig) -> float:
    """Wettbewerbsname -> K-Faktor (eloratings.net-Schema)."""
    name = tournament.strip()
    lowered = name.lower()
    if name == "FIFA World Cup":
        return config.K_WORLD_CUP
    if "qualification" in lowered or "nations league" in lowered:
        return config.K_QUALIFIER
    if any(final in name for final in config.CONTINENTAL_FINALS):
        return config.K_CONTINENTAL
    if lowered == "friendly":
        return config.K_FRIENDLY
    return config.K_OTHER


def goal_multiplier(goal_difference: int) -> float:
    """Tordifferenz-Multiplikator G nach eloratings.net."""
    if goal_difference <= 1:
        return 1.0
    if goal_difference == 2:
        return 1.5
    return (11.0 + goal_difference) / 8.0


def expected_score(rating_diff: float) -> float:
    """Erwartungswert W_e = 1 / (1 + 10^(-dr/400))."""
    return 1.0 / (1.0 + 10.0 ** (-rating_diff / 400.0))


def main() -> None:
    """Berechne die Elo-Historie chronologisch über alle Spiele."""
    config = EloConfig()
    with Path(config.RESULTS_FILE).open(encoding="utf-8", newline="") as handle:
        matches = [
            row for row in csv.DictReader(handle)
            if row["home_score"] not in ("NA", "") and row["away_score"] not in ("NA", "")
        ]
    matches.sort(key=lambda row: row["date"])

    ratings: dict[str, float] = {}
    history_path = Path(config.OUTPUT_HISTORY)
    with history_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "home_team", "away_team", "tournament",
                         "neutral", "elo_home_pre", "elo_away_pre"])
        for row in matches:
            home, away = row["home_team"], row["away_team"]
            elo_home = ratings.get(home, config.START_RATING)
            elo_away = ratings.get(away, config.START_RATING)
            writer.writerow(
                [row["date"], home, away, row["tournament"], row["neutral"],
                 round(elo_home, 1), round(elo_away, 1)]
            )
            neutral = row["neutral"].strip().upper() == "TRUE"
            diff = elo_home - elo_away + (0.0 if neutral else config.HOME_ADVANTAGE)
            home_goals = int(row["home_score"])
            away_goals = int(row["away_score"])
            if home_goals > away_goals:
                actual = 1.0
            elif home_goals == away_goals:
                actual = 0.5
            else:
                actual = 0.0
            delta = (
                k_factor(row["tournament"], config)
                * goal_multiplier(abs(home_goals - away_goals))
                * (actual - expected_score(diff))
            )
            ratings[home] = elo_home + delta
            ratings[away] = elo_away - delta

    snapshot_path = Path(config.OUTPUT_SNAPSHOT)
    with snapshot_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "team", "elo"])
        ranking = sorted(ratings.items(), key=lambda item: -item[1])
        for rank, (team, rating) in enumerate(ranking, start=1):
            writer.writerow([rank, team, round(rating, 1)])
    print(f"{len(matches)} Spiele -> {history_path}")
    print(f"{len(ratings)} Teams im Schluss-Ranking -> {snapshot_path}")


if __name__ == "__main__":
    main()
