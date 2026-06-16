"""Match-Style-Metriken je Team und Spiel (Wyscout-Teil + geteiltes Kernmodul).

Erzeugt aus Eventdaten einen Stil- und Staerke-Fingerabdruck je Team und Spiel,
der weit ueber Tore und Quoten hinausgeht. Dieses Skript baut den Wyscout-Teil
(SPADL actions.csv) und stellt die Berechnung bereit, die der StatsBomb-Teil
(build_match_style_statsbomb.py) wiederverwendet.

Kennzahlen je Team und Spiel:
  - pass_share (Ballbesitz-Proxy), field_tilt (Territorium im letzten Drittel),
  - ppda (Paesse je Defensivaktion, Pressingintensitaet),
  - def_action_height_m (Hoehe der Defensivaktionen, Abwehrlinie),
  - passes_into_box, directness_m (Vorwaertsgewinn je Pass),
  - set_piece_pass_share, take_on_success_rate, crosses,
  - shots, shots_in_box,
  - xg, np_xg, xg_per_shot, set_piece_xg_share (nur StatsBomb, sonst leer),
  - pass_share_leading/level/trailing (Verhalten je Spielstand).

Eine normalisierte Aktion ist das Tupel
(team, kind, success, sx, sy, ex, ey, goal_for, xg, set_piece_shot, period, t)
mit Koordinaten in Metern und der Spielrichtung des handelnden Teams nach
SPADL (links nach rechts). Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator, Optional

Action = tuple


class MatchStyleConfig:
    """Pfade, Geometrie und Schwellen."""

    WYSCOUT_DIR: str = "Data/Wyscout Events (Pappalardo 2017-18)"
    OUTPUT_FILE: str = "Data/Custom_Data/match_style.csv"

    PITCH_X: float = 105.0
    PITCH_Y: float = 68.0
    FINAL_THIRD_X: float = 70.0
    BOX_X: float = 88.5
    BOX_Y_MIN: float = 13.84
    BOX_Y_MAX: float = 54.16
    PPDA_PASS_MAX_X: float = 63.0   # gegnerischer Aufbau in dessen eigenen 60 Prozent
    PPDA_DEF_MIN_X: float = 42.0    # eigene Defensivaktion in fortgeschrittener Zone

    FIELDNAMES: list[str] = [
        "source", "game_id", "competition", "season", "date", "team", "opponent",
        "is_home", "passes", "pass_share", "field_tilt", "ppda",
        "def_action_height_m", "passes_into_box", "directness_m",
        "set_piece_pass_share", "take_on_success_rate", "crosses", "shots",
        "shots_in_box", "xg", "np_xg", "xg_per_shot", "set_piece_xg_share",
        "xga", "np_xga", "xga_per_shot",
        "pass_share_leading", "pass_share_level", "pass_share_trailing",
    ]


def new_stat() -> dict[str, float]:
    return {key: 0.0 for key in (
        "passes_any", "passes_oc", "sp_passes", "crosses", "into_box", "forward_sum",
        "oc_low", "final_third", "def_ppda_high", "def_height_sum", "def_height_n",
        "take_on", "take_on_success", "shots", "shots_in_box", "xg", "np_xg", "sp_xg",
        "state_leading", "state_level", "state_trailing",
    )}


def accumulate(stat: dict[str, float], action: Action, config: MatchStyleConfig) -> None:
    """Verbucht eine normalisierte Aktion in der Team-Statistik."""
    kind, success, sx, sy, ex, ey, xg, set_piece_shot = (
        action[1], action[2], action[3], action[4], action[5], action[6], action[8], action[9]
    )
    is_open_cross = kind in ("open_pass", "cross")
    if kind in ("open_pass", "cross", "sp_pass"):
        stat["passes_any"] += 1
    if is_open_cross:
        stat["passes_oc"] += 1
        if ex is not None:
            stat["forward_sum"] += ex - sx
            if ex >= config.BOX_X and config.BOX_Y_MIN <= ey <= config.BOX_Y_MAX:
                stat["into_box"] += 1
        if kind == "cross":
            stat["crosses"] += 1
        if sx <= config.PPDA_PASS_MAX_X:
            stat["oc_low"] += 1
        if sx >= config.FINAL_THIRD_X:
            stat["final_third"] += 1
    elif kind == "sp_pass":
        stat["sp_passes"] += 1
    elif kind in ("tackle", "interception", "foul"):
        if sx >= config.PPDA_DEF_MIN_X:
            stat["def_ppda_high"] += 1
    if kind in ("tackle", "interception", "foul", "clearance"):
        stat["def_height_sum"] += sx
        stat["def_height_n"] += 1
    if kind == "take_on":
        stat["take_on"] += 1
        stat["take_on_success"] += 1 if success else 0
    if kind in ("shot", "pen_shot"):
        stat["shots"] += 1
        if sx >= config.BOX_X and config.BOX_Y_MIN <= sy <= config.BOX_Y_MAX:
            stat["shots_in_box"] += 1
        if xg is not None:
            stat["xg"] += xg
            if kind != "pen_shot":
                stat["np_xg"] += xg
            if set_piece_shot:
                stat["sp_xg"] += xg


def compute_team_stats(
    actions: list[Action], home: str, away: str, config: MatchStyleConfig
) -> dict[str, dict[str, float]]:
    """Aggregiert beide Teams inkl. der Spielstand-abhaengigen Passverteilung."""
    stats = {home: new_stat(), away: new_stat()}
    for action in actions:
        if action[0] in stats:
            accumulate(stats[action[0]], action, config)

    score = {home: 0, away: 0}
    for action in sorted(actions, key=lambda item: (item[10], item[11])):
        team = action[0]
        if team in stats and action[1] in ("open_pass", "cross"):
            opponent = away if team == home else home
            margin = score[team] - score[opponent]
            key = "state_leading" if margin > 0 else ("state_level" if margin == 0 else "state_trailing")
            stats[team][key] += 1
        if action[7] is not None:
            beneficiary = team if action[7] == "self" else (away if team == home else home)
            if beneficiary in score:
                score[beneficiary] += 1
    return stats


def _ratio(numerator: float, denominator: float, digits: int) -> object:
    return round(numerator / denominator, digits) if denominator else ""


def build_row(team: str, opponent: str, is_home: int, stats: dict[str, dict[str, float]],
              meta: dict[str, str], source: str, has_xg: bool,
              config: MatchStyleConfig) -> dict[str, object]:
    """Formt die Kennzahlen eines Teams in eine Ausgabezeile."""
    stat, opponent_stat = stats[team], stats[opponent]
    state_total = stat["state_leading"] + stat["state_level"] + stat["state_trailing"]
    row: dict[str, object] = {
        "source": source, "game_id": meta["game_id"], "competition": meta["competition"],
        "season": meta["season"], "date": meta["date"], "team": team,
        "opponent": opponent, "is_home": is_home,
        "passes": int(stat["passes_any"]),
        "pass_share": _ratio(stat["passes_any"], stat["passes_any"] + opponent_stat["passes_any"], 3),
        "field_tilt": _ratio(stat["final_third"], stat["final_third"] + opponent_stat["final_third"], 3),
        "ppda": _ratio(opponent_stat["oc_low"], stat["def_ppda_high"], 2),
        "def_action_height_m": _ratio(stat["def_height_sum"], stat["def_height_n"], 1),
        "passes_into_box": int(stat["into_box"]),
        "directness_m": _ratio(stat["forward_sum"], stat["passes_oc"], 2),
        "set_piece_pass_share": _ratio(stat["sp_passes"], stat["passes_any"], 3),
        "take_on_success_rate": _ratio(stat["take_on_success"], stat["take_on"], 3),
        "crosses": int(stat["crosses"]),
        "shots": int(stat["shots"]),
        "shots_in_box": int(stat["shots_in_box"]),
        "xg": round(stat["xg"], 3) if has_xg else "",
        "np_xg": round(stat["np_xg"], 3) if has_xg else "",
        "xg_per_shot": _ratio(stat["xg"], stat["shots"], 3) if has_xg else "",
        "set_piece_xg_share": (_ratio(stat["sp_xg"], stat["xg"], 3) if has_xg and stat["xg"] else ("" if not has_xg else 0.0)),
        "xga": "", "np_xga": "", "xga_per_shot": "",
        "pass_share_leading": _ratio(stat["state_leading"], state_total, 3),
        "pass_share_level": _ratio(stat["state_level"], state_total, 3),
        "pass_share_trailing": _ratio(stat["state_trailing"], state_total, 3),
    }
    return row


def match_rows(actions: list[Action], meta: dict[str, str], home: str, away: str,
               source: str, has_xg: bool, config: MatchStyleConfig) -> list[dict[str, object]]:
    """Zwei Zeilen (Heim und Gast) fuer ein Spiel."""
    stats = compute_team_stats(actions, home, away, config)
    rows: list[dict[str, object]] = []
    for team, opponent, is_home in ((home, away, 1), (away, home, 0)):
        if stats[team]["passes_any"] == 0:
            continue
        rows.append(build_row(team, opponent, is_home, stats, meta, source, has_xg, config))
    return rows


# --- Wyscout-Quelle (SPADL) ------------------------------------------------

_SPADL_KIND = {
    "pass": "open_pass", "cross": "cross",
    "throw_in": "sp_pass", "freekick_short": "sp_pass", "corner_short": "sp_pass",
    "goalkick": "sp_pass", "freekick_crossed": "sp_pass", "corner_crossed": "sp_pass",
    "take_on": "take_on", "foul": "foul", "tackle": "tackle",
    "interception": "interception", "clearance": "clearance",
    "shot": "shot", "shot_freekick": "shot", "shot_penalty": "pen_shot",
}


def decode_escapes(text: str) -> str:
    if "\\u" not in text:
        return text
    try:
        return text.encode("latin-1", "backslashreplace").decode("unicode_escape")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def normalize_id(value: str) -> str:
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return value.strip()


def load_lookup(path: Path, key: str, value: str) -> dict[str, str]:
    with open(path, encoding="utf-8") as handle:
        return {normalize_id(row[key]): decode_escapes(row[value]) for row in csv.DictReader(handle)}


def load_games(path: Path) -> dict[str, dict[str, str]]:
    games: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            games[normalize_id(row["game_id"])] = {
                "competition_id": normalize_id(row["competition_id"]),
                "season": row["season_id"], "date": row["game_date"][:10],
                "home": normalize_id(row["home_team_id"]), "away": normalize_id(row["away_team_id"]),
            }
    return games


def _spadl_action(row: list[str], column: dict[str, int], teams: dict[str, str]) -> Optional[Action]:
    try:
        # Wyscout-SPADL greift Richtung x=0 an; auf Standard (Richtung x=105) spiegeln.
        start_x, start_y = 105.0 - float(row[column["start_x"]]), float(row[column["start_y"]])
        end_x, end_y = 105.0 - float(row[column["end_x"]]), float(row[column["end_y"]])
        period = int(float(row[column["period_id"]]))
        seconds = float(row[column["time_seconds"]])
    except (ValueError, KeyError):
        return None
    kind = _SPADL_KIND.get(row[column["type_name"]], "other")
    result = row[column["result_name"]]
    goal_for = "self" if (kind in ("shot", "pen_shot") and result == "success") else (
        "opp" if result == "owngoal" else None)
    team = teams.get(normalize_id(row[column["team_id"]]), normalize_id(row[column["team_id"]]))
    return (team, kind, result == "success", start_x, start_y, end_x, end_y,
            goal_for, None, False, period, seconds)


def iter_wyscout_rows(config: MatchStyleConfig) -> Iterator[dict[str, object]]:
    source_dir = Path(config.WYSCOUT_DIR)
    games = load_games(source_dir / "games.csv")
    teams = load_lookup(source_dir / "teams.csv", "wyId", "name")
    competitions = load_lookup(source_dir / "competitions.csv", "wyId", "name")
    with open(source_dir / "actions.csv", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        column = {name: index for index, name in enumerate(next(reader))}
        current: Optional[str] = None
        buffer: list[Action] = []
        for raw in reader:
            game_id = normalize_id(raw[column["game_id"]])
            if game_id != current:
                yield from _flush_wyscout(current, buffer, games, teams, competitions, config)
                current, buffer = game_id, []
            action = _spadl_action(raw, column, teams)
            if action is not None:
                buffer.append(action)
        yield from _flush_wyscout(current, buffer, games, teams, competitions, config)


def _flush_wyscout(game_id: Optional[str], buffer: list[Action], games, teams, competitions,
                   config: MatchStyleConfig) -> list[dict[str, object]]:
    if game_id is None or not buffer:
        return []
    meta_raw = games.get(game_id)
    if meta_raw is None:
        return []
    meta = {"game_id": game_id, "competition": competitions.get(meta_raw["competition_id"], ""),
            "season": meta_raw["season"], "date": meta_raw["date"]}
    home = teams.get(meta_raw["home"], meta_raw["home"])
    away = teams.get(meta_raw["away"], meta_raw["away"])
    return match_rows(buffer, meta, home, away, "wyscout", has_xg=False, config=config)


def _to_float(value: object) -> Optional[float]:
    try:
        return float(value) if value not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def fill_xga(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Leitet xGA je Zeile aus dem xG der gegnerischen Zeile desselben Spiels ab."""
    groups: dict[tuple, list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault((row.get("source"), str(row.get("game_id"))), []).append(row)
    for group in groups.values():
        for row in group:
            partner = next((other for other in group if other is not row), None)
            opponent_xg = _to_float(partner.get("xg")) if partner else None
            opponent_np_xg = _to_float(partner.get("np_xg")) if partner else None
            opponent_shots = _to_float(partner.get("shots")) if partner else None
            row["xga"] = round(opponent_xg, 3) if opponent_xg is not None else ""
            row["np_xga"] = round(opponent_np_xg, 3) if opponent_np_xg is not None else ""
            row["xga_per_shot"] = (round(opponent_xg / opponent_shots, 3)
                                   if opponent_xg is not None and opponent_shots else "")
    return rows


def load_existing(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_all(rows: list[dict[str, object]], config: MatchStyleConfig) -> None:
    ordered = sorted(rows, key=lambda row: (str(row["source"]), str(row["competition"]),
                                            str(row["date"]), str(row["game_id"]), str(row["is_home"])))
    path = Path(config.OUTPUT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=config.FIELDNAMES)
        writer.writeheader()
        writer.writerows(ordered)


def main() -> None:
    config = MatchStyleConfig()
    kept_statsbomb = [row for row in load_existing(Path(config.OUTPUT_FILE))
                      if row.get("source") == "statsbomb"]
    wyscout_rows = list(iter_wyscout_rows(config))
    write_all(fill_xga(wyscout_rows + kept_statsbomb), config)
    print(f"  OK    {len(wyscout_rows)} Wyscout-Team-Spiel-Zeilen "
          f"(plus {len(kept_statsbomb)} vorhandene StatsBomb-Zeilen erhalten)")


if __name__ == "__main__":
    main()
