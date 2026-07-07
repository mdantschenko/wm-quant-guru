"""Erweitert substitutions.csv um alle frei verfuegbaren StatsBomb-Maennerwettbewerbe.

StatsBomb fuehrt Auswechslungen als Substitution-Events mit dem ausgewechselten
Spieler, dem eingewechselten Ersatz und der Minute. Events werden gestreamt,
nicht persistiert. Resumierbar je Wettbewerb.

Start als Modul:
    python -m scripts.builders.build_substitutions_statsbomb
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

from src.scripts.builders.build_expected_threat import write_csv
from src.scripts.builders.build_substitutions import FIELDNAMES, OUTPUT_FILE
from src.scripts.builders.build_player_metrics_statsbomb import (
    StatsBombPlayerConfig, fetch_json, select_targets,
)


def process_match(match: dict, competition: str, season: str,
                  config: StatsBombPlayerConfig) -> list[dict[str, object]]:
    events = fetch_json(f"{config.BASE_URL}/events/{match['match_id']}.json", config)
    time.sleep(config.POLITE_DELAY_SECONDS)
    if not isinstance(events, list):
        return []
    home = match["home_team"]["home_team_name"]
    away = match["away_team"]["away_team_name"]
    date = str(match.get("match_date", ""))[:10]
    rows: list[dict[str, object]] = []
    for event in events:
        if event.get("type", {}).get("name") != "Substitution":
            continue
        team = event.get("team", {}).get("name")
        rows.append({
            "source": "statsbomb", "date": date, "competition": competition, "season": season,
            "game_id": match["match_id"], "team": team,
            "opponent": away if team == home else home,
            "player_out": event.get("player", {}).get("name"),
            "player_in": event.get("substitution", {}).get("replacement", {}).get("name"),
            "minute": event.get("minute", ""),
        })
    return rows


def main() -> None:
    config = StatsBombPlayerConfig()
    output_path = Path(OUTPUT_FILE)
    rows: list[dict[str, object]] = []
    if output_path.exists():
        with open(output_path, encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    done = {(str(r["competition"]), str(r["season"])) for r in rows if r.get("source") == "statsbomb"}
    competitions = fetch_json(f"{config.BASE_URL}/competitions.json", config)
    if not isinstance(competitions, list):
        raise SystemExit("competitions.json nicht ladbar")
    pending = [t for t in select_targets(competitions, config) if (t[2], t[3]) not in done]
    print(f"Offene Wettbewerbe {len(pending)}", flush=True)
    for competition_id, season_id, competition, season in pending:
        matches = fetch_json(f"{config.BASE_URL}/matches/{competition_id}/{season_id}.json", config)
        if not isinstance(matches, list):
            continue
        for match in sorted(matches, key=lambda m: str(m.get("match_date"))):
            rows.extend(process_match(match, competition, season, config))
        rows.sort(key=lambda row: (str(row["competition"]), str(row["season"]),
                                   str(row["date"]), str(row["game_id"]),
                                   int(row["minute"]) if str(row["minute"]).isdigit() else 0))
        write_csv(output_path, rows, FIELDNAMES)
        print(f"  PERSIST  {competition} {season}: {len(matches)} Spiele (Datei {len(rows)})", flush=True)
    print(f"\nFertig: substitutions.csv enthaelt {len(rows)} Zeilen.")


if __name__ == "__main__":
    main()
