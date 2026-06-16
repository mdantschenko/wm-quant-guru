"""Kartenstatistik je Spieler und Spiel aus den Wyscout-Events.

Wyscout markiert Karten ueber Tags am Foulereignis des verursachenden Spielers:
1702 gelb, 1701 rot, 1703 gelb-rot. Pro Spieler und Spiel werden diese Karten
gezaehlt. StatsBomb-Wettbewerbe werden ueber build_player_cards_statsbomb.py
ergaenzt (Spalte source). Nur Spieler-Spiele mit mindestens einer Karte
erscheinen. Reine Standardbibliothek.

Start als Modul:
    python -m scripts.builders.build_player_cards
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from scripts.builders.build_player_metrics import load_games, load_simple, normalize_id
from scripts.helpers.text import decode_escapes

WYSCOUT_DIR = "Data/Wyscout Events (Pappalardo 2017-18)"
OUTPUT_FILE = "Data/Custom_Data/player_cards.csv"
CARD_TAGS = {1702: "yellow", 1701: "red", 1703: "second_yellow"}
FIELDNAMES = ["source", "date", "competition", "season", "team", "opponent",
              "player", "yellow", "red", "second_yellow"]
_NUMBER = re.compile(r"\d+")


def stream_cards(path: Path) -> dict[tuple, dict[str, int]]:
    """Zaehlt Karten je (Spieler, Spiel, Team) ueber eine Eventdatei."""
    counts: dict[tuple, dict[str, int]] = {}
    with open(path, encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        column = {name: index for index, name in enumerate(next(reader))}
        for raw in reader:
            tags = raw[column["tagsList"]]
            if "170" not in tags:
                continue
            present = {tag for tag in (int(value) for value in _NUMBER.findall(tags)) if tag in CARD_TAGS}
            if not present:
                continue
            key = (normalize_id(raw[column["playerId"]]), normalize_id(raw[column["matchId"]]),
                   normalize_id(raw[column["teamId"]]))
            bucket = counts.setdefault(key, {name: 0 for name in CARD_TAGS.values()})
            for tag in present:
                bucket[CARD_TAGS[tag]] += 1
    return counts


def build_rows(counts: dict[tuple, dict[str, int]], games: dict, teams: dict,
               players: dict, competitions: dict) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (player, game, team), bucket in counts.items():
        meta = games.get(game)
        if meta is None:
            continue
        opponent = meta["away"] if team == meta["home"] else meta["home"]
        rows.append({
            "source": "wyscout", "date": meta["date"],
            "competition": competitions.get(meta["competition_id"], meta["competition_id"]),
            "season": meta["season"], "team": teams.get(team, team),
            "opponent": teams.get(opponent, opponent), "player": players.get(player, player),
            "yellow": bucket["yellow"], "red": bucket["red"],
            "second_yellow": bucket["second_yellow"],
        })
    rows.sort(key=lambda row: (str(row["competition"]), str(row["season"]),
                               str(row["date"]), str(row["team"]), str(row["player"])))
    return rows


def main() -> None:
    source = Path(WYSCOUT_DIR)
    games = load_games(source / "games.csv")
    teams = {key: decode_escapes(value)
             for key, value in load_simple(source / "teams.csv", "wyId", "name").items()}
    players = {key: decode_escapes(value)
               for key, value in load_simple(source / "players.csv", "wyId", "shortName").items()}
    competitions = load_simple(source / "competitions.csv", "wyId", "name")

    counts: dict[tuple, dict[str, int]] = {}
    for path in sorted(source.glob("events_*.csv")):
        counts.update(stream_cards(path))
    rows = build_rows(counts, games, teams, players, competitions)

    output_path = Path(OUTPUT_FILE)
    kept = []
    if output_path.exists():
        with open(output_path, encoding="utf-8", newline="") as handle:
            kept = [row for row in csv.DictReader(handle) if row.get("source") == "statsbomb"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows + kept)
    print(f"  OK    {len(rows)} Karten-Spieler-Spiele (Wyscout, plus {len(kept)} StatsBomb erhalten)")


if __name__ == "__main__":
    main()
