"""Whether a hard team and a strict referee together give extra cards.

Fouls come off the prepared Wyscout actions, cards off the card tags of the
raw events, and the referee off the prepared match table. Both the foul count
of a team and the strictness of a referee are standardised first, so a team of
one league can be compared with a team of another.

Two files come out: what each referee is like, and the table of foul band
against strictness band.
"""

from typing import Any

import numpy as np
import pandas as pd

from wmguru.helpers.constant import (
    MatchDisciplineFeature,
    MatchStyleFeature,
    RefereeEscalationCalculation,
)
from wmguru.helpers.utils import (
    CsvFile,
    DecimalRounder,
    PreparedWyscoutTables,
    TextNormalizer,
    WyscoutDataReader,
)


class RefereeEscalationBuilder:
    """The fouls and cards of every match, banded by referee."""

    TEAM_KEYS = ["game_identifier", "team_name"]

    def __init__(
        self,
        wyscout_data_reader: WyscoutDataReader,
        prepared_tables: PreparedWyscoutTables,
    ) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._prepared_tables = prepared_tables

    def build_the_tables(self) -> int:
        """Write what each referee is like and the band table.

        Returns:
            How many band cells the table holds.

        Raises:
            SystemExit: When the actions have not been prepared yet.
        """
        identities = self._prepared_tables.read_the_match_identities()
        cards_per_team = self._count_the_cards_of_every_team()
        per_team = self._count_the_fouls_and_cards_of_every_team(
            cards_per_team, identities
        )

        strictness_rows = self._measure_every_referee(
            per_team, cards_per_team, identities
        )
        table_rows = self._build_the_band_table(per_team, strictness_rows)

        CsvFile(
            RefereeEscalationCalculation.STRICTNESS_OUTPUT_FILE,
            RefereeEscalationCalculation.STRICTNESS_COLUMN_NAMES,
        ).write_table(strictness_rows)
        CsvFile(
            RefereeEscalationCalculation.ESCALATION_OUTPUT_FILE,
            RefereeEscalationCalculation.ESCALATION_COLUMN_NAMES,
        ).write_table(table_rows)
        print(f"  OK    {len(strictness_rows)} referees, {len(table_rows)} band cells")
        print(f"  INFO  {self._describe_the_excess(table_rows)}")
        return len(table_rows)

    def _count_the_fouls_and_cards_of_every_team(
        self, cards_per_team: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Count the fouls of each team in each match, its cards beside them.

        Returns:
            One row per team that fouled in a match, with its cards and the
            match it belongs to. A team that was carded without ever fouling
            has no row, the way the walk this replaces had none.
        """
        actions = self._prepared_tables.read_the_actions()
        fouls = (
            actions[actions["kind"] == MatchStyleFeature.FOUL_KIND]
            .groupby(self.TEAM_KEYS, sort=False)
            .size()
            .reset_index(name="fouls")
        )
        of_the_team = fouls.merge(cards_per_team, on=self.TEAM_KEYS, how="left")
        return of_the_team.assign(cards=of_the_team["cards"].fillna(0)).merge(
            identities, on="game_identifier", how="left"
        )

    def _count_the_cards_of_every_team(self) -> pd.DataFrame:
        """Count the cards of each team in each match, out of the event tags."""
        marked_events = self._wyscout_data_reader.read_every_card_and_foul()
        cards_of_event = marked_events[list(MatchDisciplineFeature.CARD_NAMES)].sum(
            axis="columns"
        )
        team_names = self._wyscout_data_reader.read_team_names()
        return (
            marked_events.assign(
                cards=cards_of_event,
                team_name=self._wyscout_data_reader.name_every_identifier(
                    marked_events["team_identifier"], team_names
                ),
            )
            .groupby(self.TEAM_KEYS, sort=False)["cards"]
            .sum()
            .reset_index()
        )

    def _measure_every_referee(
        self,
        per_team: pd.DataFrame,
        cards_per_team: pd.DataFrame,
        identities: pd.DataFrame,
    ) -> pd.DataFrame:
        """Work out the cards per foul of every referee.

        The two counts are added up per match on their own, so a card of a
        team that never fouled in that match still counts towards the referee.

        Returns:
            One row per referee who took charge of enough matches, the
            strictest first. A referee whose matches held no foul at all is
            left out, because their ratio cannot be worked out.
        """
        of_the_referee = (
            identities[identities["referee_name"] != ""]
            .merge(self._added_up_per_match(per_team, "fouls"), how="left")
            .merge(self._added_up_per_match(cards_per_team, "cards"), how="left")
        )
        per_referee = (
            of_the_referee.assign(
                fouls=of_the_referee["fouls"].fillna(0),
                cards=of_the_referee["cards"].fillna(0),
            )
            .groupby("referee_name", sort=False)
            .agg(
                matches=("game_identifier", "size"),
                fouls=("fouls", "sum"),
                cards=("cards", "sum"),
            )
            .reset_index()
        )
        took_charge_of_enough = (
            per_referee["matches"] >= RefereeEscalationCalculation.MINIMUM_MATCHES
        ) & (per_referee["fouls"] > 0)
        measured = per_referee[took_charge_of_enough]
        exact_ratio = measured["cards"] / measured["fouls"]
        rows = pd.DataFrame(
            {
                "referee": measured["referee_name"],
                "matches": measured["matches"],
                "fouls": measured["fouls"].astype(int),
                "cards": measured["cards"].astype(int),
                "cards_per_foul": DecimalRounder(
                    RefereeEscalationCalculation.RATIO_DECIMAL_PLACES
                ).round_every_value(exact_ratio),
                "exact_cards_per_foul": exact_ratio,
            }
        )
        return rows.sort_values(
            "cards_per_foul", ascending=False, kind="stable"
        ).reset_index(drop=True)

    def _added_up_per_match(
        self, per_team: pd.DataFrame, counted_name: str
    ) -> pd.DataFrame:
        """Add the two teams of each match into one count per match."""
        return (
            per_team.groupby("game_identifier", sort=False)[counted_name]
            .sum()
            .reset_index()
        )

    def _build_the_band_table(
        self, per_team: pd.DataFrame, strictness_rows: pd.DataFrame
    ) -> pd.DataFrame:
        """Average the cards over every combination of the two bands.

        What a normal foul count is for a season is measured over every team
        of it, and only then are the teams of a referee nobody could measure
        dropped.
        """
        of_a_measured_referee = per_team.assign(
            aggression_band=self._which_band_the_foul_count_falls_into(per_team)
        ).merge(
            strictness_rows[["referee", "exact_cards_per_foul"]],
            left_on="referee_name",
            right_on="referee",
        )
        banded = of_a_measured_referee.assign(
            strictness_band=self._which_band_every_value_falls_into(
                of_a_measured_referee["exact_cards_per_foul"],
                *self._the_middle_and_the_spread_of(
                    strictness_rows["exact_cards_per_foul"]
                ),
            ),
        )
        counted = (
            banded[banded["aggression_band"] != ""]
            .groupby(["aggression_band", "strictness_band"], sort=False)
            .agg(
                team_matches=("fouls", "size"),
                fouls=("fouls", "sum"),
                cards=("cards", "sum"),
            )
            .reset_index()
        )
        return self._build_table_rows(counted)

    def _which_band_the_foul_count_falls_into(
        self, per_team: pd.DataFrame
    ) -> pd.Series:
        """Band the foul count of every team against its own season.

        Returns:
            The band per row, and an empty one for a season with too few
            values to say what a normal foul count is there.
        """
        season_keys = ["competition_name", "season_name"]
        of_the_season = per_team.groupby(season_keys, sort=False)["fouls"]
        has_a_scale = of_the_season.transform("size") >= (
            RefereeEscalationCalculation.MINIMUM_VALUES_FOR_A_SCALE
        )
        return self._which_band_every_value_falls_into(
            per_team["fouls"],
            of_the_season.transform("mean"),
            of_the_season.transform(lambda values: values.std(ddof=0)),
        ).where(has_a_scale, "")

    def _the_middle_and_the_spread_of(self, values: pd.Series) -> tuple[float, float]:
        """The middle and the spread a value is standardised with."""
        if len(values) < RefereeEscalationCalculation.MINIMUM_VALUES_FOR_A_SCALE:
            return 0.0, 0.0
        return values.mean(), values.std(ddof=0)

    def _which_band_every_value_falls_into(
        self, values: pd.Series, middle: Any, spread: Any
    ) -> pd.Series:
        """Say of every value whether it is high, medium or low for its scale."""
        standardised = pd.Series(
            np.where(spread, (values - middle) / np.where(spread, spread, 1.0), 0.0),
            index=values.index,
        )
        return pd.Series(
            np.select(
                [
                    standardised >= RefereeEscalationCalculation.HIGH_BAND_FROM,
                    standardised <= RefereeEscalationCalculation.LOW_BAND_UP_TO,
                ],
                [
                    RefereeEscalationCalculation.HIGH_BAND_NAME,
                    RefereeEscalationCalculation.LOW_BAND_NAME,
                ],
                default=RefereeEscalationCalculation.MIDDLE_BAND_NAME,
            ),
            index=values.index,
        )

    def _build_table_rows(self, counted: pd.DataFrame) -> pd.DataFrame:
        """Turn the counted cells into the rows of the table, in band order."""
        order = list(RefereeEscalationCalculation.BAND_ORDER)
        rows = pd.DataFrame(
            {
                "aggression_band": counted["aggression_band"],
                "strictness_band": counted["strictness_band"],
                "team_matches": counted["team_matches"],
                "mean_fouls": DecimalRounder(
                    RefereeEscalationCalculation.FOUL_DECIMAL_PLACES
                ).round_every_value(counted["fouls"] / counted["team_matches"]),
                "mean_cards": DecimalRounder(
                    RefereeEscalationCalculation.CARD_DECIMAL_PLACES
                ).round_every_value(counted["cards"] / counted["team_matches"]),
            }
        )
        in_band_order = pd.DataFrame(
            {
                "aggression": counted["aggression_band"].map(order.index),
                "strictness": counted["strictness_band"].map(order.index),
            }
        ).sort_values(["aggression", "strictness"], kind="stable")
        return rows.loc[in_band_order.index].reset_index(drop=True)

    def _describe_the_excess(self, table_rows: pd.DataFrame) -> str:
        """Compare the hardest cell with what simply adding up would predict.

        Returns:
            One line for the log. An excess above zero is the whole point of
            the feature: it says the two do not merely add up.
        """
        high = RefereeEscalationCalculation.HIGH_BAND_NAME
        is_the_hardest_cell = (table_rows["aggression_band"] == high) & (
            table_rows["strictness_band"] == high
        )
        if not is_the_hardest_cell.any():
            return "no high against high cell, nothing to compare"
        observed = float(table_rows.loc[is_the_hardest_cell, "mean_cards"].iloc[0])
        overall = table_rows["mean_cards"].mean()
        hard_teams = self._average_over(table_rows, "aggression_band", high) or overall
        strict_referees = (
            self._average_over(table_rows, "strictness_band", high) or overall
        )
        adding_up = hard_teams + strict_referees - overall
        return (
            f"high against high gives {observed:.3f} cards per team and match, "
            f"adding up would give {adding_up:.3f}, "
            f"excess {observed - adding_up:+.3f}"
        )

    def _average_over(
        self, table_rows: pd.DataFrame, band_column: str, band_name: str
    ) -> float:
        """Average the cells of one band, or zero when there are none."""
        wanted = table_rows.loc[table_rows[band_column] == band_name, "mean_cards"]
        return float(wanted.mean()) if len(wanted) else 0.0


if __name__ == "__main__":
    RefereeEscalationBuilder(
        WyscoutDataReader(TextNormalizer()), PreparedWyscoutTables()
    ).build_the_tables()
