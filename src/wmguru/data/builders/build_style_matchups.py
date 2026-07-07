"""Stil-Archetypen und Matchup-Matrix (das Pokemon-Prinzip) aus match_style.csv.

Manche Teams glaenzen gegen einen tiefen Block und gehen gegen hohes Pressing
unter. Dieser Schere-Stein-Papier-Effekt wird hier datenbasiert gemessen.

Schritt eins ordnet jedem Team je Wettbewerb und Saison einen Stil-Archetyp zu,
abgeleitet aus den innerhalb der Liga standardisierten Stilkennzahlen
(Ballbesitzanteil, Field Tilt, PPDA als Pressingmass, Direktheit, Defensivhoehe).
Schritt zwei misst je Archetyp-Paarung die mittlere Bedrohungsdifferenz (xG fuer
minus xG gegen), also welcher Stil welchen auskontert.

Ausgaben nach Data/Custom_Data/:
  - team_style_archetype.csv     je Team, Saison der Archetyp und die z-Werte,
  - style_matchup_matrix.csv     je Archetyp-Paarung die xG-Bilanz.

Die Matrix beruht auf xG und deckt daher vor allem die StatsBomb-Wettbewerbe ab.
Reine Standardbibliothek.

Start als Modul:
    python -m scripts.builders.build_style_matchups
"""
from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean, pstdev

from src.scripts.builders.build_team_style_stability import load_rows, to_float


class MatchupConfig:
    """Pfade, Dimensionen und Schwellen der Archetyp-Regeln."""

    INPUT_FILE: str = "Data/Custom_Data/match_style.csv"
    ARCHETYPE_FILE: str = "Data/Custom_Data/team_style_archetype.csv"
    MATRIX_FILE: str = "Data/Custom_Data/style_matchup_matrix.csv"
    MINIMUM_MATCHES: int = 5
    DIMENSIONS: tuple[str, ...] = (
        "pass_share", "field_tilt", "ppda", "directness_m", "def_action_height_m")
    HIGH: float = 0.5
    LOW: float = -0.5


def team_season_profiles(rows: list[dict], config: MatchupConfig) -> dict[tuple, dict]:
    """Mittelt je Team und Saison jede Stildimension und zaehlt die Spiele."""
    pools: dict[tuple, dict] = {}
    for row in rows:
        key = (row["source"], row["competition"], row["season"], row["team"])
        bucket = pools.setdefault(key, {"matches": 0, **{d: [] for d in config.DIMENSIONS}})
        bucket["matches"] += 1
        for dimension in config.DIMENSIONS:
            value = to_float(row.get(dimension, ""))
            if value is not None:
                bucket[dimension].append(value)
    return {key: {"matches": bucket["matches"],
                  **{d: (mean(bucket[d]) if bucket[d] else None) for d in config.DIMENSIONS}}
            for key, bucket in pools.items()}


def zscore_profiles(profiles: dict[tuple, dict], config: MatchupConfig) -> dict[tuple, dict]:
    """Standardisiert jede Dimension innerhalb von Wettbewerb und Saison."""
    leagues: dict[tuple, list] = {}
    for (source, competition, season, team), profile in profiles.items():
        leagues.setdefault((source, competition, season), []).append((team, profile))
    z_values: dict[tuple, dict] = {}
    for (source, competition, season), members in leagues.items():
        for dimension in config.DIMENSIONS:
            values = [profile[dimension] for _, profile in members if profile[dimension] is not None]
            center = mean(values) if len(values) >= 2 else 0.0
            spread = pstdev(values) if len(values) >= 2 else 0.0
            for team, profile in members:
                entry = z_values.setdefault((source, competition, season, team), {})
                value = profile[dimension]
                entry[dimension] = (value - center) / spread if value is not None and spread else 0.0
    return z_values


