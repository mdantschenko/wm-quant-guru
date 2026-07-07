"""Holt tagesgenaue Trainerhistorien aller Nationalteams (Wikidata SPARQL).

Wikidata pflegt je Nationalteam die Eigenschaft P286 (head coach) mit
Start-/End-Qualifiern -- die sauberste freie Quelle für Trainer-Features:
Amtszeit zum Turnierstart (Trainer-Frische, Lopetegui-Effekt),
Trainerwechsel-Dichte, Interimstrainer. Team-Q-IDs werden über die
Wikipedia-Artikel aufgelöst; danach genügt EINE SPARQL-Abfrage für alle
Teams. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


class CoachHistoryConfig:
    """Endpunkte, Quellen und Zielpfad."""

    WIKIPEDIA_API: str = "https://en.wikipedia.org/w/api.php"
    SPARQL_URL: str = "https://query.wikidata.org/sparql"
    USER_AGENT: str = "wm-quant-guru/1.0 (research; coach history)"
    TIMEOUT_SECONDS: int = 90
    POLITE_DELAY_SECONDS: float = 1.0
    BATCH_SIZE: int = 50  # Wikipedia-API: max. Titel je Abfrage

    CLIMATE_FILE: str = "Data/Computed Features/country_climate.csv"
    OUTPUT_FILE: str = "Data/Tournament Squads (Wikipedia)/coach_history.csv"

    TITLE_OVERRIDES: dict[str, str] = {
        "United States": "United States men's national soccer team",
        "Ireland": "Republic of Ireland national football team",
    }


def api_json(url: str, config: CoachHistoryConfig) -> dict | None:
    """GET mit JSON-Antwort; None bei Fehler."""
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except Exception:
        return None


def team_titles(config: CoachHistoryConfig) -> dict[str, str]:
    """Land -> Wikipedia-Artikeltitel des Nationalteams."""
    with Path(config.CLIMATE_FILE).open(encoding="utf-8", newline="") as handle:
        countries = sorted(row["country"] for row in csv.DictReader(handle))
    return {
        country: config.TITLE_OVERRIDES.get(
            country, f"{country} national football team"
        )
        for country in countries
    }


def resolve_qids(
    titles: dict[str, str], config: CoachHistoryConfig
) -> dict[str, str]:
    """Wikipedia-Titel -> Wikidata-Q-IDs (gebatcht, folgt Redirects)."""
    qids: dict[str, str] = {}
    title_to_country = {title: country for country, title in titles.items()}
    all_titles = list(title_to_country)
    for start in range(0, len(all_titles), config.BATCH_SIZE):
        batch = all_titles[start:start + config.BATCH_SIZE]
        url = (
            f"{config.WIKIPEDIA_API}?action=query&prop=pageprops"
            f"&ppprop=wikibase_item&redirects=1&format=json&formatversion=2"
            f"&titles={urllib.parse.quote('|'.join(batch))}"
        )
        data = api_json(url, config)
        time.sleep(config.POLITE_DELAY_SECONDS)
        if data is None:
            continue
        redirect_map = {
            r["to"]: r["from"]
            for r in data.get("query", {}).get("redirects", [])
        }
        for page in data.get("query", {}).get("pages", []):
            qid = page.get("pageprops", {}).get("wikibase_item")
            title = page.get("title", "")
            original = redirect_map.get(title, title)
            country = title_to_country.get(original)
            if qid and country:
                qids[country] = qid
    return qids


def fetch_coach_statements(
    qids: dict[str, str], config: CoachHistoryConfig
) -> list[list[str]]:
    """Eine SPARQL-Abfrage: alle P286-Trainer mit Start/Ende je Team."""
    values = " ".join(f"wd:{qid}" for qid in qids.values())
    qid_to_country = {qid: country for country, qid in qids.items()}
    query = f"""SELECT ?team ?coachLabel ?start ?end WHERE {{
      VALUES ?team {{ {values} }}
      ?team p:P286 ?statement.
      ?statement ps:P286 ?coach.
      OPTIONAL {{ ?statement pq:P580 ?start. }}
      OPTIONAL {{ ?statement pq:P582 ?end. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}"""
    data = api_json(
        f"{config.SPARQL_URL}?format=json&query={urllib.parse.quote(query)}",
        config,
    )
    rows: list[list[str]] = []
    for binding in (data or {}).get("results", {}).get("bindings", []):
        team_qid = binding["team"]["value"].rsplit("/", 1)[-1]
        rows.append(
            [qid_to_country.get(team_qid, team_qid),
             binding.get("coachLabel", {}).get("value", ""),
             binding.get("start", {}).get("value", "")[:10],
             binding.get("end", {}).get("value", "")[:10]]
        )
    return rows


def main() -> None:
    """Löse Q-IDs auf, hole Trainerhistorien und schreibe eine CSV."""
    config = CoachHistoryConfig()
    titles = team_titles(config)
    qids = resolve_qids(titles, config)
    missing = sorted(set(titles) - set(qids))
    if missing:
        print(f"  Ohne Q-ID ({len(missing)}): {', '.join(missing[:8])} ...")
    rows = fetch_coach_statements(qids, config)
    rows.sort(key=lambda r: (r[0], r[2]))
    target = Path(config.OUTPUT_FILE)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "coach", "start_date", "end_date"])
        writer.writerows(rows)
    print(f"{len(rows)} Trainer-Amtszeiten für {len(qids)} Teams -> {target}")


if __name__ == "__main__":
    main()
