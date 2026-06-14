"""Deckt die verborgene Konfoederations-Verzerrung der Elo-Ratings auf.

Nationalteams spielen ueberwiegend innerhalb der eigenen Konfoederation.
Dadurch ist das ABSOLUTE Niveau zwischen den Konfoederationen (UEFA vs.
CONMEBOL vs. AFC ...) im Elo nur schwach identifiziert -- genau die
Relation, die bei einer WM entscheidet. Dieses Skript isoliert das Signal
aus den seltenen INTERKONTINENTALEN Spielen: Fuer jedes Spiel mit pre-match
Elo wird die tatsaechliche Punktausbeute des Heimteams mit der Elo-Erwartung
verglichen. Der Mittelwert dieser Residuen je Konfoederations-Paar und Epoche
zeigt, welche Konfoederation das Elo systematisch ueber- oder unterschaetzt.
Zusaetzlich wird je Epoche ein Satz Elo-Offsets geschaetzt (UEFA als
Referenz), der die Kreuz-Konfoederations-Ergebnisse am besten erklaert.

Eingaben (reine Standardbibliothek):
  - results.csv (Ergebnis, neutral)
  - elo_prematch_history.csv (pre-match Elo beider Teams)
Ausgaben nach Data/Custom_Data/:
  - confederation_pair_residuals.csv
  - confederation_elo_offsets.csv
  - team_confederation_map.csv (Audit der Zuordnung)
"""
from __future__ import annotations

import csv
import math
import unicodedata
from pathlib import Path


class CalibrationConfig:
    """Pfade, Heimvorteil und Epochengrenzen."""

    RESULTS_FILE: str = (
        "Data/International football results from 1872 to 2026/results.csv"
    )
    ELO_FILE: str = (
        "Data/International Football Elo Ratings (1872-2025)/elo_prematch_history.csv"
    )
    OUTPUT_DIR: str = "Data/Custom_Data"

    HOME_ADVANTAGE: float = 100.0  # entfaellt bei neutral=TRUE (wie Elo-Engine)
    REFERENCE_CONFEDERATION: str = "UEFA"
    MIN_MATCHES_FOR_FIT: int = 40  # Mindestzahl Kreuzspiele je Epoche
    ITERATIONS: int = 60  # diagonaler Gauss-Newton-Schritt konvergiert schnell


