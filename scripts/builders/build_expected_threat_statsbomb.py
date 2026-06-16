"""Erweitert die xT-Datensaetze um alle frei verfuegbaren StatsBomb-Maennerwettbewerbe.

Wendet das in build_expected_threat.py gelernte Gitter (xt_grid.csv) an, damit
die Werte ueber beide Quellen vergleichbar bleiben. StatsBomb greift Richtung
x=120 an, daher wird nicht gespiegelt, sondern nur auf 105 mal 68 skaliert.
Bewegungen sind vollendete Paesse und Ballmitnahmen (Carry). Events werden
gestreamt, nicht persistiert. Resumierbar je Wettbewerb.

Start als Modul:
    python -m scripts.builders.build_expected_threat_statsbomb
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

from scripts.builders.build_expected_threat import ExpectedThreatConfig, cell_index, write_csv
from scripts.builders.build_player_metrics_statsbomb import (
    StatsBombPlayerConfig, fetch_json, select_targets,
)

PLAYER_FILE = "Data/Custom_Data/xt_player_match.csv"
TEAM_FILE = "Data/Custom_Data/xt_team_match.csv"


def load_grid(path: Path, config: ExpectedThreatConfig) -> list[float]:
    """Liest das gelernte Gitter als lineare Werteliste."""
    threat = [0.0] * (config.GRID_COLS * config.GRID_ROWS)
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            cell = int(row["grid_row"]) * config.GRID_COLS + int(row["grid_col"])
            threat[cell] = float(row["xt"])
    return threat


def move_endpoints(event: dict, scale_x: float, scale_y: float,
                   config: ExpectedThreatConfig) -> tuple[int, int] | None:
    """Gibt Start- und Zielzelle einer vollendeten Bewegung zurueck, sonst None."""
    name = event.get("type", {}).get("name")
    location = event.get("location")
    if not location:
        return None
    if name == "Pass":
        info = event.get("pass", {})
        if "outcome" in info or not info.get("end_location"):
            return None
        end = info["end_location"]
    elif name == "Carry":
        end = event.get("carry", {}).get("end_location")
        if not end:
            return None
    else:
        return None
    start_cell = cell_index(location[0] * scale_x, location[1] * scale_y, config)
    end_cell = cell_index(end[0] * scale_x, end[1] * scale_y, config)
    return start_cell, end_cell


def process_match(match: dict, competition: str, season: str, threat: list[float],
                  sb_config: StatsBombPlayerConfig, config: ExpectedThreatConfig) -> tuple[list, list]:
    events = fetch_json(f"{sb_config.BASE_URL}/events/{match['match_id']}.json", sb_config)
    time.sleep(sb_config.POLITE_DELAY_SECONDS)
    if not isinstance(events, list):
        return [], []
    scale_x, scale_y = config.PITCH_X / sb_config.STATSBOMB_X, config.PITCH_Y / sb_config.STATSBOMB_Y
    players: dict[str, list] = {}
    teams: dict[str, list] = {}
    for event in events:
        cells = move_endpoints(event, scale_x, scale_y, config)
        if cells is None:
            continue
        delta = threat[cells[1]] - threat[cells[0]]
        team = event.get("team", {}).get("name")
        player = event.get("player", {}).get("name")
        if player:
            entry = players.setdefault(player, [0.0, 0, team])
            entry[0] += delta
            entry[1] += 1
        if team:
            team_entry = teams.setdefault(team, [0.0, 0])
            team_entry[0] += delta
            team_entry[1] += 1
    return _rows(match, competition, season, players, teams)


def _rows(match: dict, competition: str, season: str,
          players: dict, teams: dict) -> tuple[list, list]:
    home = match["home_team"]["home_team_name"]
    away = match["away_team"]["away_team_name"]
    date = str(match.get("match_date", ""))[:10]
    player_rows = [{
        "source": "statsbomb", "date": date, "competition": competition, "season": season,
        "team": team, "opponent": away if team == home else home, "player": player,
        "moves": moves, "xt_added": round(xt_sum, 4),
        "xt_added_per_move": round(xt_sum / moves, 5) if moves else "",
    } for player, (xt_sum, moves, team) in players.items()]
    team_rows = [{
        "source": "statsbomb", "date": date, "competition": competition, "season": season,
        "team": team, "opponent": away if team == home else home,
        "is_home": int(team == home), "moves": moves, "xt_for": round(xt_sum, 4),
        "xt_against": round(teams.get(away if team == home else home, [0.0])[0], 4),
        "xt_net": round(xt_sum - teams.get(away if team == home else home, [0.0])[0], 4),
    } for team, (xt_sum, moves) in teams.items()]
    return player_rows, team_rows


def read_existing(path: Path) -> tuple[list[dict], set]:
    rows: list[dict] = []
    if path.exists():
        with open(path, encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    done = {(r["competition"], r["season"]) for r in rows if r.get("source") == "statsbomb"}
    return rows, done


def persist(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    rows.sort(key=lambda row: (str(row["competition"]), str(row["season"]),
                               str(row["date"]), str(row["team"]), str(row.get("player", ""))))
    write_csv(path, rows, fieldnames)


def main() -> None:
    config = ExpectedThreatConfig()
    sb_config = StatsBombPlayerConfig()
    threat = load_grid(Path(config.OUTPUT_DIR) / "xt_grid.csv", config)
    player_rows, done = read_existing(Path(PLAYER_FILE))
    team_rows, _ = read_existing(Path(TEAM_FILE))
    player_fields = ["source", "date", "competition", "season", "team", "opponent",
                     "player", "moves", "xt_added", "xt_added_per_move"]
    team_fields = ["source", "date", "competition", "season", "team", "opponent",
                   "is_home", "moves", "xt_for", "xt_against", "xt_net"]

    competitions = fetch_json(f"{sb_config.BASE_URL}/competitions.json", sb_config)
    if not isinstance(competitions, list):
        raise SystemExit("competitions.json nicht ladbar")
    pending = [t for t in select_targets(competitions, sb_config) if (t[2], t[3]) not in done]
    print(f"Offene Wettbewerbe {len(pending)}", flush=True)
    for competition_id, season_id, competition, season in pending:
        matches = fetch_json(f"{sb_config.BASE_URL}/matches/{competition_id}/{season_id}.json", sb_config)
        if not isinstance(matches, list):
            continue
        for match in sorted(matches, key=lambda m: str(m.get("match_date"))):
            new_players, new_teams = process_match(match, competition, season, threat, sb_config, config)
            player_rows.extend(new_players)
            team_rows.extend(new_teams)
        persist(Path(PLAYER_FILE), player_rows, player_fields)
        persist(Path(TEAM_FILE), team_rows, team_fields)
        print(f"  PERSIST  {competition} {season}: {len(matches)} Spiele", flush=True)
    print(f"\nFertig: {len(player_rows)} Spieler-Spiel- und {len(team_rows)} Team-Spiel-Zeilen.")


if __name__ == "__main__":
    main()
