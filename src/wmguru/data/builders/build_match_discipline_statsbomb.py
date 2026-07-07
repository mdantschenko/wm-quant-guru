"""Erweitert das Disziplinarbild um alle frei verfuegbaren StatsBomb-Maennerwettbewerbe.

Fouls stammen aus Foul Committed, Karten aus dem Feld card von Foul Committed und
Bad Behaviour, der Schiedsrichter aus den Spiel-Metadaten. Ergaenzt
player_match_discipline.csv und match_officiating.csv ueber die Spalte source.
Events werden gestreamt, nicht persistiert. Resumierbar je Wettbewerb.

Start als Modul:
    python -m scripts.builders.build_match_discipline_statsbomb
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

from src.scripts.builders.build_expected_threat import write_csv
from src.scripts.builders.build_match_discipline import MATCH_FIELDS, PLAYER_FIELDS
from src.scripts.builders.build_player_metrics_statsbomb import (
    StatsBombPlayerConfig, fetch_json, select_targets,
)

OUTPUT_DIR = "Data/Custom_Data"
CARD_NAMES = {"Yellow Card": "yellow", "Red Card": "red", "Second Yellow": "second_yellow"}


def new_counter(team: str) -> dict[str, object]:
    return {"team": team, "fouls": 0, "yellow": 0, "red": 0, "second_yellow": 0}


def accumulate(counters: dict, event: dict) -> None:
    """Verbucht Foul Committed und Bad Behaviour eines Spielers."""
    name = event.get("type", {}).get("name")
    player = event.get("player", {}).get("name")
    if not player:
        return
    if name == "Foul Committed":
        counter = counters.setdefault(player, new_counter(event.get("team", {}).get("name")))
        counter["fouls"] += 1
        card = event.get("foul_committed", {}).get("card", {}).get("name")
        if card in CARD_NAMES:
            counter[CARD_NAMES[card]] += 1
    elif name == "Bad Behaviour":
        card = event.get("bad_behaviour", {}).get("card", {}).get("name")
        if card in CARD_NAMES:
            counter = counters.setdefault(player, new_counter(event.get("team", {}).get("name")))
            counter[CARD_NAMES[card]] += 1


def process_match(match: dict, competition: str, season: str,
                  config: StatsBombPlayerConfig) -> tuple[list[dict], dict | None]:
    events = fetch_json(f"{config.BASE_URL}/events/{match['match_id']}.json", config)
    time.sleep(config.POLITE_DELAY_SECONDS)
    if not isinstance(events, list):
        return [], None
    counters: dict[str, dict] = {}
    for event in events:
        accumulate(counters, event)
    home = match["home_team"]["home_team_name"]
    away = match["away_team"]["away_team_name"]
    date = str(match.get("match_date", ""))[:10]
    referee = (match.get("referee") or {}).get("name", "")
    context = (competition, season, str(match["match_id"]), referee, home, away, date)
    player_rows = [_player_row(player, counter, context) for player, counter in counters.items()]
    return player_rows, _match_row(counters, context)


def _player_row(player: str, counter: dict, context: tuple) -> dict:
    competition, season, game_id, referee, home, away, date = context
    team = counter["team"]
    return {"source": "statsbomb", "date": date, "competition": competition, "season": season,
            "game_id": game_id, "referee": referee, "team": team,
            "opponent": away if team == home else home, "player": player,
            "fouls": counter["fouls"], "yellow": counter["yellow"],
            "red": counter["red"], "second_yellow": counter["second_yellow"]}


def _match_row(counters: dict, context: tuple) -> dict:
    competition, season, game_id, referee, home, away, date = context
    sides = {home: new_counter(home), away: new_counter(away)}
    for counter in counters.values():
        target = sides.get(counter["team"])
        if target is None:
            continue
        for key in ("fouls", "yellow", "red", "second_yellow"):
            target[key] += counter[key]
    home_stat, away_stat = sides[home], sides[away]
    return {"source": "statsbomb", "date": date, "competition": competition, "season": season,
            "game_id": game_id, "home": home, "away": away, "referee": referee,
            "home_fouls": home_stat["fouls"], "away_fouls": away_stat["fouls"],
            "home_yellow": home_stat["yellow"], "home_red": home_stat["red"] + home_stat["second_yellow"],
            "away_yellow": away_stat["yellow"], "away_red": away_stat["red"] + away_stat["second_yellow"],
            "total_cards": sum(home_stat[k] + away_stat[k] for k in ("yellow", "red", "second_yellow"))}


def read_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def persist(path: Path, rows: list[dict], fieldnames: list[str], with_player: bool) -> None:
    rows.sort(key=lambda row: (str(row["competition"]), str(row["season"]), str(row["date"]),
                               str(row["game_id"]), str(row.get("team", "")),
                               str(row.get("player", "")) if with_player else ""))
    write_csv(path, rows, fieldnames)


def main() -> None:
    config = StatsBombPlayerConfig()
    player_path = Path(OUTPUT_DIR) / "player_match_discipline.csv"
    match_path = Path(OUTPUT_DIR) / "match_officiating.csv"
    player_rows = read_existing(player_path)
    match_rows = read_existing(match_path)
    done = {(str(r["competition"]), str(r["season"])) for r in player_rows if r.get("source") == "statsbomb"}
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
            new_players, match_row = process_match(match, competition, season, config)
            player_rows.extend(new_players)
            if match_row is not None:
                match_rows.append(match_row)
        persist(player_path, player_rows, PLAYER_FIELDS, with_player=True)
        persist(match_path, match_rows, MATCH_FIELDS, with_player=False)
        print(f"  PERSIST  {competition} {season}: {len(matches)} Spiele", flush=True)
    print(f"\nFertig: {len(player_rows)} Spieler-Spiel-Zeilen, {len(match_rows)} Spiele.")


if __name__ == "__main__":
    main()
