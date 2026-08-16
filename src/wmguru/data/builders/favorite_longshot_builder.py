"""Whether the market prices favourites and outsiders fairly.

Every match with a three way price is turned into one row: how likely the
market thought the favourite was once the margin is out, and whether it really
won. The bands then show where the market is off, and the flat return says
what that is worth in money.

Four sources are read, each with its own column, because the pattern only
means something if it shows up in more than one of them.
"""

from collections.abc import Iterator
from typing import Any

from wmguru.helpers.constant import (
    FavoriteLongshotCalculation,
    LineMovementCalculation,
)
from wmguru.helpers.data_class import PricedMatch
from wmguru.helpers.utils import CsvFile, DateNormalizer


class FavoriteLongshotBuilder:
    """What the market charged for a favourite, against how often it won."""

    def __init__(self, date_normalizer: DateNormalizer) -> None:
        self._date_normalizer = date_normalizer

    def build_every_match(self) -> int:
        """Write the row of every priced match and both band summaries.

        Returns:
            How many matches carried a usable three way price.
        """
        match_rows: list[dict[str, Any]] = []
        counts_of_band: dict[str, dict[str, float]] = {}
        counts_of_source: dict[str, dict[str, dict[str, float]]] = {}

        for match in self._read_every_priced_match():
            row = self._build_one_row(match)
            if row is None:
                continue
            match_rows.append(row)
            self._add_to_the_bands(counts_of_band, row)
            self._add_to_the_bands(counts_of_source.setdefault(match.source, {}), row)

        self._write_the_files(match_rows, counts_of_band, counts_of_source)
        print(f"  OK    {len(match_rows)} priced matches")
        for source in sorted(counts_of_source):
            every_band = counts_of_source[source][
                FavoriteLongshotCalculation.EVERY_BAND_NAME
            ]
            print(f"        {source}: {int(every_band['matches'])} matches")
        return len(match_rows)

    def _read_every_priced_match(self) -> Iterator[PricedMatch]:
        """Walk all four sources, one match at a time."""
        yield from self._read_football_data()
        yield from self._read_club_engineered()
        yield from self._read_footystats()
        yield from self._read_closing_odds()

    def _read_football_data(self) -> Iterator[PricedMatch]:
        """Read the club league files, taking the sharpest book each carries."""
        for odds_file in sorted(
            LineMovementCalculation.FOOTBALL_DATA_FOLDER.rglob("*.csv")
        ):
            if odds_file.name == LineMovementCalculation.COVERAGE_FILE_NAME:
                continue
            for row in CsvFile(odds_file).read_rows():
                result = row.get(LineMovementCalculation.RESULT_COLUMN, "")
                odds = self._sharpest_odds_of(row)
                if result not in LineMovementCalculation.RESULT_LETTERS or odds is None:
                    continue
                yield PricedMatch(
                    source=LineMovementCalculation.FOOTBALL_DATA_NAME,
                    match_date=row.get("Date", ""),
                    competition=odds_file.parent.name,
                    home_team=row.get("HomeTeam", ""),
                    away_team=row.get("AwayTeam", ""),
                    result_index=LineMovementCalculation.RESULT_LETTERS.index(result),
                    odds=odds,
                )

    def _sharpest_odds_of(
        self, row: dict[str, str]
    ) -> tuple[float, float, float] | None:
        """Take the first book of the file that priced all three outcomes."""
        for columns in FavoriteLongshotCalculation.ODDS_COLUMNS_BY_PREFERENCE:
            odds = self._read_odds(row, columns)
            if odds is not None:
                return odds
        return None

    def _read_club_engineered(self) -> Iterator[PricedMatch]:
        """Read the engineered club file, which overlaps football-data heavily."""
        for row in CsvFile(
            FavoriteLongshotCalculation.CLUB_ENGINEERED_FILE
        ).read_rows():
            result = row.get("FTResult", "")
            odds = self._read_odds(
                row, FavoriteLongshotCalculation.CLUB_ENGINEERED_ODDS_COLUMNS
            )
            if result not in LineMovementCalculation.RESULT_LETTERS or odds is None:
                continue
            yield PricedMatch(
                source=FavoriteLongshotCalculation.CLUB_ENGINEERED_NAME,
                match_date=row.get("MatchDate", ""),
                competition=row.get("Division", ""),
                home_team=row.get("HomeTeam", ""),
                away_team=row.get("AwayTeam", ""),
                result_index=LineMovementCalculation.RESULT_LETTERS.index(result),
                odds=odds,
            )

    def _read_footystats(self) -> Iterator[PricedMatch]:
        """Read the international and tournament files, which cover the teams."""
        for folder in FavoriteLongshotCalculation.FOOTYSTATS_FOLDERS:
            for odds_file in sorted(folder.rglob("*.csv")):
                competition = (
                    odds_file.stem
                    if odds_file.parent == folder
                    else odds_file.parent.name
                )
                for row in CsvFile(odds_file).read_rows():
                    if row.get("status") != FavoriteLongshotCalculation.COMPLETE_STATUS:
                        continue
                    odds = self._read_odds(
                        row, FavoriteLongshotCalculation.FOOTYSTATS_ODDS_COLUMNS
                    )
                    result_index = self._result_index_of(
                        row.get("home_team_goal_count"),
                        row.get("away_team_goal_count"),
                    )
                    if odds is None or result_index is None:
                        continue
                    yield PricedMatch(
                        source=FavoriteLongshotCalculation.FOOTYSTATS_NAME,
                        match_date=row.get("date_GMT", ""),
                        competition=competition,
                        home_team=row.get("home_team_name", ""),
                        away_team=row.get("away_team_name", ""),
                        result_index=result_index,
                        odds=odds,
                    )

    def _read_closing_odds(self) -> Iterator[PricedMatch]:
        """Read the international closing prices of the older tournaments."""
        for row in CsvFile(FavoriteLongshotCalculation.CLOSING_ODDS_FILE).read_rows():
            odds = self._read_odds(
                row, FavoriteLongshotCalculation.CLOSING_ODDS_COLUMNS
            )
            result_index = self._result_index_of(
                row.get("home_score"), row.get("away_score")
            )
            if odds is None or result_index is None:
                continue
            yield PricedMatch(
                source=LineMovementCalculation.BEAT_THE_BOOKIE_NAME,
                match_date=row.get("match_date", ""),
                competition=row.get("league", ""),
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                result_index=result_index,
                odds=odds,
            )

    def _read_odds(
        self, row: dict[str, str], columns: tuple[str, str, str]
    ) -> tuple[float, float, float] | None:
        """Read three prices, or None when one of them is missing or nonsense."""
        try:
            odds = tuple(float(row[column]) for column in columns)
        except (KeyError, TypeError, ValueError):
            return None
        if any(one <= LineMovementCalculation.LOWEST_SENSIBLE_ODDS for one in odds):
            return None
        return odds

    def _result_index_of(
        self, home_goals: str | None, away_goals: str | None
    ) -> int | None:
        """Read which of the three outcomes a pair of goal counts stands for."""
        try:
            scored, conceded = int(home_goals), int(away_goals)
        except (TypeError, ValueError):
            return None
        if scored > conceded:
            return 0
        return 1 if scored == conceded else 2

    def _build_one_row(self, match: PricedMatch) -> dict[str, Any] | None:
        """Build the row of one match, or None when its favourite has no band."""
        implied = self._probabilities_without_the_margin(match.odds)
        favorite = min(range(len(match.odds)), key=lambda one: match.odds[one])
        longshot = max(range(len(match.odds)), key=lambda one: match.odds[one])
        band = self._band_of(implied[favorite])
        if band is None:
            return None

        favorite_won = match.result_index == favorite
        longshot_won = match.result_index == longshot
        places = FavoriteLongshotCalculation.PROBABILITY_DECIMAL_PLACES
        return {
            "source": match.source,
            "date": self._date_normalizer.to_iso_date(match.match_date),
            "competition": match.competition,
            "home": match.home_team,
            "away": match.away_team,
            "result": LineMovementCalculation.RESULT_LETTERS[match.result_index],
            "home_odds": match.odds[0],
            "draw_odds": match.odds[1],
            "away_odds": match.odds[2],
            "favorite": FavoriteLongshotCalculation.OUTCOME_NAMES[favorite],
            "implied_favorite_probability": round(implied[favorite], places),
            "favorite_won": int(favorite_won),
            "favorite_odds": match.odds[favorite],
            "favorite_band": band,
            "favorite_profit": self._profit_of(match.odds[favorite], favorite_won),
            "longshot_profit": self._profit_of(match.odds[longshot], longshot_won),
        }

    def _profit_of(self, odds: float, was_won: bool) -> float:
        """What one unit staked on an outcome paid back, the stake taken off."""
        stake = FavoriteLongshotCalculation.ONE_UNIT_STAKE
        return odds * stake - stake if was_won else -stake

    def _probabilities_without_the_margin(
        self, odds: tuple[float, float, float]
    ) -> tuple[float, ...]:
        """Turn three prices into probabilities that add up to one."""
        implied = [1.0 / one for one in odds]
        with_the_margin = sum(implied)
        return tuple(one / with_the_margin for one in implied)

    def _band_of(self, favorite_probability: float) -> str | None:
        """Say which band a favourite of this strength falls into."""
        edges = FavoriteLongshotCalculation.BAND_EDGES
        for lower, upper in zip(edges[:-1], edges[1:], strict=False):
            if lower <= favorite_probability < upper:
                return f"{lower:.2f}_{min(upper, 1.0):.2f}"
        return None

    def _add_to_the_bands(
        self, counts_of_band: dict[str, dict[str, float]], row: dict[str, Any]
    ) -> None:
        """Add one match to its own band and to the total."""
        for band in (
            row["favorite_band"],
            FavoriteLongshotCalculation.EVERY_BAND_NAME,
        ):
            counts = counts_of_band.setdefault(band, self._empty_counts())
            counts["matches"] += 1.0
            counts["implied_sum"] += row["implied_favorite_probability"]
            counts["favorite_wins"] += row["favorite_won"]
            counts["favorite_profit"] += row["favorite_profit"]
            counts["longshot_profit"] += row["longshot_profit"]

    def _empty_counts(self) -> dict[str, float]:
        """Build a count that holds a zero for everything that is counted."""
        return {
            "matches": 0.0,
            "implied_sum": 0.0,
            "favorite_wins": 0.0,
            "favorite_profit": 0.0,
            "longshot_profit": 0.0,
        }

    def _build_band_rows(
        self,
        counts_of_band: dict[str, dict[str, float]],
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """Turn the counted bands into rows, the total last."""
        every_band = FavoriteLongshotCalculation.EVERY_BAND_NAME
        ordered = [name for name in sorted(counts_of_band) if name != every_band]
        if every_band in counts_of_band:
            ordered.append(every_band)

        rows: list[dict[str, Any]] = []
        for band in ordered:
            counts = counts_of_band[band]
            if not counts["matches"]:
                continue
            match_count = counts["matches"]
            charged = counts["implied_sum"] / match_count
            really_won = counts["favorite_wins"] / match_count
            places = FavoriteLongshotCalculation.PROBABILITY_DECIMAL_PLACES
            row: dict[str, Any] = {} if source is None else {"source": source}
            row.update(
                {
                    "favorite_band": band,
                    "matches": int(match_count),
                    "mean_implied_favorite_probability": round(charged, places),
                    "actual_favorite_win_rate": round(really_won, places),
                    "calibration_gap": round(charged - really_won, places),
                    "favorite_flat_return_percent": self._return_percent(
                        counts["favorite_profit"], match_count
                    ),
                    "longshot_flat_return_percent": self._return_percent(
                        counts["longshot_profit"], match_count
                    ),
                }
            )
            rows.append(row)
        return rows

    def _return_percent(self, profit: float, match_count: float) -> float:
        """What staking one unit on every match of a band paid back, per cent."""
        return round(
            100.0 * profit / match_count,
            FavoriteLongshotCalculation.PERCENT_DECIMAL_PLACES,
        )

    def _written_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Cut a row down to the columns of the file, rounding the profit.

        The profit is carried unrounded until here, because rounding every
        match first and adding those up afterwards would drift away from the
        real return of a band.
        """
        written = {
            name: row[name] for name in FavoriteLongshotCalculation.MATCH_COLUMN_NAMES
        }
        written["favorite_profit"] = round(
            row["favorite_profit"],
            FavoriteLongshotCalculation.PROBABILITY_DECIMAL_PLACES,
        )
        return written

    def _write_the_files(
        self,
        match_rows: list[dict[str, Any]],
        counts_of_band: dict[str, dict[str, float]],
        counts_of_source: dict[str, dict[str, dict[str, float]]],
    ) -> None:
        """Write the match rows and the two band summaries."""
        CsvFile(
            FavoriteLongshotCalculation.MATCH_OUTPUT_FILE,
            FavoriteLongshotCalculation.MATCH_COLUMN_NAMES,
        ).write_dict_rows(
            [
                self._written_row(row)
                for row in sorted(
                    match_rows,
                    key=lambda one: (
                        str(one["competition"]),
                        str(one["date"]),
                        str(one["home"]),
                    ),
                )
            ]
        )
        CsvFile(
            FavoriteLongshotCalculation.BAND_OUTPUT_FILE,
            FavoriteLongshotCalculation.BAND_COLUMN_NAMES,
        ).write_dict_rows(self._build_band_rows(counts_of_band))

        by_source_rows: list[dict[str, Any]] = []
        for source in sorted(counts_of_source):
            by_source_rows.extend(
                self._build_band_rows(counts_of_source[source], source=source)
            )
        CsvFile(
            FavoriteLongshotCalculation.BY_SOURCE_OUTPUT_FILE,
            FavoriteLongshotCalculation.BY_SOURCE_COLUMN_NAMES,
        ).write_dict_rows(by_source_rows)


if __name__ == "__main__":
    FavoriteLongshotBuilder(DateNormalizer()).build_every_match()
