"""The cards of every player and match, out of the Wyscout events.

Only a player who saw a card in a match gets a row, so this is the discipline
count with the fouls left out. How Wyscout marks a card is the reader's
business, this class only counts.
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
    PreparedWyscoutTables,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutPlayerCardBuilder:
    """The cards of every Wyscout match, per player and team."""

    def __init__(
        self,
        wyscout_data_reader: WyscoutDataReader,
        prepared_tables: PreparedWyscoutTables,
        discipline_counter: MatchDisciplineCounter,
    ) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._prepared_tables = prepared_tables
        self._discipline_counter = discipline_counter
        self._output_file = SharedFeatureFile(
            CsvFile(PlayerCardFeature.OUTPUT_FILE, PlayerCardFeature.COLUMN_NAMES),
            EventSourceSetting.WYSCOUT_NAME,
            PlayerCardFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Count over every event file and write one row per carded player.

        Returns:
            How many rows the file holds afterwards, the rows the StatsBomb
            half wrote included.

        Raises:
            SystemExit: When the match identities have not been prepared yet.
        """
        identities = self._prepared_tables.read_the_match_identities()
        marked_events = self._wyscout_data_reader.read_every_card_and_foul()
        per_player = self._discipline_counter.count_every_player(marked_events)

        rows = self._build_the_rows_of_every_carded_player(per_player, identities)
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} carded players from Wyscout, {total_count} in all")
        return total_count

    def _build_the_rows_of_every_carded_player(
        self, per_player: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Build one row per player who saw a card, naming teams and players.

        A player who only fouled has no card to report and drops out here,
        which is the one thing this file counts differently to the discipline
        one it shares its counting with.
        """
        cards = list(MatchDisciplineFeature.CARD_NAMES)
        was_carded = per_player[cards].sum(axis="columns") > 0
        named = self._wyscout_data_reader.name_every_counted_player(
            per_player[was_carded], identities
        )
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
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
    WyscoutPlayerCardBuilder(
        WyscoutDataReader(TextNormalizer()),
        PreparedWyscoutTables(),
        MatchDisciplineCounter(),
    ).build_every_match()
