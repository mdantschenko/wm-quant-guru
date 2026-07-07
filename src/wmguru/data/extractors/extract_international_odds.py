"""Extrahiert Länderspiel-/Turnierquoten aus dem Beat-The-Bookie-Datensatz.

Der closing_odds-Datensatz (2005--2015) enthält neben Vereinsligen auch
Closing-Quoten für Männer-Nationalmannschaften (WM, EM, Länderspiele,
Kontinentalturniere). Dieses Skript filtert genau diese Spiele heraus und
legt sie als nutzbare CSV in einem beschrifteten Ordner ab. Reine
Standardbibliothek.
"""
from __future__ import annotations

import csv
import gzip
import re
from collections import Counter
from pathlib import Path


class ExtractConfig:
    """Pfade und Filtermuster für Männer-Nationalmannschaftsspiele."""

    SOURCE_GZ: str = (
        "Data/Beat The Bookie Odds Series Football Dataset/closing_odds.csv.gz"
    )
    OUTPUT_DIR: str = "Data/International & Tournament Odds (Beat The Bookie 2005-2015)"
    OUTPUT_FILE: str = "international_closing_odds.csv"
    LEAGUE_COLUMN: str = "league"

    # Senior-Männer-Nationalwettbewerbe: EXAKTER Wettbewerbsname (nach
    # "Region: "), kleingeschrieben. Exakte Gleichheit verhindert, dass
    # "Euro" auf "Europe:"/"Europa League" oder "Euro U21" matcht.
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


def is_senior_national(league: str, config: ExtractConfig) -> bool:
    """Prüfe via exaktem Wettbewerbsnamen, ob Senior-Männer-Nationalspiel.

    Akzente werden normalisiert ("Copa América" -> "copa america").
    """
    import unicodedata
    competition = league.split(":", 1)[-1].strip().lower()
    competition = "".join(
        ch for ch in unicodedata.normalize("NFKD", competition)
        if not unicodedata.combining(ch)
    )
    return competition in config.INCLUDE_COMPETITIONS


def extract_rows(
    config: ExtractConfig,
) -> tuple[list[str], list[list[str]], Counter[str]]:
    """Lies die Quelle und filtere Senior-Nationalmannschaftsspiele."""
    source = Path(config.SOURCE_GZ)
    kept: list[list[str]] = []
    competitions: Counter[str] = Counter()
    with gzip.open(source, mode="rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        league_index = header.index(config.LEAGUE_COLUMN)
        for row in reader:
            if len(row) <= league_index:
                continue
            league = row[league_index].strip()
            if is_senior_national(league, config):
                kept.append(row)
                competitions[league] += 1
    return header, kept, competitions


def write_output(
    header: list[str], rows: list[list[str]], config: ExtractConfig
) -> Path:
    """Schreibe die gefilterten Zeilen als CSV in den Zielordner."""
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / config.OUTPUT_FILE
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return target


def year_of(row: list[str], date_index: int) -> str:
    """Extrahiere das Jahr aus dem Datumsfeld (Format YYYY-MM-DD)."""
    match = re.match(r"(\d{4})", row[date_index])
    return match.group(1) if match else "?"


def main() -> None:
    """Filtere und schreibe die Länderspiel-/Turnierquoten."""
    config = ExtractConfig()
    header, rows, competitions = extract_rows(config)
    target = write_output(header, rows, config)
    date_index = header.index("match_date")
    years = Counter(year_of(row, date_index) for row in rows)
    print(f"Gefiltert: {len(rows)} Spiele -> {target}")
    print("\nWettbewerbe:")
    for league, count in competitions.most_common():
        print(f"  {count:>6}  {league}")
    print("\nSpiele pro Jahr:")
    for year in sorted(years):
        print(f"  {year}: {years[year]}")


if __name__ == "__main__":
    main()
