"""Lädt Aufstellungen und Bank-Nutzung aller Turnierspiele (StatsBomb).

Die lineups-Dateien enthalten je Spiel den kompletten Spieltagskader
beider Teams: Startelf, Einwechslungen (mit Minute) und unbenutzte
Bankspieler. Daraus entstehen Bank-Features, die der Markt kaum preist:
Bank-Tiefe (Wert der Bank via Ratings-Join), Joker-Nutzung und das
Wechsel-Timing des Trainers (frueh/spaet) -- seit der 5-Wechsel-Regel
ein deutlich groesserer Hebel als frueher. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

from scripts.downloads.download_statsbomb_xg import StatsBombConfig, fetch_json


class LineupsConfig:
    """Zielpfad (Quelle und Turniere kommen aus StatsBombConfig)."""

    OUTPUT_FILE: str = (
        "Data/xG Tournament Data (StatsBomb Open Data)/lineups_bench.csv"
    )


def minute_of(timestamp: str | None) -> str:
    """Spielminute aus 'MM:SS'; die Timestamps der lineups-Dateien sind
    bereits ABSOLUTE Spielminuten (kein Perioden-Offset addieren)."""
    if not timestamp:
        return ""
    try:
        return str(int(timestamp.split(":")[0]))
    except ValueError:
        return ""


def player_rows(
    tournament: str, match_id: int, match_date: str, team: dict
) -> list[list[object]]:
    """Zeilen (eine je Spieler) für ein Team eines Spiels."""
    rows: list[list[object]] = []
    for player in team.get("lineup", []):
        positions = player.get("positions", [])
        if positions:
            first = positions[0]
            last = positions[-1]
            is_starter = first.get("start_reason") == "Starting XI"
            role = "starter" if is_starter else "sub_used"
            minute_on = "0" if is_starter else minute_of(first.get("from"))
            minute_off = minute_of(last.get("to"))
            position = first.get("position", "")
        else:
            role, minute_on, minute_off, position = "bench_unused", "", "", ""
        rows.append(
            [tournament, match_id, match_date, team.get("team_name", ""),
             player.get("player_name", ""), player.get("jersey_number", ""),
             role, position, minute_on, minute_off]
        )
    return rows


def main() -> None:
    """Streame alle Lineups und schreibe eine flache Spieler-Spiel-CSV."""
    statsbomb = StatsBombConfig()
    target = Path(LineupsConfig.OUTPUT_FILE)
    written = 0
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tournament", "match_id", "match_date", "team",
                         "player", "jersey", "role", "position",
                         "minute_on", "minute_off"])
        for label, (competition_id, season_id) in statsbomb.TOURNAMENTS.items():
            matches = fetch_json(
                f"{statsbomb.BASE_URL}/matches/{competition_id}/{season_id}.json",
                statsbomb,
            )
            if not isinstance(matches, list):
                print(f"  FAIL  {label} (Spielliste)")
                continue
            done = 0
            for match in matches:
                lineups = fetch_json(
                    f"{statsbomb.BASE_URL}/lineups/{match['match_id']}.json",
                    statsbomb,
                )
                time.sleep(statsbomb.POLITE_DELAY_SECONDS)
                if not isinstance(lineups, list):
                    continue
                for team in lineups:
                    rows = player_rows(
                        label, match["match_id"], match.get("match_date", ""),
                        team,
                    )
                    writer.writerows(rows)
                    written += len(rows)
                done += 1
            print(f"  OK    {label}: {done} Spiele", flush=True)
    print(f"{written} Spieler-Spiel-Zeilen -> {target}")


if __name__ == "__main__":
    main()
