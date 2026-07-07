"""Favorite-Longshot-Bias je Spiel und je Favoritenband ueber ALLE Quotenquellen.

Pro Spiel mit 1X2-Quoten werden die entvigte Favoritenwahrscheinlichkeit
(Favorit = niedrigste Quote) und der tatsaechliche Ausgang gegenuebergestellt.
Ausgaben nach Data/Custom_Data/:
  - favorite_longshot_matches.csv  eine Zeile JE SPIEL (die Rohdaten) mit
    entvigten Wahrscheinlichkeiten, Favorit, Ergebnis, Quote und Flat-Profit.
  - favorite_longshot_bias.csv     Kalibrierung je Favoritenband (gesamt).
  - favorite_longshot_bias_by_source.csv  dasselbe je Quelle.

Quellen (jeweils mit eigener Spalte `source`):
  - football-data.co.uk (Vereinsligen, schaerfste Quote je Spiel),
  - Club Football Engineered (Vereinsligen, ueberlappt football-data stark),
  - FootyStats International und Turnier (Nationalteams, fuer die WM relevant),
  - Beat The Bookie International (Nationalteams 2005-2015, Closing).
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from itertools import chain
from pathlib import Path
from typing import Iterator

from src.scripts.helpers.dates import to_iso_date


class BiasConfig:
    """Pfade, Quotenspalten und Bandgrenzen."""

    FOOTBALL_DATA_DIR: str = "Data/Football Betting Odds (football-data.co.uk)"
    CLUB_ENGINEERED_FILE: str = "Data/Club Football Engineered (2000-2025)/Matches.csv"
    FOOTYSTATS_DIRS: tuple[str, ...] = (
        "Data/International Matches & Odds (FootyStats)",
        "Data/Tournament Odds (FootyStats)",
    )
    BEAT_THE_BOOKIE_FILE: str = (
        "Data/International & Tournament Odds (Beat The Bookie 2005-2015)/"
        "international_closing_odds.csv"
    )
    OUTPUT_DIR: str = "Data/Custom_Data"

    FOOTBALL_DATA_ODDS: tuple[tuple[str, str, str], ...] = (
        ("PSCH", "PSCD", "PSCA"), ("PSH", "PSD", "PSA"),
        ("B365H", "B365D", "B365A"), ("AvgH", "AvgD", "AvgA"),
    )
    RESULT_LETTERS: tuple[str, str, str] = ("H", "D", "A")
    OUTCOME_NAMES: tuple[str, str, str] = ("home", "draw", "away")
    BAND_EDGES: tuple[float, ...] = (
        0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.90, 0.95, 1.0001,
    )


def valid_triple(values: tuple[float, float, float]) -> bool:
    return all(value > 1.0 for value in values)


def band_of(probability: float, config: BiasConfig) -> str | None:
    for lower, upper in zip(config.BAND_EDGES[:-1], config.BAND_EDGES[1:]):
        if lower <= probability < upper:
            return f"{lower:.2f}_{min(upper, 1.0):.2f}"
    return None


def make_record(source: str, date: str, competition: str, home: str, away: str,
                result_index: int, odds: tuple[float, float, float]) -> dict[str, object]:
    return {"source": source, "date": date, "competition": competition,
            "home": home, "away": away, "result_index": result_index, "odds": odds}


def iter_football_data(config: BiasConfig) -> Iterator[dict[str, object]]:
    for path in sorted(Path(config.FOOTBALL_DATA_DIR).rglob("*.csv")):
        if path.name == "coverage_report.csv":
            continue
        with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
            for row in csv.DictReader(handle):
                result = row.get("FTR", "")
                if result not in config.RESULT_LETTERS:
                    continue
                odds = _best_football_data_odds(row, config)
                if odds is None:
                    continue
                yield make_record("football-data", row.get("Date", ""), path.parent.name,
                                  row.get("HomeTeam", ""), row.get("AwayTeam", ""),
                                  config.RESULT_LETTERS.index(result), odds)


def _best_football_data_odds(
    row: dict[str, str], config: BiasConfig
) -> tuple[float, float, float] | None:
    for triple in config.FOOTBALL_DATA_ODDS:
        try:
            values = (float(row[triple[0]]), float(row[triple[1]]), float(row[triple[2]]))
        except (KeyError, ValueError):
            continue
        if valid_triple(values):
            return values
    return None


def iter_club_engineered(config: BiasConfig) -> Iterator[dict[str, object]]:
    path = Path(config.CLUB_ENGINEERED_FILE)
    if not path.exists():
        return
    with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
        for row in csv.DictReader(handle):
            result = row.get("FTResult", "")
            if result not in config.RESULT_LETTERS:
                continue
            try:
                odds = (float(row["OddHome"]), float(row["OddDraw"]), float(row["OddAway"]))
            except (KeyError, ValueError):
                continue
            if not valid_triple(odds):
                continue
            yield make_record("club-engineered", row.get("MatchDate", ""),
                              row.get("Division", ""), row.get("HomeTeam", ""),
                              row.get("AwayTeam", ""), config.RESULT_LETTERS.index(result), odds)


def iter_footystats(config: BiasConfig) -> Iterator[dict[str, object]]:
    for base in config.FOOTYSTATS_DIRS:
        base_path = Path(base)
        for path in sorted(base_path.rglob("*.csv")):
            competition = path.stem if path.parent == base_path else path.parent.name
            with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
                for row in csv.DictReader(handle):
                    if row.get("status") != "complete":
                        continue
                    try:
                        home_goals = int(row["home_team_goal_count"])
                        away_goals = int(row["away_team_goal_count"])
                        odds = (float(row["odds_ft_home_team_win"]),
                                float(row["odds_ft_draw"]),
                                float(row["odds_ft_away_team_win"]))
                    except (KeyError, ValueError):
                        continue
                    if not valid_triple(odds):
                        continue
                    result_index = 0 if home_goals > away_goals else (1 if home_goals == away_goals else 2)
                    yield make_record("footystats", row.get("date_GMT", ""), competition,
                                      row.get("home_team_name", ""), row.get("away_team_name", ""),
                                      result_index, odds)


def iter_beat_the_bookie(config: BiasConfig) -> Iterator[dict[str, object]]:
    path = Path(config.BEAT_THE_BOOKIE_FILE)
    if not path.exists():
        return
    with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                home_score = int(row["home_score"])
                away_score = int(row["away_score"])
                odds = (float(row["avg_odds_home_win"]), float(row["avg_odds_draw"]),
                        float(row["avg_odds_away_win"]))
            except (KeyError, ValueError):
                continue
            if not valid_triple(odds):
                continue
            result_index = 0 if home_score > away_score else (1 if home_score == away_score else 2)
            yield make_record("beat-the-bookie", row.get("match_date", ""),
                              row.get("league", ""), row.get("home_team", ""),
                              row.get("away_team", ""), result_index, odds)


def empty_bucket() -> dict[str, float]:
    return {"matches": 0.0, "implied_sum": 0.0, "favorite_wins": 0.0,
            "favorite_profit": 0.0, "longshot_profit": 0.0}


def summary_rows(bands: dict[str, dict[str, float]], config: BiasConfig,
                 source: str | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    ordered = [key for key in sorted(bands) if key != "all"] + ["all"]
    for band in ordered:
        bucket = bands.get(band)
        if not bucket or bucket["matches"] == 0:
            continue
        count = bucket["matches"]
        mean_implied = bucket["implied_sum"] / count
        actual = bucket["favorite_wins"] / count
        row: dict[str, object] = {} if source is None else {"source": source}
        row.update({
            "favorite_band": band,
            "matches": int(count),
            "mean_implied_fav": round(mean_implied, 4),
            "actual_fav_winrate": round(actual, 4),
            "calibration_gap": round(mean_implied - actual, 4),
            "fav_flat_roi_pct": round(100.0 * bucket["favorite_profit"] / count, 2),
            "longshot_flat_roi_pct": round(100.0 * bucket["longshot_profit"] / count, 2),
        })
        rows.append(row)
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

    overall: dict[str, dict[str, float]] = {}
    by_source: dict[str, dict[str, dict[str, float]]] = {}
    match_fields = ["source", "date", "competition", "home", "away", "result",
                    "odds_home", "odds_draw", "odds_away", "favorite", "implied_fav",
                    "favorite_won", "favorite_odds", "favorite_band", "favorite_profit"]
    match_rows: list[dict[str, object]] = []
    sources = chain(iter_football_data(config), iter_club_engineered(config),
                    iter_footystats(config), iter_beat_the_bookie(config))
    for record in sources:
        odds = record["odds"]
        inverse = [1.0 / value for value in odds]
        overround = sum(inverse)
        implied = [value / overround for value in inverse]
        favorite = min(range(3), key=lambda k: odds[k])
        longshot = max(range(3), key=lambda k: odds[k])
        band = band_of(implied[favorite], config)
        if band is None:
            continue
        favorite_won = 1.0 if record["result_index"] == favorite else 0.0
        longshot_won = 1.0 if record["result_index"] == longshot else 0.0
        favorite_profit = odds[favorite] * favorite_won - 1.0
        longshot_profit = odds[longshot] * longshot_won - 1.0
        for scope in (overall, by_source.setdefault(record["source"], {})):
            for key in (band, "all"):
                bucket = scope.setdefault(key, empty_bucket())
                bucket["matches"] += 1.0
                bucket["implied_sum"] += implied[favorite]
                bucket["favorite_wins"] += favorite_won
                bucket["favorite_profit"] += favorite_profit
                bucket["longshot_profit"] += longshot_profit
        match_rows.append({
            "source": record["source"], "date": to_iso_date(str(record["date"])),
            "competition": record["competition"], "home": record["home"],
            "away": record["away"], "result": config.RESULT_LETTERS[record["result_index"]],
            "odds_home": odds[0], "odds_draw": odds[1], "odds_away": odds[2],
            "favorite": config.OUTCOME_NAMES[favorite],
            "implied_fav": round(implied[favorite], 4),
            "favorite_won": int(favorite_won),
            "favorite_odds": odds[favorite], "favorite_band": band,
            "favorite_profit": round(favorite_profit, 4),
        })
    match_rows.sort(key=lambda row: (str(row["competition"]), str(row["date"]), str(row["home"])))
    write_csv(output_dir / "favorite_longshot_matches.csv", match_rows, match_fields)
    written = len(match_rows)

    write_csv(output_dir / "favorite_longshot_bias.csv", summary_rows(overall, config),
              ["favorite_band", "matches", "mean_implied_fav", "actual_fav_winrate",
               "calibration_gap", "fav_flat_roi_pct", "longshot_flat_roi_pct"])
    by_source_rows: list[dict[str, object]] = []
    for source in sorted(by_source):
        by_source_rows.extend(summary_rows(by_source[source], config, source=source))
    write_csv(output_dir / "favorite_longshot_bias_by_source.csv", by_source_rows,
              ["source", "favorite_band", "matches", "mean_implied_fav", "actual_fav_winrate",
               "calibration_gap", "fav_flat_roi_pct", "longshot_flat_roi_pct"])

    print(f"  OK    {written} Spiele (Rohdaten) -> favorite_longshot_matches.csv")
    for source in sorted(by_source):
        print(f"        {source}: {int(by_source[source]['all']['matches'])} Spiele")


if __name__ == "__main__":
    main()
