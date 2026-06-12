"""Misst historische Reddit-Aufmerksamkeit je WM-Team (PullPush-Archiv).

Zaehlt fuer jedes WM-2026-Team die r/soccer-Submissions in einem
konfigurierbaren historischen Fenster (Default: WM-2022-Turnierfenster),
samt mittlerem Score -- ein Fan-Aufmerksamkeits-Proxy ausserhalb der
Wettmaerkte, nutzbar fuer Backtests.

EINSCHRAENKUNG: Live-Daten sind keyless nicht verfuegbar -- reddit.com
blockt anonyme JSON-Suchen (HTTP 403), und das freie PullPush-Archiv
hinkt der Gegenwart Monate hinterher. Fuer Live-Aufmerksamkeit dienen
die Wikipedia-Pageviews; echtes Live-Reddit braeuchte eine (kostenlose)
OAuth-App. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class RedditConfig:
    """Endpunkt, historisches Fenster und Logpfad."""

    API_URL: str = "https://api.pullpush.io/reddit/search/submission/"
    SUBREDDIT: str = "soccer"
    # Historisches Analysefenster (ISO-Daten, inklusiv).
    WINDOW_START: str = "2022-11-20"  # WM-2022-Eroeffnung
    WINDOW_END: str = "2022-12-18"    # WM-2022-Finale
    PAGE_SIZE: int = 100  # PullPush-Maximum; zaehlt bis zu dieser Obergrenze
    TIMEOUT_SECONDS: int = 40
    POLITE_DELAY_SECONDS: float = 1.0
    USER_AGENT: str = "wm-quant-guru/1.0 (research; attention history)"
    TEAMS_FILE: str = "World Cup 2026 (FootyStats)/teams.csv"
    LOG_FILE: str = "Alternative Data (Reddit)/reddit_activity_log.csv"


def team_names(config: RedditConfig) -> list[str]:
    """Lies die 48 Teamnamen der WM 2026 (FootyStats-Suffix entfernen)."""
    with Path(config.TEAMS_FILE).open(encoding="utf-8", newline="") as handle:
        return sorted({
            re.sub(r"\s+(?:Men'?s\s+)?National\s+Team$", "",
                   row["team_name"].strip(), flags=re.IGNORECASE)
            for row in csv.DictReader(handle)
        })


def iso_to_epoch(day: str) -> int:
    """ISO-Datum -> Unix-Epoche (UTC, Tagesbeginn)."""
    return int(
        datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()
    )


def fetch_submissions(team: str, config: RedditConfig) -> list[dict] | None:
    """Hole bis zu PAGE_SIZE Submissions im historischen Fenster zum Team."""
    url = (
        f"{config.API_URL}?subreddit={config.SUBREDDIT}"
        f"&q={urllib.parse.quote(team)}"
        f"&after={iso_to_epoch(config.WINDOW_START)}"
        f"&before={iso_to_epoch(config.WINDOW_END) + 86400}"
        f"&size={config.PAGE_SIZE}"
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": config.USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read()).get("data", [])
    except Exception:
        return None


def main() -> None:
    """Ziehe einen Aufmerksamkeits-Snapshot aller 48 Teams."""
    config = RedditConfig()
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    target = Path(config.LOG_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    is_new = not target.exists()
    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(["fetched_at_utc", "team", "window_days",
                             "n_submissions", "avg_score", "max_score"])
        for team in team_names(config):
            submissions = fetch_submissions(team, config)
            time.sleep(config.POLITE_DELAY_SECONDS)
            if submissions is None:
                print(f"  FAIL  {team}")
                continue
            scores = [int(s.get("score") or 0) for s in submissions]
            writer.writerow(
                [fetched_at, team, config.WINDOW_DAYS, len(scores),
                 round(sum(scores) / len(scores), 1) if scores else 0,
                 max(scores) if scores else 0]
            )
            print(f"  OK    {team}: {len(scores)} Posts")
    print(f"-> {target}")


if __name__ == "__main__":
    main()
