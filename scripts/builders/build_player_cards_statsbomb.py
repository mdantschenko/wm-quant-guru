"""Erweitert player_cards.csv um alle frei verfuegbaren StatsBomb-Maennerwettbewerbe.

StatsBomb fuehrt Karten im Feld card von Foul Committed und Bad Behaviour.
Je Spieler und Spiel werden gelbe, rote und gelb-rote Karten gezaehlt. Events
werden gestreamt, nicht persistiert. Resumierbar je Wettbewerb.

Start als Modul:
    python -m scripts.builders.build_player_cards_statsbomb
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

from scripts.builders.build_expected_threat import write_csv
from scripts.builders.build_player_cards import FIELDNAMES, OUTPUT_FILE
from scripts.builders.build_player_metrics_statsbomb import (
    StatsBombPlayerConfig, fetch_json, select_targets,
)

CARD_NAMES = {"Yellow Card": "yellow", "Red Card": "red", "Second Yellow": "second_yellow"}


def card_of(event: dict) -> str | None:
    """Gibt den Kartennamen eines Events zurueck, sonst None."""
    name = event.get("type", {}).get("name")
    if name == "Foul Committed":
        return event.get("foul_committed", {}).get("card", {}).get("name")
    if name == "Bad Behaviour":
        return event.get("bad_behaviour", {}).get("card", {}).get("name")
    return None


def process_match(match: dict, competition: str, season: str,
                  config: StatsBombPlayerConfig) -> list[dict[str, object]]:
    events = fetch_json(f"{config.BASE_URL}/events/{match['match_id']}.json", config)
    time.sleep(config.POLITE_DELAY_SECONDS)
    if not isinstance(events, list):
        return []
    counters: dict[str, dict[str, object]] = {}
    for event in events:
        key = CARD_NAMES.get(card_of(event) or "")
        player = event.get("player", {}).get("name")
        if not key or not player:
            continue
        bucket = counters.setdefault(player, {"team": event.get("team", {}).get("name"),
                                              "yellow": 0, "red": 0, "second_yellow": 0})
        bucket[key] += 1
    home = match["home_team"]["home_team_name"]
    away = match["away_team"]["away_team_name"]
    date = str(match.get("match_date", ""))[:10]
    return [{
        "source": "statsbomb", "date": date, "competition": competition, "season": season,
        "team": bucket["team"], "opponent": away if bucket["team"] == home else home,
        "player": player, "yellow": bucket["yellow"], "red": bucket["red"],
        "second_yellow": bucket["second_yellow"],
    } for player, bucket in counters.items()]


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
                                   str(row["date"]), str(row["team"]), str(row["player"])))
        write_csv(output_path, rows, FIELDNAMES)
        print(f"  PERSIST  {competition} {season}: {len(matches)} Spiele (Datei {len(rows)})", flush=True)
    print(f"\nFertig: player_cards.csv enthaelt {len(rows)} Zeilen.")


if __name__ == "__main__":
    main()
