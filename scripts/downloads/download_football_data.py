"""Lädt historische Quoten/Ergebnisse von football-data.co.uk.

Reine Standardbibliothek (kein requests/pandas nötig). Die Original-CSVs
werden unverändert in beschriftete Ordner gelegt; die Überführung in das
kanonische Match-Schema ist ein späterer Pipeline-Schritt, nicht Teil des
Downloads.

Wichtige Einschränkungen der Quelle (siehe README im Zielordner):
* Nur nationale Vereinsligen, KEINE WM-/EM-/Turnierquoten.
* Closing-Quoten (Spalten mit 'C', z. B. PSCH) nur in jüngeren Saisons.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path


class FootballDataConfig:
    """Zugriffs- und Pfadkonstanten für football-data.co.uk."""

    MAIN_BASE_URL: str = "https://www.football-data.co.uk/mmz4281"
    EXTRA_BASE_URL: str = "https://www.football-data.co.uk/new"
    USER_AGENT: str = "Mozilla/5.0 (research; football-data downloader)"
    TIMEOUT_SECONDS: int = 30
    POLITE_DELAY_SECONDS: float = 0.5

    FIRST_SEASON_START: int = 1993  # aelteste football-data-Saison (93/94)
    LAST_SEASON_START: int = 2025   # laufende Saison 2025/26

    OUTPUT_ROOT: str = "Data/Football Betting Odds (football-data.co.uk)"

    # Hauptligen: Kürzel -> beschrifteter Ordnername (Saison-Einzeldateien).
    MAIN_LEAGUES: dict[str, str] = {
        "E0": "E0 (England - Premier League)",
        "E1": "E1 (England - Championship)",
        "E2": "E2 (England - League One)",
        "E3": "E3 (England - League Two)",
        "EC": "EC (England - National League)",
        "SC0": "SC0 (Scotland - Premiership)",
        "SC1": "SC1 (Scotland - Championship)",
        "SC2": "SC2 (Scotland - League One)",
        "SC3": "SC3 (Scotland - League Two)",
        "D1": "D1 (Germany - Bundesliga)",
        "D2": "D2 (Germany - 2. Bundesliga)",
        "I1": "I1 (Italy - Serie A)",
        "I2": "I2 (Italy - Serie B)",
        "SP1": "SP1 (Spain - La Liga)",
        "SP2": "SP2 (Spain - Segunda Division)",
        "F1": "F1 (France - Ligue 1)",
        "F2": "F2 (France - Ligue 2)",
        "N1": "N1 (Netherlands - Eredivisie)",
        "B1": "B1 (Belgium - Jupiler Pro League)",
        "P1": "P1 (Portugal - Primeira Liga)",
        "T1": "T1 (Turkey - Super Lig)",
        "G1": "G1 (Greece - Super League)",
    }

    # Extra-Ligen: je eine kombinierte Datei (anderes Spaltenschema!).
    EXTRA_LEAGUES: dict[str, str] = {
        "ARG": "ARG (Argentina - Primera Division)",
        "AUT": "AUT (Austria - Bundesliga)",
        "BRA": "BRA (Brazil - Serie A)",
        "CHN": "CHN (China - Super League)",
        "DNK": "DNK (Denmark - Superliga)",
        "FIN": "FIN (Finland - Veikkausliiga)",
        "IRL": "IRL (Ireland - Premier Division)",
        "JPN": "JPN (Japan - J1 League)",
        "MEX": "MEX (Mexico - Liga MX)",
        "NOR": "NOR (Norway - Eliteserien)",
        "POL": "POL (Poland - Ekstraklasa)",
        "ROU": "ROU (Romania - Liga I)",
        "RUS": "RUS (Russia - Premier League)",
        "SWE": "SWE (Sweden - Allsvenskan)",
        "SWZ": "SWZ (Switzerland - Super League)",
        "USA": "USA (USA - MLS)",
    }


def season_code(start_year: int) -> str:
    """Bilde den Saisoncode, z. B. 2013 -> '1314', 2000 -> '0001'."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def season_label(start_year: int) -> str:
    """Beschrifteter Dateiname, z. B. 2013 -> '2013-14'."""
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def fetch_bytes(url: str, config: FootballDataConfig) -> bytes | None:
    """Lade eine URL; None, falls nicht verfügbar.

    Bei echtem 404 (Liga/Saison existiert nicht) sofort None. Bei
    transienten Antworten (300 Multiple Choices, 5xx, Netzfehler), die
    football-data.co.uk gelegentlich liefert, einmal nachfassen.
    """
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(
                request, timeout=config.TIMEOUT_SECONDS
            ) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None  # echte Abwesenheit -> kein Retry
        except urllib.error.URLError:
            pass
        if attempt == 0:
            time.sleep(1.0)  # kurzer Backoff vor dem einzigen Retry
    return None


