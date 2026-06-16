"""Pressresistenz je Spieler und Spiel aus den StatsBomb-Events.

Pressresistenz misst, wie gut ein Spieler den Ball unter gegnerischem Druck
behaelt und weiterspielt. StatsBomb markiert Aktionen mit dem Flag
under_pressure, daher ist diese Kennzahl sauber ableitbar. Wyscout kennt kein
Druck-Flag, eine raeumliche Naeherung waere stark verrauscht, daher bleibt
dieser Datensatz bewusst auf StatsBomb beschraenkt.

Je Spieler und Spiel werden Paesse, Ballmitnahmen und Dribblings sowie deren
Erfolg getrennt nach mit und ohne Druck gezaehlt, dazu Ballverluste
(Dispossessed) und Fehlannahmen (Miscontrol). Die abgeleitete Quote
pressured_pass_completion ist die Passquote unter Druck. Events werden
gestreamt, nicht persistiert. Resumierbar je Wettbewerb.

Start als Modul:
    python -m scripts.builders.build_press_resistance_statsbomb
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

from scripts.builders.build_expected_threat import write_csv
from scripts.builders.build_player_metrics_statsbomb import (
    StatsBombPlayerConfig, fetch_json, select_targets,
)

OUTPUT_FILE = "Data/Custom_Data/press_resistance.csv"
FIELDNAMES = [
    "source", "date", "competition", "season", "team", "opponent", "player",
    "passes", "passes_completed", "passes_pressured", "passes_pressured_completed",
    "carries", "carries_pressured", "take_ons", "take_ons_won",
    "dispossessed", "miscontrols", "pressured_pass_completion", "pressured_share",
]


def new_counter() -> dict[str, float]:
    return {key: 0.0 for key in (
        "passes", "passes_ok", "passes_press", "passes_press_ok", "carries",
        "carries_press", "take_ons", "take_ons_ok", "dispossessed", "miscontrols")}


def accumulate(counter: dict[str, float], event: dict) -> None:
    """Verbucht ein Event in die Zaehler eines Spielers."""
    name = event.get("type", {}).get("name")
    pressured = bool(event.get("under_pressure"))
    if name == "Pass":
        counter["passes"] += 1
        completed = "outcome" not in event.get("pass", {})
        counter["passes_ok"] += 1 if completed else 0
        if pressured:
            counter["passes_press"] += 1
            counter["passes_press_ok"] += 1 if completed else 0
    elif name == "Carry":
        counter["carries"] += 1
        counter["carries_press"] += 1 if pressured else 0
    elif name == "Dribble":
        counter["take_ons"] += 1
        counter["take_ons_ok"] += 1 if event.get("dribble", {}).get("outcome", {}).get("name") == "Complete" else 0
    elif name == "Dispossessed":
        counter["dispossessed"] += 1
    elif name == "Miscontrol":
        counter["miscontrols"] += 1


def process_match(match: dict, competition: str, season: str,
                  config: StatsBombPlayerConfig) -> list[dict[str, object]]:
    events = fetch_json(f"{config.BASE_URL}/events/{match['match_id']}.json", config)
    time.sleep(config.POLITE_DELAY_SECONDS)
    if not isinstance(events, list):
        return []
    counters: dict[str, dict[str, float]] = {}
    teams: dict[str, str] = {}
    for event in events:
        player = event.get("player", {}).get("name")
        if not player:
            continue
        accumulate(counters.setdefault(player, new_counter()), event)
        teams[player] = event.get("team", {}).get("name")
    home = match["home_team"]["home_team_name"]
    away = match["away_team"]["away_team_name"]
    date = str(match.get("match_date", ""))[:10]
    return [_row(player, counter, teams.get(player), home, away, date, competition, season)
            for player, counter in counters.items()]


def _row(player: str, counter: dict[str, float], team: str, home: str, away: str,
         date: str, competition: str, season: str) -> dict[str, object]:
    pressured = counter["passes_press"]
    return {
        "source": "statsbomb", "date": date, "competition": competition, "season": season,
        "team": team, "opponent": away if team == home else home, "player": player,
        "passes": int(counter["passes"]), "passes_completed": int(counter["passes_ok"]),
        "passes_pressured": int(pressured),
        "passes_pressured_completed": int(counter["passes_press_ok"]),
        "carries": int(counter["carries"]), "carries_pressured": int(counter["carries_press"]),
        "take_ons": int(counter["take_ons"]), "take_ons_won": int(counter["take_ons_ok"]),
        "dispossessed": int(counter["dispossessed"]), "miscontrols": int(counter["miscontrols"]),
        "pressured_pass_completion": round(counter["passes_press_ok"] / pressured, 4) if pressured else "",
        "pressured_share": round(pressured / counter["passes"], 4) if counter["passes"] else "",
    }


def main() -> None:
    config = StatsBombPlayerConfig()
    output_path = Path(OUTPUT_FILE)
    rows: list[dict[str, object]] = []
    if output_path.exists():
        with open(output_path, encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    done = {(str(r["competition"]), str(r["season"])) for r in rows}
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
    print(f"\nFertig: {len(rows)} Spieler-Spiel-Zeilen.")


if __name__ == "__main__":
    main()