class Confederations:
    """Aktuelle Konfoederations-Zugehoerigkeit aller Nationalteams.

    Die Namen folgen der Schreibweise des results.csv (martj42). Akzente und
    Gross-/Kleinschreibung werden bei der Suche normalisiert, sodass Varianten
    wie Cote d'Ivoire / Ivory Coast oder Curacao / Curacao erkannt werden.
    Historische Teams werden ihrer geografischen Nachfolge zugeordnet.
    """

    _MEMBERS: dict[str, tuple[str, ...]] = {
        "UEFA": (
            "Albania", "Andorra", "Armenia", "Austria", "Azerbaijan", "Belarus",
            "Belgium", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus",
            "Czech Republic", "Czechia", "Denmark", "England", "Estonia",
            "Faroe Islands", "Finland", "France", "Georgia", "Germany",
            "Gibraltar", "Greece", "Hungary", "Iceland", "Israel", "Italy",
            "Kazakhstan", "Kosovo", "Latvia", "Liechtenstein", "Lithuania",
            "Luxembourg", "Malta", "Moldova", "Montenegro", "Netherlands",
            "North Macedonia", "Macedonia", "Northern Ireland", "Norway",
            "Poland", "Portugal", "Republic of Ireland", "Ireland", "Romania",
            "Russia", "San Marino", "Scotland", "Serbia", "Slovakia", "Slovenia",
            "Spain", "Sweden", "Switzerland", "Turkey", "Ukraine", "Wales",
            "Soviet Union", "CIS", "Yugoslavia", "Serbia and Montenegro",
            "Czechoslovakia", "East Germany", "German DR", "West Germany", "Saar",
        ),
        "CONMEBOL": (
            "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador",
            "Paraguay", "Peru", "Uruguay", "Venezuela",
        ),
        "CONCACAF": (
            "United States", "USA", "Mexico", "Canada", "Costa Rica", "Honduras",
            "Panama", "Jamaica", "Trinidad and Tobago", "El Salvador",
            "Guatemala", "Haiti", "Cuba", "Curacao", "Suriname", "Guyana",
            "Nicaragua", "Belize", "Antigua and Barbuda", "Aruba", "Bahamas",
            "Barbados", "Bermuda", "British Virgin Islands", "Cayman Islands",
            "Dominica", "Dominican Republic", "Grenada", "Montserrat",
            "Puerto Rico", "Saint Kitts and Nevis", "Saint Lucia",
            "Saint Vincent and the Grenadines", "Sint Maarten",
            "Turks and Caicos Islands", "US Virgin Islands", "Anguilla",
            "Martinique", "Guadeloupe", "French Guiana", "Bonaire",
            "Netherlands Antilles",
        ),
        "AFC": (
            "Afghanistan", "Australia", "Bahrain", "Bangladesh", "Bhutan",
            "Brunei", "Cambodia", "China PR", "China", "Chinese Taipei",
            "Taiwan", "Guam", "Hong Kong", "India", "Indonesia", "Iran",
            "IR Iran", "Iraq", "Japan", "Jordan", "Kuwait", "Kyrgyzstan",
            "Laos", "Lebanon", "Macau", "Malaysia", "Maldives", "Mongolia",
            "Myanmar", "Burma", "Nepal", "North Korea", "Korea DPR", "Oman",
            "Pakistan", "Palestine", "Philippines", "Qatar", "Saudi Arabia",
            "Singapore", "South Korea", "Korea Republic", "Sri Lanka", "Syria",
            "Tajikistan", "Thailand", "Timor-Leste", "Turkmenistan",
            "United Arab Emirates", "Uzbekistan", "Vietnam", "Vietnam Republic",
            "South Vietnam", "Yemen", "South Yemen", "North Yemen", "Yemen DPR",
        ),
        "CAF": (
            "Algeria", "Angola", "Benin", "Dahomey", "Botswana", "Burkina Faso",
            "Upper Volta", "Burundi", "Cameroon", "Cape Verde", "Cabo Verde",
            "Central African Republic", "Chad", "Comoros", "Congo",
            "DR Congo", "Congo DR", "Zaire", "Djibouti", "Egypt",
            "Equatorial Guinea", "Eritrea", "Eswatini", "Swaziland", "Ethiopia",
            "Gabon", "Gambia", "Ghana", "Guinea", "Guinea-Bissau", "Ivory Coast",
            "Cote d'Ivoire", "Kenya", "Lesotho", "Liberia", "Libya",
            "Madagascar", "Malawi", "Mali", "Mauritania", "Mauritius", "Morocco",
            "Mozambique", "Namibia", "Niger", "Nigeria", "Rwanda",
            "Sao Tome and Principe", "Senegal", "Seychelles", "Sierra Leone",
            "Somalia", "South Africa", "South Sudan", "Sudan", "Tanzania",
            "Togo", "Tunisia", "Uganda", "Zambia", "Zimbabwe", "Reunion",
            "Mayotte", "Zanzibar",
        ),
        "OFC": (
            "American Samoa", "Cook Islands", "Fiji", "New Caledonia",
            "New Zealand", "Papua New Guinea", "Samoa", "Western Samoa",
            "Solomon Islands", "Tahiti", "Tonga", "Tuvalu", "Vanuatu",
        ),
    }

    def __init__(self) -> None:
        self._lookup: dict[str, str] = {}
        for confederation, members in self._MEMBERS.items():
            for member in members:
                self._lookup[self._normalize(member)] = confederation

    @staticmethod
    def _normalize(name: str) -> str:
        decomposed = unicodedata.normalize("NFKD", name)
        without_accents = "".join(
            character for character in decomposed
            if not unicodedata.combining(character)
        )
        return without_accents.casefold().strip()

    def confederation_of(self, team: str) -> str | None:
        return self._lookup.get(self._normalize(team))


def era_of(year: int) -> str:
    """Bildet ein Jahr auf eine Analyse-Epoche ab."""
    if year < 1990:
        return "pre_1990"
    if year < 2000:
        return "1990_1999"
    if year < 2010:
        return "2000_2009"
    if year < 2020:
        return "2010_2019"
    return "2020_2026"


def expected_home_score(
    elo_home: float, elo_away: float, neutral: bool, config: CalibrationConfig
) -> float:
    """Elo-Gewinnerwartung des Heimteams (Sieg 1, Remis 0,5, Niederlage 0)."""
    advantage = 0.0 if neutral else config.HOME_ADVANTAGE
    difference = elo_home + advantage - elo_away
    return 1.0 / (1.0 + 10.0 ** (-difference / 400.0))


