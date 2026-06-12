"""Holt News-Volumen und -Tonalität je WM-2026-Team (GDELT, frei).

GDELT indiziert weltweite Nachrichten; die DOC-API liefert Zeitreihen
des Artikelvolumens und der mittleren Tonalität zu einer Suchanfrage.
Negative Ton-Spikes um ein Nationalteam (Verbandskrisen, Skandale,
Trainerentlassungen) sind ein Signal ausserhalb der Wettmaerkte.
Rate-Limit der API: eine Anfrage pro 5 Sekunden. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


class GdeltConfig:
    """Endpunkt, Abfrageparameter und Zielpfad."""

    API_URL: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    TIMESPAN: str = "12months"
    QUERY_TEMPLATE: str = '"{team} national team" sourcelang:eng'
    RATE_LIMIT_SECONDS: float = 5.2
    TIMEOUT_SECONDS: int = 40
    TEAMS_FILE: str = "Data/World Cup 2026 (FootyStats)/teams.csv"
    OUTPUT_FILE: str = "Data/Alternative Data (GDELT News Tone)/gdelt_news_teams.csv"


def api_series(query: str, mode: str, config: GdeltConfig) -> dict[str, float]:
    """Hole eine GDELT-Zeitreihe (datum -> wert); leer bei Fehler."""
    url = (
        f"{config.API_URL}?query={urllib.parse.quote(query)}"
        f"&mode={mode}&timespan={config.TIMESPAN}&format=json"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "wm-quant-guru"})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
    except Exception:
        return {}
    series: dict[str, float] = {}
    for timeline in payload.get("timeline", []):
        for point in timeline.get("data", []):
            series[point["date"][:8]] = float(point["value"])
    return series


def main() -> None:
    """Hole Volumen + Tonalität für alle 48 Teams und schreibe eine CSV."""
    config = GdeltConfig()
    with Path(config.TEAMS_FILE).open(encoding="utf-8", newline="") as handle:
        # FootyStats-Suffix "(Men's) National Team" entfernen.
        teams = sorted({
            re.sub(r"\s+(?:Men'?s\s+)?National\s+Team$", "",
                   row["team_name"].strip(), flags=re.IGNORECASE)
            for row in csv.DictReader(handle)
        })
    target = Path(config.OUTPUT_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "date", "article_volume", "avg_tone"])
        for team in teams:
            query = config.QUERY_TEMPLATE.format(team=team)
            volume = api_series(query, "timelinevolraw", config)
            time.sleep(config.RATE_LIMIT_SECONDS)
            tone = api_series(query, "timelinetone", config)
            time.sleep(config.RATE_LIMIT_SECONDS)
            for day in sorted(set(volume) | set(tone)):
                writer.writerow(
                    [team, day, volume.get(day, ""), tone.get(day, "")]
                )
                written += 1
            print(f"  OK    {team}: {len(volume)} Volumen-, {len(tone)} Ton-Punkte",
                  flush=True)
    print(f"{written} Zeilen -> {target}")


if __name__ == "__main__":
    main()
