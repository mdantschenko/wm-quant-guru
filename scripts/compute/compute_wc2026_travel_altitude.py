"""Reise-, Zeitzonen- und Hoehenlast je Team fuer die WM-2026-Gruppenphase.

compute_travel_load.py deckt nur die historischen StatsBomb-Turniere ab und
kennt keine Hoehenlage. Dieses Skript erzeugt die WM-2026-spezifische
Belastung. Aus den 72 Gruppenspielen (Teams und Spielorte stehen nach der
Auslosung fest, K.o.-Runde noch offen) wird je Team die chronologische
Venue-Kette gebildet und daraus berechnet:
  - Grosskreis-Kilometer seit dem letzten Spiel und kumuliert,
  - Zeitzonen-Verschiebung (Laengengrad/15) als zirkadianer Proxy,
  - Hoehe des Spielorts und Hoehengewinn gegenueber dem Vorspiel,
  - Ruhetage zwischen den Spielen.

Das macht die verborgene Ungleichheit der Spielplaene sichtbar (welches Team
quer ueber den Kontinent reist, welches in Mexiko-Stadt auf 2254 m spielt).

Eingaben: results.csv (WM-2026-Fixtures), match_city_geocodes.csv,
venue_country_elevations.csv. Ausgaben nach Data/Custom_Data/. Reine
Standardbibliothek.
"""
from __future__ import annotations

import csv
import math
from datetime import date
from pathlib import Path


