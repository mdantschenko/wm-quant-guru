"""From which season on each league carries the prices we need.

A closing price is what a closing line value check rests on, so how far back
a backtest can reach is decided here rather than guessed. A column that stands
in the header but is empty in most rows does not count as present.
"""

from pathlib import Path

import pandas as pd

from wmguru.helpers.constant import OddsCoverageReport
from wmguru.helpers.utils import CsvFile


class OddsCoverageReporter:
    """What each season of each league really carries."""

    def build_the_report(self) -> int:
        """Print the overview and write the details.

        Returns:
            How many league seasons carry a closing price.
        """
        seasons = pd.concat(
            [
                self._read_every_season(league_folder)
                for league_folder in sorted(OddsCoverageReport.LEAGUE_FOLDER.iterdir())
                if league_folder.is_dir()
            ],
            ignore_index=True,
        ).sort_values(["league", "season"], kind="stable")

        self._print_the_overview(seasons)
        CsvFile(
            OddsCoverageReport.OUTPUT_FILE, OddsCoverageReport.COLUMN_NAMES
        ).write_table(seasons)

        with_closing = int(seasons["has_closing"].sum())
        print(f"\nLeague seasons with a closing price: {with_closing}")
        print(f"Details: {OddsCoverageReport.OUTPUT_FILE}")
        return with_closing

    def _read_every_season(self, league_folder: Path) -> pd.DataFrame:
        """Look at every season file of one league, oldest first."""
        return pd.concat(
            [
                self._read_one_season(season_file).assign(league=league_folder.name)
                for season_file in sorted(
                    league_folder.glob("*.csv"), key=lambda one: one.stem
                )
            ],
            ignore_index=True,
        )

    def _read_one_season(self, season_file: Path) -> pd.DataFrame:
        """Say how many matches one season holds and which prices it carries."""
        every_row = CsvFile(season_file).read_table()
        matches = every_row[every_row.get(OddsCoverageReport.DATE_COLUMN, "") != ""]
        return pd.DataFrame(
            [
                {
                    "season": season_file.stem,
                    "matches": len(matches),
                    "has_opening": int(
                        self._any_column_is_filled(
                            matches, OddsCoverageReport.OPENING_COLUMNS
                        )
                    ),
                    "has_closing": int(
                        self._any_column_is_filled(
                            matches, OddsCoverageReport.CLOSING_COLUMNS
                        )
                    ),
                    "has_pinnacle_closing": int(
                        self._is_filled(
                            matches, OddsCoverageReport.PINNACLE_CLOSING_COLUMN
                        )
                    ),
                }
            ]
        )

    def _any_column_is_filled(
        self, matches: pd.DataFrame, column_names: tuple[str, ...]
    ) -> bool:
        """Return True when at least one of the books priced this season."""
        return any(self._is_filled(matches, name) for name in column_names)

    def _is_filled(self, matches: pd.DataFrame, column_name: str) -> bool:
        """Return True when a column is filled in enough of the matches."""
        return (
            self._fill_rate(matches, column_name)
            >= OddsCoverageReport.LOWEST_USABLE_FILL_RATE
        )

    def _fill_rate(self, matches: pd.DataFrame, column_name: str) -> float:
        """How much of a column is filled in, between nothing and all of it."""
        if matches.empty or column_name not in matches.columns:
            return 0.0
        return (matches[column_name].str.strip() != "").mean()

    def _print_the_overview(self, seasons: pd.DataFrame) -> None:
        """Print one line per league, saying where its closing prices start."""
        header = f"{'League':<42}{'Seasons':>9}{'Opening':>9}{'Closing':>9}{'From':>10}"
        print(header)
        print("-" * len(header))
        per_league = seasons.groupby("league", sort=True).agg(
            seasons=("season", "size"),
            with_opening=("has_opening", "sum"),
            with_closing=("has_closing", "sum"),
            first_closing=(
                "season",
                lambda names: self._first_with_a_closing_price(
                    seasons.loc[names.index]
                ),
            ),
        )
        print(
            "\n".join(
                per_league.index.str.ljust(42)
                + per_league["seasons"].astype(str).str.rjust(9)
                + per_league["with_opening"].astype(str).str.rjust(9)
                + per_league["with_closing"].astype(str).str.rjust(9)
                + per_league["first_closing"].str.rjust(10)
            )
        )

    def _first_with_a_closing_price(self, league_seasons: pd.DataFrame) -> str:
        """Name the oldest season of a league that carries a closing price."""
        priced = league_seasons[league_seasons["has_closing"] == 1]
        return (
            priced["season"].iloc[0]
            if len(priced)
            else OddsCoverageReport.NO_SEASON_TEXT
        )


if __name__ == "__main__":
    OddsCoverageReporter().build_the_report()
