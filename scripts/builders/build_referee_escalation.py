"""Schiedsrichter-Eskalation: werden Karten ueberadditiv, wenn ein foulintensives
Team auf einen strengen Schiedsrichter trifft (Wyscout 2017/18).

Die uebliche Annahme ist additiv: erwartete Karten gleich Teamschnitt plus
Schiedsrichterschnitt. Diese Auswertung prueft, ob stattdessen eine
Wechselwirkung vorliegt, also ob die Kombination aus hoher Foulrate und strengem
Schiedsrichter mehr Karten erzeugt als die Summe der Einzelteile.

Datenquellen sind lokal: Fouls je Team und Spiel aus actions.csv, Karten aus den
Event-Tags, der Hauptschiedsrichter je Spiel aus matches_*.csv. Die Strenge
eines Schiedsrichters ist sein Verhaeltnis Karten zu Fouls ueber alle geleiteten
Spiele.

Ausgaben nach Data/Custom_Data/:
  - referee_strictness.csv    je Schiedsrichter Spiele, Fouls, Karten, Strenge,
  - referee_escalation.csv    die Bandtabelle Foulrate mal Strenge.

Reine Standardbibliothek.

Start als Modul:
    python -m scripts.builders.build_referee_escalation
"""
from __future__ import annotations

import ast
import csv
from pathlib import Path
from statistics import mean, pstdev

from scripts.builders.build_player_cards import stream_cards
from scripts.builders.build_player_metrics import normalize_id
from scripts.helpers.text import decode_escapes

WYSCOUT_DIR = "Data/Wyscout Events (Pappalardo 2017-18)"
OUTPUT_DIR = "Data/Custom_Data"
MINIMUM_REFEREE_MATCHES = 8
HIGH = 0.5
LOW = -0.5


def load_match_meta(directory: Path) -> dict[str, dict]:
    """Liest je Spiel Wettbewerb, Saison und Hauptschiedsrichter aus matches_*.csv."""
    meta: dict[str, dict] = {}
    for path in sorted(directory.glob("matches_*.csv")):
        with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
            for row in csv.DictReader(handle):
                referee = main_referee(row.get("referees", ""))
                meta[normalize_id(row.get("wyId", ""))] = {
                    "league": (normalize_id(row.get("competitionId", "")), row.get("seasonId", "")),
                    "referee": referee}
    return meta


def main_referee(cell: str) -> str:
    """Gibt die Id des Hauptschiedsrichters zurueck, sonst leere Zeichenkette."""
    try:
        officials = ast.literal_eval(cell)
    except (ValueError, SyntaxError):
        return ""
    for official in officials if isinstance(officials, list) else []:
        if official.get("role") == "referee":
            return normalize_id(str(official.get("refereeId")))
    return ""


