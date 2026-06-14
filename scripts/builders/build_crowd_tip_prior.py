"""Crowd-Tip-Prior als Startwert fuer das Gegnermodell C_m in Modus B2.

Modus B2 braucht eine Verteilung ueber die Ergebnistipps der Mitspieler,
bevor ueberhaupt Live-Tipps beobachtet wurden. Gelegenheitstipper verteilen
sich nicht zufaellig, sondern konzentrieren sich auf wenige psychologisch
attraktive Ergebnisse (knapper Favoritensieg, runde Resultate). Dieses Skript
schaetzt einen nach Favoritenstaerke bedingten Prior:

  crowd_prior = (1 - beta) * empirische_Verteilung + beta * Heuristik

Die empirische Verteilung kommt aus den realen Ergebnissen (was der rationale
Tipper spielen wuerde), die Heuristik bildet die dokumentierte Crowd-Vorliebe
fuer Ergebnisse wie 1:0, 2:1 und 2:0 ab. Der Abstand beider zeigt je
Favoritenband, wo das Kollektiv am staerksten von der Realitaet abweicht --
also wo Modus B2 den groessten Contrarian-Spielraum hat.

Eingaben: results.csv, elo_prematch_history.csv. Ausgaben nach
Data/Custom_Data/. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from pathlib import Path


class CrowdPriorConfig:
    """Pfade, Gitter, Banding und Mischungsgewicht."""

    RESULTS_FILE: str = (
        "Data/International football results from 1872 to 2026/results.csv"
    )
    ELO_FILE: str = (
        "Data/International Football Elo Ratings (1872-2025)/elo_prematch_history.csv"
    )
    OUTPUT_DIR: str = "Data/Custom_Data"

    HOME_ADVANTAGE: float = 100.0
    GRID_MAX: int = 5
    CROWD_BIAS_WEIGHT: float = 0.5  # beta, Gewicht der Heuristik im Prior
    BAND_EDGES: tuple[float, ...] = (0.50, 0.60, 0.70, 0.80, 0.90, 1.001)

    # Heuristik als favoritenorientierte Tippdichte (Favoritentore, Aussenseitertore).
    HEURISTIC: dict[tuple[int, int], float] = {
        (1, 0): 0.22, (2, 1): 0.20, (2, 0): 0.17, (1, 1): 0.12,
        (3, 1): 0.10, (3, 0): 0.08, (0, 0): 0.06, (2, 2): 0.05,
    }


def band_of(favorite_expectation: float, config: CrowdPriorConfig) -> str | None:
    """Ordnet die Favoriten-Gewinnerwartung einem Band zu."""
    for lower, upper in zip(config.BAND_EDGES[:-1], config.BAND_EDGES[1:]):
        if lower <= favorite_expectation < upper:
            return f"{lower:.2f}_{min(upper, 1.0):.2f}"
    return None


def load_elo_lookup(config: CrowdPriorConfig) -> dict[tuple[str, str, str], tuple[float, float]]:
    """Liest pre-match Elo, indiziert nach (Datum, Heim, Gast)."""
    lookup: dict[tuple[str, str, str], tuple[float, float]] = {}
    with open(config.ELO_FILE, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            lookup[(row["date"], row["home_team"], row["away_team"])] = (
                float(row["elo_home_pre"]), float(row["elo_away_pre"])
            )
    return lookup


def tally_empirical(
    config: CrowdPriorConfig,
) -> dict[str, dict[tuple[int, int], int]]:
    """Zaehlt favoritenorientierte Ergebnisse je Favoritenband."""
    elo_lookup = load_elo_lookup(config)
    counts: dict[str, dict[tuple[int, int], int]] = {}
    with open(config.RESULTS_FILE, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not (row["home_score"] and row["away_score"]):
                continue
            elo = elo_lookup.get((row["date"], row["home_team"], row["away_team"]))
            if elo is None:
                continue
            advantage = 0.0 if row["neutral"].strip().upper() == "TRUE" else config.HOME_ADVANTAGE
            difference = elo[0] + advantage - elo[1]
            expected_home = 1.0 / (1.0 + 10.0 ** (-difference / 400.0))
            home_goals = min(int(row["home_score"]), config.GRID_MAX)
            away_goals = min(int(row["away_score"]), config.GRID_MAX)
            if expected_home >= 0.5:
                favorite_goals, underdog_goals, favorite_expectation = home_goals, away_goals, expected_home
            else:
                favorite_goals, underdog_goals, favorite_expectation = away_goals, home_goals, 1.0 - expected_home
            band = band_of(favorite_expectation, config)
            if band is None:
                continue
            cell = (favorite_goals, underdog_goals)
            counts.setdefault(band, {})[cell] = counts.setdefault(band, {}).get(cell, 0) + 1
    return counts


def normalized_heuristic(config: CrowdPriorConfig) -> dict[tuple[int, int], float]:
    """Normiert die Heuristik auf Summe 1."""
    total = sum(config.HEURISTIC.values())
    return {cell: weight / total for cell, weight in config.HEURISTIC.items()}


def build_prior_rows(
    counts: dict[str, dict[tuple[int, int], int]], config: CrowdPriorConfig
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Erzeugt die Prior-Zeilen je Zelle und die Band-Zusammenfassung."""
    heuristic = normalized_heuristic(config)
    beta = config.CROWD_BIAS_WEIGHT
    cells = [(x, y) for x in range(config.GRID_MAX + 1) for y in range(config.GRID_MAX + 1)]

    prior_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for band in sorted(counts):
        band_counts = counts[band]
        total = sum(band_counts.values())
        distortion = 0.0
        best_cell, best_prior = (0, 0), -1.0
        for favorite_goals, underdog_goals in cells:
            cell = (favorite_goals, underdog_goals)
            empirical = band_counts.get(cell, 0) / total
            heuristic_probability = heuristic.get(cell, 0.0)
            crowd_prior = (1.0 - beta) * empirical + beta * heuristic_probability
            distortion += abs(empirical - heuristic_probability)
            if crowd_prior > best_prior:
                best_cell, best_prior = cell, crowd_prior
            prior_rows.append({
                "favorite_band": band,
                "favorite_goals": favorite_goals,
                "underdog_goals": underdog_goals,
                "empirical_prob": round(empirical, 4),
                "heuristic_prob": round(heuristic_probability, 4),
                "crowd_prior_prob": round(crowd_prior, 4),
            })
        summary_rows.append({
            "favorite_band": band,
            "matches": total,
            "crowd_distortion": round(0.5 * distortion, 4),
            "top_crowd_cell": f"{best_cell[0]}:{best_cell[1]}",
            "top_crowd_prob": round(best_prior, 4),
        })
    return prior_rows, summary_rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = CrowdPriorConfig()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    counts = tally_empirical(config)
    prior_rows, summary_rows = build_prior_rows(counts, config)

    write_csv(
        output_dir / "crowd_tip_prior_by_band.csv",
        prior_rows,
        ["favorite_band", "favorite_goals", "underdog_goals",
         "empirical_prob", "heuristic_prob", "crowd_prior_prob"],
    )
    write_csv(
        output_dir / "crowd_tip_prior_summary.csv",
        summary_rows,
        ["favorite_band", "matches", "crowd_distortion", "top_crowd_cell", "top_crowd_prob"],
    )

    print(f"  OK    {len(prior_rows)} Prior-Zellen ueber {len(summary_rows)} Favoritenbaender")


if __name__ == "__main__":
    main()
