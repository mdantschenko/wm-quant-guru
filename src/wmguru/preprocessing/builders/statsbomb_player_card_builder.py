"""The cards of every player and match, out of the StatsBomb open data.

Only a player who saw a card in a match gets a row, so this is the discipline
count with the fouls left out. Where StatsBomb keeps a card is the prepared
event table's business, this class only counts.
"""

import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchDisciplineFeature,
    PlayerCardFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    MatchDisciplineCounter,
    PreparedStatsBombTables,
    SharedFeatureFile,
)


class StatsBombPlayerCardBuilder:
    """The card events of every free men's competition."""

    def __init__(
        self,
        prepared_tables: PreparedStatsBombTables,
        discipline_counter: MatchDisciplineCounter,
    ) -> None:
        self._prepared_tables = prepared_tables
        self._discipline_counter = discipline_counter
        self._output_file = SharedFeatureFile(
            CsvFile(PlayerCardFeature.OUTPUT_FILE, PlayerCardFeature.COLUMN_NAMES),
            EventSourceSetting.STATSBOMB_NAME,
            PlayerCardFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Count over the prepared events and write one row per carded player.

        Returns:
            How many rows the file holds afterwards, the rows the Wyscout half
            wrote included.

        Raises:
            SystemExit: When the events have not been prepared yet.
        """
        sides = self._prepared_tables.read_the_sides_of_every_match()
        marked_events = self._prepared_tables.read_every_card_and_foul()
        per_player = self._discipline_counter.count_every_player(marked_events)

        rows = self._build_the_rows_of_every_carded_player(
            per_player, marked_events, sides
        )
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(
            f"  OK    {len(rows)} carded players from StatsBomb, {total_count} in all"
        )
        return total_count

    def _build_the_rows_of_every_carded_player(
        self,
        per_player: pd.DataFrame,
        marked_events: pd.DataFrame,
        sides: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build one row per player who saw a card, naming teams and players.

        A player who only fouled has no card to report and drops out here,
        which is the one thing this file counts differently to the discipline
        one it shares its counting with.
        """
        cards = list(MatchDisciplineFeature.CARD_NAMES)
        was_carded = per_player[cards].sum(axis="columns") > 0
        named = self._prepared_tables.name_every_counted_player(
            per_player[was_carded], marked_events, sides
        )
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                "date": named["match_date"],
                "competition": named["competition_name"],
                "season": named["season_name"],
                "team": named["team_name"],
                "opponent": named["opponent_name"],
                "player": named["player_name"],
                **{name: named[name] for name in cards},
            }
        )


if __name__ == "__main__":
    StatsBombPlayerCardBuilder(
        PreparedStatsBombTables(), MatchDisciplineCounter()
    ).build_every_match()
