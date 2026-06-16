"""Granulare Passlinien je Spiel (komplettes Passnetzwerk, Wyscout-Teil).

Waehrend passing_networks.csv je Team und Spiel nur Kennzahlen zusammenfasst,
enthaelt dieser Datensatz die VOLLEN Netzwerkkanten: je Spiel, Team und
Passgeber-Empfaenger-Paar die Zahl der Paesse, davon vorwaerts, sowie die
mittlere Start- und Endposition. Damit laesst sich das Passnetzwerk komplett
rekonstruieren.

Empfaenger wird ueber die unmittelbar folgende Aktion desselben Teams
erschlossen (Standardheuristik). Der StatsBomb-Teil
(build_passing_lanes_statsbomb.py) nutzt das praezisere pass.recipient und
mischt ueber die Spalte source ein. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator, Optional

PASS_TYPES = {"pass", "cross", "throw_in", "freekick_short", "freekick_crossed",
              "corner_short", "corner_crossed", "goalkick"}


class LanesConfig:
    """Pfade und Geometrie."""

    WYSCOUT_DIR: str = "Data/Wyscout Events (Pappalardo 2017-18)"
    OUTPUT_FILE: str = "Data/Custom_Data/passing_lanes.csv"
    FORWARD_THRESHOLD_M: float = 5.0
    FIELDNAMES: list[str] = [
        "source", "game_id", "competition", "season", "date", "team",
        "passer", "receiver", "passes", "forward_passes", "mean_start_x", "mean_end_x",
    ]


def decode_escapes(text: str) -> str:
    if "\\u" not in text:
        return text
    try:
        return text.encode("latin-1", "backslashreplace").decode("unicode_escape")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def normalize_id(value: str) -> str:
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return value.strip()


def load_lookup(path: Path, key: str, value: str) -> dict[str, str]:
    with open(path, encoding="utf-8") as handle:
        return {normalize_id(row[key]): decode_escapes(row[value]) for row in csv.DictReader(handle)}


def load_games(path: Path) -> dict[str, dict[str, str]]:
    games: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            games[normalize_id(row["game_id"])] = {
                "competition_id": normalize_id(row["competition_id"]),
                "season": row["season_id"], "date": row["game_date"][:10],
            }
    return games


def edges_from_actions(actions: list[tuple], config: LanesConfig) -> dict[tuple, list]:
    """Aggregiert Kanten (team, passer, receiver) aus der Aktionsfolge eines Spiels."""
    edges: dict[tuple, list] = {}
    count = len(actions)
    for index in range(count - 1):
        team, kind, success, start_x, end_x, passer = actions[index]
        if kind not in PASS_TYPES or not success:
            continue
        next_team, _, _, _, _, receiver = actions[index + 1]
        if next_team != team or not receiver or receiver == passer:
            continue
        key = (team, passer, receiver)
        record = edges.setdefault(key, [0, 0, 0.0, 0.0])
        record[0] += 1
        record[1] += 1 if (end_x - start_x) > config.FORWARD_THRESHOLD_M else 0
        record[2] += start_x
        record[3] += end_x
    return edges


def iter_wyscout_lanes(config: LanesConfig) -> Iterator[dict[str, object]]:
    source_dir = Path(config.WYSCOUT_DIR)
    games = load_games(source_dir / "games.csv")
    teams = load_lookup(source_dir / "teams.csv", "wyId", "name")
    players = load_lookup(source_dir / "players.csv", "wyId", "shortName")
    competitions = load_lookup(source_dir / "competitions.csv", "wyId", "name")
    with open(source_dir / "actions.csv", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        column = {name: index for index, name in enumerate(next(reader))}
        current: Optional[str] = None
        buffer: list[tuple] = []
        for raw in reader:
            game_id = normalize_id(raw[column["game_id"]])
            if game_id != current:
                yield from _emit(current, buffer, games, teams, players, competitions, config)
                current, buffer = game_id, []
            buffer.append(_read_action(raw, column))
        yield from _emit(current, buffer, games, teams, players, competitions, config)


def _read_action(raw: list[str], column: dict[str, int]) -> tuple:
    try:
        # Wyscout-SPADL greift Richtung x=0 an; auf Standard (Richtung x=105) spiegeln.
        start_x, end_x = 105.0 - float(raw[column["start_x"]]), 105.0 - float(raw[column["end_x"]])
    except (ValueError, KeyError):
        start_x, end_x = 0.0, 0.0
    return (normalize_id(raw[column["team_id"]]), raw[column["type_name"]],
            raw[column["result_name"]] == "success", start_x, end_x,
            normalize_id(raw[column["player_id"]]))


def _emit(game_id, buffer, games, teams, players, competitions, config) -> list[dict[str, object]]:
    if game_id is None or not buffer:
        return []
    meta = games.get(game_id)
    if meta is None:
        return []
    rows: list[dict[str, object]] = []
    for (team, passer, receiver), record in edges_from_actions(buffer, config).items():
        rows.append({
            "source": "wyscout", "game_id": game_id,
            "competition": competitions.get(meta["competition_id"], ""), "season": meta["season"],
            "date": meta["date"], "team": teams.get(team, team),
            "passer": players.get(passer, passer), "receiver": players.get(receiver, receiver),
            "passes": record[0], "forward_passes": record[1],
            "mean_start_x": round(record[2] / record[0], 1), "mean_end_x": round(record[3] / record[0], 1),
        })
    return rows


def load_existing(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_all(rows: list[dict[str, object]], config: LanesConfig) -> None:
    path = Path(config.OUTPUT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=config.FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = LanesConfig()
    kept_statsbomb = [row for row in load_existing(Path(config.OUTPUT_FILE))
                      if row.get("source") == "statsbomb"]
    wyscout_rows = list(iter_wyscout_lanes(config))
    write_all(wyscout_rows + kept_statsbomb, config)
    print(f"  OK    {len(wyscout_rows)} Wyscout-Passlinien "
          f"(plus {len(kept_statsbomb)} vorhandene StatsBomb-Linien erhalten)")


if __name__ == "__main__":
    main()
