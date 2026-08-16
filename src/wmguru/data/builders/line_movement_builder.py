"""How the odds moved between the opening price and the closing one.

The difference between the two, once the bookmaker margin is out, is the
clearest trace of informed money there is. A league summary then says whether
the closing line really was sharper than the opening one, which is the check
every closing line value claim rests on.

Only the two sources that carry both prices can say anything here. The others
give one snapshot and are left out.
"""

import math
from collections.abc import Iterator
from typing import Any

from wmguru.helpers.constant import LineMovementCalculation
from wmguru.helpers.utils import CsvFile, DateNormalizer


class LineMovementBuilder:
    """The movement of every match, out of its opening and closing odds."""

    def __init__(self, date_normalizer: DateNormalizer) -> None:
        self._date_normalizer = date_normalizer

    def build_every_match(self) -> int:
        """Write the movement of every match and the summary per league.

        Returns:
            How many matches carried both an opening and a closing price.
        """
        rows = sorted(
            [
                *self._read_football_data(),
                *self._read_beat_the_bookie(),
            ],
            key=lambda one: (str(one["league"]), str(one["date"]), str(one["home"])),
        )
        summary_rows = self._summarise_per_league(rows)

        CsvFile(
            LineMovementCalculation.OUTPUT_FILE,
            LineMovementCalculation.COLUMN_NAMES,
        ).write_dict_rows([self._without_the_log_loss(row) for row in rows])
        CsvFile(
            LineMovementCalculation.SUMMARY_OUTPUT_FILE,
            LineMovementCalculation.SUMMARY_COLUMN_NAMES,
        ).write_dict_rows(summary_rows)

        sharper = sum(
            1 for row in summary_rows if float(row["log_loss_improvement"]) > 0
        )
        print(f"  OK    {len(rows)} matches with an opening and a closing price")
        print(
            f"  OK    {len(summary_rows)} source and league groups, "
            f"{sharper} of them with a sharper closing line"
        )
        return len(rows)

    def _read_football_data(self) -> Iterator[dict[str, Any]]:
        """Read the club league files, which carry the Pinnacle prices."""
        for odds_file in sorted(
            LineMovementCalculation.FOOTBALL_DATA_FOLDER.rglob("*.csv")
        ):
            if odds_file.name == LineMovementCalculation.COVERAGE_FILE_NAME:
                continue
            for row in CsvFile(odds_file).read_rows():
                result = row.get(LineMovementCalculation.RESULT_COLUMN, "")
                if result not in LineMovementCalculation.RESULT_LETTERS:
                    continue
                built = self._build_one_row(
                    row,
                    LineMovementCalculation.FOOTBALL_DATA_NAME,
                    odds_file.parent.name,
                    odds_file.stem,
                    row.get("Date", ""),
                    row.get("HomeTeam", ""),
                    row.get("AwayTeam", ""),
                    LineMovementCalculation.RESULT_LETTERS.index(result),
                    LineMovementCalculation.OPENING_COLUMNS,
                    LineMovementCalculation.CLOSING_COLUMNS,
                )
                if built is not None:
                    yield built

    def _read_beat_the_bookie(self) -> Iterator[dict[str, Any]]:
        """Read the international file, which carries an average of the books."""
        if not LineMovementCalculation.BEAT_THE_BOOKIE_FILE.exists():
            return
        for row in CsvFile(LineMovementCalculation.BEAT_THE_BOOKIE_FILE).read_rows():
            result_index = self._result_index_of(row.get("score", ""))
            if result_index is None:
                continue
            built = self._build_one_row(
                row,
                LineMovementCalculation.BEAT_THE_BOOKIE_NAME,
                row.get("league", ""),
                LineMovementCalculation.BEAT_THE_BOOKIE_SEASON,
                row.get("match_datetime", ""),
                row.get("home_team", ""),
                row.get("away_team", ""),
                result_index,
                LineMovementCalculation.BEAT_THE_BOOKIE_OPENING_COLUMNS,
                LineMovementCalculation.BEAT_THE_BOOKIE_CLOSING_COLUMNS,
            )
            if built is not None:
                yield built

    def _result_index_of(self, score: str) -> int | None:
        """Read which of the three outcomes a written score stands for."""
        try:
            home_goals, away_goals = (int(part) for part in score.split(":"))
        except (TypeError, ValueError):
            return None
        if home_goals > away_goals:
            return 0
        return 1 if home_goals == away_goals else 2

    def _build_one_row(
        self,
        row: dict[str, str],
        source: str,
        league: str,
        season: str,
        raw_date: str,
        home_team: str,
        away_team: str,
        result_index: int,
        opening_columns: tuple[str, str, str],
        closing_columns: tuple[str, str, str],
    ) -> dict[str, Any] | None:
        """Build the movement row of one match, or None when a price is missing."""
        opening = self._read_probabilities(row, opening_columns)
        closing = self._read_probabilities(row, closing_columns)
        if opening is None or closing is None:
            return None

        movements = [
            closing[outcome] - opening[outcome] for outcome in range(len(opening))
        ]
        places = LineMovementCalculation.DECIMAL_PLACES
        return {
            "source": source,
            "league": league,
            "season": season,
            "date": self._date_normalizer.to_iso_date(raw_date),
            "home": home_team,
            "away": away_team,
            "result": LineMovementCalculation.RESULT_LETTERS[result_index],
            "opening_home_probability": round(opening[0], places),
            "opening_draw_probability": round(opening[1], places),
            "opening_away_probability": round(opening[2], places),
            "closing_home_probability": round(closing[0], places),
            "closing_draw_probability": round(closing[1], places),
            "closing_away_probability": round(closing[2], places),
            "home_movement": round(movements[0], places),
            "draw_movement": round(movements[1], places),
            "away_movement": round(movements[2], places),
            "total_movement": round(
                0.5 * sum(abs(movement) for movement in movements), places
            ),
            "movement_towards_the_result": round(
                closing[result_index] - opening[result_index], places
            ),
            "opening_log_loss": self._log_loss_of(opening[result_index]),
            "closing_log_loss": self._log_loss_of(closing[result_index]),
        }

    def _read_probabilities(
        self, row: dict[str, str], columns: tuple[str, str, str]
    ) -> tuple[float, float, float] | None:
        """Read three odds and turn them into probabilities without the margin.

        Returns:
            The three probabilities, which add up to one, or None when the
            row carries no usable price. The three prices always imply more
            than one between them, and that surplus is the margin of the
            bookmaker, which is divided out.
        """
        try:
            odds = tuple(float(row[column]) for column in columns)
        except (KeyError, TypeError, ValueError):
            return None
        if any(one <= LineMovementCalculation.LOWEST_SENSIBLE_ODDS for one in odds):
            return None
        implied = [1.0 / one for one in odds]
        with_the_margin = sum(implied)
        return tuple(one / with_the_margin for one in implied)

    def _log_loss_of(self, probability: float) -> float:
        """How badly a price missed the outcome that really happened."""
        return -math.log(max(probability, LineMovementCalculation.PROBABILITY_FLOOR))

    def _summarise_per_league(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Say per source and league whether the closing line really was sharper."""
        rows_of_league: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            rows_of_league.setdefault((row["source"], row["league"]), []).append(row)

        places = LineMovementCalculation.DECIMAL_PLACES
        summary: list[dict[str, Any]] = []
        for (source, league), league_rows in sorted(rows_of_league.items()):
            match_count = len(league_rows)
            opening_loss = self._average(league_rows, "opening_log_loss")
            closing_loss = self._average(league_rows, "closing_log_loss")
            summary.append(
                {
                    "source": source,
                    "league": league,
                    "matches": match_count,
                    "opening_log_loss": round(opening_loss, places),
                    "closing_log_loss": round(closing_loss, places),
                    "log_loss_improvement": round(opening_loss - closing_loss, places),
                    "mean_total_movement": round(
                        self._average(league_rows, "total_movement"), places
                    ),
                    "share_moved_towards_the_result": round(
                        sum(
                            1
                            for one in league_rows
                            if one["movement_towards_the_result"] > 0
                        )
                        / match_count,
                        places,
                    ),
                }
            )
        return sorted(summary, key=lambda one: -int(one["matches"]))

    def _average(self, rows: list[dict[str, Any]], column_name: str) -> float:
        """Average one column over the rows of a league."""
        return sum(float(row[column_name]) for row in rows) / len(rows)

    def _without_the_log_loss(self, row: dict[str, Any]) -> dict[str, Any]:
        """Drop the two columns that only the summary needs."""
        return {name: row[name] for name in LineMovementCalculation.COLUMN_NAMES}


if __name__ == "__main__":
    LineMovementBuilder(DateNormalizer()).build_every_match()
