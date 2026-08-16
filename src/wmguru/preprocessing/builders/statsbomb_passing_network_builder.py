"""The passing network of every StatsBomb team and match, summarised.

Only a pass out of open play counts, no cross and no set piece, so the number
means the same thing as it does on the Wyscout side. StatsBomb names the
player who received the pass itself.
"""

import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchStyleFeature,
    PassingNetworkFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    PassingNetworkCalculator,
    PreparedStatsBombTables,
    SharedFeatureFile,
)


class StatsBombPassingNetworkBuilder:
    """The open play passes of every free men's competition."""

    def __init__(
        self,
        prepared_tables: PreparedStatsBombTables,
        passing_network_calculator: PassingNetworkCalculator,
    ) -> None:
        self._prepared_tables = prepared_tables
        self._passing_network_calculator = passing_network_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(
                PassingNetworkFeature.OUTPUT_FILE,
                PassingNetworkFeature.COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            PassingNetworkFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Group the prepared events and write one row per team and match.

        Returns:
            How many rows the file holds afterwards, the rows the Wyscout half
            wrote included.

        Raises:
            SystemExit: When the events have not been prepared yet.
        """
        events = self._prepared_tables.read_the_events()
        identities = self._prepared_tables.read_the_match_identities()

        summaries = self._passing_network_calculator.summarise_every_team(
            self._every_open_play_pass(events)
        )
        rows = self._build_the_rows_of_every_team(summaries, identities)
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} team rows from StatsBomb, {total_count} in all")
        return total_count

    def _every_open_play_pass(self, events: pd.DataFrame) -> pd.DataFrame:
        """Keep the open play passes, each with the player who received it.

        A pass off a set piece and a cross say nothing about how a team builds
        up, and one the source placed nowhere cannot say where it ran.
        """
        out_of_open_play = (
            (events["event_name"] == MatchStyleFeature.PASS_EVENT_NAME)
            & ~events["pass_type_name"].isin(MatchStyleFeature.SET_PIECE_PASS_NAMES)
            & ~events["was_a_cross"]
            & (events["player_name"] != "")
            & (events["team_name"] != "")
            & events["start_x_in_metres"].notna()
            & events["end_x_in_metres"].notna()
        )
        of_open_play = events[out_of_open_play]
        return of_open_play.assign(
            passer_name=of_open_play["player_name"],
            receiver_name=of_open_play["receiver_name"].where(
                of_open_play["was_a_completed_pass"], ""
            ),
            was_successful=of_open_play["was_a_completed_pass"],
        )

    def _build_the_rows_of_every_team(
        self, summaries: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Put the match around every summary and say which side played it."""
        of_named_matches = summaries.merge(identities, on="game_identifier")
        plays_at_home = (
            of_named_matches["team_name"] == of_named_matches["home_team_name"]
        )
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                "game_id": of_named_matches["game_identifier"],
                "competition": of_named_matches["competition_name"],
                "season": of_named_matches["season_name"],
                "date": of_named_matches["match_date"],
                "team": of_named_matches["team_name"],
                "opponent": of_named_matches["away_team_name"].where(
                    plays_at_home, of_named_matches["home_team_name"]
                ),
                "is_home": plays_at_home.astype(int),
                **{
                    name: of_named_matches[name]
                    for name in PassingNetworkFeature.SUMMARY_COLUMN_NAMES
                },
            }
        )


if __name__ == "__main__":
    StatsBombPassingNetworkBuilder(
        PreparedStatsBombTables(), PassingNetworkCalculator()
    ).build_every_match()
