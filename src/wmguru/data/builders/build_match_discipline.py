"""Disziplinarbild je Spiel aus den Wyscout-Events.

Verbindet je Spiel die beteiligten Teams, den Hauptschiedsrichter sowie die
Fouls und Karten jedes Spielers. So laesst sich nachvollziehen, wer gegen wen
spielte, wer pfiff, wie viele Karten fielen und wer sie bekam.

Ausgaben nach Data/Custom_Data/ (StatsBomb wird ueber
build_match_discipline_statsbomb.py ergaenzt, Spalte source):
  - player_match_discipline.csv  je Spieler und Spiel Fouls und Karten mit
    Gegner und Schiedsrichter,
  - match_officiating.csv         je Spiel Heim, Auswaerts, Schiedsrichter sowie
    Fouls und Karten beider Seiten.

Reine Standardbibliothek.

Start als Modul:
    python -m scripts.builders.build_match_discipline
"""
from __future__ import annotations

import ast
import csv
import re
from pathlib import Path

from src.scripts.builders.build_player_metrics import load_simple, normalize_id
from src.scripts.helpers.text import decode_escapes

WYSCOUT_DIR = "Data/Wyscout Events (Pappalardo 2017-18)"
OUTPUT_DIR = "Data/Custom_Data"
CARD_TAGS = {1702: "yellow", 1701: "red", 1703: "second_yellow"}
PLAYER_FIELDS = ["source", "date", "competition", "season", "game_id", "referee",
                 "team", "opponent", "player", "fouls", "yellow", "red", "second_yellow"]
MATCH_FIELDS = ["source", "date", "competition", "season", "game_id", "home", "away",
                "referee", "home_fouls", "away_fouls", "home_yellow", "home_red",
                "away_yellow", "away_red", "total_cards"]
_NUMBER = re.compile(r"\d+")


def main_referee(cell: str) -> str:
    """Gibt die Id des Hauptschiedsrichters zurueck, sonst leere Zeichenkette."""
    try:
        officials = ast.literal_eval(cell)
    except (ValueError, SyntaxError):
        return ""
    for official in officials if isinstance(officials, list) else []:
        if official.get("role") == "referee":
            return normalize_id(str(official.get("refereeId")))
    return ""


def load_match_meta(directory: Path) -> dict[str, dict]:
    """Liest je Spiel Teams, Schiedsrichter, Wettbewerb, Saison und Datum."""
    meta: dict[str, dict] = {}
    for path in sorted(directory.glob("matches_*.csv")):
        with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
            for row in csv.DictReader(handle):
                meta[normalize_id(row.get("wyId", ""))] = {
                    "home": normalize_id(row.get("team1.teamId", "")),
                    "away": normalize_id(row.get("team2.teamId", "")),
                    "referee": main_referee(row.get("referees", "")),
                    "competition_id": normalize_id(row.get("competitionId", "")),
                    "season": row.get("seasonId", ""), "date": row.get("dateutc", "")[:10]}
    return meta


def stream_discipline(directory: Path) -> dict[tuple, dict[str, int]]:
    """Zaehlt Fouls und Karten je (Spiel, Spieler, Team) ueber alle Eventdateien."""
    counts: dict[tuple, dict[str, int]] = {}
    for path in sorted(directory.glob("events_*.csv")):
        with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.reader(handle)
            column = {name: index for index, name in enumerate(next(reader))}
            for raw in reader:
                is_foul = raw[column["eventName"]] == "Foul"
                tags = raw[column["tagsList"]]
                cards = {tag for tag in (int(value) for value in _NUMBER.findall(tags))
                         if tag in CARD_TAGS} if "170" in tags else set()
                player = normalize_id(raw[column["playerId"]])
                if (not is_foul and not cards) or not player:
                    continue
                key = (normalize_id(raw[column["matchId"]]), player, normalize_id(raw[column["teamId"]]))
                bucket = counts.setdefault(key, {"fouls": 0, "yellow": 0, "red": 0, "second_yellow": 0})
                bucket["fouls"] += 1 if is_foul else 0
                for tag in cards:
                    bucket[CARD_TAGS[tag]] += 1
    return counts


