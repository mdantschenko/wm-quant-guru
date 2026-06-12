"""Extrahiert die WM-2026-Team-Basecamps aus dem Wikipedia-Hauptartikel.

Der Abschnitt "Team base camps" listet je Team den Standort des
Trainingsquartiers -- Grundlage fuer ein realistisches Reisemodell
(Basecamp -> Spielort -> Basecamp statt Stadion -> Stadion).
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


class BasecampConfig:
    """Quelle und Zielpfad."""

    PAGE: str = "2026 FIFA World Cup"
    API_URL: str = (
        "https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext"
        "&format=json&formatversion=2&page="
    )
    USER_AGENT: str = "wm-quant-guru/1.0 (research; base camps)"
    TIMEOUT_SECONDS: int = 60
    OUTPUT_FILE: str = "Data/World Cup 2026 (FootyStats)/base_camps.csv"


def strip_links(raw: str) -> str:
    """Alle ``[[Ziel|Anzeige]]``-Links durch ihre Anzeige ersetzen."""
    return re.sub(
        r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", raw
    ).strip()


def basecamp_section(wikitext: str) -> str:
    """Den Abschnitt 'Team base camps' (bis zur naechsten Ueberschrift)."""
    match = re.search(
        r"==+\s*Team base camps\s*==+(.*?)(?:\n==[^=])", wikitext, re.DOTALL
    )
    return match.group(1) if match else ""


def parse_rows(section: str) -> list[tuple[str, str]]:
    """(team, basecamp_ort) aus Tabellen-/Listenzeilen des Abschnitts."""
    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        flag = re.search(r"\{\{(?:fb|flagicon)\|([A-Za-z ]{2,20})\}\}", line)
        if not flag:
            continue
        rest = line[flag.end():]
        location = strip_links(
            re.sub(r"\{\{[^}]*\}\}|<[^>]+>|^[|;:*\s]+", "", rest)
        ).strip(" |–-")
        team = strip_links(line[:flag.end()])
        team_link = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", line)
        team_name = team_link.group(1) if team_link else flag.group(1)
        if location:
            rows.append((team_name.strip(), location))
    return rows


def main() -> None:
    """Lade den Artikel, parse die Basecamps und schreibe eine CSV."""
    config = BasecampConfig()
    request = urllib.request.Request(
        config.API_URL + urllib.parse.quote(config.PAGE),
        headers={"User-Agent": config.USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
        wikitext = json.loads(response.read())["parse"]["wikitext"]
    rows = parse_rows(basecamp_section(wikitext))
    target = Path(config.OUTPUT_FILE)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "base_camp"])
        writer.writerows(sorted(rows))
    print(f"{len(rows)} Basecamps -> {target}")


if __name__ == "__main__":
    main()
