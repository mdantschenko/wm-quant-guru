"""The metrics of every player and match, out of the Wyscout actions.

A row is built for everybody who was on the pitch, even for somebody who
touched the ball twice, because the minutes are in the row and any filter can
still be applied later.
"""

import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    PlayerMatchMetricFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    PlayerMatchMetricCalculator,
    PreparedWyscoutTables,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutPlayerMetricBuilder:
    """What every Wyscout player did in every match they played."""

    def __init__(
        self,
        wyscout_data_reader: WyscoutDataReader,
        prepared_tables: PreparedWyscoutTables,
        player_metric_calculator: PlayerMatchMetricCalculator,
    ) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._prepared_tables = prepared_tables
        self._player_metric_calculator = player_metric_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(
                PlayerMatchMetricFeature.OUTPUT_FILE,
                PlayerMatchMetricFeature.COLUMN_NAMES,
            ),
            EventSourceSetting.WYSCOUT_NAME,
            PlayerMatchMetricFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Group the prepared actions and write one row per player and match.

        Returns:
            How many rows the file holds afterwards, the rows the StatsBomb
            half wrote included.

        Raises:
            SystemExit: When the actions have not been prepared yet.
        """
        roles = self._wyscout_data_reader.read_the_role_of_every_player()
        identities = self._prepared_tables.read_the_match_identities()
        counts = self._player_metric_calculator.count_every_player(
            self._actions_with_the_role_of_their_player(roles)
        )

        rows = self._build_the_rows_of_every_appearance(counts, roles, identities)
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} player rows from Wyscout, {total_count} in all")
        return total_count

    def _actions_with_the_role_of_their_player(
        self, roles: pd.DataFrame
    ) -> pd.DataFrame:
        """Say of every action whether the player who made it keeps goal."""
        actions = self._prepared_tables.read_the_actions()
        of_the_player = actions.merge(roles, on="player_identifier", how="left")
        return of_the_player.assign(
            is_goalkeeper=of_the_player["role"]
            == PlayerMatchMetricFeature.GOALKEEPER_ROLE
        )

    def _build_the_rows_of_every_appearance(
        self,
        counts: pd.DataFrame,
        roles: pd.DataFrame,
        identities: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build one row per appearance, whether the player touched the ball or not.

        A match that is in no match file drops out: the row could name neither
        the opponent nor the day it was played.
        """
        appearances = self._wyscout_data_reader.read_every_appearance()
        of_named_matches = appearances.merge(identities, on="game_identifier").merge(
            roles, on="player_identifier", how="left"
        )
        counted = self._counts_lined_up_with(of_named_matches, counts)
        role = of_named_matches["role"].fillna("")
        plays_at_home = (
            of_named_matches["team_identifier"]
            == of_named_matches["home_team_identifier"]
        )
        team_names = self._wyscout_data_reader.read_team_names()
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
                "date": of_named_matches["match_date"],
                "competition": of_named_matches["competition_name"],
                "season": of_named_matches["season_name"],
                "team": self._wyscout_data_reader.name_every_identifier(
                    of_named_matches["team_identifier"], team_names
                ),
                "opponent": self._wyscout_data_reader.name_every_identifier(
                    of_named_matches["away_team_identifier"].where(
                        plays_at_home, of_named_matches["home_team_identifier"]
                    ),
                    team_names,
                ),
                "player": of_named_matches["player_name"],
                "role": role,
                "minutes": of_named_matches["minutes_played"],
                **self._player_metric_calculator.build_the_columns_of_every_player(
                    counted, role == PlayerMatchMetricFeature.GOALKEEPER_ROLE
                ),
            }
        )

    def _counts_lined_up_with(
        self, appearances: pd.DataFrame, counts: pd.DataFrame
    ) -> pd.DataFrame:
        """Look the counts of every appearance up, zeros where none were made."""
        looked_up = appearances[["player_identifier", "game_identifier"]].merge(
            counts, on=PlayerMatchMetricCalculator.PLAYER_KEYS, how="left"
        )
        return (
            looked_up[list(PlayerMatchMetricCalculator.COUNTED_NAMES)]
            .fillna(0.0)
            .set_axis(appearances.index)
        )


if __name__ == "__main__":
    WyscoutPlayerMetricBuilder(
        WyscoutDataReader(TextNormalizer()),
        PreparedWyscoutTables(),
        PlayerMatchMetricCalculator(),
    ).build_every_match()