def count_fouls(actions_path: Path) -> dict[tuple, int]:
    """Zaehlt Fouls je (Spiel, Team) aus dem Aktionsstrom."""
    fouls: dict[tuple, int] = {}
    with open(actions_path, encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        column = {name: index for index, name in enumerate(next(reader))}
        for raw in reader:
            if raw[column["type_name"]] != "foul":
                continue
            key = (normalize_id(raw[column["game_id"]]), normalize_id(raw[column["team_id"]]))
            fouls[key] = fouls.get(key, 0) + 1
    return fouls


def count_cards(directory: Path) -> dict[tuple, int]:
    """Zaehlt Karten je (Spiel, Team) ueber die Event-Tags."""
    cards: dict[tuple, int] = {}
    for path in sorted(directory.glob("events_*.csv")):
        for (_player, game, team), bucket in stream_cards(path).items():
            cards[(game, team)] = cards.get((game, team), 0) + sum(bucket.values())
    return cards


def referee_strictness(fouls: dict[tuple, int], cards: dict[tuple, int],
                       meta: dict[str, dict], names: dict[str, str]) -> tuple[dict, list]:
    """Bestimmt je Schiedsrichter das Verhaeltnis Karten zu Fouls."""
    game_fouls: dict[str, int] = {}
    for (game, _team), value in fouls.items():
        game_fouls[game] = game_fouls.get(game, 0) + value
    game_cards: dict[str, int] = {}
    for (game, _team), value in cards.items():
        game_cards[game] = game_cards.get(game, 0) + value
    totals: dict[str, list] = {}
    for game, info in meta.items():
        referee = info["referee"]
        if not referee:
            continue
        entry = totals.setdefault(referee, [0, 0, 0])
        entry[0] += 1
        entry[1] += game_fouls.get(game, 0)
        entry[2] += game_cards.get(game, 0)
    strictness: dict[str, float] = {}
    rows: list[dict] = []
    for referee, (matches, total_fouls, total_cards) in totals.items():
        if matches < MINIMUM_REFEREE_MATCHES or total_fouls == 0:
            continue
        ratio = total_cards / total_fouls
        strictness[referee] = ratio
        rows.append({"referee": names.get(referee, referee), "matches": matches,
                     "fouls": total_fouls, "cards": total_cards,
                     "cards_per_foul": round(ratio, 4)})
    rows.sort(key=lambda row: row["cards_per_foul"], reverse=True)
    return strictness, rows


def band(value: float) -> str:
    return "hoch" if value >= HIGH else ("niedrig" if value <= LOW else "mittel")


def league_foul_scales(fouls: dict[tuple, int], meta: dict) -> dict[tuple, tuple]:
    """Mittelwert und Streuung der Team-Foulzahl je Liga und Saison."""
    pools: dict[tuple, list] = {}
    for (game, _team), value in fouls.items():
        info = meta.get(game)
        if info:
            pools.setdefault(info["league"], []).append(value)
    return {league: (mean(values), pstdev(values))
            for league, values in pools.items() if len(values) >= 2}


def escalation_table(fouls: dict, cards: dict, meta: dict, strictness: dict) -> list[dict]:
    """Aggregiert mittlere Karten je Band aus Foulrate und Schiedsrichterstrenge."""
    foul_scales = league_foul_scales(fouls, meta)
    strict_values = list(strictness.values())
    strict_center, strict_spread = mean(strict_values), pstdev(strict_values)
    cells: dict[tuple, list] = {}
    for (game, team), team_fouls in fouls.items():
        info = meta.get(game)
        if info is None or info["referee"] not in strictness or info["league"] not in foul_scales:
            continue
        foul_center, foul_spread = foul_scales[info["league"]]
        foul_z = (team_fouls - foul_center) / foul_spread if foul_spread else 0.0
        strict_z = (strictness[info["referee"]] - strict_center) / strict_spread if strict_spread else 0.0
        entry = cells.setdefault((band(foul_z), band(strict_z)), [0, 0, 0])
        entry[0] += 1
        entry[1] += team_fouls
        entry[2] += cards.get((game, team), 0)
    return _table_rows(cells)


def _table_rows(cells: dict[tuple, list]) -> list[dict]:
    rows: list[dict] = []
    for (foul_band, strict_band), (count, sum_fouls, sum_cards) in cells.items():
        rows.append({"aggression_band": foul_band, "strictness_band": strict_band,
                     "team_matches": count, "mean_fouls": round(sum_fouls / count, 2),
                     "mean_cards": round(sum_cards / count, 3)})
    order = {"niedrig": 0, "mittel": 1, "hoch": 2}
    rows.sort(key=lambda row: (order[row["aggression_band"]], order[row["strictness_band"]]))
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def report_excess(table: list[dict]) -> None:
    """Vergleicht die Zelle hoch mal hoch mit der additiven Erwartung."""
    lookup = {(row["aggression_band"], row["strictness_band"]): row["mean_cards"] for row in table}
    grand = mean([row["mean_cards"] for row in table]) if table else 0.0
    high_aggr = mean([v for (a, _s), v in lookup.items() if a == "hoch"]) if any(a == "hoch" for a, _ in lookup) else grand
    high_strict = mean([v for (_a, s), v in lookup.items() if s == "hoch"]) if any(s == "hoch" for _, s in lookup) else grand
    observed = lookup.get(("hoch", "hoch"))
    if observed is None:
        return
    additive = high_aggr + high_strict - grand
    print(f"  INFO  hoch x hoch beobachtet {observed:.3f}, additiv erwartet {additive:.3f}, "
          f"Ueberschuss {observed - additive:+.3f} Karten je Teamspiel")


def main() -> None:
    directory = Path(WYSCOUT_DIR)
    names = {normalize_id(row["wyId"]): decode_escapes(row["shortName"])
             for row in csv.DictReader(open(directory / "referees.csv", encoding="utf-8"))}
    meta = load_match_meta(directory)
    fouls = count_fouls(directory / "actions.csv")
    cards = count_cards(directory)
    strictness, strictness_rows = referee_strictness(fouls, cards, meta, names)
    table = escalation_table(fouls, cards, meta, strictness)

    output_dir = Path(OUTPUT_DIR)
    write_csv(output_dir / "referee_strictness.csv", strictness_rows,
              ["referee", "matches", "fouls", "cards", "cards_per_foul"])
    write_csv(output_dir / "referee_escalation.csv", table,
              ["aggression_band", "strictness_band", "team_matches", "mean_fouls", "mean_cards"])
    print(f"  OK    {len(strictness_rows)} Schiedsrichter, {len(table)} Bandzellen")
    report_excess(table)


if __name__ == "__main__":
    main()
