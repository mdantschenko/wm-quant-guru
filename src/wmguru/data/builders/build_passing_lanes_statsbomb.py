"""Granulare Passlinien aus StatsBomb Open Data (alle Maennerwettbewerbe).

Erweitert passing_lanes.csv um die vollen Netzwerkkanten aus StatsBomb. Der
Empfaenger kommt direkt aus pass.recipient (keine Heuristik noetig). Alle
abgeschlossenen Paesse zaehlen (offenes Spiel und Standards), damit das
Netzwerk vollstaendig ist. Events werden gestreamt, nicht persistiert.
Resumierbar: nach jedem Wettbewerb wird geschrieben und Vorhandenes
uebersprungen.

Start als Modul:
    python -m scripts.builders.build_passing_lanes_statsbomb
Reine Standardbibliothek.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from src.scripts.builders.build_passing_lanes import LanesConfig, load_existing, write_all


class StatsBombLanesConfig:
    BASE_URL: str = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    USER_AGENT: str = "wm-quant-guru (research)"
    TIMEOUT_SECONDS: int = 60
    POLITE_DELAY_SECONDS: float = 0.2
    GENDER: str = "male"
    STATSBOMB_X: float = 120.0
    STATSBOMB_Y: float = 80.0
    PITCH_X: float = 105.0
    FORWARD_THRESHOLD_M: float = 5.0


def fetch_json(url: str, config: StatsBombLanesConfig) -> object | None:
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def select_targets(competitions: list[dict], config: StatsBombLanesConfig) -> list[tuple]:
    return [(entry["competition_id"], entry["season_id"],
             entry.get("competition_name", ""), str(entry.get("season_name", "")))
            for entry in competitions if entry.get("competition_gender") == config.GENDER]


def match_edges(events: list[dict], config: StatsBombLanesConfig) -> dict[tuple, list]:
    """Aggregiert Kanten (team, passer, receiver) aus abgeschlossenen Paessen."""
    scale = config.PITCH_X / config.STATSBOMB_X
    edges: dict[tuple, list] = {}
    for event in events:
        if event.get("type", {}).get("name") != "Pass":
            continue
        info = event.get("pass", {})
        if "outcome" in info:
            continue
        recipient = info.get("recipient", {}).get("name")
        passer = event.get("player", {}).get("name")
        team = event.get("team", {}).get("name")
        location = event.get("location")
        end = info.get("end_location")
        if not (recipient and passer and team and location and end) or recipient == passer:
            continue
        key = (team, passer, recipient)
        record = edges.setdefault(key, [0, 0, 0.0, 0.0])
        start_x, end_x = location[0] * scale, end[0] * scale
        record[0] += 1
        record[1] += 1 if (end_x - start_x) > config.FORWARD_THRESHOLD_M else 0
        record[2] += start_x
        record[3] += end_x
    return edges


def process_target(competition_id: int, season_id: int, competition: str, season: str,
                   config: StatsBombLanesConfig) -> list[dict[str, object]]:
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
        date = str(match.get("match_date", ""))[:10]
        for (team, passer, receiver), record in match_edges(events, config).items():
            rows.append({
                "source": "statsbomb", "game_id": match["match_id"], "competition": competition,
                "season": season, "date": date, "team": team, "passer": passer,
                "receiver": receiver, "passes": record[0], "forward_passes": record[1],
                "mean_start_x": round(record[2] / record[0], 1), "mean_end_x": round(record[3] / record[0], 1),
            })
        if index % 25 == 0:
            print(f"    ... {competition} {season}: {index}/{len(matches)} Spiele", flush=True)
    print(f"  OK    {competition} {season}: {len(matches)} Spiele", flush=True)
    return rows


def main() -> None:
    config = StatsBombLanesConfig()
    lanes_config = LanesConfig()
    competitions = fetch_json(f"{config.BASE_URL}/competitions.json", config)
    if not isinstance(competitions, list):
        raise SystemExit("competitions.json nicht ladbar")
    targets = select_targets(competitions, config)
    rows = load_existing(Path(lanes_config.OUTPUT_FILE))
    done = {(str(r.get("competition")), str(r.get("season"))) for r in rows if r.get("source") == "statsbomb"}
    pending = [target for target in targets if (target[2], target[3]) not in done]
    print(f"Maenner-Wettbewerbe gesamt {len(targets)}, bereits vorhanden {len(done)}, "
          f"offen {len(pending)}", flush=True)
    for competition_id, season_id, competition, season in pending:
        new_rows = process_target(competition_id, season_id, competition, season, config)
        if not new_rows:
            continue
        rows.extend(new_rows)
        write_all(rows, lanes_config)
        print(f"  PERSIST  {competition} {season}: +{len(new_rows)} (Datei jetzt {len(rows)})", flush=True)
    print(f"\nFertig: passing_lanes.csv enthaelt {len(rows)} Zeilen.")


if __name__ == "__main__":
    main()
