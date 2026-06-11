"""Lädt die offiziellen WM-2026-Kader von Wikipedia (API, frei).

Die Seite ``2026 FIFA World Cup squads`` listet alle 48 Kader als
strukturierte ``nat fs g player``-Templates (Nummer, Position, Name,
Geburtsdatum, Länderspiele, Tore, Verein, Verbandsland des Vereins).
Dieses Skript parst den Wikitext in eine flache CSV -- Grundlage für
Club-Chemistry (HHI), Legionärs-Anteile und Ratings-Joins der echten
WM-Kader. Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import re
import urllib.request
from pathlib import Path


class SquadsWikiConfig:
    """Quelle und Zielpfad."""

    API_URL: str = (
        "https://en.wikipedia.org/w/api.php?action=parse"
        "&page=2026_FIFA_World_Cup_squads&prop=wikitext"
        "&format=json&formatversion=2"
    )
    USER_AGENT: str = "wm-quant-guru/1.0 (research; squad parser)"
    TIMEOUT_SECONDS: int = 60
    OUTPUT_DIR: str = "World Cup 2026 Squads (Wikipedia)"
    OUTPUT_FILE: str = "wc2026_squads.csv"


def fetch_wikitext(config: SquadsWikiConfig) -> str:
    """Lade den Wikitext der Kaderseite."""
    request = urllib.request.Request(
        config.API_URL, headers={"User-Agent": config.USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read())
    return payload["parse"]["wikitext"]


def strip_link(raw: str) -> str:
    """``[[Ziel|Anzeige]]`` bzw. ``[[Ziel]]`` -> Anzeige/Ziel."""
    match = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", raw)
    return (match.group(1) if match else raw).strip()


def parse_player(line: str) -> dict[str, str] | None:
    """Extrahiere die Felder eines ``nat fs g player``-Templates."""
    if "nat fs g player" not in line.lower():
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
    dob_match = re.search(
        r"[Bb]irth date and age2?\s*(?:\|df=yes)?\|(\d{4})\|(\d{1,2})\|(\d{1,2})", line
    )
    fields["date_of_birth"] = (
        f"{dob_match.group(1)}-{int(dob_match.group(2)):02d}-{int(dob_match.group(3)):02d}"
        if dob_match
        else ""
    )
    club_match = re.search(r"\|\s*club\s*=\s*(\[\[[^\]]+\]\])", line)
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
    """Lade, parse und schreibe die WM-2026-Kader."""
    config = SquadsWikiConfig()
    rows = parse_squads(fetch_wikitext(config))
    target = Path(config.OUTPUT_DIR) / config.OUTPUT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["group", "team", "number", "position", "name", "date_of_birth",
             "caps", "goals", "club", "club_country"]
        )
        writer.writerows(rows)
    teams = {row[1] for row in rows}
    print(f"{len(rows)} Spieler in {len(teams)} Teams -> {target}")


if __name__ == "__main__":
    main()