def build_player_rows(counts: dict, meta: dict, teams: dict, players: dict,
                      competitions: dict, referees: dict) -> list[dict]:
    rows: list[dict] = []
    for (game, player, team), bucket in counts.items():
        info = meta.get(game)
        if info is None:
            continue
        opponent = info["away"] if team == info["home"] else info["home"]
        rows.append({
            "source": "wyscout", "date": info["date"],
            "competition": competitions.get(info["competition_id"], info["competition_id"]),
            "season": info["season"], "game_id": game,
            "referee": referees.get(info["referee"], info["referee"]),
            "team": teams.get(team, team), "opponent": teams.get(opponent, opponent),
            "player": players.get(player, player), "fouls": bucket["fouls"],
            "yellow": bucket["yellow"], "red": bucket["red"], "second_yellow": bucket["second_yellow"]})
    rows.sort(key=lambda row: (str(row["competition"]), str(row["season"]),
                               str(row["date"]), str(row["game_id"]), str(row["team"]), str(row["player"])))
    return rows


def build_match_rows(counts: dict, meta: dict, teams: dict,
                     competitions: dict, referees: dict) -> list[dict]:
    per_team: dict[tuple, dict[str, int]] = {}
    for (game, _player, team), bucket in counts.items():
        target = per_team.setdefault((game, team), {"fouls": 0, "yellow": 0, "red": 0, "second_yellow": 0})
        for name, value in bucket.items():
            target[name] += value
    rows: list[dict] = []
    for game, info in meta.items():
        home_stat = per_team.get((game, info["home"]), {})
        away_stat = per_team.get((game, info["away"]), {})
        rows.append({
            "source": "wyscout", "date": info["date"],
            "competition": competitions.get(info["competition_id"], info["competition_id"]),
            "season": info["season"], "game_id": game,
            "home": teams.get(info["home"], info["home"]), "away": teams.get(info["away"], info["away"]),
            "referee": referees.get(info["referee"], info["referee"]),
            "home_fouls": home_stat.get("fouls", 0), "away_fouls": away_stat.get("fouls", 0),
            "home_yellow": home_stat.get("yellow", 0), "home_red": home_stat.get("red", 0) + home_stat.get("second_yellow", 0),
            "away_yellow": away_stat.get("yellow", 0), "away_red": away_stat.get("red", 0) + away_stat.get("second_yellow", 0),
            "total_cards": sum(home_stat.get(k, 0) + away_stat.get(k, 0) for k in CARD_TAGS.values())})
    rows.sort(key=lambda row: (str(row["competition"]), str(row["season"]), str(row["date"]), str(row["game_id"])))
    return rows


def write_with_existing(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """Schreibt die Wyscout-Zeilen und erhaelt vorhandene StatsBomb-Zeilen."""
    kept = []
    if path.exists():
        with open(path, encoding="utf-8", newline="") as handle:
            kept = [row for row in csv.DictReader(handle) if row.get("source") == "statsbomb"]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows + kept)


def main() -> None:
    directory = Path(WYSCOUT_DIR)
    teams = {key: decode_escapes(value)
             for key, value in load_simple(directory / "teams.csv", "wyId", "name").items()}
    players = {key: decode_escapes(value)
               for key, value in load_simple(directory / "players.csv", "wyId", "shortName").items()}
    competitions = load_simple(directory / "competitions.csv", "wyId", "name")
    referees = {key: decode_escapes(value)
                for key, value in load_simple(directory / "referees.csv", "wyId", "shortName").items()}
    meta = load_match_meta(directory)
    counts = stream_discipline(directory)

    output_dir = Path(OUTPUT_DIR)
    player_rows = build_player_rows(counts, meta, teams, players, competitions, referees)
    match_rows = build_match_rows(counts, meta, teams, competitions, referees)
    write_with_existing(output_dir / "player_match_discipline.csv", player_rows, PLAYER_FIELDS)
    write_with_existing(output_dir / "match_officiating.csv", match_rows, MATCH_FIELDS)
    print(f"  OK    {len(player_rows)} Spieler-Spiel-Zeilen, {len(match_rows)} Spiele (Wyscout)")


if __name__ == "__main__":
    main()
