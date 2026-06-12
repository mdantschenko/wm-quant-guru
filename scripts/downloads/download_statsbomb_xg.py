"""Lädt Match-xG für Turniere aus StatsBomb Open Data (GitHub, frei).

StatsBomb stellt vollständige Event-Daten (inkl. xG je Schuss) für u. a.
WM 2018/2022, EM 2020/2024 und Copa América 2024 frei bereit. Dieses
Skript lädt pro Turnier die Spielliste, streamt die Event-Datei jedes
Spiels, aggregiert Schüsse zu Match-Level-xG und schreibt eine kompakte
CSV pro Turnier. Die Event-Rohdaten (~4 MB/Spiel) werden nicht
persistiert -- sie sind über das Repo jederzeit reproduzierbar.
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


class StatsBombConfig:
    """Quelle, Turnier-IDs und Zielpfade."""

    BASE_URL: str = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    USER_AGENT: str = "wm-quant-guru (research)"
    TIMEOUT_SECONDS: int = 60
    POLITE_DELAY_SECONDS: float = 0.2
    OUTPUT_DIR: str = "Data/xG Tournament Data (StatsBomb Open Data)"

    # Beschrifteter Dateiname -> (competition_id, season_id) laut
    # competitions.json des Open-Data-Repos.
    TOURNAMENTS: dict[str, tuple[int, int]] = {
        "World Cup 2018": (43, 3),
        "World Cup 2022": (43, 106),
        "Euro 2020 (EM 2021)": (55, 43),
        "Euro 2024": (55, 282),
        "Copa America 2024": (223, 282),
    }


def fetch_json(url: str, config: StatsBombConfig) -> object | None:
    """Lade eine JSON-Datei; None bei Fehler."""
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def shot_aggregates(
    events: list[dict], team_name: str, max_period: int
) -> tuple[float, int, int]:
    """Summiere (xg, schuesse, schuesse_aufs_tor) eines Teams aus den Events.

    ``max_period`` begrenzt die Spielphasen: 2 = nur 90 Minuten,
    4 = inkl. Verlaengerung. Periode 5 (Elfmeterschiessen) wird immer
    ausgeschlossen -- Shootout-Elfmeter (~0,78 xG je Versuch) wuerden
    die Match-xG massiv verzerren.
    """
    total_xg = 0.0
    shots = 0
    on_target = 0
    for event in events:
        if event.get("type", {}).get("name") != "Shot":
            continue
        if event.get("team", {}).get("name") != team_name:
            continue
        if int(event.get("period") or 1) > max_period:
            continue
        shot = event.get("shot", {})
        total_xg += float(shot.get("statsbomb_xg") or 0.0)
        shots += 1
        if shot.get("outcome", {}).get("name") in ("Goal", "Saved", "Saved To Post"):
            on_target += 1
    return round(total_xg, 4), shots, on_target


def process_tournament(
    label: str, competition_id: int, season_id: int, config: StatsBombConfig
) -> int:
    """Aggregiere alle Spiele eines Turniers in eine CSV. Gibt Spielzahl zurück."""
    matches = fetch_json(
        f"{config.BASE_URL}/matches/{competition_id}/{season_id}.json", config
    )
    if not isinstance(matches, list):
        print(f"  FAIL  {label}: Spielliste nicht ladbar")
        return 0
    target = Path(config.OUTPUT_DIR) / f"{label}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["match_id", "match_date", "stage", "home_team", "away_team",
             "home_score", "away_score",
             "home_xg_90", "away_xg_90",          # nur 90 Minuten
             "home_xg", "away_xg",                # inkl. Verlaengerung, ohne ES
             "home_shots", "away_shots", "home_shots_on_target",
             "away_shots_on_target", "referee", "stadium", "kick_off"]
        )
        for match in sorted(matches, key=lambda m: str(m.get("match_date"))):
            match_id = match["match_id"]
            home = match["home_team"]["home_team_name"]
            away = match["away_team"]["away_team_name"]
            events = fetch_json(f"{config.BASE_URL}/events/{match_id}.json", config)
            time.sleep(config.POLITE_DELAY_SECONDS)
            if not isinstance(events, list):
                print(f"    SKIP  {home} - {away} (Events nicht ladbar)")
                continue
            home_xg_90, _, _ = shot_aggregates(events, home, max_period=2)
            away_xg_90, _, _ = shot_aggregates(events, away, max_period=2)
            home_xg, home_shots, home_sot = shot_aggregates(events, home, max_period=4)
            away_xg, away_shots, away_sot = shot_aggregates(events, away, max_period=4)
            writer.writerow(
                [match_id, match.get("match_date"),
                 match.get("competition_stage", {}).get("name", ""),
                 home, away, match.get("home_score"), match.get("away_score"),
                 home_xg_90, away_xg_90,
                 home_xg, away_xg, home_shots, away_shots, home_sot, away_sot,
                 match.get("referee", {}).get("name", ""),
                 match.get("stadium", {}).get("name", ""),
                 match.get("kick_off", "")]
            )
            written += 1
            if written % 16 == 0:
                print(f"    ... {written}/{len(matches)} Spiele", flush=True)
    print(f"  OK    {label}: {written} Spiele -> {target}", flush=True)
    return written


def main() -> None:
    """Aggregiere alle konfigurierten Turniere."""
    config = StatsBombConfig()
    total = 0
    for label, (competition_id, season_id) in config.TOURNAMENTS.items():
        print(f"Turnier: {label}", flush=True)
        total += process_tournament(label, competition_id, season_id, config)
    print(f"\nFertig: {total} Spiele mit Match-xG.")


if __name__ == "__main__":
    main()
