"""The market value of every national squad, per dated key date.

This is the market value feature of the concept, the prior that carries the
Bayesian hierarchy over teams that play too rarely to be judged on results
alone.

For every country and every half year it sums the value of its most valuable
players. Only valuations dated on or before the key date count, so nothing
from the future leaks in, and a valuation older than the look back is dropped
as stale rather than carried forward for ever.
"""

from datetime import date
from typing import Any

from wmguru.helpers.constant import SquadValueCalculation
from wmguru.helpers.utils import CsvFile


class SquadValueBuilder:
    """The top players of every citizenship, summed per half year key date."""

    def build_every_key_date(self) -> int:
        """Write one row per country and key date.

        Returns:
            How many country and key date rows the file holds. A country with
            too few valued players on a key date does not get a row at all.
        """
        rows = self._build_rows()
        output_file = CsvFile(
            SquadValueCalculation.SOURCE_FOLDER
            / SquadValueCalculation.OUTPUT_FILE_NAME,
            SquadValueCalculation.COLUMN_NAMES,
        )
        output_file.write_rows(rows)
        print(f"{len(rows)} country and key date rows -> {output_file.path}")
        return len(rows)

    def key_dates_between(self, first: date, last: date) -> list[date]:
        """List the first of January and the first of July in a range.

        Args:
            first: Earliest key date that may appear.
            last: Latest key date that may appear, usually the day of the
                newest valuation in the source.

        Returns:
            Every half year mark inside the range, in order.
        """
        key_dates: list[date] = []
        for year in range(first.year, last.year + 1):
            for month in SquadValueCalculation.KEY_DATE_MONTHS:
                candidate = date(year, month, SquadValueCalculation.FIRST_DAY_OF_MONTH)
                if first <= candidate <= last:
                    key_dates.append(candidate)
        return key_dates

    def value_on(
        self, valuations: list[tuple[date, int]], key_date: date
    ) -> int | None:
        """Read what a player was worth on a key date.

        Args:
            valuations: The value history of one player, sorted by date.
            key_date: The day the value is wanted for.

        Returns:
            The newest value dated on or before the key date, or None when
            there is none or the newest one is older than the look back. A
            stale value would pretend to know something it cannot.
        """
        newest: tuple[date, int] | None = None
        for valuation_date, value in valuations:
            if valuation_date > key_date:
                break
            newest = (valuation_date, value)
        if newest is None:
            return None
        if (key_date - newest[0]).days > SquadValueCalculation.LOOK_BACK_IN_DAYS:
            return None
        return newest[1]

    def _build_rows(self) -> list[list[Any]]:
        """Build one row per country and key date, over the whole history."""
        citizenship_of_player = self._read_citizenships()
        valuations_of_player = self._read_valuations()
        newest_valuation_date = max(
            history[-1][0] for history in valuations_of_player.values()
        )

        rows: list[list[Any]] = []
        first_key_date = date(
            SquadValueCalculation.FIRST_KEY_DATE_YEAR,
            SquadValueCalculation.KEY_DATE_MONTHS[0],
            SquadValueCalculation.FIRST_DAY_OF_MONTH,
        )
        for key_date in self.key_dates_between(first_key_date, newest_valuation_date):
            values_of_country = self._collect_values_on(
                key_date, citizenship_of_player, valuations_of_player
            )
            rows.extend(self._build_rows_of_one_key_date(key_date, values_of_country))
        return rows

    def _collect_values_on(
        self,
        key_date: date,
        citizenship_of_player: dict[int, str],
        valuations_of_player: dict[int, list[tuple[date, int]]],
    ) -> dict[str, list[int]]:
        """Collect every usable player value per country on one key date."""
        values_of_country: dict[str, list[int]] = {}
        for player_identifier, valuations in valuations_of_player.items():
            country = citizenship_of_player.get(player_identifier)
            if country is None:
                continue
            value = self.value_on(valuations, key_date)
            if value is not None:
                values_of_country.setdefault(country, []).append(value)
        return values_of_country

    def _build_rows_of_one_key_date(
        self, key_date: date, values_of_country: dict[str, list[int]]
    ) -> list[list[Any]]:
        """Build the rows of one key date, dropping thinly covered countries."""
        rows: list[list[Any]] = []
        for country, values in values_of_country.items():
            if len(values) < SquadValueCalculation.SMALLEST_USABLE_PLAYER_COUNT:
                continue
            squad = sorted(values, reverse=True)[: SquadValueCalculation.SQUAD_SIZE]
            rows.append([key_date.isoformat(), country, sum(squad), len(squad)])
        return rows

    def _read_citizenships(self) -> dict[int, str]:
        """Read the country every player may play for.

        A player without a citizenship in the source is left out, and a
        Transfermarkt spelling is turned into the name the squads use.
        """
        source_file = CsvFile(
            SquadValueCalculation.SOURCE_FOLDER / SquadValueCalculation.PLAYER_FILE_NAME
        )
        citizenship_of_player: dict[int, str] = {}
        for player in source_file.read_rows():
            country = (
                player.get(SquadValueCalculation.CITIZENSHIP_COLUMN) or ""
            ).strip()
            if not country:
                continue
            player_identifier = int(
                player[SquadValueCalculation.PLAYER_IDENTIFIER_COLUMN]
            )
            citizenship_of_player[player_identifier] = (
                SquadValueCalculation.COUNTRY_ALIASES.get(country, country)
            )
        return citizenship_of_player

    def _read_valuations(self) -> dict[int, list[tuple[date, int]]]:
        """Read the value history of every player, sorted by date."""
        source_file = CsvFile(
            SquadValueCalculation.SOURCE_FOLDER
            / SquadValueCalculation.VALUATION_FILE_NAME
        )
        valuations_of_player: dict[int, list[tuple[date, int]]] = {}
        for valuation in source_file.read_rows():
            value = valuation.get(SquadValueCalculation.VALUE_COLUMN) or ""
            if not value.isdigit():
                continue
            player_identifier = int(
                valuation[SquadValueCalculation.PLAYER_IDENTIFIER_COLUMN]
            )
            valuations_of_player.setdefault(player_identifier, []).append(
                (
                    date.fromisoformat(valuation[SquadValueCalculation.DATE_COLUMN]),
                    int(value),
                )
            )
        for history in valuations_of_player.values():
            history.sort()
        return valuations_of_player


if __name__ == "__main__":
    SquadValueBuilder().build_every_key_date()
