"""The metrics of every player and match, out of the StatsBomb data.

StatsBomb has no minutes column, so who was on the pitch and for how long is
read out of the starting line up and the substitutions. A match that ran into
extra time therefore ends when its last event does, not after ninety minutes.
"""

import numpy as np
import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    PlayerMatchMetricFeature,
    SubstitutionFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    PlayerMatchMetricCalculator,
    PreparedStatsBombTables,
    SharedFeatureFile,
)


class StatsBombPlayerMetricBuilder:
    """What every StatsBomb player did in every match they played."""

    PLAYER_KEYS = ["game_identifier", "player_identifier"]

    def __init__(
        self,
        prepared_tables: PreparedStatsBombTables,
        player_metric_calculator: PlayerMatchMetricCalculator,
    ) -> None:
        self._prepared_tables = prepared_tables
        self._player_metric_calculator = player_metric_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(
                PlayerMatchMetricFeature.OUTPUT_FILE,
                PlayerMatchMetricFeature.COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            PlayerMatchMetricFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Group the prepared events and write one row per player and match.

        Returns:
            How many rows the file holds afterwards, the rows the Wyscout half
            wrote included.

        Raises:
            SystemExit: When the events have not been prepared yet.
        """
        events = self._prepared_tables.read_the_events()
        appearances = self._read_who_was_on_the_pitch(events)
        counts = self._player_metric_calculator.count_every_player(
            self._actions_with_the_role_of_their_player(appearances)
        )

        rows = self._build_the_rows_of_every_appearance(appearances, counts)
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} player rows from StatsBomb, {total_count} in all")
        return total_count

    def _read_who_was_on_the_pitch(self, events: pd.DataFrame) -> pd.DataFrame:
        """Read who played in every match, in which role and for how long.

        A substitute gets the minutes from when they came on, the player they
        replaced the minutes up to that moment, and whoever the last event
        touching them names decides.

        Returns:
            One row per player who was on the pitch at all. Somebody whose
            minutes come to nothing is left out, because a row of zeros over
            zero minutes says nothing, and so is somebody who was only ever
            taken off, because they were never put on.
        """
        last_minute = self._last_minute_of_every_match(events)
        went_on_or_off = self._every_change_to_the_line_up(events, last_minute)
        of_the_last_change = went_on_or_off.groupby(
            self.PLAYER_KEYS, sort=False, as_index=False
        ).last()
        was_ever_put_on = of_the_last_change["team_name"].notna() & (
            of_the_last_change["minutes_played"] > 0
        )
        return of_the_last_change[was_ever_put_on].assign(
            minutes_played=of_the_last_change.loc[
                was_ever_put_on, "minutes_played"
            ].astype(int)
        )

    def _last_minute_of_every_match(self, events: pd.DataFrame) -> pd.Series:
        """Read the minute every match ended in, extra time included."""
        return events.groupby("game_identifier", sort=False)["minute_in_match"].max()

    def _every_change_to_the_line_up(
        self, events: pd.DataFrame, last_minute: pd.Series
    ) -> pd.DataFrame:
        """Put the starters on the pitch, then every substitution after them.

        The starting line ups all come first, the way the walk this replaces
        put the whole eleven on before it looked at a single substitution.
        """
        substitutions = events[
            events["event_name"] == SubstitutionFeature.SUBSTITUTION_EVENT_NAME
        ]
        return pd.concat(
            [
                self._the_starters(last_minute),
                self._who_came_on(substitutions, last_minute),
                self._who_went_off(substitutions),
            ]
        ).sort_values("order_of_the_change", kind="stable")

    def _the_starters(self, last_minute: pd.Series) -> pd.DataFrame:
        """Put the eleven players of every starting line up on the pitch."""
        line_ups = self._prepared_tables.read_the_starting_line_ups()
        return pd.DataFrame(
            {
                "game_identifier": line_ups["game_identifier"],
                "player_identifier": line_ups["player_identifier"],
                "player_name": line_ups["player_name"],
                "team_name": line_ups["team_name"],
                "role": self.role_of_every_position(line_ups["position_name"]),
                "minutes_played": line_ups["game_identifier"]
                .map(last_minute)
                .fillna(PlayerMatchMetricFeature.FULL_MATCH_MINUTES),
                "order_of_the_change": 0,
            }
        )

    def _who_came_on(
        self, substitutions: pd.DataFrame, last_minute: pd.Series
    ) -> pd.DataFrame:
        """Put every replacement on, for what was left of their match."""
        minutes_left = substitutions["game_identifier"].map(last_minute) - (
            substitutions["minute_in_match"]
        )
        return pd.DataFrame(
            {
                "game_identifier": substitutions["game_identifier"],
                "player_identifier": substitutions["replacement_player_identifier"],
                "player_name": substitutions["replacement_player_name"],
                "team_name": substitutions["team_name"],
                "role": "",
                "minutes_played": minutes_left.clip(lower=0),
                "order_of_the_change": substitutions.index + 1,
            }
        )

    def _who_went_off(self, substitutions: pd.DataFrame) -> pd.DataFrame:
        """Take every replaced player off, after the minute they lasted.

        The role and the team of a player who goes off are left empty here,
        because the change that put them on has already said both.
        """
        return pd.DataFrame(
            {
                "game_identifier": substitutions["game_identifier"],
                "player_identifier": substitutions["player_identifier"],
                "player_name": substitutions["player_name"],
                "team_name": None,
                "role": None,
                "minutes_played": substitutions["minute_in_match"],
                "order_of_the_change": substitutions.index + 1,
            }
        )

    def role_of_every_position(self, position_names: pd.Series) -> pd.Series:
        """Read the role out of a whole column of position names.

        Args:
            position_names: What StatsBomb calls the position, such as Right
                Center Back or Left Wing.

        Returns:
            The two letter role of each, or an empty one for a position none
            of the words fit. The first word that fits wins, so a wing back is
            a defender rather than a forward.
        """
        return pd.Series(
            np.select(
                [
                    position_names.str.contains(word, regex=False)
                    for word, _role in PlayerMatchMetricFeature.ROLE_OF_POSITION_WORD
                ],
                [
                    role
                    for _word, role in PlayerMatchMetricFeature.ROLE_OF_POSITION_WORD
                ],
                default="",
            ),
            index=position_names.index,
        )

    def _actions_with_the_role_of_their_player(
        self, appearances: pd.DataFrame
    ) -> pd.DataFrame:
        """Say of every action whether the player who made it keeps goal."""
        actions = self._prepared_tables.read_the_actions()
        of_the_player = actions.merge(
            appearances[[*self.PLAYER_KEYS, "role"]], on=self.PLAYER_KEYS, how="left"
        )
        return of_the_player.assign(
            is_goalkeeper=of_the_player["role"]
            == PlayerMatchMetricFeature.GOALKEEPER_ROLE
        )

    def _build_the_rows_of_every_appearance(
        self, appearances: pd.DataFrame, counts: pd.DataFrame
    ) -> pd.DataFrame:
        """Build one row per appearance, whether the player touched the ball or not."""
        sides = self._prepared_tables.read_the_sides_of_every_match()
        of_named_matches = appearances.merge(sides, on="game_identifier")
        counted = self._counts_lined_up_with(of_named_matches, counts)
        plays_at_home = (
            of_named_matches["team_name"] == of_named_matches["home_team_name"]
        )
        role = of_named_matches["role"]
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
    StatsBombPlayerMetricBuilder(
        PreparedStatsBombTables(), PlayerMatchMetricCalculator()
    ).build_every_match()
