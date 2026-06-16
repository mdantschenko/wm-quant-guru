"""Neuartige Spielerbewertung je Spieler und EINZELSPIEL (Wyscout-Teil).

Misst Rollenbeitraege, die klassische Statistiken nicht erfassen (etwa den
mitspielenden Torwart, das Manuel-Neuer-Problem von 2014). Ausgabe ist
bewusst granular je Spieler und Spiel (jeder Zeitpunkt), sortiert nach
Wettbewerb und Datum, ohne Mindestminuten-Filter, mit Rohzahlen plus
gespielten Minuten, sodass beliebig (Saison, gleitend, Liga) aggregiert
werden kann.

StatsBomb-Wettbewerbe werden ueber build_player_metrics_statsbomb.py
ergaenzt (Spalte source). Koordinaten werden auf den Standard gespiegelt
(Wyscout-SPADL greift Richtung x=0 an). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

PASS_TYPES = {"pass", "cross", "throw_in", "freekick_short", "freekick_crossed",
              "corner_short", "corner_crossed", "goalkick"}
DEF_TYPES = {"tackle", "interception", "clearance", "foul"}
_ROLE = re.compile(r"'code2':\s*'([A-Z]{2})'")


class PlayerMetricsConfig:
    """Pfade, Geometrie und Schwellen."""

    WYSCOUT_DIR: str = "Data/Wyscout Events (Pappalardo 2017-18)"
    OUTPUT_FILE: str = "Data/Custom_Data/player_metrics.csv"
    BOX_X: float = 88.5
    BOX_Y_MIN: float = 13.84
    BOX_Y_MAX: float = 54.16
    PENALTY_AREA_X: float = 16.5
    FINAL_THIRD_X: float = 70.0
    DEEP_X: float = 85.0
    PROGRESS_MIN_M: float = 15.0
    HIGH_RECOVERY_X: float = 60.0
    LONG_PASS_M: float = 30.0
    FIELDNAMES: list[str] = [
        "source", "date", "competition", "season", "team", "opponent", "player", "role",
        "minutes", "passes", "pass_completed", "progressive_passes", "passes_into_box",
        "deep_completions", "progression_value", "def_actions", "def_action_height_m",
        "ball_recoveries_high", "take_ons", "take_ons_won", "shots", "shots_in_box",
        "gk_actions", "gk_actions_outside_box", "gk_action_height_m", "gk_long_passes", "gk_passes",
    ]


def normalize_id(value: str) -> str:
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return value.strip()


def load_simple(path: Path, key: str, value: str) -> dict[str, str]:
    with open(path, encoding="utf-8") as handle:
        return {normalize_id(row[key]): row[value] for row in csv.DictReader(handle)}


def load_games(path: Path) -> dict[str, dict[str, str]]:
    games: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            games[normalize_id(row["game_id"])] = {
                "competition_id": normalize_id(row["competition_id"]), "season": row["season_id"],
                "date": row["game_date"][:10], "home": normalize_id(row["home_team_id"]),
                "away": normalize_id(row["away_team_id"])}
    return games


def load_roles(path: Path) -> dict[str, str]:
    roles: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            match = _ROLE.search(row.get("role", ""))
            roles[normalize_id(row["wyId"])] = match.group(1) if match else ""
    return roles


def load_appearances(path: Path) -> tuple[dict[tuple, dict[str, object]], dict[str, str]]:
    """Je (Spieler, Spiel) die Minuten, das Team und der Name."""
    appearances: dict[tuple, dict[str, object]] = {}
    names: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                minutes = int(float(row["minutes_played"]))
            except (ValueError, KeyError):
                continue
            if minutes <= 0:
                continue
            player, game = normalize_id(row["player_id"]), normalize_id(row["game_id"])
            names[player] = row.get("player_name", player)
            appearances[(player, game)] = {"minutes": minutes, "team_id": normalize_id(row["team_id"])}
    return appearances, names


def new_counters() -> dict[str, float]:
    return {key: 0.0 for key in (
        "passes", "passes_ok", "progressive", "into_box", "deep", "progression_value",
        "def_actions", "def_height_sum", "recoveries_high", "take_on", "take_on_ok",
        "shots", "shots_in_box", "gk_actions", "gk_outside", "gk_height_sum", "gk_passes", "gk_long")}


def accumulate(counters: dict[str, float], kind: str, success: bool, start_x: float,
               end_x: float, end_y: float, start_y: float, is_keeper: bool,
               config: PlayerMetricsConfig) -> None:
    if is_keeper:
        counters["gk_actions"] += 1
        counters["gk_height_sum"] += start_x
        if start_x > config.PENALTY_AREA_X:
            counters["gk_outside"] += 1
    if kind in PASS_TYPES:
        counters["passes"] += 1
        if is_keeper:
            counters["gk_passes"] += 1
            counters["gk_long"] += 1 if end_x - start_x > config.LONG_PASS_M else 0
        if success:
            counters["passes_ok"] += 1
            counters["progression_value"] += max(0.0, end_x - start_x) * (end_x / 105.0) ** 2
            if end_x - start_x >= config.PROGRESS_MIN_M and end_x >= config.FINAL_THIRD_X:
                counters["progressive"] += 1
            if end_x >= config.BOX_X and config.BOX_Y_MIN <= end_y <= config.BOX_Y_MAX:
                counters["into_box"] += 1
            if end_x >= config.DEEP_X:
                counters["deep"] += 1
    if kind in DEF_TYPES:
        counters["def_actions"] += 1
        counters["def_height_sum"] += start_x
        if start_x >= config.HIGH_RECOVERY_X:
            counters["recoveries_high"] += 1
    if kind == "take_on":
        counters["take_on"] += 1
        counters["take_on_ok"] += 1 if success else 0
    if kind in ("shot", "shot_freekick", "shot_penalty"):
        counters["shots"] += 1
        if start_x >= config.BOX_X and config.BOX_Y_MIN <= start_y <= config.BOX_Y_MAX:
            counters["shots_in_box"] += 1


def stream_actions(path: Path, roles: dict[str, str],
                   config: PlayerMetricsConfig) -> dict[tuple, dict[str, float]]:
    counters: dict[tuple, dict[str, float]] = {}
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        column = {name: index for index, name in enumerate(next(reader))}
        for raw in reader:
            try:
                # Wyscout-SPADL greift Richtung x=0 an; auf Standard spiegeln.
                start_x, end_x = 105.0 - float(raw[column["start_x"]]), 105.0 - float(raw[column["end_x"]])
                start_y, end_y = float(raw[column["start_y"]]), float(raw[column["end_y"]])
            except ValueError:
                continue
            player, game = normalize_id(raw[column["player_id"]]), normalize_id(raw[column["game_id"]])
            accumulate(counters.setdefault((player, game), new_counters()),
                       raw[column["type_name"]], raw[column["result_name"]] == "success",
                       start_x, end_x, end_y, start_y, roles.get(player) == "GK", config)
    return counters


def build_rows(appearances, names, counters, games, roles, competitions, teams,
               config: PlayerMetricsConfig) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (player, game), info in appearances.items():
        meta = games.get(game)
        if meta is None:
            continue
        counter = counters.get((player, game), new_counters())
        role = roles.get(player, "")
        is_keeper = role == "GK"
        team_id = info["team_id"]
        opponent_id = meta["away"] if team_id == meta["home"] else meta["home"]
        rows.append({
            "source": "wyscout", "date": meta["date"],
            "competition": competitions.get(meta["competition_id"], meta["competition_id"]),
            "season": meta["season"], "team": teams.get(team_id, team_id),
            "opponent": teams.get(opponent_id, opponent_id),
            "player": names.get(player, player), "role": role, "minutes": info["minutes"],
            "passes": int(counter["passes"]), "pass_completed": int(counter["passes_ok"]),
            "progressive_passes": int(counter["progressive"]), "passes_into_box": int(counter["into_box"]),
            "deep_completions": int(counter["deep"]), "progression_value": round(counter["progression_value"], 2),
            "def_actions": int(counter["def_actions"]),
            "def_action_height_m": round(counter["def_height_sum"] / counter["def_actions"], 1) if counter["def_actions"] else "",
            "ball_recoveries_high": int(counter["recoveries_high"]),
            "take_ons": int(counter["take_on"]), "take_ons_won": int(counter["take_on_ok"]),
            "shots": int(counter["shots"]), "shots_in_box": int(counter["shots_in_box"]),
            "gk_actions": int(counter["gk_actions"]) if is_keeper else "",
            "gk_actions_outside_box": int(counter["gk_outside"]) if is_keeper else "",
            "gk_action_height_m": round(counter["gk_height_sum"] / counter["gk_actions"], 1) if is_keeper and counter["gk_actions"] else "",
            "gk_long_passes": int(counter["gk_long"]) if is_keeper else "",
            "gk_passes": int(counter["gk_passes"]) if is_keeper else "",
        })
    rows.sort(key=lambda row: (str(row["competition"]), str(row["season"]), str(row["date"]),
                               str(row["team"]), str(row["player"])))
    return rows


def main() -> None:
    config = PlayerMetricsConfig()
    source = Path(config.WYSCOUT_DIR)
    games = load_games(source / "games.csv")
    roles = load_roles(source / "players.csv")
    competitions = load_simple(source / "competitions.csv", "wyId", "name")
    teams = load_simple(source / "teams.csv", "wyId", "name")
    appearances, names = load_appearances(source / "player_games.csv")
    counters = stream_actions(source / "actions.csv", roles, config)
    rows = build_rows(appearances, names, counters, games, roles, competitions, teams, config)

    output_path = Path(config.OUTPUT_FILE)
    kept = []
    if output_path.exists():
        with open(output_path, encoding="utf-8", newline="") as handle:
            kept = [row for row in csv.DictReader(handle) if row.get("source") == "statsbomb"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=config.FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows + kept)
    print(f"  OK    {len(rows)} Spieler-Spiel-Zeilen (Wyscout, plus {len(kept)} StatsBomb erhalten)")


if __name__ == "__main__":
    main()
