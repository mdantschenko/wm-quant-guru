"""Lädt Football-Manager-Spielerdatenbanken (Kaggle, anonym) -- alle Jahrgänge.

Sports Interactive unterhält eines der größten Scouting-Netzwerke der
Welt; die FM-Datenbanken enthalten je Spieler ~50 Attribute inklusive
der MENTAL-Skala (Determination, Composure, Leadership, Decisions ...),
die EA-Ratings nicht abbilden. Vier frei verfügbare Jahrgänge decken
die Turnier-Ära ab (Scouting-Stand jeweils VOR dem Turnier):

  FM17 (Nov 2016) -> WM 2018          FM20 (Nov 2019, inkl. CA/PA)
  FM21 (Nov 2020) -> EM 2021 / Copa 2021
  FM23 (Nov 2022) -> WM 2022 (erschien 2 Wochen vor Anpfiff) und
                     naechster Stand fuer EM/Copa 2024
FM 24/26 existieren nicht als freie Dumps (FM 25 wurde eingestellt);
WM 2014 / EM 2016 bleiben ohne FM-Stand. Reine Standardbibliothek.
"""
from __future__ import annotations

import io
import time
import urllib.request
import zipfile
from pathlib import Path


class FmConfig:
    """Editionen (Kaggle-Ref, Quelldatei) und Zielstruktur."""

    USER_AGENT: str = "Mozilla/5.0 (research)"
    TIMEOUT_SECONDS: int = 300
    POLITE_DELAY_SECONDS: float = 1.0
    OUTPUT_ROOT: str = "Data/Football Manager Database"
    BASE_URL: str = "https://www.kaggle.com/api/v1/datasets/download/"

    # Edition -> (Kaggle-Datensatz, Name der Spieler-CSV im ZIP).
    EDITIONS: dict[str, tuple[str, str]] = {
        "FM17": ("ajinkyablaze/football-manager-data", "dataset.csv"),
        "FM20": ("ktyptorio/football-manager-2020", "datafm20.csv"),
        "FM21": ("furkanuluta/football-manager-2021-dataset", "worldfmdata.csv"),
        "FM23": (
            "siddhrajthakor/football-manager-2023-dataset",
            "merged_players (1).csv",
        ),
    }


def main() -> None:
    """Lade alle Editionen (vorhandene werden übersprungen)."""
    config = FmConfig()
    for edition, (ref, source_name) in config.EDITIONS.items():
        target = (
            Path(config.OUTPUT_ROOT) / edition
            / f"{edition.lower()}_players.csv"
        )
        if target.exists():
            print(f"  SKIP  {edition}")
            continue
        request = urllib.request.Request(
            config.BASE_URL + ref, headers={"User-Agent": config.USER_AGENT}
        )
        try:
            with urllib.request.urlopen(
                request, timeout=config.TIMEOUT_SECONDS
            ) as response:
                payload = response.read()
        except Exception as error:
            print(f"  FAIL  {edition}: {error}")
            continue
        time.sleep(config.POLITE_DELAY_SECONDS)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            with archive.open(source_name) as source:
                target.write_bytes(source.read())
        print(f"  OK    {edition}: {target} ({target.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
