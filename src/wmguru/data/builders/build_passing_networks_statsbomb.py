"""Erweitert passing_networks.csv um StatsBomb-Open-Data-Wettbewerbe.

Erganzt den Passnetzwerk-Datensatz (gleiches Schema wie der Wyscout-Teil) um
die frei verfugbaren StatsBomb-Wettbewerbe: die genannten Turniere WM 2022,
EM 2024 und Copa America 2024 sowie alle frei verfugbaren Saisons der
1. Bundesliga. Die Auswahl wird aus competitions.json datengetrieben
ermittelt; weitere Wettbewerbe lassen sich uber die Konfiguration zuschalten.

StatsBomb liefert den Passempfanger direkt (pass.recipient), sodass keine
Folge-Aktions-Heuristik notig ist. Koordinaten 0..120 / 0..80 werden in Meter
umgerechnet. Open-Play-Pass = Typ Pass ohne Standardsituation und ohne Flanke
(zur Vergleichbarkeit mit dem SPADL-Pass des Wyscout-Teils). Eventrohdaten
werden gestreamt und nicht persistiert. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.error
import urllib.request
from math import hypot
from pathlib import Path


class StatsBombPassingConfig:
    """Quelle, Auswahl, Schema und Umrechnungen."""

    BASE_URL: str = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    USER_AGENT: str = "wm-quant-guru (research)"
    TIMEOUT_SECONDS: int = 60
    POLITE_DELAY_SECONDS: float = 0.2
    OUTPUT_FILE: str = "Data/Custom_Data/passing_networks.csv"

    PITCH_X: float = 105.0
    PITCH_Y: float = 68.0
    STATSBOMB_X: float = 120.0
    STATSBOMB_Y: float = 80.0
    FORWARD_THRESHOLD_M: float = 5.0

    SET_PIECE_TYPES: frozenset[str] = frozenset(
        {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"}
    )
    # Alle frei verfugbaren Wettbewerbe dieses Geschlechts werden gezogen.
    GENDER: str = "male"

    FIELDNAMES: list[str] = [
        "game_id", "source", "competition", "season_id", "date", "team", "opponent",
        "is_home", "passes", "pass_success_rate", "forward_pass_share",
        "mean_pass_length_m", "mean_forward_gain_m", "players_involved",
        "distinct_lanes", "unused_lane_share", "centralization_hhi",
        "top_player_share", "top_lane", "top_lane_count",
    ]


def fetch_json(url: str, config: StatsBombPassingConfig) -> object | None:
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def select_targets(
    competitions: list[dict], config: StatsBombPassingConfig
) -> list[tuple[int, int, str, str]]:
    """Alle frei verfugbaren Wettbewerb/Saison-Kombinationen des Geschlechts."""
    targets: list[tuple[int, int, str, str]] = []
    for entry in competitions:
        if entry.get("competition_gender") != config.GENDER:
            continue
        targets.append((
            entry["competition_id"], entry["season_id"],
            entry.get("competition_name", ""), str(entry.get("season_name", "")),
        ))
    return targets


def pass_records_by_team(
    events: list[dict], config: StatsBombPassingConfig
) -> dict[str, list[tuple]]:
    """Sammelt je Team die Open-Play-Passe als (Passgeber, sx, sy, ex, ey, erfolg, empfaenger)."""
    records: dict[str, list[tuple]] = {}
    for event in events:
        if event.get("type", {}).get("name") != "Pass":
            continue
        pass_info = event.get("pass", {})
        if pass_info.get("type", {}).get("name") in config.SET_PIECE_TYPES:
            continue
        if pass_info.get("cross"):
            continue
        location = event.get("location")
        end = pass_info.get("end_location")
        passer = event.get("player", {}).get("name")
        team = event.get("team", {}).get("name")
        if not (location and end and passer and team):
            continue
        success = "outcome" not in pass_info
        recipient = pass_info.get("recipient", {}).get("name") if success else None
        records.setdefault(team, []).append((
            passer,
            location[0] / config.STATSBOMB_X * config.PITCH_X,
            location[1] / config.STATSBOMB_Y * config.PITCH_Y,
            end[0] / config.STATSBOMB_X * config.PITCH_X,
            end[1] / config.STATSBOMB_Y * config.PITCH_Y,
            success,
            recipient,
        ))
    return records


def summarize_team(records: list[tuple], config: StatsBombPassingConfig) -> dict[str, object]:
    """Berechnet die Passnetzwerk-Kennzahlen aus den Passsatzen eines Teams."""
    passes = len(records)
    success = sum(1 for record in records if record[5])
    forward = sum(1 for record in records if record[3] - record[1] > config.FORWARD_THRESHOLD_M)
    length_sum = sum(hypot(record[3] - record[1], record[4] - record[2]) for record in records)
    forward_gain_sum = sum(record[3] - record[1] for record in records)
    passer: dict[str, int] = {}
    lane: dict[tuple[str, str], int] = {}
    for record in records:
        passer[record[0]] = passer.get(record[0], 0) + 1
        if record[5] and record[6] and record[6] != record[0]:
            key = (record[0], record[6])
            lane[key] = lane.get(key, 0) + 1
    players_involved = len(passer)
    centralization = sum((value / passes) ** 2 for value in passer.values())
    possible_lanes = players_involved * (players_involved - 1)
    unused_share = max(0.0, 1.0 - len(lane) / possible_lanes) if possible_lanes else ""
    top_pair, top_count = max(lane.items(), key=lambda item: item[1]) if lane else (("", ""), 0)
    return {
        "passes": passes,
        "pass_success_rate": round(success / passes, 4),
        "forward_pass_share": round(forward / passes, 4),
        "mean_pass_length_m": round(length_sum / passes, 2),
        "mean_forward_gain_m": round(forward_gain_sum / passes, 2),
        "players_involved": players_involved,
        "distinct_lanes": len(lane),
        "unused_lane_share": round(unused_share, 4) if unused_share != "" else "",
        "centralization_hhi": round(centralization, 4),
        "top_player_share": round(max(passer.values()) / passes, 4),
        "top_lane": f"{top_pair[0]} -> {top_pair[1]}" if top_count else "",
        "top_lane_count": top_count,
    }


def process_match(
    match: dict, competition: str, season: str, config: StatsBombPassingConfig
) -> list[dict[str, object]]:
    """Erzeugt die Zeilen beider Teams eines StatsBomb-Spiels."""
    match_id = match["match_id"]
    home = match["home_team"]["home_team_name"]
    away = match["away_team"]["away_team_name"]
    events = fetch_json(f"{config.BASE_URL}/events/{match_id}.json", config)
    time.sleep(config.POLITE_DELAY_SECONDS)
    if not isinstance(events, list):
        return []
    records = pass_records_by_team(events, config)
    rows: list[dict[str, object]] = []
    for team, opponent in ((home, away), (away, home)):
        team_records = records.get(team)
        if not team_records:
            continue
        row = {
            "game_id": match_id,
            "source": "statsbomb",
            "competition": competition,
            "season_id": season,
            "date": str(match.get("match_date", ""))[:10],
            "team": team,
            "opponent": opponent,
            "is_home": int(team == home),
        }
        row.update(summarize_team(team_records, config))
        rows.append(row)
    return rows


def process_target(
    competition_id: int, season_id: int, competition: str, season: str,
    config: StatsBombPassingConfig,
) -> list[dict[str, object]]:
    """Verarbeitet alle Spiele eines Wettbewerbs/einer Saison."""
    matches = fetch_json(
        f"{config.BASE_URL}/matches/{competition_id}/{season_id}.json", config
    )
    if not isinstance(matches, list):
        print(f"  FAIL  {competition} {season}: Spielliste nicht ladbar", flush=True)
        return []
    rows: list[dict[str, object]] = []
    for index, match in enumerate(sorted(matches, key=lambda m: str(m.get("match_date"))), start=1):
        rows.extend(process_match(match, competition, season, config))
        if index % 25 == 0:
            print(f"    ... {competition} {season}: {index}/{len(matches)} Spiele", flush=True)
    print(f"  OK    {competition} {season}: {len(matches)} Spiele", flush=True)
    return rows


def load_existing(config: StatsBombPassingConfig) -> list[dict[str, object]]:
    """Liest die bisherige Datei (Wyscout plus bereits gezogene StatsBomb-Zeilen)."""
    path = Path(config.OUTPUT_FILE)
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_all(rows: list[dict[str, object]], config: StatsBombPassingConfig) -> None:
    """Schreibt den vollstaendigen Datensatz (nach jedem Wettbewerb, resumierbar)."""
    ordered = sorted(rows, key=lambda row: (
        str(row["source"]), str(row["competition"]), str(row["date"]),
        str(row["game_id"]), str(row["is_home"]),
    ))
    path = Path(config.OUTPUT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=config.FIELDNAMES)
        writer.writeheader()
        writer.writerows(ordered)


def main() -> None:
    config = StatsBombPassingConfig()
    competitions = fetch_json(f"{config.BASE_URL}/competitions.json", config)
    if not isinstance(competitions, list):
        raise SystemExit("competitions.json nicht ladbar")
    targets = select_targets(competitions, config)
    rows = load_existing(config)
    done = {(str(row.get("competition")), str(row.get("season_id")))
            for row in rows if row.get("source") == "statsbomb"}
    pending = [target for target in targets if (target[2], target[3]) not in done]
    print(f"Maenner-Wettbewerbe gesamt {len(targets)}, bereits vorhanden {len(done)}, "
          f"offen {len(pending)}", flush=True)
    for competition_id, season_id, competition, season in pending:
        new_rows = process_target(competition_id, season_id, competition, season, config)
        if not new_rows:
            continue
        rows.extend(new_rows)
        write_all(rows, config)
        print(f"  PERSIST  {competition} {season}: +{len(new_rows)} Zeilen "
              f"(Datei jetzt {len(rows)})", flush=True)
    print(f"\nFertig: Datensatz enthaelt {len(rows)} Zeilen.")


if __name__ == "__main__":
    main()
