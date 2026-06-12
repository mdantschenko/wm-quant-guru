"""Aggregiert Spielermarktwerte zu zeitgestempelten Nationalkader-Werten.

Erzeugt das Marktwert-Feature aus dem Konzept (Abschnitt Bayes-Hierarchie):
pro Land und Stichtag (halbjährliches Gitter) die Summe der Marktwerte der
wertvollsten Spieler dieser Staatsbürgerschaft -- strikt zeitkausal (nur
Bewertungen mit Datum <= Stichtag, begrenzte Rückschau gegen veraltete
Werte). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path


class SquadValueConfig:
    """Pfade und Aggregationsparameter."""

    SOURCE_DIR: str = "Data/Transfermarkt Market Values (player-scores)"
    VALUATIONS_FILE: str = "player_valuations.csv"
    PLAYERS_FILE: str = "players.csv"
    OUTPUT_FILE: str = "national_squad_values.csv"

    FIRST_AS_OF: date = date(2005, 1, 1)
    SQUAD_SIZE: int = 26          # WM-Kadergröße als Top-N-Proxy
    LOOKBACK_DAYS: int = 540      # Bewertung max. ~18 Monate alt
    MIN_PLAYERS: int = 10         # Länder mit weniger bewerteten Spielern entfallen


def semiannual_grid(first: date, last: date) -> list[date]:
    """Stichtage 1.1. und 1.7. jedes Jahres im Bereich [first, last]."""
    grid: list[date] = []
    for year in range(first.year, last.year + 1):
        for month in (1, 7):
            candidate = date(year, month, 1)
            if first <= candidate <= last:
                grid.append(candidate)
    return grid


def load_citizenship(config: SquadValueConfig) -> dict[int, str]:
    """Lade player_id -> Staatsbürgerschaft (leere Eintraege entfallen)."""
    path = Path(config.SOURCE_DIR) / config.PLAYERS_FILE
    citizenship: dict[int, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            country = (row.get("country_of_citizenship") or "").strip()
            if country:
                citizenship[int(row["player_id"])] = country
    return citizenship


def load_valuations(
    config: SquadValueConfig,
) -> dict[int, list[tuple[date, int]]]:
    """Lade player_id -> zeitlich sortierte Liste (datum, wert_eur)."""
    path = Path(config.SOURCE_DIR) / config.VALUATIONS_FILE
    valuations: dict[int, list[tuple[date, int]]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            value = row.get("market_value_in_eur") or ""
            if not value.isdigit():
                continue
            valuations.setdefault(int(row["player_id"]), []).append(
                (date.fromisoformat(row["date"]), int(value))
            )
    for series in valuations.values():
        series.sort()
    return valuations


def value_as_of(
    series: list[tuple[date, int]], as_of: date, lookback_days: int
) -> int | None:
    """Letzte Bewertung <= Stichtag innerhalb der Rückschau, sonst None."""
    latest: tuple[date, int] | None = None
    for valuation_date, value in series:
        if valuation_date > as_of:
            break
        latest = (valuation_date, value)
    if latest is None or (as_of - latest[0]).days > lookback_days:
        return None
    return latest[1]


def build_rows(config: SquadValueConfig) -> list[list[object]]:
    """Berechne pro Stichtag und Land die Top-N-Kadersumme."""
    citizenship = load_citizenship(config)
    valuations = load_valuations(config)
    last_valuation = max(s[-1][0] for s in valuations.values())
    rows: list[list[object]] = []
    for as_of in semiannual_grid(config.FIRST_AS_OF, last_valuation):
        per_country: dict[str, list[int]] = {}
        for player_id, series in valuations.items():
            country = citizenship.get(player_id)
            if country is None:
                continue
            value = value_as_of(series, as_of, config.LOOKBACK_DAYS)
            if value is not None:
                per_country.setdefault(country, []).append(value)
        for country, values in per_country.items():
            if len(values) < config.MIN_PLAYERS:
                continue
            top = sorted(values, reverse=True)[: config.SQUAD_SIZE]
            rows.append([as_of.isoformat(), country, sum(top), len(top)])
    return rows


def main() -> None:
    """Aggregiere und schreibe die Nationalkader-Marktwerte."""
    config = SquadValueConfig()
    rows = build_rows(config)
    target = Path(config.SOURCE_DIR) / config.OUTPUT_FILE
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["as_of_date", "country", "squad_value_eur", "n_players"])
        writer.writerows(rows)
    print(f"{len(rows)} Land-Stichtag-Zeilen -> {target}")


if __name__ == "__main__":
    main()
