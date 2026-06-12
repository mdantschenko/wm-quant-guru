"""Holt Wikipedia-Pageview-Zeitreihen für WM-2026-Teams und -Spieler.

Tägliche Artikelaufrufe (offizielle Wikimedia-API, frei) sind ein
Aufmerksamkeits-Index: Spikes bei Spielerartikeln markieren Verletzungen,
Sperren, Form-Hypes oder Skandale -- oft bevor sie in Quoten eingepreist
sind. Teams: Tageswerte seit 2018 (Backtest-Historie). Spieler: die
Artikel-Linkziele werden direkt aus dem Wikitext der Kaderseite gelesen
(keine Namens-Heuristik). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path


class PageviewsConfig:
    """Endpunkte, Zeitfenster und Zielpfade."""

    PAGEVIEWS_URL: str = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        "en.wikipedia/all-access/user/{article}/daily/{start}/{end}"
    )
    SQUADS_API: str = (
        "https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext"
        "&format=json&formatversion=2&page=2026%20FIFA%20World%20Cup%20squads"
    )
    USER_AGENT: str = "wm-quant-guru/1.0 (research; pageview features)"
    TIMEOUT_SECONDS: int = 30
    POLITE_DELAY_SECONDS: float = 0.25  # REST-API drosselt Bursts (429)
    RETRY_WAIT_SECONDS: float = 3.0

    TEAMS_FILE: str = "Data/World Cup 2026 (FootyStats)/teams.csv"
    OUTPUT_DIR: str = "Data/Alternative Data (Wikipedia Pageviews)"
    TEAM_START: str = "20180101"
    PLAYER_START: str = "20250101"

    TEAM_TITLE_OVERRIDES: dict[str, str] = {
        "United States": "United States men's national soccer team",
        "USA": "United States men's national soccer team",
        "Iran": "Iran national football team",
        "Ireland": "Republic of Ireland national football team",
    }


def api_bytes(url: str, config: PageviewsConfig) -> bytes | None:
    """GET mit einem Retry (Drosselung); None bei endgueltigem Fehler."""
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(
                request, timeout=config.TIMEOUT_SECONDS
            ) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None  # Artikel existiert nicht -> kein Retry
        except Exception:
            pass
        if attempt == 0:
            time.sleep(config.RETRY_WAIT_SECONDS)
    return None


def daily_views(
    article: str, start: str, end: str, config: PageviewsConfig
) -> list[tuple[str, int]] | None:
    """Tages-Pageviews eines Artikels; None falls Artikel unbekannt."""
    quoted = urllib.parse.quote(article.replace(" ", "_"), safe="")
    payload = api_bytes(
        config.PAGEVIEWS_URL.format(article=quoted, start=start, end=end), config
    )
    if payload is None:
        return None
    items = json.loads(payload).get("items", [])
    return [(item["timestamp"][:8], item["views"]) for item in items]


def clean_team_name(raw: str) -> str:
    """FootyStats-Suffixe entfernen (\"Turkey National Team\" -> \"Turkey\")."""
    return re.sub(
        r"\s+(?:Men'?s\s+)?National\s+Team$", "", raw.strip(), flags=re.IGNORECASE
    )


def squad_player_articles(config: PageviewsConfig) -> list[tuple[str, str]]:
    """(team, artikel_linkziel) aller Spieler aus der WM-2026-Kaderseite."""
    payload = api_bytes(config.SQUADS_API, config)
    if payload is None:
        raise SystemExit("Kaderseite nicht ladbar (Wikipedia-Drosselung?) -- "
                         "bitte erneut ausfuehren.")
    wikitext = json.loads(payload)["parse"]["wikitext"]
    pairs: list[tuple[str, str]] = []
    team = ""
    for line in wikitext.splitlines():
        team_match = re.match(r"^===\s*([^=]+?)\s*===\s*$", line)
        if team_match:
            team = team_match.group(1)
            continue
        name_match = re.search(r"\|\s*name\s*=\s*\[\[([^|\]]+)", line)
        if name_match and team:
            pairs.append((team, name_match.group(1).strip()))
    return pairs


def existing_keys(target: Path, column: str) -> set[str]:
    """Bereits geladene Schluessel (Team/Artikel) einer Ausgabe-CSV."""
    if not target.exists():
        return set()
    with target.open(encoding="utf-8", newline="") as handle:
        return {row[column] for row in csv.DictReader(handle)}


def append_series(
    target: Path, rows: list[list[object]], header: list[str]
) -> None:
    """Haenge Zeitreihen-Zeilen an eine CSV an (Header nur bei Neuanlage)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    is_new = not target.exists()
    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    """Hole Team- und Spieler-Pageviews (resumierbar: vorhandene skippen)."""
    config = PageviewsConfig()
    end = date.today().strftime("%Y%m%d")
    output_dir = Path(config.OUTPUT_DIR)
    header = ["team", "article", "date", "views"]

    teams_target = output_dir / "wikipedia_pageviews_teams.csv"
    done_teams = existing_keys(teams_target, "team")
    team_rows: list[list[object]] = []
    missing = 0
    with Path(config.TEAMS_FILE).open(encoding="utf-8", newline="") as handle:
        teams = sorted(
            {clean_team_name(row["team_name"]) for row in csv.DictReader(handle)}
        )
    for team in teams:
        if team in done_teams:
            continue
        article = config.TEAM_TITLE_OVERRIDES.get(
            team, f"{team} national football team"
        )
        series = daily_views(article, config.TEAM_START, end, config)
        time.sleep(config.POLITE_DELAY_SECONDS)
        if series is None:
            missing += 1
            print(f"  SKIP Team {team} ({article})")
            continue
        team_rows.extend([team, article, day, views] for day, views in series)
    append_series(teams_target, team_rows, header)
    print(f"Teams: +{len(team_rows)} Tageswerte ({missing} fehlend, "
          f"{len(done_teams)} bereits vorhanden)", flush=True)

    players_target = output_dir / "wikipedia_pageviews_players.csv"
    done_articles = existing_keys(players_target, "article")
    player_rows: list[list[object]] = []
    missing = 0
    players = [
        (team, article)
        for team, article in squad_player_articles(config)
        if article not in done_articles
    ]
    for index, (team, article) in enumerate(players, start=1):
        series = daily_views(article, config.PLAYER_START, end, config)
        time.sleep(config.POLITE_DELAY_SECONDS)
        if series is None:
            missing += 1
            continue
        player_rows.extend(
            [team, article, day, views] for day, views in series
        )
        if index % 100 == 0:
            print(f"  ... {index}/{len(players)} Spieler", flush=True)
    append_series(players_target, player_rows, header)
    print(f"Spieler: +{len(player_rows)} Tageswerte ({missing} fehlend/ohne "
          f"Artikel, {len(done_articles)} bereits vorhanden)")


if __name__ == "__main__":
    main()
