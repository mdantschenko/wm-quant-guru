"""How well every player kept the ball under pressure.

StatsBomb marks an action as played under pressure, so this can be read off
rather than guessed. Passes, carries and take ons are counted with and without
pressure, together with the two ways of simply losing the ball.
"""

import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    ExpectedThreatFeature,
    MatchStyleFeature,
    PressResistanceFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    DecimalRounder,
    PreparedStatsBombTables,
    SharedFeatureFile,
)


class StatsBombPressResistanceBuilder:
    """The pressured actions of every player of every free competition."""

    PLAYER_KEYS = ["game_identifier", "player_name"]

    def __init__(self, prepared_tables: PreparedStatsBombTables) -> None:
        self._prepared_tables = prepared_tables
        self._output_file = SharedFeatureFile(
            CsvFile(
                PressResistanceFeature.OUTPUT_FILE,
                PressResistanceFeature.COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            PressResistanceFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Group the prepared events and write one row per player and match.

        Returns:
            How many rows the file holds afterwards.

        Raises:
            SystemExit: When the events have not been prepared yet.
        """
        rows = self._build_the_rows_of_every_player()
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} player rows from StatsBomb, {total_count} in all")
        return total_count

    def _build_the_rows_of_every_player(self) -> pd.DataFrame:
        """Build one row per player who touched the ball in a match."""
        events = self._prepared_tables.read_the_events()
        of_a_named_player = events[events["player_name"] != ""]
        counts = self._count_every_player(of_a_named_player)
        of_named_matches = counts.merge(
            self._prepared_tables.read_the_match_identities(), on="game_identifier"
        )
        plays_at_home = (
            of_named_matches["team_name"] == of_named_matches["home_team_name"]
        )
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                "date": of_named_matches["match_date"],
                "competition": of_named_matches["competition_name"],
                "season": of_named_matches["season_name"],
                "team": of_named_matches["team_name"],
                "opponent": of_named_matches["away_team_name"].where(
                    plays_at_home, of_named_matches["home_team_name"]
                ),
                "player": of_named_matches["player_name"],
                **{
                    name: of_named_matches[name].astype(int)
                    for name in PressResistanceFeature.COUNTED_NAMES
                },
                "pressured_pass_completion": self._divided_or_left_empty(
                    of_named_matches["completed_pressured_passes"],
                    of_named_matches["pressured_passes"],
                ),
                "pressured_share": self._divided_or_left_empty(
                    of_named_matches["pressured_passes"],
                    of_named_matches["passes"],
                ),
            }
        )

    def _count_every_player(self, events: pd.DataFrame) -> pd.DataFrame:
        """Add up what every player did in every match, under pressure and not.

        The team of a player is the one the last of their events names, the
        way the walk this replaces kept overwriting it.
        """
        marked = self._marked_up(events)
        counted = (
            marked.groupby(self.PLAYER_KEYS, sort=False)[
                list(PressResistanceFeature.COUNTED_NAMES)
            ]
            .sum()
            .reset_index()
        )
        team_of_player = (
            marked.groupby(self.PLAYER_KEYS, sort=False)["team_name"]
            .last()
            .reset_index()
        )
        return counted.merge(team_of_player, on=self.PLAYER_KEYS)

    def _marked_up(self, events: pd.DataFrame) -> pd.DataFrame:
        """Say of every single event what it counts towards."""
        event_name = events["event_name"]
        is_a_pass = event_name == MatchStyleFeature.PASS_EVENT_NAME
        is_a_carry = event_name == ExpectedThreatFeature.CARRY_EVENT_NAME
        is_a_take_on = event_name == MatchStyleFeature.DRIBBLE_EVENT_NAME
        was_under_pressure = events["was_under_pressure"]
        was_completed = is_a_pass & events["was_a_completed_pass"]
        return events.assign(
            passes=is_a_pass,
            completed_passes=was_completed,
            pressured_passes=is_a_pass & was_under_pressure,
            completed_pressured_passes=was_completed & was_under_pressure,
            carries=is_a_carry,
            pressured_carries=is_a_carry & was_under_pressure,
            take_ons=is_a_take_on,
            take_ons_won=is_a_take_on & events["was_a_completed_take_on"],
            times_dispossessed=event_name
            == PressResistanceFeature.DISPOSSESSED_EVENT_NAME,
            miscontrols=event_name == PressResistanceFeature.MISCONTROL_EVENT_NAME,
        )

    def _divided_or_left_empty(self, part: pd.Series, whole: pd.Series) -> pd.Series:
        """Divide a whole column, leaving a cell empty where nothing divides.

        Returns:
            The rounded share per row, or an empty cell. A zero would claim
            the player failed under pressure when they were never put under
            any.
        """
        can_be_divided = whole != 0
        quotient = part / whole.where(can_be_divided)
        return (
            DecimalRounder(PressResistanceFeature.RATE_DECIMAL_PLACES)
            .round_every_value(quotient)
            .where(can_be_divided, "")
        )


if __name__ == "__main__":
    StatsBombPressResistanceBuilder(PreparedStatsBombTables()).build_every_match()
