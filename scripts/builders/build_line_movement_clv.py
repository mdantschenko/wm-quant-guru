"""Quotenbewegung Open zu Close (Smart Money / CLV) ueber mehrere Quellen.

Die Eroeffnungsquote spiegelt die fruehe Markteinschaetzung, die Schlussquote
die durch informierte Einsaetze geschaerfte. Die Differenz der entvigten
Wahrscheinlichkeiten ist ein Proxy fuer informierten Geldfluss und die Basis
jeder Closing-Line-Value-Analyse.

Linienbewegung braucht ZWEI Zeitpunkte (Open und Close). Nur zwei Quellen
liefern beides:
  - football-data.co.uk (Vereinsligen), Pinnacle Open PSH/PSD/PSA und
    Close PSCH/PSCD/PSCA,
  - Beat The Bookie International 2016 (Nationalteams inkl. EM 2016),
    avg_open_* und avg_close_*.
FootyStats und Club Football Engineered haben nur einen Snapshot und koennen
keine Bewegung liefern.

Ausgaben nach Data/Custom_Data/ (mit Spalte `source`):
  - line_movement_clv.csv            je Spiel die Drift und der CLV-Baustein,
  - line_movement_league_summary.csv je Quelle und Liga die Schaerfe (Log-Loss
    Open gegen Close). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import math
from itertools import chain
from pathlib import Path
from typing import Iterator

from scripts.helpers.dates import to_iso_date


class LineMovementConfig:
    """Pfade, Spaltennamen und Schwellen."""

    FOOTBALL_DATA_DIR: str = "Data/Football Betting Odds (football-data.co.uk)"
    BEAT_THE_BOOKIE_FILE: str = (
        "Data/International & Tournament Odds (Beat The Bookie 2005-2015)/"
        "international_open_close_odds_2016.csv"
    )
    OUTPUT_DIR: str = "Data/Custom_Data"

    OPEN_COLUMNS: tuple[str, str, str] = ("PSH", "PSD", "PSA")
    CLOSE_COLUMNS: tuple[str, str, str] = ("PSCH", "PSCD", "PSCA")
    RESULT_LETTERS: tuple[str, str, str] = ("H", "D", "A")
    RESULT_INDEX: dict[str, int] = {"H": 0, "D": 1, "A": 2}
    PROBABILITY_FLOOR: float = 1e-12


def devig(odds: tuple[float, float, float]) -> tuple[float, float, float]:
    inverse = [1.0 / value for value in odds]
    overround = sum(inverse)
    return tuple(value / overround for value in inverse)


def read_odds(row: dict[str, str], columns: tuple[str, str, str]) -> tuple[float, float, float] | None:
    try:
        values = (float(row[columns[0]]), float(row[columns[1]]), float(row[columns[2]]))
    except (KeyError, ValueError):
        return None
    return values if all(value > 1.0 for value in values) else None


def compute_row(
    source: str, league: str, season: str, date: str, home: str, away: str,
    result_index: int, open_odds: tuple[float, float, float],
    close_odds: tuple[float, float, float], config: LineMovementConfig,
) -> dict[str, object]:
    """Baut eine Spielzeile aus Open- und Close-Quoten."""
    open_probability = devig(open_odds)
    close_probability = devig(close_odds)
    moves = [close_probability[k] - open_probability[k] for k in range(3)]
    floor = config.PROBABILITY_FLOOR
    return {
        "source": source, "league": league, "season": season, "date": date,
        "home": home, "away": away, "ftr": config.RESULT_LETTERS[result_index],
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
        "drift_to_result": round(close_probability[result_index] - open_probability[result_index], 4),
        "_logloss_open": -math.log(max(open_probability[result_index], floor)),
        "_logloss_close": -math.log(max(close_probability[result_index], floor)),
    }


def iter_football_data(config: LineMovementConfig) -> Iterator[dict[str, object]]:
    for path in sorted(Path(config.FOOTBALL_DATA_DIR).rglob("*.csv")):
        if path.name == "coverage_report.csv":
            continue
        with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or config.CLOSE_COLUMNS[0] not in reader.fieldnames:
                continue
            for row in reader:
                result = row.get("FTR", "")
                if result not in config.RESULT_INDEX:
                    continue
                open_odds = read_odds(row, config.OPEN_COLUMNS)
                close_odds = read_odds(row, config.CLOSE_COLUMNS)
                if open_odds is None or close_odds is None:
                    continue
                yield compute_row("football-data", path.parent.name, path.stem,
                                  row.get("Date", ""), row.get("HomeTeam", ""),
                                  row.get("AwayTeam", ""), config.RESULT_INDEX[result],
                                  open_odds, close_odds, config)


def iter_beat_the_bookie(config: LineMovementConfig) -> Iterator[dict[str, object]]:
    path = Path(config.BEAT_THE_BOOKIE_FILE)
    if not path.exists():
        return
    open_columns = ("avg_open_home", "avg_open_draw", "avg_open_away")
    close_columns = ("avg_close_home", "avg_close_draw", "avg_close_away")
    with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
        for row in csv.DictReader(handle):
            open_odds = read_odds(row, open_columns)
            close_odds = read_odds(row, close_columns)
            if open_odds is None or close_odds is None:
                continue
            try:
                home_score, away_score = (int(part) for part in row["score"].split(":"))
            except (KeyError, ValueError):
                continue
            result_index = 0 if home_score > away_score else (1 if home_score == away_score else 2)
            yield compute_row("beat-the-bookie", row.get("league", ""), "2016",
                              row.get("match_datetime", "")[:10], row.get("home_team", ""),
                              row.get("away_team", ""), result_index, open_odds, close_odds, config)


def build_league_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Je Quelle und Liga die Schaerfe der Schlusslinie (Log-Loss Open gegen Close)."""
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((row["source"], row["league"]), []).append(row)
    summary: list[dict[str, object]] = []
    for (source, league), league_rows in sorted(grouped.items()):
        count = len(league_rows)
        logloss_open = sum(row["_logloss_open"] for row in league_rows) / count
        logloss_close = sum(row["_logloss_close"] for row in league_rows) / count
        summary.append({
            "source": source, "league": league, "matches": count,
            "logloss_open": round(logloss_open, 4),
            "logloss_close": round(logloss_close, 4),
            "logloss_improvement": round(logloss_open - logloss_close, 4),
            "mean_total_abs_move": round(sum(row["total_abs_move"] for row in league_rows) / count, 4),
            "frac_drift_to_result_positive": round(
                sum(1 for row in league_rows if row["drift_to_result"] > 0) / count, 4),
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

    rows = list(chain(iter_football_data(config), iter_beat_the_bookie(config)))
    for row in rows:
        row["date"] = to_iso_date(str(row["date"]))
    rows.sort(key=lambda row: (str(row["league"]), str(row["date"]), str(row["home"])))
    write_csv(
        output_dir / "line_movement_clv.csv", rows,
        ["source", "league", "season", "date", "home", "away", "ftr",
         "q_open_home", "q_open_draw", "q_open_away",
         "q_close_home", "q_close_draw", "q_close_away",
         "move_home", "move_draw", "move_away", "total_abs_move", "drift_to_result"],
    )
    summary = build_league_summary(rows)
    write_csv(
        output_dir / "line_movement_league_summary.csv", summary,
        ["source", "league", "matches", "logloss_open", "logloss_close",
         "logloss_improvement", "mean_total_abs_move", "frac_drift_to_result_positive"],
    )
    by_source: dict[str, int] = {}
    for row in rows:
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1
    improved = sum(1 for row in summary if row["logloss_improvement"] > 0)
    print(f"  OK    {len(rows)} Spiele mit Open- und Close-Quoten")
    for source, count in sorted(by_source.items()):
        print(f"        {source}: {count} Spiele")
    print(f"  OK    {len(summary)} Quelle/Liga-Gruppen, davon {improved} mit schaerferer Schlusslinie")


if __name__ == "__main__":
    main()
