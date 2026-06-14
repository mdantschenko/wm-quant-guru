"""Macht Smart Money sichtbar: Quotenbewegung von Open zu Close (CLV-Basis).

Die Eroeffnungsquote spiegelt die fruehe Markteinschaetzung, die Schlussquote
die finale, durch informierte Einsaetze geschaerfte Einschaetzung. Die
Differenz der entvigten Wahrscheinlichkeiten zwischen beiden ist ein Proxy
fuer informierten Geldfluss und die Grundlage jeder Closing-Line-Value-Analyse.

Aus den Pinnacle-Quoten der football-data.co.uk-Saisons mit Schlusslinie
(PSH/PSD/PSA fuer Open, PSCH/PSCD/PSCA fuer Close) wird je Spiel berechnet:
  - entvigte Wahrscheinlichkeiten Open und Close (proportionale Normierung),
  - Bewegung je Ausgang und die Gesamtbewegung (halbe L1-Distanz, Steam),
  - Drift zum tatsaechlichen Ergebnis (schaerft sich die Linie zum Ausgang).
Die Zusammenfassung belegt je Liga, dass die Schlusslinie den Open-Markt im
Log-Loss schlaegt (die zentrale CLV-Praemisse).

Eingabe: football-data.co.uk-Saison-CSVs. Ausgaben nach Data/Custom_Data/.
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path


class LineMovementConfig:
    """Pfade und Spaltennamen."""

    SOURCE_DIR: str = "Data/Football Betting Odds (football-data.co.uk)"
    OUTPUT_DIR: str = "Data/Custom_Data"

    OPEN_COLUMNS: tuple[str, str, str] = ("PSH", "PSD", "PSA")
    CLOSE_COLUMNS: tuple[str, str, str] = ("PSCH", "PSCD", "PSCA")
    RESULT_INDEX: dict[str, int] = {"H": 0, "D": 1, "A": 2}
    PROBABILITY_FLOOR: float = 1e-12


def devig(odds: tuple[float, float, float]) -> tuple[float, float, float]:
    """Proportional normierte Wahrscheinlichkeiten aus Dezimalquoten."""
    inverse = [1.0 / value for value in odds]
    overround = sum(inverse)
    return tuple(value / overround for value in inverse)


def read_odds(row: dict[str, str], columns: tuple[str, str, str]) -> tuple[float, float, float] | None:
    """Liest drei Dezimalquoten oder None, falls eine fehlt oder unzulaessig ist."""
    try:
        values = tuple(float(row[column]) for column in columns)
    except (KeyError, ValueError):
        return None
    return values if all(value > 1.0 for value in values) else None


def build_match_rows(config: LineMovementConfig) -> list[dict[str, object]]:
    """Verarbeitet alle Saison-CSVs mit Pinnacle-Schlusslinie."""
    rows: list[dict[str, object]] = []
    for path in sorted(Path(config.SOURCE_DIR).rglob("*.csv")):
        if path.name == "coverage_report.csv":
            continue
        with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or config.CLOSE_COLUMNS[0] not in reader.fieldnames:
                continue
            for row in reader:
                rows.extend(_match_row(row, path, config))
    return rows


def _match_row(
    row: dict[str, str], path: Path, config: LineMovementConfig
) -> list[dict[str, object]]:
    """Baut eine Ergebniszeile fuer ein Spiel oder eine leere Liste."""
    result = row.get("FTR", "")
    if result not in config.RESULT_INDEX:
        return []
    open_odds = read_odds(row, config.OPEN_COLUMNS)
    close_odds = read_odds(row, config.CLOSE_COLUMNS)
    if open_odds is None or close_odds is None:
        return []

    open_probability = devig(open_odds)
    close_probability = devig(close_odds)
    index = config.RESULT_INDEX[result]
    moves = [close_probability[k] - open_probability[k] for k in range(3)]
    return [{
        "league": path.parent.name,
        "season": path.stem,
        "date": row.get("Date", ""),
        "home": row.get("HomeTeam", ""),
        "away": row.get("AwayTeam", ""),
        "ftr": result,
        "q_open_home": round(open_probability[0], 4),
        "q_open_draw": round(open_probability[1], 4),
        "q_open_away": round(open_probability[2], 4),
        "q_close_home": round(close_probability[0], 4),
        "q_close_draw": round(close_probability[1], 4),
        "q_close_away": round(close_probability[2], 4),
        "move_home": round(moves[0], 4),
        "move_draw": round(moves[1], 4),
        "move_away": round(moves[2], 4),
        "total_abs_move": round(0.5 * sum(abs(move) for move in moves), 4),
        "drift_to_result": round(close_probability[index] - open_probability[index], 4),
        "_logloss_open": -math.log(max(open_probability[index], config.PROBABILITY_FLOOR)),
        "_logloss_close": -math.log(max(close_probability[index], config.PROBABILITY_FLOOR)),
    }]


def build_league_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Aggregiert je Liga die CLV-Kennzahlen (Schaerfe der Schlusslinie)."""
    by_league: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_league.setdefault(row["league"], []).append(row)

    summary: list[dict[str, object]] = []
    for league, league_rows in sorted(by_league.items()):
        count = len(league_rows)
        logloss_open = sum(row["_logloss_open"] for row in league_rows) / count
        logloss_close = sum(row["_logloss_close"] for row in league_rows) / count
        summary.append({
            "league": league,
            "matches": count,
            "logloss_open": round(logloss_open, 4),
            "logloss_close": round(logloss_close, 4),
            "logloss_improvement": round(logloss_open - logloss_close, 4),
            "mean_total_abs_move": round(
                sum(row["total_abs_move"] for row in league_rows) / count, 4
            ),
            "frac_drift_to_result_positive": round(
                sum(1 for row in league_rows if row["drift_to_result"] > 0) / count, 4
            ),
        })
    summary.sort(key=lambda row: row["matches"], reverse=True)
    return summary


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = LineMovementConfig()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = build_match_rows(config)
    write_csv(
        output_dir / "line_movement_clv.csv",
        rows,
        ["league", "season", "date", "home", "away", "ftr",
         "q_open_home", "q_open_draw", "q_open_away",
         "q_close_home", "q_close_draw", "q_close_away",
         "move_home", "move_draw", "move_away",
         "total_abs_move", "drift_to_result"],
    )
    summary = build_league_summary(rows)
    write_csv(
        output_dir / "line_movement_league_summary.csv",
        summary,
        ["league", "matches", "logloss_open", "logloss_close", "logloss_improvement",
         "mean_total_abs_move", "frac_drift_to_result_positive"],
    )

    improved = sum(1 for row in summary if row["logloss_improvement"] > 0)
    print(f"  OK    {len(rows)} Spiele mit Open- und Close-Quoten")
    print(f"  OK    {len(summary)} Ligen, davon {improved} mit schaerferer Schlusslinie")


if __name__ == "__main__":
    main()
