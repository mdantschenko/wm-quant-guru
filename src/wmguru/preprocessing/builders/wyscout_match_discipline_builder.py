"""The fouls and cards per player and per match, out of the Wyscout events.

This is what pairs a strict referee with an undisciplined team. It writes two
files: one row per player and match, and one row per match with both sides and
the referee.

Wyscout has no card event. It hangs a tag on the foul event of the player who
caused it, so both questions are answered out of the same raw event files.
"""

import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchDisciplineFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    MatchDisciplineCounter,
    PreparedWyscoutTables,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutMatchDisciplineBuilder:
    """The fouls and cards of every Wyscout match."""

    def __init__(
        self,
        wyscout_data_reader: WyscoutDataReader,
        prepared_tables: PreparedWyscoutTables,
        discipline_counter: MatchDisciplineCounter,
    ) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._prepared_tables = prepared_tables
        self._discipline_counter = discipline_counter
        self._player_file = SharedFeatureFile(
            CsvFile(
                MatchDisciplineFeature.PLAYER_OUTPUT_FILE,
                MatchDisciplineFeature.PLAYER_COLUMN_NAMES,
            ),
            EventSourceSetting.WYSCOUT_NAME,
            MatchDisciplineFeature.PLAYER_SORT_KEY_NAMES,
        )
        self._match_file = SharedFeatureFile(
            CsvFile(
                MatchDisciplineFeature.MATCH_OUTPUT_FILE,
                MatchDisciplineFeature.MATCH_COLUMN_NAMES,
            ),
            EventSourceSetting.WYSCOUT_NAME,
            MatchDisciplineFeature.MATCH_SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Count over every event file and write both output files.

        Returns:
            How many matches the match file holds afterwards, the matches the
            StatsBomb half wrote included.

        Raises:
            SystemExit: When the match identities have not been prepared yet.
        """
        identities = self._prepared_tables.read_the_match_identities()
        marked_events = self._wyscout_data_reader.read_every_card_and_foul()
        per_player = self._discipline_counter.count_every_player(marked_events)
        per_team = self._discipline_counter.count_every_team(per_player)

        player_rows = self._build_player_rows(per_player, identities)
        match_rows = self._build_match_rows(per_team, identities)
        self._player_file.write_the_table_keeping_the_other_source(player_rows)
        match_total = self._match_file.write_the_table_keeping_the_other_source(
            match_rows
        )
        print(
            f"  OK    {len(player_rows)} player rows and {len(match_rows)} matches "
            f"from Wyscout, {match_total} matches in all"
        )
        return match_total

    def _build_player_rows(
        self, per_player: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Build one row per player who fouled or was carded in a match."""
        named = self._wyscout_data_reader.name_every_counted_player(
            per_player, identities
        )
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
                "team": named["team_name"],
                "opponent": named["opponent_name"],
                "player": named["player_name"],
                **self._the_columns_both_files_share(named),
                **{name: named[name] for name in MatchDisciplineFeature.COUNTED_NAMES},
            }
        )

    def _build_match_rows(
        self, per_team: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Build one row per match, adding both sides up.

        Every match gets a row, one in which nobody was carded included.
        """
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
                "home": identities["home_team_name"],
                "away": identities["away_team_name"],
                **self._the_columns_both_files_share(identities),
                **self._discipline_counter.summarise_both_sides(per_team, identities),
            }
        )

    def _the_columns_both_files_share(
        self, of_the_match: pd.DataFrame
    ) -> dict[str, pd.Series]:
        """Build the columns both output files have in common."""
        return {
            "date": of_the_match["match_date"],
            "competition": of_the_match["competition_name"],
            "season": of_the_match["season_name"],
            "game_id": of_the_match["game_identifier"],
            "referee": of_the_match["referee_name"],
        }


if __name__ == "__main__":
    WyscoutMatchDisciplineBuilder(
        WyscoutDataReader(TextNormalizer()),
        PreparedWyscoutTables(),
        MatchDisciplineCounter(),
    ).build_every_match()
