"""The fouls and cards per player and per match, out of the StatsBomb data.

Fouls come off the foul events, cards off the prepared event table, which
already knows that one shown without a foul sits on a different event. The
referee comes with the match identity.
"""

import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchDisciplineFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    MatchDisciplineCounter,
    PreparedStatsBombTables,
    SharedFeatureFile,
)


class StatsBombMatchDisciplineBuilder:
    """The fouls and cards of every free men's competition."""

    def __init__(
        self,
        prepared_tables: PreparedStatsBombTables,
        discipline_counter: MatchDisciplineCounter,
    ) -> None:
        self._prepared_tables = prepared_tables
        self._discipline_counter = discipline_counter
        self._player_file = SharedFeatureFile(
            CsvFile(
                MatchDisciplineFeature.PLAYER_OUTPUT_FILE,
                MatchDisciplineFeature.PLAYER_COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            MatchDisciplineFeature.PLAYER_SORT_KEY_NAMES,
        )
        self._match_file = SharedFeatureFile(
            CsvFile(
                MatchDisciplineFeature.MATCH_OUTPUT_FILE,
                MatchDisciplineFeature.MATCH_COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            MatchDisciplineFeature.MATCH_SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Count over the prepared events and write both output files.

        Returns:
            How many matches the match file holds afterwards, the matches the
            Wyscout half wrote included.

        Raises:
            SystemExit: When the events have not been prepared yet.
        """
        sides = self._prepared_tables.read_the_sides_of_every_match()
        marked_events = self._prepared_tables.read_every_card_and_foul()
        per_player = self._discipline_counter.count_every_player(marked_events)
        per_team = self._discipline_counter.count_every_team(per_player)

        player_rows = self._build_player_rows(per_player, marked_events, sides)
        match_rows = self._build_match_rows(per_team, sides)
        self._player_file.write_the_table_keeping_the_other_source(player_rows)
        match_total = self._match_file.write_the_table_keeping_the_other_source(
            match_rows
        )
        print(
            f"  OK    {len(player_rows)} player rows and {len(match_rows)} matches "
            f"from StatsBomb, {match_total} matches in all"
        )
        return match_total

    def _build_player_rows(
        self,
        per_player: pd.DataFrame,
        marked_events: pd.DataFrame,
        sides: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build one row per player who fouled or was carded in a match."""
        named = self._prepared_tables.name_every_counted_player(
            per_player, marked_events, sides
        )
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                "team": named["team_name"],
                "opponent": named["opponent_name"],
                "player": named["player_name"],
                **self._the_columns_both_files_share(named),
                **{name: named[name] for name in MatchDisciplineFeature.COUNTED_NAMES},
            }
        )

    def _build_match_rows(
        self, per_team: pd.DataFrame, sides: pd.DataFrame
    ) -> pd.DataFrame:
        """Build one row per match, adding both sides up.

        Every match gets a row, one in which nobody was carded included.
        """
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                "home": sides["home_team_name"],
                "away": sides["away_team_name"],
                **self._the_columns_both_files_share(sides),
                **self._discipline_counter.summarise_both_sides(per_team, sides),
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
    StatsBombMatchDisciplineBuilder(
        PreparedStatsBombTables(), MatchDisciplineCounter()
    ).build_every_match()