class BurdenConfig:
    """Pfade und Schwellen."""

    RESULTS_FILE: str = (
        "Data/International football results from 1872 to 2026/results.csv"
    )
    GEOCODES_FILE: str = "Data/Computed Features/match_city_geocodes.csv"
    ELEVATIONS_FILE: str = "Data/Computed Features/venue_country_elevations.csv"
    OUTPUT_DIR: str = "Data/Custom_Data"

    TOURNAMENT: str = "FIFA World Cup"
    SEASON_PREFIX: str = "2026-"
    HIGH_ALTITUDE_M: float = 1500.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Grosskreisdistanz zweier Koordinaten in Kilometern."""
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))


def timezone_proxy(longitude: float) -> int:
    """Zeitzonen-Proxy aus dem Laengengrad (15 Grad je Stunde)."""
    return round(longitude / 15.0)


def load_geocodes(config: BurdenConfig) -> dict[str, tuple[float, float, str]]:
    """Stadt zu Breite, Laenge und IANA-Zeitzone."""
    geocodes: dict[str, tuple[float, float, str]] = {}
    with open(config.GEOCODES_FILE, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            geocodes[row["city"]] = (
                float(row["latitude"]), float(row["longitude"]), row["timezone"]
            )
    return geocodes


def load_venues(config: BurdenConfig) -> list[tuple[float, float, float]]:
    """Venue-Koordinaten mit Hoehe (fuer die Naechster-Nachbar-Zuordnung)."""
    venues: list[tuple[float, float, float]] = []
    with open(config.ELEVATIONS_FILE, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["kind"] != "venue_wc2026":
                continue
            venues.append(
                (float(row["latitude"]), float(row["longitude"]), float(row["elevation_m"]))
            )
    return venues


def nearest_elevation(
    latitude: float, longitude: float, venues: list[tuple[float, float, float]]
) -> float:
    """Hoehe des naechstgelegenen WM-Stadions zur Stadt."""
    return min(
        venues, key=lambda venue: haversine_km(latitude, longitude, venue[0], venue[1])
    )[2]


def load_team_sequences(
    config: BurdenConfig,
    geocodes: dict[str, tuple[float, float, str]],
    venues: list[tuple[float, float, float]],
) -> dict[str, list[dict[str, object]]]:
    """Baut je Team die chronologische Liste seiner Gruppenspiel-Venues."""
    sequences: dict[str, list[dict[str, object]]] = {}
    with open(config.RESULTS_FILE, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["tournament"] != config.TOURNAMENT:
                continue
            if not row["date"].startswith(config.SEASON_PREFIX):
                continue
            latitude, longitude, timezone = geocodes[row["city"]]
            elevation = nearest_elevation(latitude, longitude, venues)
            is_host = row["neutral"].strip().upper() == "FALSE"
            for team, opponent in ((row["home_team"], row["away_team"]),
                                   (row["away_team"], row["home_team"])):
                sequences.setdefault(team, []).append({
                    "date": row["date"],
                    "opponent": opponent,
                    "city": row["city"],
                    "is_host": int(is_host and team == row["home_team"]),
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": timezone,
                    "elevation": elevation,
                })
    for matches in sequences.values():
        matches.sort(key=lambda match: match["date"])
    return sequences


def build_legs(sequences: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    """Berechnet je Team-Spiel die Reise-, Zeitzonen- und Hoehenkennzahlen."""
    rows: list[dict[str, object]] = []
    for team, matches in sorted(sequences.items()):
        cumulative_km = 0.0
        cumulative_tz = 0
        previous: dict[str, object] | None = None
        for number, match in enumerate(matches, start=1):
            km = tz_shift = altitude_gain = 0.0
            days_rest: object = ""
            if previous is not None:
                km = round(haversine_km(
                    previous["latitude"], previous["longitude"],
                    match["latitude"], match["longitude"],
                ))
                tz_shift = abs(timezone_proxy(match["longitude"]) - timezone_proxy(previous["longitude"]))
                altitude_gain = max(0.0, match["elevation"] - previous["elevation"])
                days_rest = (date.fromisoformat(match["date"]) - date.fromisoformat(previous["date"])).days
            cumulative_km += km
            cumulative_tz += tz_shift
            rows.append({
                "team": team,
                "match_number": number,
                "date": match["date"],
                "opponent": match["opponent"],
                "city": match["city"],
                "is_host": match["is_host"],
                "timezone": match["timezone"],
                "altitude_m": round(match["elevation"]),
                "altitude_gain_since_last": round(altitude_gain),
                "km_since_last": round(km),
                "cumulative_km": round(cumulative_km),
                "tz_shift_since_last": tz_shift,
                "cumulative_tz_shifts": cumulative_tz,
                "days_rest": days_rest,
            })
            previous = match
    return rows


def build_summary(
    legs: list[dict[str, object]], config: BurdenConfig
) -> list[dict[str, object]]:
    """Aggregiert je Team eine kompakte Belastungs-Kennzahl."""
    by_team: dict[str, list[dict[str, object]]] = {}
    for leg in legs:
        by_team.setdefault(leg["team"], []).append(leg)

    rows: list[dict[str, object]] = []
    for team, team_legs in sorted(by_team.items()):
        rows.append({
            "team": team,
            "group_matches": len(team_legs),
            "total_km": team_legs[-1]["cumulative_km"],
            "total_tz_shifts": team_legs[-1]["cumulative_tz_shifts"],
            "max_altitude_m": max(leg["altitude_m"] for leg in team_legs),
            "high_altitude_matches": sum(
                1 for leg in team_legs if leg["altitude_m"] >= config.HIGH_ALTITUDE_M
            ),
            "first_city": team_legs[0]["city"],
            "last_city": team_legs[-1]["city"],
        })
    rows.sort(key=lambda row: row["total_km"], reverse=True)
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = BurdenConfig()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    sequences = load_team_sequences(config, load_geocodes(config), load_venues(config))
    legs = build_legs(sequences)
    summary = build_summary(legs, config)

    write_csv(
        output_dir / "wc2026_travel_altitude_legs.csv",
        legs,
        ["team", "match_number", "date", "opponent", "city", "is_host", "timezone",
         "altitude_m", "altitude_gain_since_last", "km_since_last", "cumulative_km",
         "tz_shift_since_last", "cumulative_tz_shifts", "days_rest"],
    )
    write_csv(
        output_dir / "wc2026_team_burden_summary.csv",
        summary,
        ["team", "group_matches", "total_km", "total_tz_shifts", "max_altitude_m",
         "high_altitude_matches", "first_city", "last_city"],
    )

    print(f"  OK    {len(legs)} Team-Spiel-Zeilen, {len(summary)} Teams")


if __name__ == "__main__":
    main()
