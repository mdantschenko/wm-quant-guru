"""Lädt das Wyscout-Event-Dataset (Pappalardo et al., Kaggle-Mirror).

Das groesste frei verfuegbare Event-Dataset (Nature Scientific Data
2019): alle Spiele der Big-5-Ligen 2017/18, der WM 2018 und der
EM 2016 als Einzel-Events (~3 GB entpackt), inkl. PlayeRank-
Spielerbewertungen. Damit laesst sich ein eigenes xG-Modell auf
Vereins-Events trainieren und auf die EM-2016-Schuesse anwenden --
die einzige dokumentierte xG-Luecke des Test-Sets.
Reine Standardbibliothek. ~520 MB Download.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path


class WyscoutConfig:
    """Quelle und Zielpfad."""

    URL: str = (
        "https://www.kaggle.com/api/v1/datasets/download/"
        "aleespinosa/soccer-match-event-dataset"
    )
    USER_AGENT: str = "Mozilla/5.0 (research)"
    TIMEOUT_SECONDS: int = 3600
    OUTPUT_DIR: str = "Data/Wyscout Events (Pappalardo 2017-18)"


def main() -> None:
    """Lade das ZIP und entpacke alle Dateien."""
    config = WyscoutConfig()
    output_dir = Path(config.OUTPUT_DIR)
    if any(output_dir.glob("events_*.csv")):
        print(f"SKIP  {output_dir} (bereits vorhanden)")
        return
    request = urllib.request.Request(
        config.URL, headers={"User-Agent": config.USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
        payload = response.read()
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extractall(output_dir)
    print(f"OK    {len(list(output_dir.iterdir()))} Dateien -> {output_dir}")


if __name__ == "__main__":
    main()
