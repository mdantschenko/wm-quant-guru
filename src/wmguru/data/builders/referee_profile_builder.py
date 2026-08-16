"""The card and foul rates of every referee, over the tournament matches.

This is the base for the strictness feature: a referee who lets play run
against one who blows for everything. The pairing of referee strictness with
the discipline of a team is in hardly any model.

Only a match the source marks as complete counts, because a fixture that has
not been played carries zeros that would drag every rate down.
"""

import pandas as pd

from wmguru.helpers.constant import RefereeProfileCalculation
from wmguru.helpers.utils import CsvFile, DecimalRounder


class RefereeProfileBuilder:
    """The cards and fouls per referee, over every tournament file."""

    def build_every_profile(self) -> int:
        """Write one row per referee, the busiest one first.

        Returns:
            How many referees the file holds.
        """
        matches = self._read_every_tournament()
        profiles = self._summarise_every_referee(matches)

        output_file = CsvFile(
            RefereeProfileCalculation.OUTPUT_FILE,
            RefereeProfileCalculation.COLUMN_NAMES,
        )
        output_file.write_table(profiles)
        print(f"{len(profiles)} referee profiles -> {output_file.path}")
        return len(profiles)

    def _read_every_tournament(self) -> pd.DataFrame:
        """Read every tournament file into one table, with its own name on it."""
        match_files = sorted(RefereeProfileCalculation.SOURCE_FOLDER.glob("*.csv"))
        return pd.concat(
            [
                CsvFile(match_file).read_table().assign(tournament=match_file.stem)
                for match_file in match_files
            ],
            ignore_index=True,
        )

    def _summarise_every_referee(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Add the matches of every referee up and turn the totals into rates."""
        usable = self._only_the_usable_matches(matches)
        counted = usable.assign(
            yellow_cards=self._sum_of_the_named_columns(
                usable, RefereeProfileCalculation.YELLOW_CARD_COLUMNS
            ),
            red_cards=self._sum_of_the_named_columns(
                usable, RefereeProfileCalculation.RED_CARD_COLUMNS
            ),
            fouls=self._sum_of_the_named_columns(
                usable, RefereeProfileCalculation.FOUL_COLUMNS
            ),
        )
        referee_column = RefereeProfileCalculation.REFEREE_COLUMN
        grouped = counted.groupby(referee_column, dropna=False, sort=False)
        totals = grouped.agg(
            matches=("tournament", "size"),
            yellow_cards=("yellow_cards", "sum"),
            red_cards=("red_cards", "sum"),
            fouls=("fouls", "sum"),
        )
        totals["tournaments"] = grouped["tournament"].agg(
            lambda names: RefereeProfileCalculation.TOURNAMENT_SEPARATOR.join(
                sorted(set(names))
            )
        )
        busiest_first = totals.sort_values(
            "matches", ascending=False, kind="stable"
        ).reset_index()
        return busiest_first.rename(columns={referee_column: "referee"}).assign(
            mean_yellow_cards=self._rate(
                busiest_first["yellow_cards"],
                busiest_first["matches"],
                RefereeProfileCalculation.YELLOW_DECIMAL_PLACES,
            ),
            mean_red_cards=self._rate(
                busiest_first["red_cards"],
                busiest_first["matches"],
                RefereeProfileCalculation.RED_DECIMAL_PLACES,
            ),
            mean_fouls=self._rate(
                busiest_first["fouls"],
                busiest_first["matches"],
                RefereeProfileCalculation.FOUL_DECIMAL_PLACES,
            ),
        )

    def _only_the_usable_matches(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Keep the finished matches whose referee the source really names."""
        referee_names = (
            matches[RefereeProfileCalculation.REFEREE_COLUMN].fillna("").str.strip()
        )
        was_played = (
            matches[RefereeProfileCalculation.STATUS_COLUMN]
            == RefereeProfileCalculation.COMPLETE_STATUS
        )
        has_a_referee = ~referee_names.isin(
            RefereeProfileCalculation.MISSING_REFEREE_TEXTS
        )
        return matches[was_played & has_a_referee].assign(
            **{RefereeProfileCalculation.REFEREE_COLUMN: referee_names}
        )

    def _sum_of_the_named_columns(
        self, matches: pd.DataFrame, column_names: tuple[str, ...]
    ) -> pd.Series:
        """Add the named columns of every match up, reading anything odd as zero.

        The source writes N/A and empty cells for a match whose statistics it
        never collected, and those must count as nothing rather than stop the
        run.
        """
        wanted = matches.reindex(columns=list(column_names))
        return (
            wanted.apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis="columns")
        )

    def _rate(
        self, totals: pd.Series, match_counts: pd.Series, decimal_places: int
    ) -> pd.Series:
        """Turn a total into a per match rate."""
        return DecimalRounder(decimal_places).round_every_value(totals / match_counts)


if __name__ == "__main__":
    RefereeProfileBuilder().build_every_profile()