def load_elo_lookup(config: CalibrationConfig) -> dict[tuple[str, str, str], tuple[float, float]]:
    """Liest pre-match Elo, indiziert nach (Datum, Heim, Gast)."""
    lookup: dict[tuple[str, str, str], tuple[float, float]] = {}
    with open(config.ELO_FILE, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["date"], row["home_team"], row["away_team"])
            lookup[key] = (float(row["elo_home_pre"]), float(row["elo_away_pre"]))
    return lookup


def load_cross_confederation_matches(
    config: CalibrationConfig, confederations: Confederations
) -> tuple[list[dict[str, object]], dict[str, dict[str, int]]]:
    """Sammelt Kreuz-Konfoederations-Spiele mit Elo und fuehrt eine Team-Statistik.

    Rueckgabe: Liste der Spielzeilen und je Team die Konfoederation samt
    Spielzahl (fuer das Audit der Zuordnung).
    """
    elo_lookup = load_elo_lookup(config)
    matches: list[dict[str, object]] = []
    team_audit: dict[str, dict[str, int]] = {}

    with open(config.RESULTS_FILE, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            home, away = row["home_team"], row["away_team"]
            confederation_home = confederations.confederation_of(home)
            confederation_away = confederations.confederation_of(away)
            for team, confederation in ((home, confederation_home), (away, confederation_away)):
                record = team_audit.setdefault(
                    team, {"confederation": confederation or "UNMAPPED", "matches": 0}
                )
                record["matches"] += 1

            if not (row["home_score"] and row["away_score"]):
                continue  # ungespielte WM-2026-Fixtures
            if confederation_home is None or confederation_away is None:
                continue
            if confederation_home == confederation_away:
                continue

            elo = elo_lookup.get((row["date"], home, away))
            if elo is None:
                continue

            neutral = row["neutral"].strip().upper() == "TRUE"
            home_goals, away_goals = int(row["home_score"]), int(row["away_score"])
            result = 1.0 if home_goals > away_goals else (0.5 if home_goals == away_goals else 0.0)
            matches.append({
                "era": era_of(int(row["date"][:4])),
                "confederation_home": confederation_home,
                "confederation_away": confederation_away,
                "elo_home": elo[0],
                "elo_away": elo[1],
                "neutral": neutral,
                "result": result,
                "goal_difference": home_goals - away_goals,
            })
    return matches, team_audit


def compute_pair_residuals(
    matches: list[dict[str, object]], config: CalibrationConfig
) -> list[dict[str, object]]:
    """Mittelt Ergebnis- und Tordifferenz-Residuen je Epoche und Paar."""
    buckets: dict[tuple[str, str, str], list[tuple[float, float, int]]] = {}
    for match in matches:
        expected = expected_home_score(
            match["elo_home"], match["elo_away"], match["neutral"], config
        )
        residual = match["result"] - expected
        key = (match["era"], match["confederation_home"], match["confederation_away"])
        buckets.setdefault(key, []).append(
            (residual, expected, match["goal_difference"])
        )
        all_key = ("all_time", match["confederation_home"], match["confederation_away"])
        buckets.setdefault(all_key, []).append(
            (residual, expected, match["goal_difference"])
        )

    rows: list[dict[str, object]] = []
    for (era, home_confederation, away_confederation), values in sorted(buckets.items()):
        count = len(values)
        mean_residual = sum(value[0] for value in values) / count
        mean_expected = sum(value[1] for value in values) / count
        mean_goal_difference = sum(value[2] for value in values) / count
        rows.append({
            "era": era,
            "confederation_home": home_confederation,
            "confederation_away": away_confederation,
            "matches": count,
            "mean_result_residual": round(mean_residual, 4),
            "mean_elo_expected": round(mean_expected, 4),
            "mean_goal_difference": round(mean_goal_difference, 3),
        })
    return rows


def fit_offsets_for_subset(
    subset: list[dict[str, object]], config: CalibrationConfig
) -> dict[str, float]:
    """Schaetzt Elo-Offsets je Konfoederation via Gradientenabstieg.

    Positiver Offset bedeutet: die Konfoederation ist vom Elo unterschaetzt,
    ihre Spiele werden mit einem hoeheren effektiven Rating besser erklaert.
    Die Referenz-Konfoederation bleibt fix auf 0 verankert.
    """
    confederations_present = sorted(
        {match["confederation_home"] for match in subset}
        | {match["confederation_away"] for match in subset}
    )
    offsets = {confederation: 0.0 for confederation in confederations_present}
    scale = math.log(10.0) / 400.0

    for _ in range(config.ITERATIONS):
        gradient = {confederation: 0.0 for confederation in confederations_present}
        curvature = {confederation: 0.0 for confederation in confederations_present}
        for match in subset:
            home, away = match["confederation_home"], match["confederation_away"]
            advantage = 0.0 if match["neutral"] else config.HOME_ADVANTAGE
            difference = (
                match["elo_home"] + offsets[home] + advantage
                - (match["elo_away"] + offsets[away])
            )
            expected = 1.0 / (1.0 + 10.0 ** (-difference / 400.0))
            sensitivity = expected * (1.0 - expected) * scale
            slope = (expected - match["result"]) * sensitivity
            gauss_newton = sensitivity * sensitivity
            gradient[home] += slope
            gradient[away] -= slope
            curvature[home] += gauss_newton
            curvature[away] += gauss_newton
        # Diagonaler Gauss-Newton-Schritt skaliert sich selbst auf die
        # sehr flache Loss-Oberflaeche (ein Elo-Punkt bewegt p kaum).
        for confederation in confederations_present:
            if confederation == config.REFERENCE_CONFEDERATION:
                continue
            offsets[confederation] -= gradient[confederation] / (curvature[confederation] + 1e-9)
    return {confederation: round(value, 1) for confederation, value in offsets.items()}


def compute_offsets(
    matches: list[dict[str, object]], config: CalibrationConfig
) -> list[dict[str, object]]:
    """Schaetzt Offsets je Epoche und fuer den Gesamtzeitraum."""
    by_era: dict[str, list[dict[str, object]]] = {"all_time": list(matches)}
    for match in matches:
        by_era.setdefault(match["era"], []).append(match)

    rows: list[dict[str, object]] = []
    for era, subset in sorted(by_era.items()):
        if len(subset) < config.MIN_MATCHES_FOR_FIT:
            continue
        offsets = fit_offsets_for_subset(subset, config)
        reference = config.REFERENCE_CONFEDERATION
        for confederation, offset in sorted(offsets.items()):
            rows.append({
                "era": era,
                "confederation": confederation,
                "elo_offset_vs_" + reference: offset,
                "matches_in_era": len(subset),
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_team_audit(path: Path, team_audit: dict[str, dict[str, int]]) -> int:
    """Schreibt die Team-Konfoederations-Zuordnung, sortiert nach Spielzahl."""
    rows = [
        {"team": team, "confederation": record["confederation"], "matches": record["matches"]}
        for team, record in team_audit.items()
    ]
    rows.sort(key=lambda row: row["matches"], reverse=True)
    write_csv(path, rows, ["team", "confederation", "matches"])
    return sum(1 for row in rows if row["confederation"] == "UNMAPPED")


def main() -> None:
    config = CalibrationConfig()
    confederations = Confederations()
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    matches, team_audit = load_cross_confederation_matches(config, confederations)

    pair_rows = compute_pair_residuals(matches, config)
    write_csv(
        output_dir / "confederation_pair_residuals.csv",
        pair_rows,
        ["era", "confederation_home", "confederation_away", "matches",
         "mean_result_residual", "mean_elo_expected", "mean_goal_difference"],
    )

    offset_rows = compute_offsets(matches, config)
    write_csv(
        output_dir / "confederation_elo_offsets.csv",
        offset_rows,
        ["era", "confederation", "elo_offset_vs_" + config.REFERENCE_CONFEDERATION,
         "matches_in_era"],
    )

    unmapped = write_team_audit(output_dir / "team_confederation_map.csv", team_audit)

    print(f"  OK    {len(matches)} Kreuz-Konfoederations-Spiele mit Elo")
    print(f"  OK    {len(pair_rows)} Paar-Epochen-Zeilen, {len(offset_rows)} Offset-Zeilen")
    print(f"  INFO  {unmapped} Teams ohne Konfoederations-Zuordnung (siehe team_confederation_map.csv)")


if __name__ == "__main__":
    main()
