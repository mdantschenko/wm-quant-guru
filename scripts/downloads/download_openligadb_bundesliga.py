"""Lädt Bundesliga 1+2 von OpenLigaDB (freie API, kein Key).

OpenLigaDB liefert je Saison alle Spiele beider Ligen mit Endergebnis,
Halbzeitstand und minutengenauen Toren (Schütze, Minute, Elfmeter,
Eigentor). Ergänzt football-data.co.uk (das keine Torschützen/Minuten
führt) und reicht für BL1 bis 2010 sauber zurück. Eine flache CSV je
Liga (Spielebene) plus eine Torschützen-CSV. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.request
from pathlib import Path


class OpenLigaConfig:
    """Endpunkt, Liga-/Saisonbereich und Zielpfade."""

    API_URL: str = "https://api.openligadb.de/getmatchdata/{league}/{season}"
    USER_AGENT: str = "wm-quant-guru/1.0 (research)"
    TIMEOUT_SECONDS: int = 40
    POLITE_DELAY_SECONDS: float = 0.4
    OUTPUT_DIR: str = "Data/Bundesliga Detail (OpenLigaDB)"
    LEAGUES: tuple[str, ...] = ("bl1", "bl2")
    FIRST_SEASON: int = 2010  # vollstaendige Abdeckung ab hier
    LAST_SEASON: int = 2025


def fetch_season(league: str, season: int, config: OpenLigaConfig) -> list[dict]:
    """Hole die Spiele einer Liga-Saison; leere Liste bei Fehler."""
    url = config.API_URL.format(league=league, season=season)
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            data = json.loads(response.read())
            return data if isinstance(data, list) else []
    except Exception:
        return []


def final_score(match: dict) -> tuple[str, str]:
    """Endstand (home, away) aus den matchResults; leer falls fehlend."""
    for result in match.get("matchResults", []):
        if result.get("resultName") == "Endergebnis":
            return str(result.get("pointsTeam1", "")), str(result.get("pointsTeam2", ""))
    return "", ""


def main() -> None:
    """Lade alle Liga-Saisons in eine Spiel- und eine Tor-CSV."""
    config = OpenLigaConfig()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    matches_path = output_dir / "bundesliga_matches.csv"
    goals_path = output_dir / "bundesliga_goals.csv"
    match_count = goal_count = 0
    with matches_path.open("w", encoding="utf-8", newline="") as m_file, \
            goals_path.open("w", encoding="utf-8", newline="") as g_file:
        m_writer = csv.writer(m_file)
        m_writer.writerow(["match_id", "league", "season", "matchday", "date_utc",
                           "home_team", "away_team", "home_goals", "away_goals",
                           "finished"])
        g_writer = csv.writer(g_file)
        g_writer.writerow(["match_id", "minute", "scorer", "score_home",
                           "score_away", "is_penalty", "is_own_goal"])
        for league in config.LEAGUES:
            for season in range(config.FIRST_SEASON, config.LAST_SEASON + 1):
                matches = fetch_season(league, season, config)
                time.sleep(config.POLITE_DELAY_SECONDS)
                for match in matches:
                    home_goals, away_goals = final_score(match)
                    m_writer.writerow([
                        match.get("matchID"), league, season,
                        match.get("group", {}).get("groupOrderID", ""),
                        match.get("matchDateTimeUTC", ""),
                        match.get("team1", {}).get("teamName", ""),
                        match.get("team2", {}).get("teamName", ""),
                        home_goals, away_goals,
                        match.get("matchIsFinished", ""),
                    ])
                    match_count += 1
                    for goal in match.get("goals", []):
                        g_writer.writerow([
                            match.get("matchID"), goal.get("matchMinute", ""),
                            goal.get("goalGetterName", ""),
                            goal.get("scoreTeam1", ""), goal.get("scoreTeam2", ""),
                            goal.get("isPenalty", ""), goal.get("isOwnGoal", ""),
                        ])
                        goal_count += 1
                print(f"  OK    {league}/{season}: {len(matches)} Spiele", flush=True)
    print(f"{match_count} Spiele, {goal_count} Tore -> {output_dir}")


if __name__ == "__main__":
    main()
