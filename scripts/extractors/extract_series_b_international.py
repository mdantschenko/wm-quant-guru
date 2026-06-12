"""Extrahiert Länderspiel-Open/Close-Quoten aus Beat-The-Bookie Serie B.

Serie B (März--November 2016) enthält Quoten-Zeitreihen (32 Buchmacher,
72 Stundenpunkte vor Anpfiff) -- darin die komplette EM 2016. Dieses
Skript filtert Senior-Männer-Nationalspiele, leitet pro Spiel und
Ausgang Opening- (erster belegter Zeitpunkt) und Closing-Quoten
(letzter belegter Zeitpunkt) als Buchmacher-Durchschnitt/-Maximum ab
und schreibt eine flache CSV. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import gzip
from pathlib import Path


class SeriesBConfig:
    """Pfade, Filter und Strukturkonstanten der Serie B."""

    SOURCE_DIR: str = "Data/Beat The Bookie Odds Series Football Dataset"
    MATCHES_GZ: str = "odds_series_b_matches.csv.gz"
    SERIES_GZ: str = "odds_series_b.csv.gz"
    OUTPUT_DIR: str = "Data/International & Tournament Odds (Beat The Bookie 2005-2015)"
    OUTPUT_FILE: str = "international_open_close_odds_2016.csv"

    OUTCOMES: tuple[str, ...] = ("home", "draw", "away")
    INCLUDE_COMPETITIONS: frozenset[str] = frozenset(
        {
            "world cup",
            "euro",
            "friendly international",
            "africa cup of nations",
            "asian cup",
            "copa america",
            "fifa confederations cup",
            "gold cup",
            "nations league",
        }
    )


def is_senior_national(league: str, config: SeriesBConfig) -> bool:
    """Prüfe via exaktem Wettbewerbsnamen, ob Senior-Männer-Nationalspiel."""
    competition = league.split(":", 1)[-1].strip().lower()
    return competition in config.INCLUDE_COMPETITIONS


def load_national_matches(config: SeriesBConfig) -> dict[str, list[str]]:
    """Lade Metadaten der Nationalspiele: match_id -> [liga, heim, gast, ...]."""
    path = Path(config.SOURCE_DIR) / config.MATCHES_GZ
    kept: dict[str, list[str]] = {}
    # Quelle ist latin-1-kodiert (franz. Teamnamen), nicht UTF-8.
    with gzip.open(path, mode="rt", encoding="latin-1", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)  # Header: match_id, league, home, away, score, det., datetime
        for row in reader:
            if len(row) < 7:
                continue
            league = row[1].strip()
            if is_senior_national(league, config):
                kept[row[0].strip()] = [
                    league,
                    row[2].strip(),
                    row[3].strip(),
                    row[4].strip(),
                    row[6].strip(),
                ]
    return kept


def build_column_map(
    header: list[str], config: SeriesBConfig
) -> dict[str, list[list[int]]]:
    """Ordne Spaltenindizes je Ausgang als Liste von Stunden-Listen pro Buchmacher.

    Spaltennamen haben die Form ``home_b3_17`` (Ausgang, Buchmacher, Stunde).
    Rückgabe: outcome -> Liste über Buchmacher, je chronologisch sortierte
    Spaltenindizes.
    """
    per_outcome_bookie: dict[str, dict[int, list[tuple[int, int]]]] = {
        outcome: {} for outcome in config.OUTCOMES
    }
    for index, name in enumerate(header):
        parts = name.strip().split("_")
        if len(parts) != 3 or parts[0] not in per_outcome_bookie:
            continue
        bookie = int(parts[1].lstrip("b"))
        hour = int(parts[2])
        per_outcome_bookie[parts[0]].setdefault(bookie, []).append((hour, index))
    column_map: dict[str, list[list[int]]] = {}
    for outcome, bookies in per_outcome_bookie.items():
        column_map[outcome] = [
            [idx for _, idx in sorted(hours)] for _, hours in sorted(bookies.items())
        ]
    return column_map


def open_close_for_outcome(
    row: list[str], bookie_columns: list[list[int]]
) -> tuple[float | None, float | None, float | None, int]:
    """Berechne (avg_open, avg_close, max_close, n_bookies) eines Ausgangs."""
    opens: list[float] = []
    closes: list[float] = []
    for columns in bookie_columns:
        series = [
            float(row[i])
            for i in columns
            if i < len(row) and row[i] not in ("", "nan")
        ]
        series = [value for value in series if value > 1.0]
        if series:
            opens.append(series[0])
            closes.append(series[-1])
    if not closes:
        return None, None, None, 0
    return (
        round(sum(opens) / len(opens), 4),
        round(sum(closes) / len(closes), 4),
        round(max(closes), 4),
        len(closes),
    )


def extract(config: SeriesBConfig) -> tuple[Path, int]:
    """Streame die Serie, aggregiere Open/Close und schreibe die Ziel-CSV."""
    matches = load_national_matches(config)
    series_path = Path(config.SOURCE_DIR) / config.SERIES_GZ
    output_path = Path(config.OUTPUT_DIR) / config.OUTPUT_FILE
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with gzip.open(series_path, mode="rt", encoding="latin-1", newline="") as source, \
            output_path.open("w", encoding="utf-8", newline="") as sink:
        reader = csv.reader(source)
        column_map = build_column_map(next(reader), config)
        writer = csv.writer(sink)
        writer.writerow(
            ["match_id", "league", "match_datetime", "home_team", "away_team",
             "score", "n_bookies"]
            + [f"avg_open_{o}" for o in config.OUTCOMES]
            + [f"avg_close_{o}" for o in config.OUTCOMES]
            + [f"max_close_{o}" for o in config.OUTCOMES]
        )
        for row in reader:
            meta = matches.get(row[0].strip())
            if meta is None:
                continue
            results = {
                outcome: open_close_for_outcome(row, column_map[outcome])
                for outcome in config.OUTCOMES
            }
            if all(results[o][1] is None for o in config.OUTCOMES):
                continue
            league, home, away, score, kickoff = meta
            writer.writerow(
                [row[0].strip(), league, kickoff, home, away, score,
                 max(results[o][3] for o in config.OUTCOMES)]
                + [results[o][0] for o in config.OUTCOMES]
                + [results[o][1] for o in config.OUTCOMES]
                + [results[o][2] for o in config.OUTCOMES]
            )
            written += 1
    return output_path, written


def main() -> None:
    """Führe die Serie-B-Extraktion aus und berichte Eckdaten."""
    config = SeriesBConfig()
    output_path, written = extract(config)
    print(f"{written} Nationalspiele mit Open/Close-Quoten -> {output_path}")


if __name__ == "__main__":
    main()
