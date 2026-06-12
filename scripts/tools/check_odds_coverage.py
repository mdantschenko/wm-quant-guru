"""Prüft die Quoten-Coverage der football-data.co.uk-Downloads.

Liest pro Liga/Saison aus, welche Schlüssel-Quotenspalten tatsächlich
befüllt sind (nicht nur im Header vorhanden), und bestimmt daraus, ab
welcher Saison Closing-Quoten und damit Closing-Line-Value-Backtests
möglich sind. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from pathlib import Path


class CoverageConfig:
    """Pfade und zu prüfende Quotenspalten."""

    MAIN_DIR: str = "Football Betting Odds (football-data.co.uk)/main_leagues"
    REPORT_PATH: str = (
        "Football Betting Odds (football-data.co.uk)/coverage_report.csv"
    )
    MIN_FILL_RATE: float = 0.5  # ab hier gilt eine Spalte als "vorhanden"

    # Opening- und Closing-Schlüsselspalten (Heimsieg-Spalte als Stellvertreter).
    OPENING_COLUMNS: tuple[str, ...] = ("PSH", "B365H", "AvgH")
    CLOSING_COLUMNS: tuple[str, ...] = ("PSCH", "B365CH", "AvgCH")


def fill_rate(rows: list[dict[str, str]], column: str) -> float:
    """Anteil der Zeilen mit nichtleerem Wert in der Spalte."""
    if not rows or column not in rows[0]:
        return 0.0
    filled = sum(1 for row in rows if (row.get(column) or "").strip())
    return filled / len(rows)


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    """Lies eine football-data-CSV als Liste von Zeilen-Dicts."""
    with csv_path.open(encoding="latin-1", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("Date")]


def analyze_season(csv_path: Path, config: CoverageConfig) -> dict[str, object]:
    """Bestimme Spielzahl und Open/Close-Verfügbarkeit einer Saison."""
    rows = read_rows(csv_path)
    has_opening = any(
        fill_rate(rows, col) >= config.MIN_FILL_RATE for col in config.OPENING_COLUMNS
    )
    has_closing = any(
        fill_rate(rows, col) >= config.MIN_FILL_RATE for col in config.CLOSING_COLUMNS
    )
    return {
        "season": csv_path.stem,
        "matches": len(rows),
        "opening": has_opening,
        "closing": has_closing,
        "pinnacle_close": fill_rate(rows, "PSCH") >= config.MIN_FILL_RATE,
    }


def summarize_league(league_dir: Path, config: CoverageConfig) -> list[dict[str, object]]:
    """Analysiere alle Saisons einer Liga, sortiert nach Saison."""
    seasons = sorted(league_dir.glob("*.csv"), key=lambda path: path.stem)
    return [analyze_season(path, config) for path in seasons]


def print_report(coverage: dict[str, list[dict[str, object]]]) -> None:
    """Gib eine kompakte Coverage-Übersicht pro Liga aus."""
    header = f"{'Liga':<42}{'Saisons':>9}{'Open':>6}{'Close':>7}{'CLV ab':>10}"
    print(header)
    print("-" * len(header))
    for league_name, seasons in sorted(coverage.items()):
        closing_seasons = [s for s in seasons if s["closing"]]
        opening_seasons = [s for s in seasons if s["opening"]]
        first_close = closing_seasons[0]["season"] if closing_seasons else "-"
        print(
            f"{league_name:<42}{len(seasons):>9}"
            f"{len(opening_seasons):>6}{len(closing_seasons):>7}{first_close:>10}"
        )


def write_csv_report(
    coverage: dict[str, list[dict[str, object]]], config: CoverageConfig
) -> None:
    """Schreibe die Saison-Details als CSV in den Quoten-Ordner."""
    with Path(config.REPORT_PATH).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["league", "season", "matches", "has_opening", "has_closing", "pinnacle_closing"]
        )
        for league_name, seasons in sorted(coverage.items()):
            for season in seasons:
                writer.writerow(
                    [
                        league_name,
                        season["season"],
                        season["matches"],
                        int(bool(season["opening"])),
                        int(bool(season["closing"])),
                        int(bool(season["pinnacle_close"])),
                    ]
                )


def main() -> None:
    """Analysiere alle Hauptligen und gib Bericht aus."""
    config = CoverageConfig()
    main_dir = Path(config.MAIN_DIR)
    coverage = {
        league_dir.name: summarize_league(league_dir, config)
        for league_dir in sorted(main_dir.iterdir())
        if league_dir.is_dir()
    }
    print_report(coverage)
    write_csv_report(coverage, config)
    total_close = sum(
        1 for seasons in coverage.values() for s in seasons if s["closing"]
    )
    print(f"\nCLV-faehige Liga-Saisons gesamt: {total_close}")
    print(f"Detailbericht: {config.REPORT_PATH}")


if __name__ == "__main__":
    main()
