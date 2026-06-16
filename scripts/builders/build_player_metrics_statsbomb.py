"""Erweitert player_metrics.csv um alle frei verfuegbaren StatsBomb-Maennerwettbewerbe.

Je Spieler und Einzelspiel, mit aus den Events abgeleiteten Minuten und Rolle
(Starting XI plus Substitution-Events). Nutzt das Rechenmodul aus
build_player_metrics.py (gleiche Kennzahlen, gleiches Schema) und liefert
zusaetzlich xG-naehe Aktionen ueber dieselben Zaehler. Events werden
gestreamt, nicht persistiert. Resumierbar je Wettbewerb.

Start als Modul:
    python -m scripts.builders.build_player_metrics_statsbomb
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from scripts.builders.build_player_metrics import (
    PlayerMetricsConfig, accumulate, new_counters,
)


class StatsBombPlayerConfig:
    BASE_URL: str = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    USER_AGENT: str = "wm-quant-guru (research)"
    TIMEOUT_SECONDS: int = 60
    POLITE_DELAY_SECONDS: float = 0.2
    GENDER: str = "male"
    STATSBOMB_X: float = 120.0
    STATSBOMB_Y: float = 80.0
    PITCH_X: float = 105.0
    PITCH_Y: float = 68.0
    SET_PIECE_PASS: frozenset[str] = frozenset(
        {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"})


def fetch_json(url: str, config: StatsBombPlayerConfig) -> object | None:
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def select_targets(competitions: list[dict], config: StatsBombPlayerConfig) -> list[tuple]:
    return [(entry["competition_id"], entry["season_id"],
             entry.get("competition_name", ""), str(entry.get("season_name", "")))
            for entry in competitions if entry.get("competition_gender") == config.GENDER]


def position_role(name: str) -> str:
    if "Goalkeeper" in name:
        return "GK"
    if "Back" in name:
        return "DF"
    if "Midfield" in name:
        return "MF"
    if "Forward" in name or "Wing" in name or "Striker" in name:
        return "FW"
    return ""


def lineup_info(events: list[dict]) -> tuple[dict, dict, dict, dict]:
    """Leitet Minuten, Rolle, Team und Name je Spieler aus Aufstellung und Wechseln ab."""
    minutes: dict[int, int] = {}
    roles: dict[int, str] = {}
    teams: dict[int, str] = {}
    names: dict[int, str] = {}
    match_end = max((event.get("minute", 0) for event in events), default=90)
    for event in events:
        if event.get("type", {}).get("name") != "Starting XI":
            continue
        team = event.get("team", {}).get("name")
        for entry in event.get("tactics", {}).get("lineup", []):
            player = entry.get("player", {})
            pid = player.get("id")
            if pid is None:
                continue
            names[pid] = player.get("name")
            teams[pid] = team
            roles[pid] = position_role(entry.get("position", {}).get("name", ""))
            minutes[pid] = match_end
    for event in events:
        if event.get("type", {}).get("name") != "Substitution":
            continue
        minute = event.get("minute", 0)
        off = event.get("player", {}).get("id")
        if off in minutes:
            minutes[off] = minute
        replacement = event.get("substitution", {}).get("replacement", {})
        rid = replacement.get("id")
        if rid is not None:
            names[rid] = replacement.get("name")
            teams[rid] = event.get("team", {}).get("name")
            roles.setdefault(rid, "")
            minutes[rid] = max(0, match_end - minute)
    return minutes, roles, teams, names


def map_kind(event: dict) -> tuple[Optional[str], bool, Optional[list], frozenset]:
    """Bildet einen StatsBomb-Typ auf das SPADL-aehnliche kind fuer accumulate ab."""
    name = event.get("type", {}).get("name")
    if name == "Pass":
        info = event.get("pass", {})
        success = "outcome" not in info
        if info.get("type", {}).get("name") in map_kind.set_pieces:
            return "throw_in", success, info.get("end_location"), map_kind.set_pieces
        return ("cross" if info.get("cross") else "pass"), success, info.get("end_location"), map_kind.set_pieces
    if name == "Shot":
        penalty = event.get("shot", {}).get("type", {}).get("name") == "Penalty"
        return ("shot_penalty" if penalty else "shot"), False, None, map_kind.set_pieces
    if name == "Dribble":
        return "take_on", event.get("dribble", {}).get("outcome", {}).get("name") == "Complete", None, map_kind.set_pieces
    simple = {"Interception": "interception", "Clearance": "clearance", "Foul Committed": "foul"}
    if name in simple:
        return simple[name], True, None, map_kind.set_pieces
    if name == "Duel" and event.get("duel", {}).get("type", {}).get("name") == "Tackle":
        return "tackle", True, None, map_kind.set_pieces
    return None, False, None, map_kind.set_pieces


map_kind.set_pieces = StatsBombPlayerConfig.SET_PIECE_PASS


def process_match(match: dict, competition: str, season: str,
                  config: StatsBombPlayerConfig, pcfg: PlayerMetricsConfig) -> list[dict[str, object]]:
    events = fetch_json(f"{config.BASE_URL}/events/{match['match_id']}.json", config)
    time.sleep(config.POLITE_DELAY_SECONDS)
    if not isinstance(events, list):
        return []
    minutes, roles, teams, names = lineup_info(events)
    counters: dict[int, dict[str, float]] = {}
    scale_x, scale_y = config.PITCH_X / config.STATSBOMB_X, config.PITCH_Y / config.STATSBOMB_Y
    for event in events:
        kind, success, end, _ = map_kind(event)
        location = event.get("location")
        pid = event.get("player", {}).get("id")
        if kind is None or not location or pid is None:
            continue
        start_x, start_y = location[0] * scale_x, location[1] * scale_y
        end_x, end_y = (end[0] * scale_x, end[1] * scale_y) if end else (start_x, start_y)
        accumulate(counters.setdefault(pid, new_counters()), kind, success,
                   start_x, end_x, end_y, start_y, roles.get(pid) == "GK", pcfg)

    home = match["home_team"]["home_team_name"]
    away = match["away_team"]["away_team_name"]
    date = str(match.get("match_date", ""))[:10]
    rows: list[dict[str, object]] = []
    for pid, played in minutes.items():
        if played <= 0:
            continue
        rows.append(_row(pid, played, counters.get(pid, new_counters()), roles.get(pid, ""),
                         teams.get(pid), names.get(pid, str(pid)), home, away, date,
                         competition, season, match["match_id"]))
    return rows


def _row(pid, minutes, counter, role, team, name, home, away, date, competition, season, game_id) -> dict[str, object]:
    is_keeper = role == "GK"
    opponent = away if team == home else home
    return {
        "source": "statsbomb", "date": date, "competition": competition, "season": season,
        "team": team, "opponent": opponent, "player": name, "role": role, "minutes": minutes,
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
    }


def process_target(competition_id, season_id, competition, season, config, pcfg) -> list[dict[str, object]]:
    matches = fetch_json(f"{config.BASE_URL}/matches/{competition_id}/{season_id}.json", config)
    if not isinstance(matches, list):
        print(f"  FAIL  {competition} {season}", flush=True)
        return []
    rows: list[dict[str, object]] = []
    for index, match in enumerate(sorted(matches, key=lambda m: str(m.get("match_date"))), start=1):
        rows.extend(process_match(match, competition, season, config, pcfg))
        if index % 25 == 0:
            print(f"    ... {competition} {season}: {index}/{len(matches)}", flush=True)
    print(f"  OK    {competition} {season}: {len(matches)} Spiele", flush=True)
    return rows


def main() -> None:
    config = StatsBombPlayerConfig()
    pcfg = PlayerMetricsConfig()
    output_path = Path(pcfg.OUTPUT_FILE)
    competitions = fetch_json(f"{config.BASE_URL}/competitions.json", config)
    if not isinstance(competitions, list):
        raise SystemExit("competitions.json nicht ladbar")
    targets = select_targets(competitions, config)
    rows: list[dict[str, object]] = []
    if output_path.exists():
        with open(output_path, encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    done = {(str(r.get("competition")), str(r.get("season"))) for r in rows if r.get("source") == "statsbomb"}
    pending = [t for t in targets if (t[2], t[3]) not in done]
    print(f"Maennerwettbewerbe {len(targets)}, vorhanden {len(done)}, offen {len(pending)}", flush=True)
    for competition_id, season_id, competition, season in pending:
        new_rows = process_target(competition_id, season_id, competition, season, config, pcfg)
        if not new_rows:
            continue
        rows.extend(new_rows)
        rows.sort(key=lambda row: (str(row["competition"]), str(row["season"]), str(row["date"]),
                                   str(row["team"]), str(row["player"])))
        with open(output_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=pcfg.FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  PERSIST  {competition} {season}: +{len(new_rows)} (Datei {len(rows)})", flush=True)
    print(f"\nFertig: player_metrics.csv enthaelt {len(rows)} Zeilen.")


if __name__ == "__main__":
    main()
