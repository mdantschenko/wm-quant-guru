"""How the odds moved between the opening price and the closing one.

The difference between the two, once the bookmaker margin is out, is the
clearest trace of informed money there is. A league summary then says whether
the closing line really was sharper than the opening one, which is the check
every closing line value claim rests on.

Only the two sources that carry both prices can say anything here. The others
give one snapshot and are left out.
"""

import numpy as np
import pandas as pd

from wmguru.helpers.constant import LineMovementCalculation
from wmguru.helpers.utils import CsvFile, DateNormalizer, DecimalRounder

OUTCOME_SIDES = ["home", "draw", "away"]


class LineMovementBuilder:
    """The movement of every match, out of its opening and closing odds."""

    def __init__(self, date_normalizer: DateNormalizer) -> None:
        self._date_normalizer = date_normalizer

    def build_every_match(self) -> int:
        """Write the movement of every match and the summary per league.

        Returns:
            How many matches carried both an opening and a closing price.
        """
        both_sources = pd.concat(
            [self._read_football_data(), self._read_beat_the_bookie()],
            ignore_index=True,
        )
        movements = self._measure_the_movement(both_sources)
        league_summary = self._summarise_per_league(movements)

        CsvFile(
            LineMovementCalculation.OUTPUT_FILE,
            LineMovementCalculation.COLUMN_NAMES,
        ).write_table(movements)
        CsvFile(
            LineMovementCalculation.SUMMARY_OUTPUT_FILE,
            LineMovementCalculation.SUMMARY_COLUMN_NAMES,
        ).write_table(league_summary)

        sharper = (league_summary["log_loss_improvement"] > 0).sum()
        print(f"  OK    {len(movements)} matches with an opening and a closing price")
        print(
            f"  OK    {len(league_summary)} source and league groups, "
            f"{sharper} of them with a sharper closing line"
        )
        return len(movements)

    def _read_football_data(self) -> pd.DataFrame:
        """Read the club league files, which carry the Pinnacle prices."""
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
                .assign(league=odds_file.parent.name, season=odds_file.stem)
                for odds_file in odds_files
            ],
            ignore_index=True,
        )
        result_letter = every_file[LineMovementCalculation.RESULT_COLUMN]
        with_a_result = every_file[
            result_letter.isin(list(LineMovementCalculation.RESULT_LETTERS))
        ]
        return self._as_one_priced_match(
            with_a_result,
            source=LineMovementCalculation.FOOTBALL_DATA_NAME,
            league=with_a_result["league"],
            season=with_a_result["season"],
            written_date=with_a_result["Date"],
            home_team=with_a_result["HomeTeam"],
            away_team=with_a_result["AwayTeam"],
            result_index=self._index_of_every_result_letter(
                with_a_result[LineMovementCalculation.RESULT_COLUMN]
            ),
            opening_columns=LineMovementCalculation.OPENING_COLUMNS,
            closing_columns=LineMovementCalculation.CLOSING_COLUMNS,
        )

    def _read_beat_the_bookie(self) -> pd.DataFrame:
        """Read the international file, which carries an average of the books."""
        if not LineMovementCalculation.BEAT_THE_BOOKIE_FILE.exists():
            return pd.DataFrame()
        matches = CsvFile(LineMovementCalculation.BEAT_THE_BOOKIE_FILE).read_table()
        result_index = self._index_of_every_written_score(matches["score"])
        with_a_result = matches[result_index.notna()]
        return self._as_one_priced_match(
            with_a_result,
            source=LineMovementCalculation.BEAT_THE_BOOKIE_NAME,
            league=with_a_result["league"],
            season=LineMovementCalculation.BEAT_THE_BOOKIE_SEASON,
            written_date=with_a_result["match_datetime"],
            home_team=with_a_result["home_team"],
            away_team=with_a_result["away_team"],
            result_index=result_index[result_index.notna()].astype(int),
            opening_columns=LineMovementCalculation.BEAT_THE_BOOKIE_OPENING_COLUMNS,
            closing_columns=LineMovementCalculation.BEAT_THE_BOOKIE_CLOSING_COLUMNS,
        )

    def _as_one_priced_match(
        self,
        matches: pd.DataFrame,
        source: str,
        league: pd.Series,
        season: pd.Series | str,
        written_date: pd.Series,
        home_team: pd.Series,
        away_team: pd.Series,
        result_index: pd.Series,
        opening_columns: tuple[str, str, str],
        closing_columns: tuple[str, str, str],
    ) -> pd.DataFrame:
        """Bring one source into the shape both of them are measured in.

        Every source names its columns differently, so this is where the two
        stop being different and become the same table.

        Returns:
            One row per match that carries both prices, the odds already
            turned into probabilities without the margin.
        """
        opening = self._probabilities_without_the_margin(matches, opening_columns)
        closing = self._probabilities_without_the_margin(matches, closing_columns)
        both_prices_are_there = opening.notna().all(
            axis="columns"
        ) & closing.notna().all(axis="columns")
        priced = pd.DataFrame(
            {
                "source": source,
                "league": league,
                "season": season,
                "date": self._date_normalizer.to_iso_date_of_every_row(written_date),
                "home": home_team,
                "away": away_team,
                "result_index": result_index,
                **{f"opening_{side}": opening[side] for side in OUTCOME_SIDES},
                **{f"closing_{side}": closing[side] for side in OUTCOME_SIDES},
            }
        )
        return priced[both_prices_are_there].reset_index(drop=True)

    def _probabilities_without_the_margin(
        self, matches: pd.DataFrame, column_names: tuple[str, str, str]
    ) -> pd.DataFrame:
        """Turn three odds columns into probabilities that add up to one.

        The three prices always imply more than one between them, and that
        surplus is the margin of the bookmaker, which is divided out.

        Returns:
            One column per outcome, and nothing at all in a row whose price
            is missing or nonsense.
        """
        odds = matches.reindex(columns=list(column_names)).apply(
            pd.to_numeric, errors="coerce"
        )
        odds.columns = OUTCOME_SIDES
        is_a_real_price = odds.gt(LineMovementCalculation.LOWEST_SENSIBLE_ODDS).all(
            axis="columns"
        )
        implied = 1.0 / odds
        return implied.div(implied.sum(axis="columns"), axis="index").where(
            is_a_real_price
        )

    def _index_of_every_result_letter(self, result_letters: pd.Series) -> pd.Series:
        """Read which of the three outcomes each written letter stands for."""
        letters = list(LineMovementCalculation.RESULT_LETTERS)
        return result_letters.map({letter: letters.index(letter) for letter in letters})

    def _index_of_every_written_score(self, written_scores: pd.Series) -> pd.Series:
        """Read which of the three outcomes each written score stands for.

        Returns:
            Nothing at all for a score that is no score, so the caller can
            drop the row rather than guess an outcome for it.
        """
        both_goals = written_scores.str.split(
            LineMovementCalculation.SCORE_SEPARATOR, expand=True
        )
        home_goals = pd.to_numeric(both_goals[0], errors="coerce")
        away_goals = pd.to_numeric(both_goals[1], errors="coerce")
        return pd.Series(
            np.select(
                [
                    home_goals.isna() | away_goals.isna(),
                    home_goals > away_goals,
                    home_goals == away_goals,
                ],
                [np.nan, 0.0, 1.0],
                default=2.0,
            ),
            index=written_scores.index,
        )

    def _measure_the_movement(self, priced_matches: pd.DataFrame) -> pd.DataFrame:
        """Say for every match how far the price moved and which way.

        The log loss of both prices stays on the table because the league
        summary needs it, and the writer drops it again.
        """
        movement = {
            side: priced_matches[f"closing_{side}"] - priced_matches[f"opening_{side}"]
            for side in OUTCOME_SIDES
        }
        opening_on_the_result = self._probability_of_the_result(
            priced_matches, "opening"
        )
        closing_on_the_result = self._probability_of_the_result(
            priced_matches, "closing"
        )
        rounder = DecimalRounder(LineMovementCalculation.DECIMAL_PLACES)
        measured = priced_matches.assign(
            result=priced_matches["result_index"].map(
                dict(enumerate(LineMovementCalculation.RESULT_LETTERS))
            ),
            total_movement=0.5 * sum(one.abs() for one in movement.values()),
            movement_towards_the_result=closing_on_the_result - opening_on_the_result,
            opening_log_loss=self._log_loss_of(opening_on_the_result),
            closing_log_loss=self._log_loss_of(closing_on_the_result),
            **{f"{side}_movement": movement[side] for side in OUTCOME_SIDES},
            **{
                f"{when}_{side}_probability": priced_matches[f"{when}_{side}"]
                for when in ("opening", "closing")
                for side in OUTCOME_SIDES
            },
        )
        rounded_columns = [
            *(
                f"{when}_{side}_probability"
                for when in ("opening", "closing")
                for side in OUTCOME_SIDES
            ),
            *(f"{side}_movement" for side in OUTCOME_SIDES),
            "total_movement",
            "movement_towards_the_result",
        ]
        return rounder.round_every_column(measured, rounded_columns).sort_values(
            ["league", "date", "home"], kind="stable"
        )

    def _probability_of_the_result(
        self, priced_matches: pd.DataFrame, when: str
    ) -> pd.Series:
        """Pick out what one price charged for the outcome that really happened."""
        every_side = np.column_stack(
            [priced_matches[f"{when}_{side}"] for side in OUTCOME_SIDES]
        )
        return pd.Series(
            np.take_along_axis(
                every_side,
                priced_matches["result_index"].to_numpy()[:, None],
                axis=1,
            ).ravel(),
            index=priced_matches.index,
        )

    def _log_loss_of(self, probability: pd.Series) -> pd.Series:
        """How badly a price missed the outcome that really happened."""
        return -np.log(
            probability.clip(lower=LineMovementCalculation.PROBABILITY_FLOOR)
        )

    def _summarise_per_league(self, movements: pd.DataFrame) -> pd.DataFrame:
        """Say per source and league whether the closing line really was sharper."""
        moved_the_right_way = movements["movement_towards_the_result"] > 0
        grouped = movements.assign(moved_the_right_way=moved_the_right_way).groupby(
            ["source", "league"], sort=True
        )
        summary = grouped.agg(
            matches=("total_movement", "size"),
            opening_log_loss=("opening_log_loss", "mean"),
            closing_log_loss=("closing_log_loss", "mean"),
            mean_total_movement=("total_movement", "mean"),
            share_moved_towards_the_result=("moved_the_right_way", "mean"),
        ).reset_index()

        rounder = DecimalRounder(LineMovementCalculation.DECIMAL_PLACES)
        return rounder.round_every_column(
            summary.assign(
                log_loss_improvement=summary["opening_log_loss"]
                - summary["closing_log_loss"]
            ),
            [
                "opening_log_loss",
                "closing_log_loss",
                "log_loss_improvement",
                "mean_total_movement",
                "share_moved_towards_the_result",
            ],
        ).sort_values("matches", ascending=False, kind="stable")


if __name__ == "__main__":
    LineMovementBuilder(DateNormalizer()).build_every_match()
