"""The card and foul rates of every referee, over the tournament matches.

This is the base for the strictness feature: a referee who lets play run
against one who blows for everything. The pairing of referee strictness with
the discipline of a team is in hardly any model.

Only a match the source marks as complete counts, because a fixture that has
not been played carries zeros that would drag every rate down.
"""

from typing import Any

from wmguru.helpers.constant import RefereeProfileCalculation
from wmguru.helpers.utils import CsvFile


class RefereeProfileBuilder:
    """The cards and fouls per referee, over every tournament file."""

    def build_every_profile(self) -> int:
        """Write one row per referee, the busiest one first.

        Returns:
            How many referees the file holds.
        """
        counts_of_referee = self._count_over_every_tournament()
        output_file = CsvFile(
            RefereeProfileCalculation.OUTPUT_FILE,
            RefereeProfileCalculation.COLUMN_NAMES,
        )
        output_file.write_rows(self._build_rows(counts_of_referee))
        print(f"{len(counts_of_referee)} referee profiles -> {output_file.path}")
        return len(counts_of_referee)

    def _count_over_every_tournament(self) -> dict[str, dict[str, Any]]:
        """Walk every tournament file and add its matches up per referee."""
        counts_of_referee: dict[str, dict[str, Any]] = {}
        for match_file in sorted(RefereeProfileCalculation.SOURCE_FOLDER.glob("*.csv")):
            for match in CsvFile(match_file).read_rows():
                referee_name = self._usable_referee_of(match)
                if referee_name is None:
                    continue
                self._add_one_match(
                    counts_of_referee, referee_name, match, match_file.stem
                )
        return counts_of_referee

    def _usable_referee_of(self, match: dict[str, str]) -> str | None:
        """Read the referee of a finished match, or None when it does not count."""
        referee_name = (
            match.get(RefereeProfileCalculation.REFEREE_COLUMN) or ""
        ).strip()
        if (
            match.get(RefereeProfileCalculation.STATUS_COLUMN)
            != RefereeProfileCalculation.COMPLETE_STATUS
        ):
            return None
        if referee_name in RefereeProfileCalculation.MISSING_REFEREE_TEXTS:
            return None
        return referee_name

    def _add_one_match(
        self,
        counts_of_referee: dict[str, dict[str, Any]],
        referee_name: str,
        match: dict[str, str],
        tournament_name: str,
    ) -> None:
        """Add the cards and fouls of one match to the count of its referee."""
        counts = counts_of_referee.setdefault(
            referee_name,
            {
                "matches": 0,
                "yellow_cards": 0,
                "red_cards": 0,
                "fouls": 0,
                "tournaments": set(),
            },
        )
        counts["matches"] += 1
        counts["yellow_cards"] += self._sum_of(
            match, RefereeProfileCalculation.YELLOW_CARD_COLUMNS
        )
        counts["red_cards"] += self._sum_of(
            match, RefereeProfileCalculation.RED_CARD_COLUMNS
        )
        counts["fouls"] += self._sum_of(match, RefereeProfileCalculation.FOUL_COLUMNS)
        counts["tournaments"].add(tournament_name)

    def _sum_of(self, match: dict[str, str], column_names: tuple[str, ...]) -> int:
        """Add up the named columns of one match, treating anything odd as zero."""
        return sum(self._as_whole_number(match.get(name)) for name in column_names)

    def _as_whole_number(self, value: str | None) -> int:
        """Read a count, or zero when the cell is empty or not a number.

        Args:
            value: The cell as the source wrote it.

        Returns:
            The number, or zero. The source writes N/A and empty cells for a
            match whose statistics it never collected.
        """
        try:
            return int(value or 0)
        except ValueError:
            return 0

    def _build_rows(
        self, counts_of_referee: dict[str, dict[str, Any]]
    ) -> list[list[Any]]:
        """Build one row per referee, turning the counts into rates."""
        rows: list[list[Any]] = []
        busiest_first = sorted(
            counts_of_referee.items(), key=lambda entry: -int(entry[1]["matches"])
        )
        for referee_name, counts in busiest_first:
            match_count = int(counts["matches"])
            rows.append(
                [
                    referee_name,
                    match_count,
                    self._rate(
                        counts["yellow_cards"],
                        match_count,
                        RefereeProfileCalculation.YELLOW_DECIMAL_PLACES,
                    ),
                    self._rate(
                        counts["red_cards"],
                        match_count,
                        RefereeProfileCalculation.RED_DECIMAL_PLACES,
                    ),
                    self._rate(
                        counts["fouls"],
                        match_count,
                        RefereeProfileCalculation.FOUL_DECIMAL_PLACES,
                    ),
                    RefereeProfileCalculation.TOURNAMENT_SEPARATOR.join(
                        sorted(counts["tournaments"])
                    ),
                ]
            )
        return rows

    def _rate(self, total: int, match_count: int, decimal_places: int) -> float:
        """Turn a total into a per match rate."""
        return round(int(total) / match_count, decimal_places)


if __name__ == "__main__":
    RefereeProfileBuilder().build_every_profile()
