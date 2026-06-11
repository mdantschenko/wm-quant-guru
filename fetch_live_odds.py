"""Holt Live-Quoten von The Odds API und loggt sie revisionssicher.

Betriebsskript für Modus A während der WM 2026 (Konzept: Betriebsregeln,
Quoten-Snapshot zu definiertem Zeitpunkt, Log vor Anpfiff). Jeder Lauf
speichert den rohen API-Response als zeitgestempelte JSON-Datei und
hängt die 1X2-Quoten flach an ein append-only CSV-Log an.

API-Key: kostenlos auf https://the-odds-api.com registrieren (Free Tier,
500 Requests/Monat) und als Umgebungsvariable THE_ODDS_API_KEY setzen --
der Key gehört nicht in Code oder Git.

Aufrufe:
    python fetch_live_odds.py sports   # verfügbare Wettbewerbe listen
    python fetch_live_odds.py odds     # Quoten-Snapshot ziehen (Default)

Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class OddsApiConfig:
    """Endpunkte, Marktparameter und Logpfade."""

    BASE_URL: str = "https://api.the-odds-api.com/v4"
    API_KEY_ENV_VAR: str = "THE_ODDS_API_KEY"
    TIMEOUT_SECONDS: int = 30

    SPORT_KEY: str = "soccer_fifa_world_cup"  # vor Turnierstart via 'sports' prüfen
    REGIONS: str = "eu"
    MARKETS: str = "h2h"
    ODDS_FORMAT: str = "decimal"

    OUTPUT_DIR: str = "Live Odds Snapshots (The Odds API)"
    RAW_SUBDIR: str = "raw"
    LOG_FILE: str = "odds_log.csv"
    LOG_COLUMNS: tuple[str, ...] = (
        "fetched_at_utc", "sport_key", "kickoff_utc", "home_team", "away_team",
        "bookmaker", "odds_home", "odds_draw", "odds_away",
    )


def read_api_key(config: OddsApiConfig) -> str:
    """Lies den API-Key aus der Umgebung; harter Abbruch mit Anleitung sonst."""
    api_key = os.environ.get(config.API_KEY_ENV_VAR, "").strip()
    if not api_key:
        sys.exit(
            f"Kein API-Key gefunden. Kostenlos registrieren auf "
            f"https://the-odds-api.com und setzen mit:\n"
            f'  $env:{config.API_KEY_ENV_VAR} = "<dein-key>"   (PowerShell)'
        )
    return api_key


def api_get(path: str, params: str, config: OddsApiConfig) -> tuple[object, dict[str, str]]:
    """GET gegen die API; gibt (JSON, relevante Header) zurück."""
    url = f"{config.BASE_URL}/{path}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "wm-quant-guru"})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            quota = {
                "remaining": response.headers.get("x-requests-remaining", "?"),
                "used": response.headers.get("x-requests-used", "?"),
            }
            return json.loads(response.read()), quota
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:200]
        sys.exit(f"API-Fehler HTTP {error.code}: {detail}")


def list_sports(config: OddsApiConfig) -> None:
    """Liste alle Fußball-Wettbewerbe (zur Prüfung des Sport-Keys)."""
    api_key = read_api_key(config)
    sports, quota = api_get("sports", f"all=true&apiKey={api_key}", config)
    for sport in sports:
        if str(sport.get("key", "")).startswith("soccer"):
            print(f"  {sport['key']:<40} {sport.get('title', '')}")
    print(f"\nQuota: {quota['remaining']} Requests übrig.")


def flatten_event(event: dict, fetched_at: str, config: OddsApiConfig) -> list[list[str]]:
    """Wandle ein API-Event in flache Logzeilen (eine je Buchmacher) um."""
    home, away = event.get("home_team", ""), event.get("away_team", "")
    rows: list[list[str]] = []
    for bookmaker in event.get("bookmakers", []):
        prices: dict[str, str] = {}
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                prices[outcome.get("name", "")] = str(outcome.get("price", ""))
        rows.append([
            fetched_at, config.SPORT_KEY, event.get("commence_time", ""),
            home, away, bookmaker.get("key", ""),
            prices.get(home, ""), prices.get("Draw", ""), prices.get(away, ""),
        ])
    return rows


def fetch_odds(config: OddsApiConfig) -> None:
    """Ziehe einen Quoten-Snapshot, speichere Rohdaten und Log-Zeilen."""
    api_key = read_api_key(config)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    events, quota = api_get(
        f"sports/{config.SPORT_KEY}/odds",
        f"regions={config.REGIONS}&markets={config.MARKETS}"
        f"&oddsFormat={config.ODDS_FORMAT}&apiKey={api_key}",
        config,
    )
    raw_dir = Path(config.OUTPUT_DIR) / config.RAW_SUBDIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = fetched_at.replace(":", "").replace("-", "")
    raw_path = raw_dir / f"odds_{config.SPORT_KEY}_{stamp}.json"
    raw_path.write_text(json.dumps(events, indent=1), encoding="utf-8")

    log_path = Path(config.OUTPUT_DIR) / config.LOG_FILE
    is_new_log = not log_path.exists()
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if is_new_log:
            writer.writerow(config.LOG_COLUMNS)
        row_count = 0
        for event in events:
            for row in flatten_event(event, fetched_at, config):
                writer.writerow(row)
                row_count += 1
    print(f"{len(events)} Spiele, {row_count} Quotenzeilen -> {log_path}")
    print(f"Roh-Snapshot: {raw_path}")
    print(f"Quota: {quota['remaining']} Requests übrig (Free Tier: 500/Monat).")


def main() -> None:
    """CLI-Einstieg: Modus 'odds' (Default) oder 'sports'."""
    config = OddsApiConfig()
    mode = sys.argv[1] if len(sys.argv) > 1 else "odds"
    if mode == "sports":
        list_sports(config)
    else:
        fetch_odds(config)


if __name__ == "__main__":
    main()