def classify(z: dict[str, float], config: MatchupConfig) -> str:
    """Ordnet einem Team aus seinen z-Werten einen Stil-Archetyp zu."""
    high, low = config.HIGH, config.LOW
    if z["pass_share"] >= high and z["field_tilt"] >= high:
        return "Ballbesitz-Dominanz"
    if z["pass_share"] >= high and z["field_tilt"] < 0:
        return "Leerer Ballbesitz"
    if z["directness_m"] >= high and z["pass_share"] <= low:
        return "Direkt / Physisch"
    if z["pass_share"] <= low and (z["ppda"] >= high or z["def_action_height_m"] <= low):
        return "Tiefer Block / Konter"
    return "Ausgewogen"


def build_archetypes(profiles: dict, z_values: dict,
                     config: MatchupConfig) -> tuple[list[dict], dict[tuple, str]]:
    """Erzeugt die Archetyp-Zeilen und ein Nachschlagewerk je Team und Saison."""
    rows: list[dict] = []
    lookup: dict[tuple, str] = {}
    for key, profile in profiles.items():
        if profile["matches"] < config.MINIMUM_MATCHES:
            continue
        z = z_values[key]
        archetype = classify(z, config)
        lookup[key] = archetype
        source, competition, season, team = key
        rows.append({
            "source": source, "competition": competition, "season": season, "team": team,
            "matches": profile["matches"], "pass_share_z": round(z["pass_share"], 2),
            "field_tilt_z": round(z["field_tilt"], 2), "ppda_z": round(z["ppda"], 2),
            "directness_z": round(z["directness_m"], 2),
            "def_height_z": round(z["def_action_height_m"], 2), "archetype": archetype,
            "empty_possession": int(z["pass_share"] >= config.HIGH and z["field_tilt"] < 0),
        })
    rows.sort(key=lambda row: (str(row["source"]), str(row["competition"]),
                               str(row["season"]), str(row["team"])))
    return rows, lookup


def build_matrix(rows: list[dict], lookup: dict[tuple, str]) -> list[dict]:
    """Aggregiert je Archetyp-Paarung die xG-Bilanz aus den Spielzeilen."""
    cells: dict[tuple, list] = {}
    for row in rows:
        key = (row["source"], row["competition"], row["season"])
        archetype_for = lookup.get((*key, row["team"]))
        archetype_against = lookup.get((*key, row["opponent"]))
        xg_for = to_float(row.get("xg", ""))
        xg_against = to_float(row.get("xga", ""))
        if archetype_for is None or archetype_against is None or xg_for is None or xg_against is None:
            continue
        bucket = cells.setdefault((archetype_for, archetype_against), [0, 0.0, 0.0])
        bucket[0] += 1
        bucket[1] += xg_for
        bucket[2] += xg_against
    matrix: list[dict] = []
    for (archetype_for, archetype_against), (count, sum_for, sum_against) in cells.items():
        matrix.append({
            "archetype_for": archetype_for, "archetype_against": archetype_against,
            "matches": count, "mean_xg_for": round(sum_for / count, 3),
            "mean_xg_against": round(sum_against / count, 3),
            "mean_xg_diff": round((sum_for - sum_against) / count, 3),
        })
    matrix.sort(key=lambda row: (row["archetype_for"], row["archetype_against"]))
    return matrix


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = MatchupConfig()
    rows = load_rows(Path(config.INPUT_FILE))
    profiles = team_season_profiles(rows, config)
    z_values = zscore_profiles(profiles, config)
    archetype_rows, lookup = build_archetypes(profiles, z_values, config)
    matrix_rows = build_matrix(rows, lookup)
    write_csv(Path(config.ARCHETYPE_FILE), archetype_rows,
              ["source", "competition", "season", "team", "matches", "pass_share_z",
               "field_tilt_z", "ppda_z", "directness_z", "def_height_z",
               "archetype", "empty_possession"])
    write_csv(Path(config.MATRIX_FILE), matrix_rows,
              ["archetype_for", "archetype_against", "matches", "mean_xg_for",
               "mean_xg_against", "mean_xg_diff"])
    print(f"  OK    {len(archetype_rows)} Team-Saison-Archetypen, {len(matrix_rows)} Paarungen")


if __name__ == "__main__":
    main()
