"""The whole passing network of every match, out of the StatsBomb data.

StatsBomb names the player who received a pass, so nothing has to be guessed
here. Every completed pass counts, out of open play and off a set piece, or
the network would have holes in it.
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
    PreparedStatsBombTables,
    SharedFeatureFile,
)


class StatsBombPassingLaneBuilder:
    """The passes of every free men's competition, and who received them."""

    def __init__(
        self,
        prepared_tables: PreparedStatsBombTables,
        passing_lane_counter: PassingLaneCounter,
    ) -> None:
        self._prepared_tables = prepared_tables
        self._passing_lane_counter = passing_lane_counter
        self._output_file = SharedFeatureFile(
            CsvFile(PassingLaneFeature.OUTPUT_FILE, PassingLaneFeature.COLUMN_NAMES),
            EventSourceSetting.STATSBOMB_NAME,
            PassingLaneFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Group the prepared events and write one row per pair of players.

        Returns:
            How many rows the file holds afterwards, the rows the Wyscout half
            wrote included.

        Raises:
            SystemExit: When the events have not been prepared yet.
        """
        events = self._prepared_tables.read_the_events()
        identities = self._prepared_tables.read_the_match_identities()

        lanes = self._passing_lane_counter.count_every_lane(
            self._every_pass_that_arrived(events)
        )
        rows = self._passing_lane_counter.build_the_rows_of_every_lane(
            lanes, identities, EventSourceSetting.STATSBOMB_NAME
        )
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} passing lanes from StatsBomb, {total_count} in all")
        return total_count

    def _every_pass_that_arrived(self, events: pd.DataFrame) -> pd.DataFrame:
        """Keep the passes that reached a named team mate.

        A pass to the passer themselves is no lane, and one the source placed
        nowhere cannot say where it ran from or to.
        """
        arrived = (
            (events["event_name"] == MatchStyleFeature.PASS_EVENT_NAME)
            & events["was_a_completed_pass"]
            & (events["receiver_name"] != "")
            & (events["player_name"] != "")
            & (events["team_name"] != "")
            & (events["receiver_name"] != events["player_name"])
            & events["start_x_in_metres"].notna()
            & events["end_x_in_metres"].notna()
        )
        return events[arrived].rename(
            columns={"player_name": "passer_name"},
        )


if __name__ == "__main__":
    StatsBombPassingLaneBuilder(
        PreparedStatsBombTables(), PassingLaneCounter()
    ).build_every_match()
