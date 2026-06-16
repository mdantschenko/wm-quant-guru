"""Stilstabilitaet je Team aus den Spielstilprofilen (match_style.csv).

Ein Team mit konstantem Stilprofil ist taktisch vorhersehbar, ein Team mit
stark schwankendem Profil passt sich an oder ist instabil. Gemessen wird die
Schwankung der stilistischen Kennzahlen von Spiel zu Spiel. Damit Kennzahlen
unterschiedlicher Groessenordnung vergleichbar werden, wird jede Dimension
innerhalb von Wettbewerb und Saison standardisiert (z-Wert). Die Stilvolatilitaet
eines Teams ist dann die mittlere Streuung dieser z-Werte ueber seine Spiele.

Ausgabe nach Data/Custom_Data/team_style_stability.csv je Quelle, Wettbewerb,
Saison und Team (ab fuenf Spielen). Reine Standardbibliothek.

Start als Modul:
    python -m scripts.builders.build_team_style_stability
"""
from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean, pstdev


class StabilityConfig:
    """Pfade, Stildimensionen und Mindestzahl an Spielen."""

    INPUT_FILE: str = "Data/Custom_Data/match_style.csv"
    OUTPUT_FILE: str = "Data/Custom_Data/team_style_stability.csv"
    MINIMUM_MATCHES: int = 5
    DIMENSIONS: tuple[str, ...] = (
        "pass_share", "field_tilt", "ppda", "def_action_height_m",
        "directness_m", "set_piece_pass_share", "take_on_success_rate",
    )


def load_rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def league_scales(rows: list[dict[str, str]],
                  config: StabilityConfig) -> dict[tuple, dict[str, tuple]]:
    """Bestimmt je Wettbewerb, Saison und Dimension Mittelwert und Streuung."""
    pools: dict[tuple, dict[str, list]] = {}
    for row in rows:
        key = (row["source"], row["competition"], row["season"])
        bucket = pools.setdefault(key, {dimension: [] for dimension in config.DIMENSIONS})
        for dimension in config.DIMENSIONS:
            value = to_float(row.get(dimension, ""))
            if value is not None:
                bucket[dimension].append(value)
    scales: dict[tuple, dict[str, tuple]] = {}
    for key, bucket in pools.items():
        scales[key] = {
            dimension: (mean(values), pstdev(values))
            for dimension, values in bucket.items() if len(values) >= 2
        }
    return scales


def team_groups(rows: list[dict[str, str]]) -> dict[tuple, list[dict[str, str]]]:
    groups: dict[tuple, list[dict[str, str]]] = {}
    for row in rows:
        key = (row["source"], row["competition"], row["season"], row["team"])
        groups.setdefault(key, []).append(row)
    return groups


def dimension_summary(matches: list[dict[str, str]], dimension: str,
                      scale: tuple | None) -> tuple[object, object]:
    """Liefert den Rohmittelwert und die z-standardisierte Volatilitaet einer Dimension."""
    raw_values = [value for value in (to_float(match.get(dimension, "")) for match in matches)
                  if value is not None]
    if not raw_values:
        return "", ""
    raw_mean = mean(raw_values)
    if scale is None or scale[1] == 0:
        return round(raw_mean, 4), ""
    center, spread = scale
    z_values = [(value - center) / spread for value in raw_values]
    return round(raw_mean, 4), round(pstdev(z_values), 4)


def build_rows(groups: dict[tuple, list[dict[str, str]]], scales: dict,
               config: StabilityConfig) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (source, competition, season, team), matches in groups.items():
        if len(matches) < config.MINIMUM_MATCHES:
            continue
        scale = scales.get((source, competition, season), {})
        row: dict[str, object] = {"source": source, "competition": competition,
                                  "season": season, "team": team, "matches": len(matches)}
        volatilities: list[float] = []
        for dimension in config.DIMENSIONS:
            raw_mean, volatility = dimension_summary(matches, dimension, scale.get(dimension))
            row[f"{dimension}_mean"] = raw_mean
            row[f"{dimension}_volatility"] = volatility
            if isinstance(volatility, float):
                volatilities.append(volatility)
        row["style_volatility"] = round(mean(volatilities), 4) if volatilities else ""
        rows.append(row)
    rows.sort(key=lambda item: (str(item["source"]), str(item["competition"]),
                                str(item["season"]), str(item["team"])))
    return rows


def fieldnames(config: StabilityConfig) -> list[str]:
    names = ["source", "competition", "season", "team", "matches"]
    for dimension in config.DIMENSIONS:
        names.extend([f"{dimension}_mean", f"{dimension}_volatility"])
    names.append("style_volatility")
    return names


def main() -> None:
    config = StabilityConfig()
    rows = load_rows(Path(config.INPUT_FILE))
    scales = league_scales(rows, config)
    output_rows = build_rows(team_groups(rows), scales, config)
    output_path = Path(config.OUTPUT_FILE)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames(config))
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"  OK    {len(output_rows)} Team-Saison-Zeilen (>= {config.MINIMUM_MATCHES} Spiele)")


if __name__ == "__main__":
    main()