def is_valid_csv(payload: bytes) -> bool:
    """Plausibilitätscheck: nichtleer und sieht nach football-data-CSV aus.

    football-data.co.uk liefert manche Saisons mit UTF-8-BOM; dieses wird
    vor der Header-Prüfung entfernt.
    """
    head = payload.lstrip(b"\xef\xbb\xbf").lstrip()
    return len(payload) > 100 and head.startswith(b"Div,")


def download_main_leagues(config: FootballDataConfig, output_root: Path) -> int:
    """Lade alle Hauptligen Saison für Saison. Gibt Dateianzahl zurück."""
    written = 0
    seasons = range(config.FIRST_SEASON_START, config.LAST_SEASON_START + 1)
    for code, folder_name in config.MAIN_LEAGUES.items():
        league_dir = output_root / "main_leagues" / folder_name
        league_dir.mkdir(parents=True, exist_ok=True)
        for start_year in seasons:
            target = league_dir / f"{season_label(start_year)}.csv"
            if target.exists():
                continue  # bereits geladen -> wiederaufsetzbar, keine Anfrage
            url = f"{config.MAIN_BASE_URL}/{season_code(start_year)}/{code}.csv"
            payload = fetch_bytes(url, config)
            time.sleep(config.POLITE_DELAY_SECONDS)
            if payload is None or not is_valid_csv(payload):
                continue
            target.write_bytes(payload)
            written += 1
            print(f"  {folder_name}/{season_label(start_year)}.csv", flush=True)
    return written


def download_extra_leagues(config: FootballDataConfig, output_root: Path) -> int:
    """Lade alle Extra-Ligen (je eine kombinierte Datei)."""
    written = 0
    extra_dir = output_root / "extra_leagues"
    extra_dir.mkdir(parents=True, exist_ok=True)
    for code, label in config.EXTRA_LEAGUES.items():
        target = extra_dir / f"{label}.csv"
        if target.exists():
            continue
        payload = fetch_bytes(f"{config.EXTRA_BASE_URL}/{code}.csv", config)
        time.sleep(config.POLITE_DELAY_SECONDS)
        if payload is None or len(payload) < 100:
            continue
        target.write_bytes(payload)
        written += 1
        print(f"  extra_leagues/{label}.csv", flush=True)
    return written


def write_readme(config: FootballDataConfig, output_root: Path) -> None:
    """Schreibe eine Quellen-/Spaltenlegende in den Zielordner."""
    text = (
        "Football Betting Odds - football-data.co.uk\n"
        "===========================================\n\n"
        "Quelle: https://www.football-data.co.uk (frei, statische CSVs).\n"
        f"Saisons: {config.FIRST_SEASON_START}/{config.FIRST_SEASON_START % 100 + 1:02d}"
        f" bis {config.LAST_SEASON_START}/{config.LAST_SEASON_START % 100 + 1:02d}.\n\n"
        "Ordner:\n"
        "  main_leagues/  Europ. Topligen, eine CSV pro Saison (Schema je Saison leicht\n"
        "                 unterschiedlich; Anzahl Quotenspalten waechst ueber die Jahre).\n"
        "  extra_leagues/ Uebrige Ligen, je eine kombinierte CSV ueber alle Saisons\n"
        "                 (ANDERES Spaltenschema als main_leagues!).\n\n"
        "Wichtige Spalten (main_leagues):\n"
        "  Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR   Ergebnis (Full Time).\n"
        "  PSH/PSD/PSA       Pinnacle 1X2 (Opening) - schaerfster Markt.\n"
        "  PSCH/PSCD/PSCA    Pinnacle 1X2 (Closing)  - fuer Closing Line Value.\n"
        "  AvgH/D/A, AvgCH.. Marktdurchschnitt (Opening / Closing).\n"
        "  MaxH/D/A          Bestes verfuegbares Angebot (Opening).\n"
        "  Spalten mit 'C' = Closing-Quoten (nur in juengeren Saisons vorhanden).\n\n"
        "WICHTIG: Diese Quelle enthaelt KEINE WM-/EM-/Turnierquoten, nur Vereinsligen.\n"
        "Fuer WM/EM-Quoten siehe OddsPortal-Archiv bzw. Kaggle (siehe Konzept 3.2).\n"
    )
    (output_root / "README.txt").write_text(text, encoding="utf-8")


def main() -> None:
    """Lade alle konfigurierten Ligen in den Zielordner."""
    config = FootballDataConfig()
    output_root = Path(config.OUTPUT_ROOT)
    output_root.mkdir(parents=True, exist_ok=True)
    write_readme(config, output_root)
    print("Lade Hauptligen ...", flush=True)
    main_count = download_main_leagues(config, output_root)
    print("Lade Extra-Ligen ...", flush=True)
    extra_count = download_extra_leagues(config, output_root)
    print(f"\nFertig: {main_count} Saison-Dateien + {extra_count} Extra-Ligen.", flush=True)


if __name__ == "__main__":
    main()
