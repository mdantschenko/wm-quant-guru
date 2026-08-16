"""The whole passing network of every match, out of the Wyscout actions.

Wyscout does not name the player who received a pass. The next action of the
same team is taken instead, which is the usual way to read it: whoever plays
the following action had the ball. In a table that next action is the row
below, inside the same match, which is what a shift gives.
"""

import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchStyleFeature,
    PassingLaneFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    PassingLaneCounter,
    PreparedWyscoutTables,
    SharedFeatureFile,
)


class WyscoutPassingLaneBuilder:
    """Every pass of every Wyscout match, and who most likely received it."""

    def __init__(
        self,
        prepared_tables: PreparedWyscoutTables,
        passing_lane_counter: PassingLaneCounter,
    ) -> None:
        self._prepared_tables = prepared_tables
        self._passing_lane_counter = passing_lane_counter
        self._output_file = SharedFeatureFile(
            CsvFile(PassingLaneFeature.OUTPUT_FILE, PassingLaneFeature.COLUMN_NAMES),
            EventSourceSetting.WYSCOUT_NAME,
            PassingLaneFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Group the prepared actions and write one row per pair of players.

        Returns:
            How many rows the file holds afterwards, the rows the StatsBomb
            half wrote included.

        Raises:
            SystemExit: When the actions have not been prepared yet.
        """
        actions = self._prepared_tables.read_the_actions_with_the_next_player()
        identities = self._prepared_tables.read_the_match_identities()

        lanes = self._passing_lane_counter.count_every_lane(
            self._every_pass_that_arrived(actions)
        )
        rows = self._passing_lane_counter.build_the_rows_of_every_lane(
            lanes, identities, EventSourceSetting.WYSCOUT_NAME
        )
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} passing lanes from Wyscout, {total_count} in all")
        return total_count

    def _every_pass_that_arrived(self, actions: pd.DataFrame) -> pd.DataFrame:
        """Keep the passes the next player of the same team took on.

        A pass counts only when the next action belongs to the same team and
        to somebody else, otherwise the ball never left the passer or it went
        to the other side.
        """
        arrived = (
            actions["kind"].isin(MatchStyleFeature.EVERY_PASS_KIND)
            & actions["was_successful"]
            & (actions["team_of_the_next_action"] == actions["team_name"])
            & (actions["player_of_the_next_action"] != "")
            & (actions["player_of_the_next_action"] != actions["player_name"])
        )
        return actions[arrived].rename(
            columns={
                "player_name": "passer_name",
                "player_of_the_next_action": "receiver_name",
            }
        )


if __name__ == "__main__":
    WyscoutPassingLaneBuilder(
        PreparedWyscoutTables(), PassingLaneCounter()
    ).build_every_match()
