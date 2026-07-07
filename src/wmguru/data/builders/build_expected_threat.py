"""Expected Threat (xT) je Aktion, Spieler und Team aus den Wyscout-Events.

Lernt ein Gitter nach dem Verfahren von Karun Singh. Jede Zelle des Spielfelds
erhaelt einen Bedrohungswert, der angibt, wie wahrscheinlich aus dieser Position
ein Tor folgt. Erfolgreiche Ballbewegungen werden dann mit der Wertdifferenz
zwischen Ziel und Ausgangszelle bewertet (xt_added). So wird Ballfortschritt
gemessen, der klassische Statistiken nicht erfassen.

Das Modell nutzt ausschliesslich offenes Spiel (Pass, Dribbling, Flanke als
Bewegung sowie Feldschuesse zur Torwahrscheinlichkeit). Standardsituationen und
Elfmeter bleiben aussen vor, damit sie die Torquote der Zellen nicht verzerren.

Das gelernte Gitter wird persistiert (xt_grid.csv), damit der StatsBomb-Teil
build_expected_threat_statsbomb.py dasselbe Modell anwenden und vergleichbar
bleiben kann. Koordinaten werden auf den Standard gespiegelt (Wyscout-SPADL
greift Richtung x=0 an). Reine Standardbibliothek.

Start als Modul:
    python -m scripts.builders.build_expected_threat
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from src.scripts.builders.build_player_metrics import load_games, load_simple, normalize_id
from src.scripts.helpers.text import decode_escapes


class ExpectedThreatConfig:
    """Pfade, Spielfeldgeometrie und Modellparameter."""

    WYSCOUT_DIR: str = "Data/Wyscout Events (Pappalardo 2017-18)"
    OUTPUT_DIR: str = "Data/Custom_Data"
    PITCH_X: float = 105.0
    PITCH_Y: float = 68.0
    GRID_COLS: int = 16
    GRID_ROWS: int = 12
    ITERATIONS: int = 6
    MOVE_TYPES: frozenset[str] = frozenset({"pass", "dribble", "cross"})
    SHOT_TYPES: frozenset[str] = frozenset({"shot"})


def cell_index(x: float, y: float, config: ExpectedThreatConfig) -> int:
    """Bildet eine Position auf den linearen Zellindex des Gitters ab."""
    col = min(config.GRID_COLS - 1, max(0, int(x / config.PITCH_X * config.GRID_COLS)))
    row = min(config.GRID_ROWS - 1, max(0, int(y / config.PITCH_Y * config.GRID_ROWS)))
    return row * config.GRID_COLS + col


def iter_actions(path: Path, config: ExpectedThreatConfig) -> Iterator[tuple]:
    """Streamt Aktionen als (Spiel, Team, Spieler, Typ, Erfolg, Startzelle, Zielzelle)."""
    with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        column = {name: index for index, name in enumerate(next(reader))}
        for raw in reader:
            try:
                start_x = config.PITCH_X - float(raw[column["start_x"]])
                end_x = config.PITCH_X - float(raw[column["end_x"]])
                start_y = float(raw[column["start_y"]])
                end_y = float(raw[column["end_y"]])
            except ValueError:
                continue
            yield (
                normalize_id(raw[column["game_id"]]), normalize_id(raw[column["team_id"]]),
                normalize_id(raw[column["player_id"]]), raw[column["type_name"]],
                raw[column["result_name"]] == "success",
                cell_index(start_x, start_y, config), cell_index(end_x, end_y, config),
            )


def learn_grid(path: Path, config: ExpectedThreatConfig) -> tuple[list, list, list, list]:
    """Zaehlt Schuesse, Tore, erfolgreiche Bewegungen und Uebergaenge je Zelle."""
    size = config.GRID_COLS * config.GRID_ROWS
    shots = [0] * size
    goals = [0] * size
    moves = [0] * size
    transitions = [[0] * size for _ in range(size)]
    for _, _, _, kind, success, start, end in iter_actions(path, config):
        if kind in config.SHOT_TYPES:
            shots[start] += 1
            if success:
                goals[start] += 1
        elif kind in config.MOVE_TYPES and success:
            moves[start] += 1
            transitions[start][end] += 1
    return shots, goals, moves, transitions


def solve_expected_threat(shots: list, goals: list, moves: list,
                          transitions: list, config: ExpectedThreatConfig) -> list[float]:
    """Loest die xT-Fixpunktgleichung iterativ ueber das Gitter."""
    size = len(shots)
    threat = [0.0] * size
    for _ in range(config.ITERATIONS):
        updated = [0.0] * size
        for cell in range(size):
            total = shots[cell] + moves[cell]
            if total == 0:
                continue
            goal_probability = goals[cell] / shots[cell] if shots[cell] else 0.0
            move_value = 0.0
            if moves[cell]:
                row = transitions[cell]
                move_value = sum(row[target] * threat[target]
                                 for target in range(size) if row[target]) / moves[cell]
            updated[cell] = (shots[cell] / total) * goal_probability + (moves[cell] / total) * move_value
        threat = updated
    return threat


def aggregate(path: Path, threat: list[float],
              config: ExpectedThreatConfig) -> tuple[dict, dict]:
    """Summiert die Wertdifferenz erfolgreicher Bewegungen je Spieler und Team."""
    players: dict[tuple, list] = {}
    teams: dict[tuple, list] = {}
    for game, team, player, kind, success, start, end in iter_actions(path, config):
        if kind not in config.MOVE_TYPES or not success:
            continue
        delta = threat[end] - threat[start]
        player_entry = players.setdefault((player, game), [0.0, 0, team])
        player_entry[0] += delta
        player_entry[1] += 1
        team_entry = teams.setdefault((team, game), [0.0, 0])
        team_entry[0] += delta
        team_entry[1] += 1
    return players, teams


def build_player_rows(players: dict, games: dict, names: dict,
                      teams_lookup: dict, competitions: dict) -> list[dict[str, object]]:
    """Formt die Spieler-Spiel-Aggregate in Ausgabezeilen."""
    rows: list[dict[str, object]] = []
    for (player, game), (xt_sum, moves, team) in players.items():
        meta = games.get(game)
        if meta is None:
            continue
        opponent = meta["away"] if team == meta["home"] else meta["home"]
        rows.append({
            "source": "wyscout", "date": meta["date"],
            "competition": competitions.get(meta["competition_id"], meta["competition_id"]),
            "season": meta["season"], "team": teams_lookup.get(team, team),
            "opponent": teams_lookup.get(opponent, opponent),
            "player": names.get(player, player), "moves": moves,
            "xt_added": round(xt_sum, 4),
            "xt_added_per_move": round(xt_sum / moves, 5) if moves else "",
        })
    rows.sort(key=lambda row: (str(row["competition"]), str(row["season"]),
                               str(row["date"]), str(row["team"]), str(row["player"])))
    return rows


def build_team_rows(teams: dict, games: dict,
                    teams_lookup: dict, competitions: dict) -> list[dict[str, object]]:
    """Formt die Team-Spiel-Aggregate und ergaenzt xt_against aus dem Gegner."""
    by_game: dict[str, dict[str, float]] = {}
    for (team, game), (xt_sum, _moves) in teams.items():
        by_game.setdefault(game, {})[team] = xt_sum
    rows: list[dict[str, object]] = []
    for (team, game), (xt_sum, moves) in teams.items():
        meta = games.get(game)
        if meta is None:
            continue
        opponent = meta["away"] if team == meta["home"] else meta["home"]
        against = by_game.get(game, {}).get(opponent, 0.0)
        rows.append({
            "source": "wyscout", "date": meta["date"],
            "competition": competitions.get(meta["competition_id"], meta["competition_id"]),
            "season": meta["season"], "team": teams_lookup.get(team, team),
            "opponent": teams_lookup.get(opponent, opponent),
            "is_home": int(team == meta["home"]), "moves": moves,
            "xt_for": round(xt_sum, 4), "xt_against": round(against, 4),
            "xt_net": round(xt_sum - against, 4),
        })
    rows.sort(key=lambda row: (str(row["competition"]), str(row["season"]),
                               str(row["date"]), str(row["team"])))
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_grid(path: Path, threat: list[float], config: ExpectedThreatConfig) -> None:
    """Schreibt das gelernte Gitter (Spalte, Reihe, xT)."""
    rows: list[dict[str, object]] = []
    for cell, value in enumerate(threat):
        rows.append({"grid_col": cell % config.GRID_COLS,
                     "grid_row": cell // config.GRID_COLS, "xt": round(value, 6)})
    write_csv(path, rows, ["grid_col", "grid_row", "xt"])


def main() -> None:
    config = ExpectedThreatConfig()
    source = Path(config.WYSCOUT_DIR)
    actions_path = source / "actions.csv"
    games = load_games(source / "games.csv")
    teams_lookup = {key: decode_escapes(value)
                    for key, value in load_simple(source / "teams.csv", "wyId", "name").items()}
    players = {key: decode_escapes(value)
               for key, value in load_simple(source / "players.csv", "wyId", "shortName").items()}
    competitions = load_simple(source / "competitions.csv", "wyId", "name")

    shots, goals, moves, transitions = learn_grid(actions_path, config)
    threat = solve_expected_threat(shots, goals, moves, transitions, config)
    player_aggregate, team_aggregate = aggregate(actions_path, threat, config)

    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_grid(output_dir / "xt_grid.csv", threat, config)
    player_rows = build_player_rows(player_aggregate, games, players, teams_lookup, competitions)
    team_rows = build_team_rows(team_aggregate, games, teams_lookup, competitions)
    write_csv(output_dir / "xt_player_match.csv", player_rows,
              ["source", "date", "competition", "season", "team", "opponent", "player",
               "moves", "xt_added", "xt_added_per_move"])
    write_csv(output_dir / "xt_team_match.csv", team_rows,
              ["source", "date", "competition", "season", "team", "opponent", "is_home",
               "moves", "xt_for", "xt_against", "xt_net"])

    peak = max(range(len(threat)), key=lambda cell: threat[cell])
    print(f"  OK    Gitter gelernt, Maximum {max(threat):.4f} in Zelle "
          f"col={peak % config.GRID_COLS} row={peak // config.GRID_COLS}")
    print(f"  OK    {len(player_rows)} Spieler-Spiel-Zeilen, {len(team_rows)} Team-Spiel-Zeilen")


if __name__ == "__main__":
    main()
