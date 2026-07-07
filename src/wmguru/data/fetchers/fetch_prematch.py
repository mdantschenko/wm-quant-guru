"""Holt kurz vor Anpfiff alle operativen Pre-Match-Daten je Spiel.

Buendelt fuer einen Spieltag die zeitkritischen Live-Informationen, die das
System unmittelbar vor Abgabe von Tipp oder Wette braucht:
  - bestaetigte Aufstellungen (Startelf, Bank, Formation, Trainer),
  - Verletzungen und Sperren je Team,
  - Wetter zum Anstoss am Spielort.

Quellen:
  - API-Football (v3, api-sports.io) fuer Aufstellungen, Verletzungen und die
    Spielliste. Benoetigt einen kostenlosen API-Schluessel (Free Tier 100
    Anfragen pro Tag, fuer einen WM-Spieltag ausreichend). Schluessel ueber
    Umgebungsvariable API_FOOTBALL_KEY oder Datei Data/Live/api_football_key.txt.
  - Open-Meteo (ohne Schluessel) fuer Geokodierung des Spielorts und die
    Wettervorhersage zur Anstosszeit.

Quoten sind bewusst nicht hier, dafuer dient der bestehende Odds-Fetcher
(The Odds API). Aufruf:
    python -m scripts.fetchers.fetch_prematch [YYYY-MM-DD]
Ohne Datum wird der heutige Tag (UTC) verwendet. Liga und Saison sind ueber
die Umgebungsvariablen API_FOOTBALL_LEAGUE und API_FOOTBALL_SEASON setzbar
(Standard Weltmeisterschaft 2026). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class FetchConfig:
    """Endpunkte, Schluesselquellen und Zielordner."""

    API_BASE: str = "https://v3.football.api-sports.io"
    GEOCODE_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
    KEY_ENV: str = "API_FOOTBALL_KEY"
    KEY_FILE: str = "Data/Live/api_football_key.txt"
    OUTPUT_DIR: str = "Data/Live"
    USER_AGENT: str = "wm-quant-guru (research)"
    TIMEOUT_SECONDS: int = 30
    POLITE_DELAY_SECONDS: float = 1.0
    DEFAULT_LEAGUE: str = "1"      # API-Football Weltmeisterschaft
    DEFAULT_SEASON: str = "2026"


def load_api_key(config: FetchConfig) -> Optional[str]:
    """Liest den API-Football-Schluessel aus Umgebung oder Datei."""
    key = os.environ.get(config.KEY_ENV)
    if key:
        return key.strip()
    key_path = Path(config.KEY_FILE)
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    return None


def _get_json(url: str, headers: dict[str, str], config: FetchConfig) -> Optional[dict]:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, json.JSONDecodeError, ValueError) as error:
        print(f"  WARN  {url.split('?')[0]}: {error}", flush=True)
        return None


def api_football(path: str, params: dict[str, str], key: str, config: FetchConfig) -> list:
    """Ruft einen API-Football-Endpunkt auf und gibt die Antwortliste zurueck."""
    url = f"{config.API_BASE}/{path}?{urllib.parse.urlencode(params)}"
    headers = {"x-apisports-key": key, "User-Agent": config.USER_AGENT}
    payload = _get_json(url, headers, config)
    time.sleep(config.POLITE_DELAY_SECONDS)
    return payload.get("response", []) if isinstance(payload, dict) else []


def geocode_city(city: str, config: FetchConfig) -> Optional[tuple[float, float]]:
    """Spielort zu Koordinaten (Open-Meteo, ohne Schluessel)."""
    if not city:
        return None
    url = f"{config.GEOCODE_URL}?{urllib.parse.urlencode({'name': city, 'count': 1})}"
    payload = _get_json(url, {"User-Agent": config.USER_AGENT}, config)
    results = payload.get("results") if isinstance(payload, dict) else None
    if not results:
        return None
    return results[0]["latitude"], results[0]["longitude"]


def forecast_at(latitude: float, longitude: float, kickoff_iso: str, config: FetchConfig) -> Optional[dict]:
    """Wetter zur Anstossstunde am Spielort."""
    day = kickoff_iso[:10]
    params = {
        "latitude": latitude, "longitude": longitude,
        "hourly": "temperature_2m,precipitation,wind_speed_10m,relative_humidity_2m",
        "start_date": day, "end_date": day, "timezone": "UTC",
    }
    payload = _get_json(f"{config.FORECAST_URL}?{urllib.parse.urlencode(params)}",
                        {"User-Agent": config.USER_AGENT}, config)
    hourly = payload.get("hourly") if isinstance(payload, dict) else None
    if not hourly or not hourly.get("time"):
        return None
    target_hour = kickoff_iso[:13]
    times = hourly["time"]
    index = next((i for i, value in enumerate(times) if value[:13] == target_hour), 0)
    return {
        "time": times[index],
        "temperature_c": hourly["temperature_2m"][index],
        "precipitation_mm": hourly["precipitation"][index],
        "wind_kmh": hourly["wind_speed_10m"][index],
        "humidity_pct": hourly["relative_humidity_2m"][index],
    }


def parse_lineup(team_block: dict) -> dict[str, object]:
    """Normiert einen Aufstellungsblock von API-Football."""
    def players(items: list) -> list[dict[str, object]]:
        return [{"player": entry["player"].get("name"), "number": entry["player"].get("number"),
                 "position": entry["player"].get("pos"), "grid": entry["player"].get("grid")}
                for entry in items or []]
    return {
        "team": team_block.get("team", {}).get("name"),
        "formation": team_block.get("formation"),
        "coach": team_block.get("coach", {}).get("name"),
        "start_xi": players(team_block.get("startXI")),
        "substitutes": players(team_block.get("substitutes")),
    }


def build_fixture_snapshot(fixture: dict, key: str, config: FetchConfig) -> dict[str, object]:
    """Sammelt Aufstellungen, Verletzungen und Wetter fuer ein Spiel."""
    fixture_id = fixture["fixture"]["id"]
    venue = fixture["fixture"].get("venue", {})
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    kickoff = fixture["fixture"].get("date", "")

    lineups = {parse_lineup(block)["team"]: parse_lineup(block)
               for block in api_football("fixtures/lineups", {"fixture": fixture_id}, key, config)}
    injuries: dict[str, list] = {home: [], away: []}
    for entry in api_football("injuries", {"fixture": fixture_id}, key, config):
        team_name = entry.get("team", {}).get("name")
        injuries.setdefault(team_name, []).append({
            "player": entry.get("player", {}).get("name"),
            "type": entry.get("player", {}).get("type"),
            "reason": entry.get("player", {}).get("reason"),
        })

    weather = None
    coordinates = geocode_city(venue.get("city") or venue.get("name") or "", config)
    if coordinates:
        weather = forecast_at(coordinates[0], coordinates[1], kickoff, config)

    return {
        "fixture_id": fixture_id, "kickoff": kickoff,
        "status": fixture["fixture"].get("status", {}).get("short"),
        "venue": {"name": venue.get("name"), "city": venue.get("city")},
        "home": home, "away": away,
        "lineups": lineups, "injuries": injuries, "weather": weather,
    }


def write_outputs(snapshots: list[dict[str, object]], date: str, config: FetchConfig) -> None:
    """Schreibt den JSON-Snapshot sowie flache Aufstellungs- und Verletzungs-CSVs."""
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"prematch_{date}.json").write_text(
        json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8")

    lineup_rows, injury_rows = [], []
    for snapshot in snapshots:
        for is_home, team in ((1, snapshot["home"]), (0, snapshot["away"])):
            block = snapshot["lineups"].get(team)
            if not block:
                continue
            for role, group in (("start", block["start_xi"]), ("sub", block["substitutes"])):
                for player in group:
                    lineup_rows.append({
                        "fixture_id": snapshot["fixture_id"], "kickoff": snapshot["kickoff"],
                        "team": team, "is_home": is_home, "formation": block["formation"],
                        "coach": block["coach"], "role": role, "player": player["player"],
                        "number": player["number"], "position": player["position"],
                    })
            for injury in snapshot["injuries"].get(team, []):
                injury_rows.append({"fixture_id": snapshot["fixture_id"], "team": team,
                                    "player": injury["player"], "type": injury["type"],
                                    "reason": injury["reason"]})
    _write_csv(output_dir / f"prematch_lineups_{date}.csv", lineup_rows,
               ["fixture_id", "kickoff", "team", "is_home", "formation", "coach",
                "role", "player", "number", "position"])
    _write_csv(output_dir / f"prematch_injuries_{date}.csv", injury_rows,
               ["fixture_id", "team", "player", "type", "reason"])


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = FetchConfig()
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = load_api_key(config)
    if not key:
        print("FEHLT  API-Football-Schluessel. Kostenlos unter api-sports.io anlegen, dann\n"
              f"       setze {config.KEY_ENV} oder schreibe ihn in {config.KEY_FILE}.")
        raise SystemExit(1)

    params = {"date": date, "league": os.environ.get("API_FOOTBALL_LEAGUE", config.DEFAULT_LEAGUE),
              "season": os.environ.get("API_FOOTBALL_SEASON", config.DEFAULT_SEASON)}
    fixtures = api_football("fixtures", params, key, config)
    print(f"  {len(fixtures)} Spiele am {date} (Liga {params['league']}, Saison {params['season']})", flush=True)
    snapshots = [build_fixture_snapshot(fixture, key, config) for fixture in fixtures]
    write_outputs(snapshots, date, config)
    print(f"  OK    Snapshot fuer {len(snapshots)} Spiele -> {config.OUTPUT_DIR}/prematch_{date}.*")


if __name__ == "__main__":
    main()
