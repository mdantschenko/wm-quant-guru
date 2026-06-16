"""Erweitert match_style.csv um alle frei verfuegbaren StatsBomb-Maennerwettbewerbe.

Nutzt das Rechenmodul aus build_match_style.py (gleiches Schema, gleiche
Metriken) und liefert zusaetzlich die xG-basierten Spalten, die Wyscout nicht
hat (xg, np_xg, xg_per_shot, set_piece_xg_share). Events werden gestreamt und
nicht persistiert. Resumierbar: nach jedem Wettbewerb wird geschrieben und
bereits Vorhandenes uebersprungen, sodass ein Abbruch unkritisch ist.

Start als Modul, damit der Import aufloest:
    python -m scripts.builders.build_match_style_statsbomb
Reine Standardbibliothek.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator, Optional

from scripts.builders.build_match_style import (
    Action, MatchStyleConfig, fill_xga, load_existing, match_rows, write_all,
)


class StatsBombStyleConfig:
    """Quelle und Umrechnungen."""

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
    SET_PIECE_SHOT: frozenset[str] = frozenset(
        {"From Corner", "From Free Kick", "From Throw In"})


def fetch_json(url: str, config: StatsBombStyleConfig) -> object | None:
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def select_targets(competitions: list[dict], config: StatsBombStyleConfig) -> list[tuple]:
    return [(entry["competition_id"], entry["season_id"],
             entry.get("competition_name", ""), str(entry.get("season_name", "")))
            for entry in competitions if entry.get("competition_gender") == config.GENDER]


def _to_meters(point: list, config: StatsBombStyleConfig) -> tuple[float, float]:
    return point[0] / config.STATSBOMB_X * config.PITCH_X, point[1] / config.STATSBOMB_Y * config.PITCH_Y


def normalize_event(event: dict, config: StatsBombStyleConfig) -> Optional[Action]:
    """Bildet ein StatsBomb-Event auf die gemeinsame normalisierte Aktion ab."""
    type_name = event.get("type", {}).get("name")
    team = event.get("team", {}).get("name")
    if not team:
        return None
    period = int(event.get("period") or 1)
    seconds = (event.get("minute") or 0) * 60 + (event.get("second") or 0)
    location = event.get("location")

    if type_name == "Own Goal For":
        return (team, "other", False, 0.0, 0.0, 0.0, 0.0, "self", None, False, period, seconds)
    if not location:
        return None
    start_x, start_y = _to_meters(location, config)

    if type_name == "Pass":
        info = event.get("pass", {})
        end = info.get("end_location")
        if not end:
            return None
        end_x, end_y = _to_meters(end, config)
        if info.get("type", {}).get("name") in config.SET_PIECE_PASS:
            kind = "sp_pass"
        elif info.get("cross"):
            kind = "cross"
        else:
            kind = "open_pass"
        return (team, kind, "outcome" not in info, start_x, start_y, end_x, end_y,
                None, None, False, period, seconds)
    if type_name == "Shot":
        info = event.get("shot", {})
        xg = info.get("statsbomb_xg")
        kind = "pen_shot" if info.get("type", {}).get("name") == "Penalty" else "shot"
        set_piece_shot = event.get("play_pattern", {}).get("name") in config.SET_PIECE_SHOT
        goal_for = "self" if info.get("outcome", {}).get("name") == "Goal" else None
        return (team, kind, goal_for == "self", start_x, start_y, start_x, start_y,
                goal_for, float(xg) if xg is not None else None, set_piece_shot, period, seconds)
    simple = {"Dribble": "take_on", "Interception": "interception",
              "Foul Committed": "foul", "Clearance": "clearance"}
    if type_name == "Duel" and event.get("duel", {}).get("type", {}).get("name") == "Tackle":
        return (team, "tackle", True, start_x, start_y, start_x, start_y, None, None, False, period, seconds)
    if type_name in simple:
        success = type_name != "Dribble" or event.get("dribble", {}).get("outcome", {}).get("name") == "Complete"
        return (team, simple[type_name], success, start_x, start_y, start_x, start_y,
                None, None, False, period, seconds)
    return None


def process_target(competition_id: int, season_id: int, competition: str, season: str,
                   config: StatsBombStyleConfig, style_config: MatchStyleConfig) -> list[dict[str, object]]:
    matches = fetch_json(f"{config.BASE_URL}/matches/{competition_id}/{season_id}.json", config)
    if not isinstance(matches, list):
        print(f"  FAIL  {competition} {season}: Spielliste nicht ladbar", flush=True)
        return []
    rows: list[dict[str, object]] = []
    for index, match in enumerate(sorted(matches, key=lambda m: str(m.get("match_date"))), start=1):
        events = fetch_json(f"{config.BASE_URL}/events/{match['match_id']}.json", config)
        time.sleep(config.POLITE_DELAY_SECONDS)
        if not isinstance(events, list):
            continue
        actions = [action for action in (normalize_event(event, config) for event in events) if action]
        meta = {"game_id": match["match_id"], "competition": competition, "season": season,
                "date": str(match.get("match_date", ""))[:10]}
        rows.extend(match_rows(actions, meta, match["home_team"]["home_team_name"],
                               match["away_team"]["away_team_name"], "statsbomb", True, style_config))
        if index % 25 == 0:
            print(f"    ... {competition} {season}: {index}/{len(matches)} Spiele", flush=True)
    print(f"  OK    {competition} {season}: {len(matches)} Spiele", flush=True)
    return rows


def main() -> None:
    config = StatsBombStyleConfig()
    style_config = MatchStyleConfig()
    competitions = fetch_json(f"{config.BASE_URL}/competitions.json", config)
    if not isinstance(competitions, list):
        raise SystemExit("competitions.json nicht ladbar")
    targets = select_targets(competitions, config)
    rows = load_existing(Path(style_config.OUTPUT_FILE))
    done = {(str(r.get("competition")), str(r.get("season"))) for r in rows if r.get("source") == "statsbomb"}
    pending = [target for target in targets if (target[2], target[3]) not in done]
    print(f"Maenner-Wettbewerbe gesamt {len(targets)}, bereits vorhanden {len(done)}, "
          f"offen {len(pending)}", flush=True)
    for competition_id, season_id, competition, season in pending:
        new_rows = process_target(competition_id, season_id, competition, season, config, style_config)
        if not new_rows:
            continue
        rows.extend(new_rows)
        write_all(fill_xga(rows), style_config)
        print(f"  PERSIST  {competition} {season}: +{len(new_rows)} (Datei jetzt {len(rows)})", flush=True)
    print(f"\nFertig: match_style.csv enthaelt {len(rows)} Zeilen.")


if __name__ == "__main__":
    main()
