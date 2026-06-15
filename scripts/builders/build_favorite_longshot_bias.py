"""Quantifiziert den Favorite-Longshot-Bias an den Quotenextremen.

Die Idee hinter \"uberschaetzten Quoten bei sehr guten gegen sehr schlechte
Mannschaften wird hier empirisch gepr\"uft. Aus allen Spielen mit
1X2-Quoten wird je Spiel die entvigte Wahrscheinlichkeit des Favoriten
bestimmt (Favorit = Ausgang mit der niedrigsten Quote) und mit der
tats\"achlichen Eintrittsh\"aufigkeit verglichen. Je Favoritenband ergeben
sich:
  - die mittlere implizite Favoritenwahrscheinlichkeit,
  - die tats\"achliche Siegquote des Favoriten,
  - die Kalibrierungsl\"ucke (implizit minus tats\"achlich); positiv heisst
    der Markt \"ubersch\"atzt den Favoriten,
  - der Flat-Stake-ROI f\"ur das Backen des Favoriten bzw. des Aussenseiters
    (zeigt, ob an den Extremen ein Vorteil liegt).

Quelle football-data.co.uk (Vereinsligen, viele Extrempaarungen). Pro Spiel
werden die sch\"arfsten verf\"ugbaren Quoten genutzt (Pinnacle-Closing vor
Pinnacle-Open vor Bet365 vor Durchschnitt). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from pathlib import Path


class BiasConfig:
    """Pfade, Quotenquellen-Priorit\"at und Bandgrenzen."""

    SOURCE_DIR: str = "Data/Football Betting Odds (football-data.co.uk)"
    OUTPUT_DIR: str = "Data/Custom_Data"

    # (Heim, Remis, Gast), schaerfste Quelle zuerst.
    ODDS_SOURCES: tuple[tuple[str, str, str], ...] = (
        ("PSCH", "PSCD", "PSCA"),
        ("PSH", "PSD", "PSA"),
        ("B365H", "B365D", "B365A"),
        ("AvgH", "AvgD", "AvgA"),
    )
    RESULT_LETTERS: tuple[str, str, str] = ("H", "D", "A")
    # Feiner an den Extremen, denn dort sitzt die Aussage.
    BAND_EDGES: tuple[float, ...] = (
        0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.90, 0.95, 1.0001,
    )


def read_best_odds(
    row: dict[str, str], config: BiasConfig
) -> tuple[float, float, float] | None:
    """Liefert das erste vollst\"andige, g\"ultige Quotentripel der Priorit\"at."""
    for triple in config.ODDS_SOURCES:
        try:
            values = (float(row[triple[0]]), float(row[triple[1]]), float(row[triple[2]]))
        except (KeyError, ValueError):
            continue
        if all(value > 1.0 for value in values):
            return values
    return None


def band_of(probability: float, config: BiasConfig) -> str | None:
    """Ordnet die Favoritenwahrscheinlichkeit einem Band zu."""
    for lower, upper in zip(config.BAND_EDGES[:-1], config.BAND_EDGES[1:]):
        if lower <= probability < upper:
            return f"{lower:.2f}_{min(upper, 1.0):.2f}"
    return None


def empty_bucket() -> dict[str, float]:
    return {
        "matches": 0.0,
        "implied_sum": 0.0,
        "favorite_wins": 0.0,
        "favorite_profit": 0.0,
        "longshot_profit": 0.0,
    }


def accumulate(
    bucket: dict[str, float],
    implied_favorite: float,
    favorite_won: float,
    favorite_odds: float,
    longshot_won: float,
    longshot_odds: float,
) -> None:
    bucket["matches"] += 1.0
    bucket["implied_sum"] += implied_favorite
    bucket["favorite_wins"] += favorite_won
    bucket["favorite_profit"] += favorite_odds * favorite_won - 1.0
    bucket["longshot_profit"] += longshot_odds * longshot_won - 1.0


def collect_buckets(config: BiasConfig) -> dict[str, dict[str, float]]:
    """Aggregiert alle Spiele je Favoritenband und einen Gesamteintrag."""
    buckets: dict[str, dict[str, float]] = {"all": empty_bucket()}
    for path in sorted(Path(config.SOURCE_DIR).rglob("*.csv")):
        if path.name == "coverage_report.csv":
            continue
        with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
            for row in csv.DictReader(handle):
                result = row.get("FTR", "")
                if result not in config.RESULT_LETTERS:
                    continue
                odds = read_best_odds(row, config)
                if odds is None:
                    continue
                inverse = [1.0 / value for value in odds]
                overround = sum(inverse)
                implied = [value / overround for value in inverse]
                favorite_index = min(range(3), key=lambda k: odds[k])
                longshot_index = max(range(3), key=lambda k: odds[k])
                band = band_of(implied[favorite_index], config)
                if band is None:
                    continue
                favorite_won = 1.0 if result == config.RESULT_LETTERS[favorite_index] else 0.0
                longshot_won = 1.0 if result == config.RESULT_LETTERS[longshot_index] else 0.0
                for key in (band, "all"):
                    accumulate(
                        buckets.setdefault(key, empty_bucket()),
                        implied[favorite_index], favorite_won, odds[favorite_index],
                        longshot_won, odds[longshot_index],
                    )
    return buckets


def build_rows(buckets: dict[str, dict[str, float]]) -> list[dict[str, object]]:
    """Bildet je Band die Kalibrierungs- und ROI-Kennzahlen."""
    rows: list[dict[str, object]] = []
    ordered = [key for key in sorted(buckets) if key != "all"] + ["all"]
    for band in ordered:
        bucket = buckets[band]
        count = bucket["matches"]
        if count == 0:
            continue
        mean_implied = bucket["implied_sum"] / count
        actual_rate = bucket["favorite_wins"] / count
        rows.append({
            "favorite_band": band,
            "matches": int(count),
            "mean_implied_fav": round(mean_implied, 4),
            "actual_fav_winrate": round(actual_rate, 4),
            "calibration_gap": round(mean_implied - actual_rate, 4),
            "fav_flat_roi_pct": round(100.0 * bucket["favorite_profit"] / count, 2),
            "longshot_flat_roi_pct": round(100.0 * bucket["longshot_profit"] / count, 2),
        })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = BiasConfig()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = build_rows(collect_buckets(config))
    write_csv(
        output_dir / "favorite_longshot_bias.csv",
        rows,
        ["favorite_band", "matches", "mean_implied_fav", "actual_fav_winrate",
         "calibration_gap", "fav_flat_roi_pct", "longshot_flat_roi_pct"],
    )
    total = next((row for row in rows if row["favorite_band"] == "all"), None)
    if total is not None:
        print(f"  OK    {total['matches']} Spiele \"uber {len(rows) - 1} Favoritenb\"ander")


if __name__ == "__main__":
    main()
