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

import pandas as pd

from wmguru.helpers.constant import SquadValueCalculation
from wmguru.helpers.utils import CsvFile

SQUAD_KEYS = ["key_date", "country"]


class SquadValueBuilder:
    """The top players of every citizenship, summed per half year key date."""

    def build_every_key_date(self) -> int:
        """Write one row per country and key date.

        Returns:
            How many country and key date rows the file holds. A country with
            too few valued players on a key date does not get a row at all.
        """
        valuations = self._read_valuations()
        first_key_date = date(
            SquadValueCalculation.FIRST_KEY_DATE_YEAR,
            SquadValueCalculation.KEY_DATE_MONTHS[0],
            SquadValueCalculation.FIRST_DAY_OF_MONTH,
        )
        key_dates = self.key_dates_between(
            first_key_date, valuations["valuation_date"].max().date()
        )
        worth_on_the_day = self.value_of_every_player_on_every_key_date(
            valuations, key_dates
        )
        squads = self._sum_up_the_most_valuable_players(
            worth_on_the_day.merge(self._read_citizenships(), on="player_identifier")
        )

        output_file = CsvFile(
            SquadValueCalculation.SOURCE_FOLDER
            / SquadValueCalculation.OUTPUT_FILE_NAME,
            SquadValueCalculation.COLUMN_NAMES,
        )
        output_file.write_table(squads)
        print(f"{len(squads)} country and key date rows -> {output_file.path}")
        return len(squads)

    def key_dates_between(self, first: date, last: date) -> list[date]:
        """List the first of January and the first of July in a range.

        Args:
            first: Earliest key date that may appear.
            last: Latest key date that may appear, usually the day of the
                newest valuation in the source.

        Returns:
            Every half year mark inside the range, in order.
        """
        return [
            half_year.date()
            for half_year in pd.date_range(
                start=first,
                end=last,
                freq=SquadValueCalculation.KEY_DATE_FREQUENCY,
            )
        ]

    def value_of_every_player_on_every_key_date(
        self, valuations: pd.DataFrame, key_dates: list[date]
    ) -> pd.DataFrame:
        """Look up what every player was worth on every one of the key dates.

        This is an as of join, not a search: the newest valuation dated on or
        before the key date wins, one dated after it is never seen, and one
        older than the look back drops out as stale rather than being carried
        forward for ever.

        Returns:
            One row per player and key date the player really had a value on.
        """
        every_pairing = (
            pd.MultiIndex.from_product(
                [
                    pd.to_datetime(pd.Series(key_dates)).astype(
                        valuations["valuation_date"].dtype
                    ),
                    valuations["player_identifier"].unique(),
                ],
                names=SQUAD_KEYS[:1] + ["player_identifier"],
            )
            .to_frame(index=False)
            .sort_values("key_date", kind="stable")
        )
        return pd.merge_asof(
            every_pairing,
            valuations.sort_values(["valuation_date", "value"], kind="stable"),
            left_on="key_date",
            right_on="valuation_date",
            by="player_identifier",
            tolerance=pd.Timedelta(days=SquadValueCalculation.LOOK_BACK_IN_DAYS),
            direction="backward",
        ).dropna(subset=["value"])

    def _sum_up_the_most_valuable_players(
        self, worth_on_the_day: pd.DataFrame
    ) -> pd.DataFrame:
        """Add the squad of every country and key date up, thin ones dropped."""
        valued_players = worth_on_the_day.groupby(SQUAD_KEYS)["value"].transform("size")
        well_covered = worth_on_the_day[
            valued_players >= SquadValueCalculation.SMALLEST_USABLE_PLAYER_COUNT
        ]
        most_valuable_first = well_covered.sort_values(
            [*SQUAD_KEYS, "value"], ascending=[True, True, False], kind="stable"
        )
        is_in_the_squad = (
            most_valuable_first.groupby(SQUAD_KEYS, sort=False).cumcount()
            < SquadValueCalculation.SQUAD_SIZE
        )
        squads = (
            most_valuable_first[is_in_the_squad]
            .groupby(SQUAD_KEYS, sort=False)
            .agg(squad_value_eur=("value", "sum"), players=("value", "size"))
        )
        return (
            squads.join(self._order_the_countries_were_collected_in(well_covered))
            .reset_index()
            .sort_values(["key_date", "first_player_of_the_country"], kind="stable")
            .assign(
                as_of_date=lambda squad: squad["key_date"].dt.strftime(
                    SquadValueCalculation.KEY_DATE_FORMAT
                ),
                squad_value_eur=lambda squad: squad["squad_value_eur"].astype(int),
            )
        )

    def _order_the_countries_were_collected_in(
        self, well_covered: pd.DataFrame
    ) -> pd.Series:
        """Rank the countries of a key date by the first player each brought.

        The file has always listed a country as soon as one of its players
        turned up, so the order of the rows follows the source file rather
        than the alphabet.
        """
        return (
            well_covered.groupby(SQUAD_KEYS)["player_first_seen"]
            .min()
            .rename("first_player_of_the_country")
        )

    def _read_citizenships(self) -> pd.DataFrame:
        """Read the country every player may play for.

        A player without a citizenship in the source is left out, and a
        Transfermarkt spelling is turned into the name the squads use.
        """
        players = CsvFile(
            SquadValueCalculation.SOURCE_FOLDER / SquadValueCalculation.PLAYER_FILE_NAME
        ).read_table()
        country = players[SquadValueCalculation.CITIZENSHIP_COLUMN].str.strip()
        named = players.assign(
            player_identifier=pd.to_numeric(
                players[SquadValueCalculation.PLAYER_IDENTIFIER_COLUMN]
            ),
            country=country.replace(SquadValueCalculation.COUNTRY_ALIASES),
        )
        return named[country != ""][["player_identifier", "country"]].drop_duplicates(
            subset="player_identifier", keep="last"
        )

    def _read_valuations(self) -> pd.DataFrame:
        """Read the value history of every player, with the row it first had.

        Only a whole number counts as a value, the way the source writes one.
        """
        source = CsvFile(
            SquadValueCalculation.SOURCE_FOLDER
            / SquadValueCalculation.VALUATION_FILE_NAME
        ).read_table()
        is_a_whole_number = source[SquadValueCalculation.VALUE_COLUMN].str.isdigit()
        valuations = source[is_a_whole_number].assign(
            player_identifier=pd.to_numeric(
                source.loc[
                    is_a_whole_number, SquadValueCalculation.PLAYER_IDENTIFIER_COLUMN
                ]
            ),
            valuation_date=pd.to_datetime(
                source.loc[is_a_whole_number, SquadValueCalculation.DATE_COLUMN]
            ),
            value=pd.to_numeric(
                source.loc[is_a_whole_number, SquadValueCalculation.VALUE_COLUMN]
            ),
        )
        first_row_of_player = valuations.drop_duplicates(
            subset="player_identifier", keep="first"
        )["player_identifier"]
        return valuations.assign(
            player_first_seen=valuations["player_identifier"].map(
                pd.Series(range(len(first_row_of_player)), index=first_row_of_player)
            )
        )[["player_identifier", "valuation_date", "value", "player_first_seen"]]


if __name__ == "__main__":
    SquadValueBuilder().build_every_key_date()
