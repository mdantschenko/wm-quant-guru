"""Lädt ALLE Senior-Länderspiel-Wettbewerbe von FootyStats (alle Saisons).

Im Gegensatz zu Club-Ligen sind internationale Wettbewerbe über den
freien c-dl-Endpoint ohne Login ladbar. Die league-list-API liefert
~67 Senior-Wettbewerbe mit 188 Saisons -- darunter International
Friendlies 2015--2026 (Länderspiel-Quoten NACH dem Beat-The-Bookie-
Ende!), sämtliche WM-Qualifikationen aller Konföderationen, UEFA
Nations League, AFCON inkl. Qualifikation, Gold Cup und Arab Cup.
Resumierbar. Reine Standardbibliothek.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path


class InternationalsConfig:
    """Filter, Endpunkte und Zielstruktur."""

    LEAGUE_LIST_URL: str = "https://api.football-data-api.com/league-list?key=example"
    DOWNLOAD_URL: str = "https://footystats.org/c-dl.php?type=matches&comp="
    USER_AGENT: str = "Mozilla/5.0 (research; internationals downloader)"
    TIMEOUT_SECONDS: int = 60
    POLITE_DELAY_SECONDS: float = 1.2
    OUTPUT_ROOT: str = "Data/International Matches & Odds (FootyStats)"
    HEADER_MARKER: bytes = b"timestamp"

    # Jugend-/Frauen-Ausschluss und Club-Wettbewerbe unter
    # "International"-Label (Club World Cup, CONCACAF CL, ICC ...).
    EXCLUDE_TOKENS: tuple[str, ...] = (
        "Women", "WU", "U17", "U19", "U20", "U21", "U23", "Youth",
        "Club", "Champions League", "Champions Cup",
    )


def wanted(name: str, config: InternationalsConfig) -> bool:
    """Senior-Männer-Nationalmannschafts-Wettbewerb?"""
    return name.startswith("International") and not any(
        token in name for token in config.EXCLUDE_TOKENS
    )


def season_label(year: object) -> str:
    """20162018 -> '2016-2018', 2024 -> '2024'."""
    text = str(year)
    return f"{text[:4]}-{text[4:]}" if len(text) == 8 else text


def fetch(url: str, config: InternationalsConfig) -> bytes | None:
    """GET; None bei Fehler."""
    request = urllib.request.Request(
        url, headers={"User-Agent": config.USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return response.read()
    except Exception:
        return None


def main() -> None:
    """Lade alle Saisons aller passenden Wettbewerbe (skip vorhandene)."""
    config = InternationalsConfig()
    payload = fetch(config.LEAGUE_LIST_URL, config)
    if payload is None:
        raise SystemExit("league-list nicht ladbar")
    leagues = json.loads(payload).get("data", [])
    total = failed = 0
    for league in leagues:
        name = league.get("name", "")
        if not wanted(name, config):
            continue
        folder = Path(config.OUTPUT_ROOT) / name.replace("International ", "", 1)
        folder.mkdir(parents=True, exist_ok=True)
        for season in league.get("season", []):
            target = folder / f"{season_label(season.get('year'))}.csv"
            if target.exists():
                continue
            csv_payload = fetch(
                f"{config.DOWNLOAD_URL}{int(season['id'])}", config
            )
            time.sleep(config.POLITE_DELAY_SECONDS)
            if csv_payload is None or config.HEADER_MARKER not in csv_payload[:200]:
                failed += 1
                print(f"  FAIL  {name} {season_label(season.get('year'))}",
                      flush=True)
                continue
            target.write_bytes(csv_payload)
            total += 1
            match_count = csv_payload.count(b"\n") - 1
            print(f"  OK    {name} {season_label(season.get('year'))} "
                  f"({match_count} Spiele)", flush=True)
    print(f"\n{total} Saison-Dateien ({failed} fehlgeschlagen) "
          f"-> {config.OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
