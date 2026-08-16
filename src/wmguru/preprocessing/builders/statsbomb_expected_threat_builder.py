"""The learned expected threat grid, applied to the StatsBomb data.

The grid comes out of the file the Wyscout builder wrote, so a move is worth
the same in both halves. A move here is a completed pass or a carry, which is
StatsBomb's own event for running with the ball.
"""

import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    ExpectedThreatFeature,
    MatchStyleFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    DecimalRounder,
    ExpectedThreatGrid,
    ExpectedThreatGridFile,
    PreparedStatsBombTables,
    SharedFeatureFile,
)


class StatsBombExpectedThreatBuilder:
    """Every StatsBomb move, valued with the grid the Wyscout half learned."""

    def __init__(self, prepared_tables: PreparedStatsBombTables) -> None:
        self._prepared_tables = prepared_tables
        self._grid_file = ExpectedThreatGridFile(
            CsvFile(
                ExpectedThreatFeature.GRID_FILE,
                ExpectedThreatFeature.GRID_COLUMN_NAMES,
            )
        )
        self._player_file = SharedFeatureFile(
            CsvFile(
                ExpectedThreatFeature.PLAYER_OUTPUT_FILE,
                ExpectedThreatFeature.PLAYER_COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            ExpectedThreatFeature.PLAYER_SORT_KEY_NAMES,
        )
        self._team_file = SharedFeatureFile(
            CsvFile(
                ExpectedThreatFeature.TEAM_OUTPUT_FILE,
                ExpectedThreatFeature.TEAM_COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            ExpectedThreatFeature.TEAM_SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Value every move of every match and write both files.

        Returns:
            How many team rows the team file holds afterwards, the rows the
            Wyscout half wrote included.

        Raises:
            SystemExit: When the grid was never learned, or when the events
                have not been prepared yet.
        """
        grid = self._grid_file.read()
        identities = self._prepared_tables.read_the_match_identities()
        valued_moves = self._value_every_move(grid)

        player_rows = self._build_player_rows(valued_moves, identities)
        team_rows = self._build_team_rows(valued_moves, identities)
        self._player_file.write_the_table_keeping_the_other_source(player_rows)
        team_total = self._team_file.write_the_table_keeping_the_other_source(team_rows)
        print(
            f"  OK    {len(player_rows)} player rows and {len(team_rows)} team rows "
            f"from StatsBomb, {team_total} team rows in all"
        )
        return team_total

    def _value_every_move(self, grid: ExpectedThreatGrid) -> pd.DataFrame:
        """Say of every completed move what it was worth to its player and team.

        A move is a pass that arrived or a carry, and both have to lie
        somewhere: a move the source placed nowhere runs between no cells.
        """
        events = self._prepared_tables.read_the_events()
        is_a_completed_pass = (
            events["event_name"] == MatchStyleFeature.PASS_EVENT_NAME
        ) & events["was_a_completed_pass"]
        is_a_carry = events["event_name"] == ExpectedThreatFeature.CARRY_EVENT_NAME
        was_placed = (
            events["start_x_in_metres"].notna() & events["end_x_in_metres"].notna()
        )
        moves = events[(is_a_completed_pass | is_a_carry) & was_placed]
        return moves.assign(
            gained=grid.gain_of_every_move(
                grid.which_cell_every_place_falls_into(
                    moves["start_x_in_metres"], moves["start_y_in_metres"]
                ),
                grid.which_cell_every_place_falls_into(
                    moves["end_x_in_metres"], moves["end_y_in_metres"]
                ),
            )
        )

    def _build_player_rows(
        self, valued_moves: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Build one row per player and match."""
        of_a_named_player = valued_moves[
            (valued_moves["player_name"] != "") & (valued_moves["team_name"] != "")
        ]
        per_player = self._added_up_over(
            of_a_named_player, ["player_name", "team_name", "game_identifier"]
        )
        of_named_matches = per_player.merge(identities, on="game_identifier")
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                **self._the_columns_both_files_share(of_named_matches),
                "player": of_named_matches["player_name"],
                "moves": of_named_matches["moves"],
                "expected_threat_added": DecimalRounder(
                    ExpectedThreatFeature.TOTAL_DECIMAL_PLACES
                ).round_every_value(of_named_matches["gained"]),
                "expected_threat_added_per_move": DecimalRounder(
                    ExpectedThreatFeature.PER_MOVE_DECIMAL_PLACES
                ).round_every_value(
                    of_named_matches["gained"] / of_named_matches["moves"]
                ),
            }
        )

    def _build_team_rows(
        self, valued_moves: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Build one row per team and match, with what the other side was worth."""
        of_a_named_team = valued_moves[valued_moves["team_name"] != ""]
        per_team = self._added_up_over(
            of_a_named_team, ["team_name", "game_identifier"]
        )
        of_named_matches = per_team.merge(identities, on="game_identifier")
        shared_columns = self._the_columns_both_files_share(of_named_matches)
        gained = of_named_matches["gained"]
        conceded = self._what_the_other_side_gained(
            of_named_matches, shared_columns["opponent"], per_team
        )
        rounder = DecimalRounder(ExpectedThreatFeature.TOTAL_DECIMAL_PLACES)
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                **shared_columns,
                "is_home": (
                    of_named_matches["team_name"] == of_named_matches["home_team_name"]
                ).astype(int),
                "moves": of_named_matches["moves"],
                "expected_threat_for": rounder.round_every_value(gained),
                "expected_threat_against": rounder.round_every_value(conceded),
                "expected_threat_net": rounder.round_every_value(gained - conceded),
            }
        )

    def _what_the_other_side_gained(
        self,
        of_named_matches: pd.DataFrame,
        opponent_name: pd.Series,
        per_team: pd.DataFrame,
    ) -> pd.Series:
        """Look up what the other side was worth, zero where it made no move."""
        looked_up = pd.DataFrame(
            {
                "game_identifier": of_named_matches["game_identifier"],
                "team_name": opponent_name,
            }
        ).merge(
            per_team[["game_identifier", "team_name", "gained"]],
            on=["game_identifier", "team_name"],
            how="left",
        )
        return looked_up["gained"].fillna(0.0).set_axis(of_named_matches.index)

    def _added_up_over(
        self, valued_moves: pd.DataFrame, keys: list[str]
    ) -> pd.DataFrame:
        """Add up what was gained and how many moves it took, over the given keys."""
        return (
            valued_moves.groupby(keys, sort=False)
            .agg(gained=("gained", "sum"), moves=("gained", "size"))
            .reset_index()
        )

    def _the_columns_both_files_share(
        self, of_named_matches: pd.DataFrame
    ) -> dict[str, pd.Series]:
        """Build the columns both output files have in common."""
        plays_at_home = (
            of_named_matches["team_name"] == of_named_matches["home_team_name"]
        )
        return {
            "date": of_named_matches["match_date"],
            "competition": of_named_matches["competition_name"],
            "season": of_named_matches["season_name"],
            "team": of_named_matches["team_name"],
            "opponent": of_named_matches["away_team_name"].where(
                plays_at_home, of_named_matches["home_team_name"]
            ),
        }


if __name__ == "__main__":
    StatsBombExpectedThreatBuilder(PreparedStatsBombTables()).build_every_match()
