"""From which season on each league carries the prices we need.

A closing price is what a closing line value check rests on, so how far back
a backtest can reach is decided here rather than guessed. A column that stands
in the header but is empty in most rows does not count as present.
"""

from pathlib import Path
from typing import Any

from wmguru.helpers.constant import OddsCoverageReport
from wmguru.helpers.utils import CsvFile


class OddsCoverageReporter:
    """What each season of each league really carries."""

    def build_the_report(self) -> int:
        """Print the overview and write the details.

        Returns:
            How many league seasons carry a closing price.
        """
        seasons_of_league = {
            league_folder.name: self._read_every_season(league_folder)
            for league_folder in sorted(OddsCoverageReport.LEAGUE_FOLDER.iterdir())
            if league_folder.is_dir()
        }
        self._print_the_overview(seasons_of_league)

        rows = [
            {"league": league_name, **season}
            for league_name, seasons in sorted(seasons_of_league.items())
            for season in seasons
        ]
        CsvFile(
            OddsCoverageReport.OUTPUT_FILE, OddsCoverageReport.COLUMN_NAMES
        ).write_dict_rows(rows)

        with_closing = sum(1 for row in rows if row["has_closing"])
        print(f"\nLeague seasons with a closing price: {with_closing}")
        print(f"Details: {OddsCoverageReport.OUTPUT_FILE}")
        return with_closing

    def _read_every_season(self, league_folder: Path) -> list[dict[str, Any]]:
        """Look at every season file of one league, oldest first."""
        return [
            self._read_one_season(season_file)
            for season_file in sorted(
                league_folder.glob("*.csv"), key=lambda one: one.stem
            )
        ]

    def _read_one_season(self, season_file: Path) -> dict[str, Any]:
        """Say how many matches one season holds and which prices it carries."""
        rows = [
            row
            for row in CsvFile(season_file).read_rows()
            if row.get(OddsCoverageReport.DATE_COLUMN)
        ]
        return {
            "season": season_file.stem,
            "matches": len(rows),
            "has_opening": int(
                self._any_column_is_filled(rows, OddsCoverageReport.OPENING_COLUMNS)
            ),
            "has_closing": int(
                self._any_column_is_filled(rows, OddsCoverageReport.CLOSING_COLUMNS)
            ),
            "has_pinnacle_closing": int(
                self._is_filled(rows, OddsCoverageReport.PINNACLE_CLOSING_COLUMN)
            ),
        }

    def _any_column_is_filled(
        self, rows: list[dict[str, str]], column_names: tuple[str, ...]
    ) -> bool:
        """Return True when at least one of the books priced this season."""
        return any(self._is_filled(rows, name) for name in column_names)

    def _is_filled(self, rows: list[dict[str, str]], column_name: str) -> bool:
        """Return True when a column is filled in enough of the matches."""
        return self._fill_rate(rows, column_name) >= (
            OddsCoverageReport.LOWEST_USABLE_FILL_RATE
        )

    def _fill_rate(self, rows: list[dict[str, str]], column_name: str) -> float:
        """How much of a column is filled in, between nothing and all of it."""
        if not rows or column_name not in rows[0]:
            return 0.0
        filled = sum(1 for row in rows if (row.get(column_name) or "").strip())
        return filled / len(rows)

    def _print_the_overview(
        self, seasons_of_league: dict[str, list[dict[str, Any]]]
    ) -> None:
        """Print one line per league, saying where its closing prices start."""
        header = f"{'League':<42}{'Seasons':>9}{'Opening':>9}{'Closing':>9}{'From':>10}"
        print(header)
        print("-" * len(header))
        for league_name, seasons in sorted(seasons_of_league.items()):
            with_closing = [season for season in seasons if season["has_closing"]]
            with_opening = [season for season in seasons if season["has_opening"]]
            first_closing = with_closing[0]["season"] if with_closing else "-"
            print(
                f"{league_name:<42}{len(seasons):>9}"
                f"{len(with_opening):>9}{len(with_closing):>9}{first_closing:>10}"
            )


if __name__ == "__main__":
    OddsCoverageReporter().build_the_report()
