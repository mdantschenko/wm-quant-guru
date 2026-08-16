"""The passing network of every Wyscout team and match, summarised.

Only a pass out of open play counts. Wyscout names no receiver, so the next
action of the same team is taken as the player who got the ball.
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
    PreparedWyscoutTables,
    SharedFeatureFile,
)


class WyscoutPassingNetworkBuilder:
    """The open play passes of every Wyscout match, as two rows."""

    def __init__(
        self,
        prepared_tables: PreparedWyscoutTables,
        passing_network_calculator: PassingNetworkCalculator,
    ) -> None:
        self._prepared_tables = prepared_tables
        self._passing_network_calculator = passing_network_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(
                PassingNetworkFeature.OUTPUT_FILE,
                PassingNetworkFeature.COLUMN_NAMES,
            ),
            EventSourceSetting.WYSCOUT_NAME,
            PassingNetworkFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Group the prepared actions and write one row per team and match.

        Returns:
            How many rows the file holds afterwards, the rows the StatsBomb
            half wrote included.

        Raises:
            SystemExit: When the actions have not been prepared yet.
        """
        actions = self._prepared_tables.read_the_actions_with_the_next_player()
        identities = self._prepared_tables.read_the_match_identities()

        summaries = self._passing_network_calculator.summarise_every_team(
            self._every_open_play_pass(actions)
        )
        rows = self._build_the_rows_of_every_team(summaries, identities)
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} team rows from Wyscout, {total_count} in all")
        return total_count

    def _every_open_play_pass(self, actions: pd.DataFrame) -> pd.DataFrame:
        """Keep the open play passes, each with whoever most likely received it.

        A pass that was lost, and one that was the last action of its match,
        reached nobody and forms no lane.
        """
        is_an_open_play_pass = actions["kind"] == MatchStyleFeature.OPEN_PASS_KIND
        reached_a_team_mate = actions["was_successful"] & (
            actions["team_of_the_next_action"] == actions["team_name"]
        )
        return actions[is_an_open_play_pass].assign(
            passer_name=actions.loc[is_an_open_play_pass, "player_name"],
            receiver_name=actions.loc[is_an_open_play_pass, "player_of_the_next_action"]
            .where(reached_a_team_mate[is_an_open_play_pass], "")
            .astype(str),
        )

    def _build_the_rows_of_every_team(
        self, summaries: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Put the match around every summary and say which side played it.

        A team the match names as neither side gets no row: the file would
        otherwise claim it played the home team.
        """
        of_named_matches = summaries.merge(identities, on="game_identifier")
        plays_at_home = (
            of_named_matches["team_name"] == of_named_matches["home_team_name"]
        )
        plays_in_this_match = plays_at_home | (
            of_named_matches["team_name"] == of_named_matches["away_team_name"]
        )
        of_named_matches = of_named_matches[plays_in_this_match].reset_index(drop=True)
        plays_at_home = plays_at_home[plays_in_this_match].reset_index(drop=True)
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
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
    WyscoutPassingNetworkBuilder(
        PreparedWyscoutTables(), PassingNetworkCalculator()
    ).build_every_match()
