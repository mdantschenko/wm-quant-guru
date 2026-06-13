"""Extrahiert UEFA-Klubwettbewerbs-Quoten aus Beat The Bookie.

Champions League, Europa League, UEFA-Cup, Super Cup und Intertoto Cup
liegen mit Closing-Quoten (2005--2015) bzw. Open/Close-Zeitreihen
(2016, Serie B) im Beat-The-Bookie-Datensatz -- der internationale
Extraktor filtert sie bewusst aus. Dieses Skript zieht sie in eigene
CSVs ("Eurocup"-Basis, da football-data.co.uk keine UEFA-Wettbewerbe
fuehrt). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import gzip
import unicodedata
from pathlib import Path

from scripts.extractors.extract_series_b_international import (
    SeriesBConfig,
    build_column_map,
    load_national_matches,
    open_close_for_outcome,
)


class UefaClubConfig:
    """Quellen, Wettbewerbsfilter und Zielpfade."""

    SOURCE_DIR: str = "Data/Beat The Bookie Odds Series Football Dataset"
    CLOSING_GZ: str = "closing_odds.csv.gz"
    OUTPUT_DIR: str = "Data/UEFA Club Competitions (Beat The Bookie)"

    COMPETITIONS: frozenset[str] = frozenset(
        {
            "champions league", "europa league", "uefa cup",
            "uefa super cup", "intertoto cup",
        }
    )


def is_uefa_club(league: str, config: UefaClubConfig) -> bool:
    """Liga-String (z. B. 'Europe: Champions League') -> UEFA-Klub-Cup?"""
    competition = league.split(":", 1)[-1].strip().lower()
    competition = "".join(
        ch for ch in unicodedata.normalize("NFKD", competition)
        if not unicodedata.combining(ch)
    )
    return competition in config.COMPETITIONS


def extract_closing(config: UefaClubConfig) -> int:
    """Closing-Quoten 2005--2015 in eine CSV filtern."""
    source = Path(config.SOURCE_DIR) / config.CLOSING_GZ
    target = Path(config.OUTPUT_DIR) / "uefa_club_closing_odds_2005_2015.csv"
    written = 0
    with gzip.open(source, mode="rt", encoding="latin-1", newline="") as inp, \
            target.open("w", encoding="utf-8", newline="") as out:
        reader = csv.reader(inp)
        writer = csv.writer(out)
        header = next(reader)
        league_index = header.index("league")
        writer.writerow(header)
        for row in reader:
            if len(row) > league_index and is_uefa_club(row[league_index], config):
                writer.writerow(row)
                written += 1
    print(f"{written} Spiele (Closing 2005-2015) -> {target}")
    return written


def extract_open_close_2016(config: UefaClubConfig) -> int:
    """Open/Close aus Serie B (2016) via Logik des Serie-B-Extraktors."""
    series_config = SeriesBConfig()
    # Filter des Basis-Extraktors temporaer auf UEFA-Cups umbiegen:
    series_config.INCLUDE_COMPETITIONS = config.COMPETITIONS  # type: ignore
    matches = load_national_matches(series_config)
    series_path = Path(series_config.SOURCE_DIR) / series_config.SERIES_GZ
    target = Path(config.OUTPUT_DIR) / "uefa_club_open_close_2016.csv"
    written = 0
    with gzip.open(series_path, mode="rt", encoding="latin-1", newline="") as source, \
            target.open("w", encoding="utf-8", newline="") as sink:
        reader = csv.reader(source)
        column_map = build_column_map(next(reader), series_config)
        writer = csv.writer(sink)
        outcomes = series_config.OUTCOMES
        writer.writerow(
            ["match_id", "league", "match_datetime", "home_team", "away_team",
             "score", "n_bookies"]
            + [f"avg_open_{o}" for o in outcomes]
            + [f"avg_close_{o}" for o in outcomes]
            + [f"max_close_{o}" for o in outcomes]
        )
        for row in reader:
            meta = matches.get(row[0].strip())
            if meta is None:
                continue
            results = {
                outcome: open_close_for_outcome(row, column_map[outcome])
                for outcome in outcomes
            }
            if all(results[o][1] is None for o in outcomes):
                continue
            league, home, away, score, kickoff = meta
            writer.writerow(
                [row[0].strip(), league, kickoff, home, away, score,
                 max(results[o][3] for o in outcomes)]
                + [results[o][0] for o in outcomes]
                + [results[o][1] for o in outcomes]
                + [results[o][2] for o in outcomes]
            )
            written += 1
    print(f"{written} Spiele (Open/Close 2016) -> {target}")
    return written


def main() -> None:
    """Beide Extraktionen ausführen."""
    config = UefaClubConfig()
    Path(config.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    extract_closing(config)
    extract_open_close_2016(config)


if __name__ == "__main__":
    main()
