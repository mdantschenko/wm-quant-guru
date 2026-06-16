"""Auswechslungen je Spiel aus den Wyscout-Spieldaten.

Die Wyscout-Spieldateien (matches_*.csv) fuehren je Team die Auswechslungen als
Liste mit Spieler rein, Spieler raus und Minute. Pro Auswechslung entsteht eine
Zeile. StatsBomb-Wettbewerbe werden ueber build_substitutions_statsbomb.py
ergaenzt (Spalte source). Reine Standardbibliothek.

Start als Modul:
    python -m scripts.builders.build_substitutions
"""
from __future__ import annotations

import ast
import csv
from pathlib import Path

from scripts.builders.build_player_metrics import load_simple, normalize_id
from scripts.helpers.text import decode_escapes

WYSCOUT_DIR = "Data/Wyscout Events (Pappalardo 2017-18)"
OUTPUT_FILE = "Data/Custom_Data/substitutions.csv"
FIELDNAMES = ["source", "date", "competition", "season", "game_id", "team",
              "opponent", "player_out", "player_in", "minute"]


def parse_substitutions(cell: str) -> list[dict]:
    """Liest die als Python-Literal gespeicherte Auswechselliste."""
    try:
        value = ast.literal_eval(cell)
    except (ValueError, SyntaxError):
        return []
    return value if isinstance(value, list) else []


def match_rows(row: dict[str, str], teams: dict, players: dict,
               competitions: dict) -> list[dict[str, object]]:
    """Erzeugt die Auswechselzeilen beider Teams eines Spiels."""
    date = row.get("dateutc", "")[:10]
    competition = competitions.get(normalize_id(row.get("competitionId", "")), row.get("competitionId", ""))
    season = row.get("seasonId", "")
    game_id = normalize_id(row.get("wyId", ""))
    sides = (("team1.teamId", "team1.formation.substitutions", "team2.teamId"),
             ("team2.teamId", "team2.formation.substitutions", "team1.teamId"))
    rows: list[dict[str, object]] = []
    for team_column, sub_column, opponent_column in sides:
        team = normalize_id(row.get(team_column, ""))
        opponent = normalize_id(row.get(opponent_column, ""))
        for substitution in parse_substitutions(row.get(sub_column, "")):
            rows.append({
                "source": "wyscout", "date": date, "competition": competition,
                "season": season, "game_id": game_id, "team": teams.get(team, team),
                "opponent": teams.get(opponent, opponent),
                "player_out": players.get(normalize_id(str(substitution.get("playerOut"))), substitution.get("playerOut")),
                "player_in": players.get(normalize_id(str(substitution.get("playerIn"))), substitution.get("playerIn")),
                "minute": substitution.get("minute", ""),
            })
    return rows


def main() -> None:
    source = Path(WYSCOUT_DIR)
    teams = {key: decode_escapes(value)
             for key, value in load_simple(source / "teams.csv", "wyId", "name").items()}
    players = {key: decode_escapes(value)
               for key, value in load_simple(source / "players.csv", "wyId", "shortName").items()}
    competitions = load_simple(source / "competitions.csv", "wyId", "name")

    rows: list[dict[str, object]] = []
    for path in sorted(source.glob("matches_*.csv")):
        with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
            for row in csv.DictReader(handle):
                rows.extend(match_rows(row, teams, players, competitions))
    rows.sort(key=lambda item: (str(item["competition"]), str(item["season"]),
                                str(item["date"]), str(item["game_id"]),
                                int(item["minute"]) if str(item["minute"]).isdigit() else 0))

    output_path = Path(OUTPUT_FILE)
    kept = []
    if output_path.exists():
        with open(output_path, encoding="utf-8", newline="") as handle:
            kept = [item for item in csv.DictReader(handle) if item.get("source") == "statsbomb"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows + kept)
    print(f"  OK    {len(rows)} Auswechslungen (Wyscout, plus {len(kept)} StatsBomb erhalten)")


if __name__ == "__main__":
    main()
