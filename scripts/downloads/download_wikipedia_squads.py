"""Lädt offizielle Turnier-Kader von Wikipedia (API, frei) -- alle Turniere.

Die ``...squads``-Seiten listen Kader als strukturierte
``nat fs (g) player``-Templates: Nummer, Position, Name, Geburtsdatum,
Länderspiele, Tore, Verein und Verbandsland des Vereins. Dieses Skript
parst alle konfigurierten Turniere in je eine flache CSV -- die
verlässliche Quelle für Club-Chemistry (HHI) und Legionärs-Anteile
(die FootyStats-Kaderlisten führen als \"Current Club\" nur das
Nationalteam). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


class WikiSquadsConfig:
    """Seiten, Ausgabeordner und API-Parameter."""

    API_URL: str = (
        "https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext"
        "&format=json&formatversion=2&page="
    )
    USER_AGENT: str = "wm-quant-guru/1.0 (research; squad parser)"
    TIMEOUT_SECONDS: int = 60
    POLITE_DELAY_SECONDS: float = 0.5
    OUTPUT_DIR: str = "Data/Tournament Squads (Wikipedia)"

    # Beschrifteter Dateiname -> Wikipedia-Seitentitel.
    PAGES: dict[str, str] = {
        "World Cup 2014": "2014 FIFA World Cup squads",
        "World Cup 2018": "2018 FIFA World Cup squads",
        "World Cup 2022": "2022 FIFA World Cup squads",
        "World Cup 2026": "2026 FIFA World Cup squads",
        "Euro 2016": "UEFA Euro 2016 squads",
        "Euro 2020 (EM 2021)": "UEFA Euro 2020 squads",
        "Euro 2024": "UEFA Euro 2024 squads",
        "Copa America 2019": "2019 Copa América squads",
        "Copa America 2021": "2021 Copa América squads",
        "Copa America 2024": "2024 Copa América squads",
    }


def fetch_wikitext(page: str, config: WikiSquadsConfig) -> str | None:
    """Lade den Wikitext einer Seite; None bei Fehler."""
    request = urllib.request.Request(
        config.API_URL + urllib.parse.quote(page),
        headers={"User-Agent": config.USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
        return payload["parse"]["wikitext"]
    except Exception:
        return None


def strip_link(raw: str) -> str:
    """``[[Ziel|Anzeige]]`` bzw. ``[[Ziel]]`` -> Anzeige/Ziel; sonst Rohtext."""
    match = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", raw)
    return (match.group(1) if match else raw).strip().strip("}").strip()


def parse_player(line: str) -> dict[str, str] | None:
    """Extrahiere die Felder eines Kader-Templates.

    Unterstützt ``nat fs g player``/``nat fs player`` (neuere Seiten)
    und ``National football squad player`` (ältere Seiten, z. B. 2014).
    """
    if not re.search(
        r"\{\{\s*(?:nat fs (?:g )?player|national football squad player)",
        line,
        flags=re.IGNORECASE,
    ):
        return None
    fields: dict[str, str] = {}
    for key, pattern in (
        ("number", r"\|\s*no\s*=\s*(\d+)"),
        ("position", r"\|\s*pos\s*=\s*([A-Z]{2})"),
        ("caps", r"\|\s*caps\s*=\s*(\d+)"),
        ("goals", r"\|\s*goals\s*=\s*(\d+)"),
        ("club_country", r"\|\s*clubnat\s*=\s*([A-Za-z]{3})"),
    ):
        match = re.search(pattern, line)
        fields[key] = match.group(1) if match else ""
    name_match = re.search(r"\|\s*name\s*=\s*(.*?)\s*\|\s*age\s*=", line)
    fields["name"] = strip_link(name_match.group(1)) if name_match else ""
    # "Birth date and age" enthaelt EIN Datumstripel (das Geburtsdatum),
    # "Birth date and age2" ZWEI (Referenzdatum + Geburtsdatum) -> immer
    # das LETZTE Tripel im age-Segment nehmen.
    age_match = re.search(r"\|\s*age\s*=\s*(\{\{[^{}]*\}\})", line)
    triples = (
        re.findall(r"(\d{4})\|(\d{1,2})\|(\d{1,2})", age_match.group(1))
        if age_match
        else []
    )
    fields["date_of_birth"] = (
        f"{triples[-1][0]}-{int(triples[-1][1]):02d}-{int(triples[-1][2]):02d}"
        if triples
        else ""
    )
    # Vollstaendigen Wikilink (darf '|' enthalten) ODER Klartext greifen.
    club_match = re.search(
        r"\|\s*club\s*=\s*(\[\[[^\]]*\]\]|[^|\n}]+)", line
    )
    fields["club"] = strip_link(club_match.group(1)) if club_match else ""
    return fields if fields["name"] else None


def parse_squads(wikitext: str) -> list[list[str]]:
    """Durchlaufe den Wikitext und sammle (gruppe, team, spielerfelder)."""
    rows: list[list[str]] = []
    group = ""
    team = ""
    for line in wikitext.splitlines():
        group_match = re.match(r"^==\s*(Group [A-L])\s*==\s*$", line)
        if group_match:
            group = group_match.group(1)
            continue
        team_match = re.match(r"^===\s*([^=]+?)\s*===\s*$", line)
        if team_match:
            team = team_match.group(1)
            continue
        player = parse_player(line)
        if player and team:
            rows.append(
                [group, team, player["number"], player["position"], player["name"],
                 player["date_of_birth"], player["caps"], player["goals"],
                 player["club"], player["club_country"]]
            )
    return rows


def main() -> None:
    """Lade und parse alle konfigurierten Turnier-Kader."""
    config = WikiSquadsConfig()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    for label, page in config.PAGES.items():
        target = output_dir / f"{label}.csv"
        if target.exists():
            print(f"  SKIP  {label}")
            continue
        wikitext = fetch_wikitext(page, config)
        time.sleep(config.POLITE_DELAY_SECONDS)
        if wikitext is None:
            print(f"  FAIL  {label} ({page})")
            continue
        rows = parse_squads(wikitext)
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["group", "team", "number", "position", "name",
                             "date_of_birth", "caps", "goals", "club",
                             "club_country"])
            writer.writerows(rows)
        teams = {row[1] for row in rows}
        print(f"  OK    {label}: {len(rows)} Spieler, {len(teams)} Teams")


if __name__ == "__main__":
    main()
