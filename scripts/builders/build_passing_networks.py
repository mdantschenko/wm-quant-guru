"""Passnetzwerk-Kennzahlen je Team und Spiel aus den Wyscout-Events.

Aus dem vereinheitlichten SPADL-Aktionsstrom (actions.csv) wird fuer jedes
Team in jedem Spiel das Passnetzwerk rekonstruiert. Der Empfaenger eines
erfolgreichen Passes wird ueber die unmittelbar folgende Aktion desselben
Teams erschlossen (Standardheuristik fuer Passnetzwerke aus Eventdaten).

Pro Team und Spiel entstehen unter anderem:
  - Passzahl und Erfolgsquote,
  - Anteil Vorwaertspaesse (Vertikalitaet) und mittlere Passlaenge in Metern,
  - Netzwerk-Zentralisierung (HHI der Passverteilung ueber die Spieler) und
    der Anteil des passstaerksten Spielers,
  - genutzte Passlinien, Anteil ungenutzter Linien und die staerkste Linie.

Abdeckung ist der komplette Pappalardo-Korpus 2017/18 (England, Frankreich,
Deutschland, Italien, Spanien, EM 2016, WM 2018). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from math import hypot
from pathlib import Path


class PassingConfig:
    """Pfade und Schwellen."""

    SOURCE_DIR: str = "Data/Wyscout Events (Pappalardo 2017-18)"
    OUTPUT_FILE: str = "Data/Custom_Data/passing_networks.csv"
    FORWARD_THRESHOLD_M: float = 5.0  # Vorwaertspass ab diesem Laengsgewinn


def normalize_id(value: str) -> str:
    """Vereinheitlicht IDs (auch 1659.0 zu 1659)."""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return value.strip()


def decode_escapes(text: str) -> str:
    """Wandelt literale \\uXXXX-Escapes der Quelle in echte Zeichen um."""
    if "\\u" not in text:
        return text
    try:
        return text.encode("latin-1", "backslashreplace").decode("unicode_escape")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def load_lookup(path: Path, key_column: str, value_column: str) -> dict[str, str]:
    """Liest ein einfaches ID-zu-Name-Mapping."""
    mapping: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            mapping[normalize_id(row[key_column])] = decode_escapes(row[value_column])
    return mapping


def load_games(path: Path) -> dict[str, dict[str, str]]:
    """Liest die Spiel-Metadaten (Wettbewerb, Saison, Datum, Teams)."""
    games: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            games[normalize_id(row["game_id"])] = {
                "competition_id": normalize_id(row["competition_id"]),
                "season_id": row["season_id"],
                "date": row["game_date"][:10],
                "home": normalize_id(row["home_team_id"]),
                "away": normalize_id(row["away_team_id"]),
            }
    return games


def new_team_stat() -> dict[str, object]:
    return {
        "passes": 0, "success": 0, "forward": 0,
        "length_sum": 0.0, "forward_gain_sum": 0.0,
        "passer": {}, "lane": {},
    }


def accumulate_action(
    stat: dict[str, object], player: str, start_x: float, end_x: float,
    start_y: float, end_y: float, success: bool, config: PassingConfig,
) -> None:
    stat["passes"] += 1
    delta_x = end_x - start_x
    stat["forward_gain_sum"] += delta_x
    stat["length_sum"] += hypot(delta_x, end_y - start_y)
    if delta_x > config.FORWARD_THRESHOLD_M:
        stat["forward"] += 1
    if success:
        stat["success"] += 1
    stat["passer"][player] = stat["passer"].get(player, 0) + 1


def process_game(
    game_id: str, actions: list[tuple], games: dict[str, dict[str, str]],
    teams: dict[str, str], players: dict[str, str], competitions: dict[str, str],
    config: PassingConfig,
) -> list[dict[str, object]]:
    """Berechnet die Kennzahlen beider Teams eines Spiels."""
    meta = games.get(game_id)
    if meta is None:
        return []
    stats: dict[str, dict[str, object]] = {}
    count = len(actions)
    for index, action in enumerate(actions):
        team, player, start_x, start_y, end_x, end_y, action_type, result = action
        if action_type != "pass":
            continue
        stat = stats.setdefault(team, new_team_stat())
        success = result == "success"
        accumulate_action(stat, player, start_x, end_x, start_y, end_y, success, config)
        if success and index + 1 < count and actions[index + 1][0] == team:
            receiver = actions[index + 1][1]
            if receiver and receiver != player:
                lane = stat["lane"]
                lane[(player, receiver)] = lane.get((player, receiver), 0) + 1

    rows: list[dict[str, object]] = []
    for team, stat in stats.items():
        rows.append(build_row(game_id, team, stat, meta, teams, players, competitions))
    return rows


def build_row(
    game_id: str, team: str, stat: dict[str, object], meta: dict[str, str],
    teams: dict[str, str], players: dict[str, str], competitions: dict[str, str],
) -> dict[str, object]:
    """Formt die aggregierten Statistiken in eine Ausgabezeile."""
    passes = stat["passes"]
    passer_counts = stat["passer"]
    players_involved = len(passer_counts)
    total = sum(passer_counts.values())
    centralization = sum((value / total) ** 2 for value in passer_counts.values())
    top_player_share = max(passer_counts.values()) / total
    distinct_lanes = len(stat["lane"])
    possible_lanes = players_involved * (players_involved - 1)
    unused_share = max(0.0, 1.0 - distinct_lanes / possible_lanes) if possible_lanes else ""
    top_pair, top_count = ("", ""), 0
    if stat["lane"]:
        top_pair, top_count = max(stat["lane"].items(), key=lambda item: item[1])
    opponent = meta["away"] if team == meta["home"] else meta["home"]
    return {
        "game_id": game_id,
        "source": "wyscout",
        "competition": competitions.get(meta["competition_id"], meta["competition_id"]),
        "season_id": meta["season_id"],
        "date": meta["date"],
        "team": teams.get(team, team),
        "opponent": teams.get(opponent, opponent),
        "is_home": int(team == meta["home"]),
        "passes": passes,
        "pass_success_rate": round(stat["success"] / passes, 4),
        "forward_pass_share": round(stat["forward"] / passes, 4),
        "mean_pass_length_m": round(stat["length_sum"] / passes, 2),
        "mean_forward_gain_m": round(stat["forward_gain_sum"] / passes, 2),
        "players_involved": players_involved,
        "distinct_lanes": distinct_lanes,
        "unused_lane_share": round(unused_share, 4) if unused_share != "" else "",
        "centralization_hhi": round(centralization, 4),
        "top_player_share": round(top_player_share, 4),
        "top_lane": f"{players.get(top_pair[0], top_pair[0])} -> {players.get(top_pair[1], top_pair[1])}" if top_count else "",
        "top_lane_count": top_count,
    }


def stream_games(actions_path: Path, config: PassingConfig, context: dict) -> list[dict[str, object]]:
    """Streamt actions.csv, gruppiert nach Spiel und verarbeitet je Spiel."""
    rows: list[dict[str, object]] = []
    with open(actions_path, encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        column = {name: position for position, name in enumerate(header)}
        current_game: str | None = None
        buffer: list[tuple] = []
        for raw in reader:
            game_id = normalize_id(raw[column["game_id"]])
            if game_id != current_game:
                if buffer:
                    rows.extend(process_game(current_game, buffer, **context, config=config))
                current_game = game_id
                buffer = []
            buffer.append((
                normalize_id(raw[column["team_id"]]),
                normalize_id(raw[column["player_id"]]),
                float(raw[column["start_x"]]), float(raw[column["start_y"]]),
                float(raw[column["end_x"]]), float(raw[column["end_y"]]),
                raw[column["type_name"]], raw[column["result_name"]],
            ))
        if buffer:
            rows.extend(process_game(current_game, buffer, **context, config=config))
    return rows


def main() -> None:
    config = PassingConfig()
    source = Path(config.SOURCE_DIR)
    context = {
        "games": load_games(source / "games.csv"),
        "teams": load_lookup(source / "teams.csv", "wyId", "name"),
        "players": load_lookup(source / "players.csv", "wyId", "shortName"),
        "competitions": load_lookup(source / "competitions.csv", "wyId", "name"),
    }
    rows = stream_games(source / "actions.csv", config, context)
    rows.sort(key=lambda row: (row["competition"], row["date"], row["game_id"], -row["is_home"]))

    output_path = Path(config.OUTPUT_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "game_id", "source", "competition", "season_id", "date", "team", "opponent", "is_home",
        "passes", "pass_success_rate", "forward_pass_share", "mean_pass_length_m",
        "mean_forward_gain_m", "players_involved", "distinct_lanes", "unused_lane_share",
        "centralization_hhi", "top_player_share", "top_lane", "top_lane_count",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    competitions_seen = sorted({row["competition"] for row in rows})
    print(f"  OK    {len(rows)} Team-Spiel-Zeilen ueber {len(competitions_seen)} Wettbewerbe")
    print(f"  INFO  Wettbewerbe: {', '.join(competitions_seen)}")


if __name__ == "__main__":
    main()
