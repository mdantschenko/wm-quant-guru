"""The expected threat grid, learned on and applied to the Wyscout actions.

The grid is learned here and written down, so the StatsBomb half applies the
very same one. Learning counts what happens in each cell of the pitch and then
solves for what each cell is worth.

Only open play counts. A corner or a penalty would push the goal rate of its
cell far above what that place on the pitch is really worth.
"""

import numpy as np
import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    ExpectedThreatFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    DecimalRounder,
    ExpectedThreatGrid,
    ExpectedThreatGridFile,
    PreparedWyscoutTables,
    SharedFeatureFile,
)


class WyscoutExpectedThreatBuilder:
    """The grid learned off the Wyscout actions, and every move valued with it."""

    def __init__(self, prepared_tables: PreparedWyscoutTables) -> None:
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
            EventSourceSetting.WYSCOUT_NAME,
            ExpectedThreatFeature.PLAYER_SORT_KEY_NAMES,
        )
        self._team_file = SharedFeatureFile(
            CsvFile(
                ExpectedThreatFeature.TEAM_OUTPUT_FILE,
                ExpectedThreatFeature.TEAM_COLUMN_NAMES,
            ),
            EventSourceSetting.WYSCOUT_NAME,
            ExpectedThreatFeature.TEAM_SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Learn the grid, write it, and value every move of every match.

        Returns:
            How many team rows the team file holds afterwards, the rows the
            StatsBomb half wrote included.

        Raises:
            SystemExit: When the actions have not been prepared yet.
        """
        actions = self._actions_with_their_cells()
        grid = self._learn_the_grid(actions)
        self._grid_file.write(grid)
        print(f"  OK    grid learned, {grid.describe_the_best_cell()}")

        identities = self._prepared_tables.read_the_match_identities()
        valued_moves = self._value_every_move(actions, grid)
        player_rows = self._build_player_rows(valued_moves, identities)
        team_rows = self._build_team_rows(valued_moves, identities)
        self._player_file.write_the_table_keeping_the_other_source(player_rows)
        team_total = self._team_file.write_the_table_keeping_the_other_source(team_rows)
        print(
            f"  OK    {len(player_rows)} player rows and {len(team_rows)} team rows "
            f"from Wyscout, {team_total} team rows in all"
        )
        return team_total

    def _actions_with_their_cells(self) -> pd.DataFrame:
        """Read the actions, each with the cell it started and ended in."""
        actions = self._prepared_tables.read_the_actions()
        empty_grid = ExpectedThreatGrid([0.0] * self._cell_count())
        return actions.assign(
            start_cell=empty_grid.which_cell_every_place_falls_into(
                actions["start_x_in_metres"], actions["start_y_in_metres"]
            ),
            end_cell=empty_grid.which_cell_every_place_falls_into(
                actions["end_x_in_metres"], actions["end_y_in_metres"]
            ),
            is_a_shot=actions["kind"].isin(ExpectedThreatFeature.SHOT_KINDS),
            is_a_completed_move=actions["kind"].isin(ExpectedThreatFeature.MOVE_KINDS)
            & actions["was_successful"],
        )

    def _cell_count(self) -> int:
        """How many cells the pitch is cut into."""
        return ExpectedThreatFeature.COLUMN_COUNT * ExpectedThreatFeature.ROW_COUNT

    def _learn_the_grid(self, actions: pd.DataFrame) -> ExpectedThreatGrid:
        """Count what happens in each cell, then solve for the value of each."""
        shots_of_cell = self._counted_per_cell(actions[actions["is_a_shot"]])
        goals_of_cell = self._counted_per_cell(
            actions[actions["is_a_shot"] & actions["was_successful"]]
        )
        completed_moves = actions[actions["is_a_completed_move"]]
        moves_of_cell = self._counted_per_cell(completed_moves)
        return self._solve(
            shots_of_cell,
            goals_of_cell,
            moves_of_cell,
            self._moves_between_the_cells(completed_moves),
        )

    def _counted_per_cell(self, actions: pd.DataFrame) -> np.ndarray:
        """Count how often something happened in each cell of the pitch."""
        return np.bincount(actions["start_cell"], minlength=self._cell_count()).astype(
            float
        )

    def _moves_between_the_cells(self, completed_moves: pd.DataFrame) -> np.ndarray:
        """Count how often the ball went from each cell to each other cell."""
        cell_count = self._cell_count()
        return (
            np.bincount(
                completed_moves["start_cell"] * cell_count
                + completed_moves["end_cell"],
                minlength=cell_count * cell_count,
            )
            .astype(float)
            .reshape(cell_count, cell_count)
        )

    def _solve(
        self,
        shots_of_cell: np.ndarray,
        goals_of_cell: np.ndarray,
        moves_of_cell: np.ndarray,
        moves_between_the_cells: np.ndarray,
    ) -> ExpectedThreatGrid:
        """Work out what each cell is worth, going round until it settles.

        A cell is worth the chance of scoring from it when the ball is shot,
        and what the cells it is moved to are worth when it is not. That is
        circular, so it is solved by passing over the grid a few times.
        """
        events_in_cell = shots_of_cell + moves_of_cell
        was_ever_used = events_in_cell > 0
        scoring_chance = np.divide(
            goals_of_cell,
            shots_of_cell,
            out=np.zeros_like(goals_of_cell),
            where=shots_of_cell > 0,
        )
        shot_share = np.divide(
            shots_of_cell,
            events_in_cell,
            out=np.zeros_like(shots_of_cell),
            where=was_ever_used,
        )
        move_share = np.divide(
            moves_of_cell,
            events_in_cell,
            out=np.zeros_like(moves_of_cell),
            where=was_ever_used,
        )
        values = np.zeros(len(shots_of_cell))
        for _round in range(ExpectedThreatFeature.SOLVING_ROUNDS):
            value_moved_to = np.divide(
                moves_between_the_cells @ values,
                moves_of_cell,
                out=np.zeros_like(values),
                where=moves_of_cell > 0,
            )
            values = shot_share * scoring_chance + move_share * value_moved_to
        return ExpectedThreatGrid(list(values))

    def _value_every_move(
        self, actions: pd.DataFrame, grid: ExpectedThreatGrid
    ) -> pd.DataFrame:
        """Say of every completed move what it was worth to its player and team."""
        completed_moves = actions[actions["is_a_completed_move"]]
        return completed_moves.assign(
            gained=grid.gain_of_every_move(
                completed_moves["start_cell"], completed_moves["end_cell"]
            )
        )

    def _build_player_rows(
        self, valued_moves: pd.DataFrame, identities: pd.DataFrame
    ) -> pd.DataFrame:
        """Build one row per player and match."""
        per_player = self._added_up_over(
            valued_moves, ["player_name", "game_identifier", "team_name"]
        )
        of_named_matches = per_player.merge(identities, on="game_identifier")
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
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
        per_team = self._added_up_over(valued_moves, ["team_name", "game_identifier"])
        of_named_matches = per_team.merge(identities, on="game_identifier")
        shared_columns = self._the_columns_both_files_share(of_named_matches)
        gained = of_named_matches["gained"]
        conceded = self._what_the_other_side_gained(
            of_named_matches, shared_columns["opponent"], per_team
        )
        rounder = DecimalRounder(ExpectedThreatFeature.TOTAL_DECIMAL_PLACES)
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
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
    WyscoutExpectedThreatBuilder(PreparedWyscoutTables()).build_every_match()
