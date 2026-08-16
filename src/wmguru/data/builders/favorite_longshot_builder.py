"""Whether the market prices favourites and outsiders fairly.

Every match with a three way price is turned into one row: how likely the
market thought the favourite was once the margin is out, and whether it really
won. The bands then show where the market is off, and the flat return says
what that is worth in money.

Four sources are read, each with its own column, because the pattern only
means something if it shows up in more than one of them.
"""

import numpy as np
import pandas as pd

from wmguru.helpers.constant import (
    FavoriteLongshotCalculation,
    LineMovementCalculation,
)
from wmguru.helpers.utils import CsvFile, DateNormalizer, DecimalRounder

ODDS_COLUMNS = ["home_odds", "draw_odds", "away_odds"]


class FavoriteLongshotBuilder:
    """What the market charged for a favourite, against how often it won."""

    def __init__(self, date_normalizer: DateNormalizer) -> None:
        self._date_normalizer = date_normalizer

    def build_every_match(self) -> int:
        """Write the row of every priced match and both band summaries.

        Returns:
            How many matches carried a usable three way price.
        """
        priced_matches = self._read_every_priced_match()
        matches = self._describe_every_match(priced_matches)

        CsvFile(
            FavoriteLongshotCalculation.MATCH_OUTPUT_FILE,
            FavoriteLongshotCalculation.MATCH_COLUMN_NAMES,
        ).write_table(self._rounded_for_writing(matches))
        CsvFile(
            FavoriteLongshotCalculation.BAND_OUTPUT_FILE,
            FavoriteLongshotCalculation.BAND_COLUMN_NAMES,
        ).write_table(self._summarise_the_bands(matches, []))
        by_source = self._summarise_the_bands(matches, ["source"])
        CsvFile(
            FavoriteLongshotCalculation.BY_SOURCE_OUTPUT_FILE,
            FavoriteLongshotCalculation.BY_SOURCE_COLUMN_NAMES,
        ).write_table(by_source)

        print(f"  OK    {len(matches)} priced matches")
        whole_source = by_source[
            by_source["favorite_band"] == FavoriteLongshotCalculation.EVERY_BAND_NAME
        ]
        print(
            "\n".join(
                "        "
                + whole_source["source"]
                + ": "
                + whole_source["matches"].astype(str)
                + " matches"
            )
        )
        return len(matches)

    def _read_every_priced_match(self) -> pd.DataFrame:
        """Stack all four sources into the one table they are measured in."""
        return pd.concat(
            [
                self._read_football_data(),
                self._read_club_engineered(),
                self._read_footystats(),
                self._read_closing_odds(),
            ],
            ignore_index=True,
        )

    def _read_football_data(self) -> pd.DataFrame:
        """Read the club league files, taking the sharpest book each carries."""
        odds_files = [
            odds_file
            for odds_file in sorted(
                LineMovementCalculation.FOOTBALL_DATA_FOLDER.rglob("*.csv")
            )
            if odds_file.name != LineMovementCalculation.COVERAGE_FILE_NAME
        ]
        every_file = pd.concat(
            [
                CsvFile(odds_file)
                .read_table()
                .assign(competition=odds_file.parent.name)
                for odds_file in odds_files
            ],
            ignore_index=True,
        )
        with_a_result = every_file[
            every_file[LineMovementCalculation.RESULT_COLUMN].isin(
                list(LineMovementCalculation.RESULT_LETTERS)
            )
        ]
        return self._as_one_priced_match(
            with_a_result,
            source=LineMovementCalculation.FOOTBALL_DATA_NAME,
            competition=with_a_result["competition"],
            written_date=with_a_result["Date"],
            home_team=with_a_result["HomeTeam"],
            away_team=with_a_result["AwayTeam"],
            result_index=self._index_of_every_result_letter(
                with_a_result[LineMovementCalculation.RESULT_COLUMN]
            ),
            odds=self._sharpest_odds_of(with_a_result),
        )

    def _sharpest_odds_of(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Take the first book of the file that priced all three outcomes.

        Every book is read on its own and a row that one of them left half
        priced is emptied out completely, so falling back to the next book
        can never mix two books into one price.
        """
        every_book = [
            self._readable_odds(matches, columns)
            for columns in FavoriteLongshotCalculation.ODDS_COLUMNS_BY_PREFERENCE
        ]
        sharpest = every_book[0]
        for next_book in every_book[1:]:
            sharpest = sharpest.fillna(next_book)
        return sharpest

    def _read_club_engineered(self) -> pd.DataFrame:
        """Read the engineered club file, which overlaps football-data heavily."""
        matches = CsvFile(FavoriteLongshotCalculation.CLUB_ENGINEERED_FILE).read_table()
        with_a_result = matches[
            matches["FTResult"].isin(list(LineMovementCalculation.RESULT_LETTERS))
        ]
        return self._as_one_priced_match(
            with_a_result,
            source=FavoriteLongshotCalculation.CLUB_ENGINEERED_NAME,
            competition=with_a_result["Division"],
            written_date=with_a_result["MatchDate"],
            home_team=with_a_result["HomeTeam"],
            away_team=with_a_result["AwayTeam"],
            result_index=self._index_of_every_result_letter(with_a_result["FTResult"]),
            odds=self._readable_odds(
                with_a_result, FavoriteLongshotCalculation.CLUB_ENGINEERED_ODDS_COLUMNS
            ),
        )

    def _read_footystats(self) -> pd.DataFrame:
        """Read the international and tournament files, which cover the teams."""
        named_files = [
            (
                odds_file,
                odds_file.stem if odds_file.parent == folder else odds_file.parent.name,
            )
            for folder in FavoriteLongshotCalculation.FOOTYSTATS_FOLDERS
            for odds_file in sorted(folder.rglob("*.csv"))
        ]
        every_file = pd.concat(
            [
                CsvFile(odds_file).read_table().assign(competition=competition)
                for odds_file, competition in named_files
            ],
            ignore_index=True,
        )
        finished = every_file[
            every_file["status"] == FavoriteLongshotCalculation.COMPLETE_STATUS
        ]
        return self._as_one_priced_match(
            finished,
            source=FavoriteLongshotCalculation.FOOTYSTATS_NAME,
            competition=finished["competition"],
            written_date=finished["date_GMT"],
            home_team=finished["home_team_name"],
            away_team=finished["away_team_name"],
            result_index=self._index_of_every_goal_count(
                finished["home_team_goal_count"], finished["away_team_goal_count"]
            ),
            odds=self._readable_odds(
                finished, FavoriteLongshotCalculation.FOOTYSTATS_ODDS_COLUMNS
            ),
        )

    def _read_closing_odds(self) -> pd.DataFrame:
        """Read the international closing prices of the older tournaments."""
        matches = CsvFile(FavoriteLongshotCalculation.CLOSING_ODDS_FILE).read_table()
        return self._as_one_priced_match(
            matches,
            source=LineMovementCalculation.BEAT_THE_BOOKIE_NAME,
            competition=matches["league"],
            written_date=matches["match_date"],
            home_team=matches["home_team"],
            away_team=matches["away_team"],
            result_index=self._index_of_every_goal_count(
                matches["home_score"], matches["away_score"]
            ),
            odds=self._readable_odds(
                matches, FavoriteLongshotCalculation.CLOSING_ODDS_COLUMNS
            ),
        )

    def _as_one_priced_match(
        self,
        matches: pd.DataFrame,
        source: str,
        competition: pd.Series,
        written_date: pd.Series,
        home_team: pd.Series,
        away_team: pd.Series,
        result_index: pd.Series,
        odds: pd.DataFrame,
    ) -> pd.DataFrame:
        """Bring one source into the shape all four of them are measured in.

        Returns:
            One row per match that has both a result and a full price, the
            date already rewritten the same way for every source.
        """
        priced = pd.DataFrame(
            {
                "source": source,
                "match_date": self._date_normalizer.to_iso_date_of_every_row(
                    written_date
                ),
                "competition": competition,
                "home_team": home_team,
                "away_team": away_team,
                "result_index": result_index,
                **{name: odds[name] for name in ODDS_COLUMNS},
            }
        )
        is_usable = priced[["result_index", *ODDS_COLUMNS]].notna().all(axis="columns")
        return priced[is_usable].astype({"result_index": int}).reset_index(drop=True)

    def _readable_odds(
        self, matches: pd.DataFrame, column_names: tuple[str, str, str]
    ) -> pd.DataFrame:
        """Read three price columns, emptying a row that one of them spoils.

        Returns:
            The three prices, or nothing at all in a row where one is
            missing or too small to be a real price.
        """
        odds = matches.reindex(columns=list(column_names)).apply(
            pd.to_numeric, errors="coerce"
        )
        odds.columns = ODDS_COLUMNS
        is_a_real_price = odds.gt(LineMovementCalculation.LOWEST_SENSIBLE_ODDS).all(
            axis="columns"
        )
        return odds.where(is_a_real_price)

    def _index_of_every_result_letter(self, result_letters: pd.Series) -> pd.Series:
        """Read which of the three outcomes each written letter stands for."""
        letters = list(LineMovementCalculation.RESULT_LETTERS)
        return result_letters.map({letter: letters.index(letter) for letter in letters})

    def _index_of_every_goal_count(
        self, home_goals: pd.Series, away_goals: pd.Series
    ) -> pd.Series:
        """Read which of the three outcomes each pair of goal counts stands for."""
        scored = pd.to_numeric(home_goals, errors="coerce")
        conceded = pd.to_numeric(away_goals, errors="coerce")
        return pd.Series(
            np.select(
                [
                    scored.isna() | conceded.isna(),
                    scored > conceded,
                    scored == conceded,
                ],
                [np.nan, 0.0, 1.0],
                default=2.0,
            ),
            index=home_goals.index,
        )

    def _describe_every_match(self, priced_matches: pd.DataFrame) -> pd.DataFrame:
        """Name the favourite and the outsider of every match and price both.

        A match whose favourite falls outside every band drops out, because
        there is no row of the summary it could belong to.
        """
        odds = priced_matches[ODDS_COLUMNS].to_numpy(dtype=float)
        implied = 1.0 / odds
        without_the_margin = implied / implied.sum(axis=1, keepdims=True)

        favorite = odds.argmin(axis=1)
        longshot = odds.argmax(axis=1)
        result = priced_matches["result_index"].to_numpy()
        favorite_won = result == favorite
        longshot_won = result == longshot

        described = priced_matches.assign(
            date=priced_matches["match_date"],
            home=priced_matches["home_team"],
            away=priced_matches["away_team"],
            result=priced_matches["result_index"].map(
                dict(enumerate(LineMovementCalculation.RESULT_LETTERS))
            ),
            favorite=[
                FavoriteLongshotCalculation.OUTCOME_NAMES[one] for one in favorite
            ],
            implied_favorite_probability=self._the_value_of_the_wanted_outcome(
                without_the_margin, favorite
            ),
            favorite_won=favorite_won.astype(int),
            favorite_odds=self._the_value_of_the_wanted_outcome(odds, favorite),
            favorite_band=self._which_band_the_favourite_falls_into(
                pd.Series(
                    self._the_value_of_the_wanted_outcome(without_the_margin, favorite),
                    index=priced_matches.index,
                )
            ),
            favorite_profit=self._profit_of(
                self._the_value_of_the_wanted_outcome(odds, favorite), favorite_won
            ),
            longshot_profit=self._profit_of(
                self._the_value_of_the_wanted_outcome(odds, longshot), longshot_won
            ),
        )
        return (
            described.dropna(subset=["favorite_band"])
            .sort_values(["competition", "date", "home"], kind="stable")
            .reset_index(drop=True)
        )

    def _the_value_of_the_wanted_outcome(
        self, of_every_outcome: np.ndarray, wanted: np.ndarray
    ) -> np.ndarray:
        """Take one of the three outcome values out of every row."""
        return np.take_along_axis(of_every_outcome, wanted[:, None], axis=1).ravel()

    def _profit_of(self, odds: np.ndarray, was_won: np.ndarray) -> np.ndarray:
        """What one unit staked on an outcome paid back, the stake taken off."""
        stake = FavoriteLongshotCalculation.ONE_UNIT_STAKE
        return np.where(was_won, odds * stake - stake, -stake)

    def _which_band_the_favourite_falls_into(
        self, favorite_probability: pd.Series
    ) -> pd.Series:
        """Say which band a favourite of this strength falls into."""
        edges = FavoriteLongshotCalculation.BAND_EDGES
        names = [
            f"{lower:.2f}_{min(upper, 1.0):.2f}"
            for lower, upper in zip(edges[:-1], edges[1:], strict=False)
        ]
        return pd.cut(
            favorite_probability, bins=list(edges), labels=names, right=False
        ).astype(object)

    def _summarise_the_bands(
        self, matches: pd.DataFrame, split_by: list[str]
    ) -> pd.DataFrame:
        """Add every band up, and every band of every source when asked to.

        Args:
            matches: One row per priced match, the band already on it.
            split_by: The columns to keep apart, empty for the summary over
                all four sources together.

        Returns:
            One row per band, the row that holds them all last.
        """
        every_band = FavoriteLongshotCalculation.EVERY_BAND_NAME
        counted = pd.concat(
            [matches, matches.assign(favorite_band=every_band)], ignore_index=True
        )
        summary = (
            counted.groupby([*split_by, "favorite_band"], sort=True)
            .agg(
                matches=("favorite_won", "size"),
                mean_implied_favorite_probability=(
                    "implied_favorite_probability",
                    "mean",
                ),
                actual_favorite_win_rate=("favorite_won", "mean"),
                favorite_flat_return_percent=("favorite_profit", "mean"),
                longshot_flat_return_percent=("longshot_profit", "mean"),
            )
            .reset_index()
        )
        probability_rounder = DecimalRounder(
            FavoriteLongshotCalculation.PROBABILITY_DECIMAL_PLACES
        )
        percent_rounder = DecimalRounder(
            FavoriteLongshotCalculation.PERCENT_DECIMAL_PLACES
        )
        priced = summary.assign(
            calibration_gap=summary["mean_implied_favorite_probability"]
            - summary["actual_favorite_win_rate"],
            favorite_flat_return_percent=100.0
            * summary["favorite_flat_return_percent"],
            longshot_flat_return_percent=100.0
            * summary["longshot_flat_return_percent"],
        )
        rounded = percent_rounder.round_every_column(
            probability_rounder.round_every_column(
                priced,
                [
                    "mean_implied_favorite_probability",
                    "actual_favorite_win_rate",
                    "calibration_gap",
                ],
            ),
            ["favorite_flat_return_percent", "longshot_flat_return_percent"],
        )
        return rounded.sort_values(
            [*split_by, "favorite_band"],
            key=lambda column: (
                (column == every_band) if column.name == "favorite_band" else column
            ),
            kind="stable",
        )

    def _rounded_for_writing(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Cut the probability and the profit down to the digits the file holds.

        The profit is carried unrounded until here, because rounding every
        match first and adding those up afterwards would drift away from the
        real return of a band.
        """
        return DecimalRounder(
            FavoriteLongshotCalculation.PROBABILITY_DECIMAL_PLACES
        ).round_every_column(
            matches, ["implied_favorite_probability", "favorite_profit"]
        )


if __name__ == "__main__":
    FavoriteLongshotBuilder(DateNormalizer()).build_every_match()
