"""Erzeugt Residuen-Datensaetze, die Form und Glueck von Staerke trennen.

Zwei verborgene Signale werden sichtbar gemacht, indem das Erwartbare
abgezogen wird:

1. Elo-Form-Residuum (alle Laenderspiele): tatsaechliche Punktausbeute minus
   Elo-Erwartung. Das ist Form ORTHOGONAL zum Staerkeniveau. Ein Team kann
   stark sein (hohes Elo) und trotzdem unter Erwartung spielen.
2. xG-Finishing-Residuum (StatsBomb-Turniere 2018-2024): erzielte Tore minus
   Expected Goals. Positiv heisst Ueberperformance im Abschluss, die
   erfahrungsgemaess zur Varianz zurueckkehrt. Der Markt ankert oft an
   Ergebnissen statt an xG.

Beide Datensaetze tragen je Zeile den VOR dem Spiel bekannten gleitenden
Mittelwert (EWMA und Fenster der letzten Spiele), strikt zeitkausal
(Zustand wird erst nach dem Emittieren der Zeile aktualisiert).

Eingaben: results.csv, elo_prematch_history.csv, StatsBomb-Turnier-CSVs.
Ausgaben nach Data/Custom_Data/: elo_form_residuals.csv,
xg_finishing_residuals.csv. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from pathlib import Path


class ResidualConfig:
    """Pfade und Glaettungsparameter."""

    RESULTS_FILE: str = (
        "Data/International football results from 1872 to 2026/results.csv"
    )
    ELO_FILE: str = (
        "Data/International Football Elo Ratings (1872-2025)/elo_prematch_history.csv"
    )
    STATSBOMB_DIR: str = "Data/xG Tournament Data (StatsBomb Open Data)"
    OUTPUT_DIR: str = "Data/Custom_Data"

    HOME_ADVANTAGE: float = 100.0
    EWMA_ALPHA: float = 0.4
    WINDOW: int = 5


class RollingResidual:
    """Haelt je Team den zeitkausalen Zustand der Residuen-Glaettung."""

    def __init__(self, alpha: float, window: int) -> None:
        self._alpha = alpha
        self._window = window
        self._ewma: dict[str, float] = {}
        self._recent: dict[str, list[float]] = {}
        self._count: dict[str, int] = {}

    def prematch(self, team: str) -> tuple[float, float, int]:
        """Gibt EWMA, Fenster-Mittel und Spielzahl VOR dem aktuellen Spiel."""
        recent = self._recent.get(team, [])
        window_mean = sum(recent) / len(recent) if recent else 0.0
        return self._ewma.get(team, 0.0), window_mean, self._count.get(team, 0)

    def update(self, team: str, value: float) -> None:
        previous = self._ewma.get(team)
        self._ewma[team] = (
            value if previous is None else self._alpha * value + (1.0 - self._alpha) * previous
        )
        recent = self._recent.setdefault(team, [])
        recent.append(value)
        if len(recent) > self._window:
            recent.pop(0)
        self._count[team] = self._count.get(team, 0) + 1


def load_results_with_elo(config: ResidualConfig) -> list[dict[str, object]]:
    """Joint Ergebnisse und pre-match Elo, chronologisch sortiert."""
    elo_lookup: dict[tuple[str, str, str], tuple[float, float]] = {}
    with open(config.ELO_FILE, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            elo_lookup[(row["date"], row["home_team"], row["away_team"])] = (
                float(row["elo_home_pre"]), float(row["elo_away_pre"])
            )

    matches: list[dict[str, object]] = []
    with open(config.RESULTS_FILE, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not (row["home_score"] and row["away_score"]):
                continue
            elo = elo_lookup.get((row["date"], row["home_team"], row["away_team"]))
            if elo is None:
                continue
            home_goals, away_goals = int(row["home_score"]), int(row["away_score"])
            matches.append({
                "date": row["date"],
                "tournament": row["tournament"],
                "home": row["home_team"],
                "away": row["away_team"],
                "neutral": row["neutral"].strip().upper() == "TRUE",
                "elo_home": elo[0],
                "elo_away": elo[1],
                "home_result": 1.0 if home_goals > away_goals else (0.5 if home_goals == away_goals else 0.0),
            })
    matches.sort(key=lambda match: match["date"])
    return matches


def build_elo_form_residuals(
    matches: list[dict[str, object]], config: ResidualConfig
) -> list[dict[str, object]]:
    """Team-Spiel-Zeilen mit Elo-Residuum und pre-match Form-Glaettung."""
    rolling = RollingResidual(config.EWMA_ALPHA, config.WINDOW)
    rows: list[dict[str, object]] = []
    for match in matches:
        advantage = 0.0 if match["neutral"] else config.HOME_ADVANTAGE
        difference = match["elo_home"] + advantage - match["elo_away"]
        expected_home = 1.0 / (1.0 + 10.0 ** (-difference / 400.0))
        home_residual = match["home_result"] - expected_home
        for team, opponent, is_home, result, expected, residual in (
            (match["home"], match["away"], 1, match["home_result"], expected_home, home_residual),
            (match["away"], match["home"], 0, 1.0 - match["home_result"], 1.0 - expected_home, -home_residual),
        ):
            ewma, window_mean, count = rolling.prematch(team)
            rows.append({
                "date": match["date"],
                "tournament": match["tournament"],
                "team": team,
                "opponent": opponent,
                "is_home": is_home,
                "neutral": int(match["neutral"]),
                "result": result,
                "elo_expected": round(expected, 4),
                "elo_residual": round(residual, 4),
                "prematch_form_ewma": round(ewma, 4),
                "prematch_form_mean5": round(window_mean, 4),
                "prematch_matches": count,
            })
            rolling.update(team, residual)
    return rows


def load_statsbomb_matches(config: ResidualConfig) -> list[dict[str, object]]:
    """Liest alle StatsBomb-Turnier-CSVs (eine Datei je Turnier)."""
    matches: list[dict[str, object]] = []
    for path in sorted(Path(config.STATSBOMB_DIR).glob("*.csv")):
        if path.stem.startswith("lineups"):
            continue
        with open(path, encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if not (row.get("home_xg_90") and row.get("away_xg_90")):
                    continue
                matches.append({
                    "date": row["match_date"],
                    "tournament": path.stem,
                    "home": row["home_team"],
                    "away": row["away_team"],
                    "home_goals": int(row["home_score"]),
                    "away_goals": int(row["away_score"]),
                    "home_xg": float(row["home_xg_90"]),
                    "away_xg": float(row["away_xg_90"]),
                })
    matches.sort(key=lambda match: match["date"])
    return matches


def build_xg_residuals(
    matches: list[dict[str, object]], config: ResidualConfig
) -> list[dict[str, object]]:
    """Team-Spiel-Zeilen mit Finishing- und Defensiv-Residuum (Tore minus xG)."""
    finishing = RollingResidual(config.EWMA_ALPHA, config.WINDOW)
    rows: list[dict[str, object]] = []
    for match in matches:
        for team, opponent, is_home, goals_for, xg_for, goals_against, xg_against in (
            (match["home"], match["away"], 1, match["home_goals"], match["home_xg"], match["away_goals"], match["away_xg"]),
            (match["away"], match["home"], 0, match["away_goals"], match["away_xg"], match["home_goals"], match["home_xg"]),
        ):
            finishing_residual = goals_for - xg_for
            defensive_residual = goals_against - xg_against
            ewma, window_mean, count = finishing.prematch(team)
            rows.append({
                "match_date": match["date"],
                "tournament": match["tournament"],
                "team": team,
                "opponent": opponent,
                "is_home": is_home,
                "goals_for": goals_for,
                "xg_for": round(xg_for, 3),
                "goals_against": goals_against,
                "xg_against": round(xg_against, 3),
                "finishing_residual": round(finishing_residual, 3),
                "defensive_residual": round(defensive_residual, 3),
                "prematch_finishing_ewma": round(ewma, 3),
                "prematch_finishing_mean5": round(window_mean, 3),
                "prematch_matches": count,
            })
            finishing.update(team, finishing_residual)
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = ResidualConfig()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    elo_rows = build_elo_form_residuals(load_results_with_elo(config), config)
    write_csv(
        output_dir / "elo_form_residuals.csv",
        elo_rows,
        ["date", "tournament", "team", "opponent", "is_home", "neutral", "result",
         "elo_expected", "elo_residual", "prematch_form_ewma", "prematch_form_mean5",
         "prematch_matches"],
    )

    xg_rows = build_xg_residuals(load_statsbomb_matches(config), config)
    write_csv(
        output_dir / "xg_finishing_residuals.csv",
        xg_rows,
        ["match_date", "tournament", "team", "opponent", "is_home", "goals_for",
         "xg_for", "goals_against", "xg_against", "finishing_residual",
         "defensive_residual", "prematch_finishing_ewma", "prematch_finishing_mean5",
         "prematch_matches"],
    )

    print(f"  OK    {len(elo_rows)} Team-Spiel-Zeilen Elo-Form-Residuen")
    print(f"  OK    {len(xg_rows)} Team-Spiel-Zeilen xG-Finishing-Residuen")


if __name__ == "__main__":
    main()
