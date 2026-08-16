"""The expected threat grid, learned on and applied to the Wyscout actions.

The grid is learned here and written down, so the StatsBomb half applies the
very same one. Learning walks the action file twice: once to count what
happens in each cell, once to add up what each player and team was worth.

Only open play counts. A corner or a penalty would push the goal rate of its
cell far above what that place on the pitch is really worth.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    ExpectedThreatFeature,
)
from wmguru.helpers.data_class import (
    MatchAction,
    WyscoutMatchFacts,
    WyscoutNameLookups,
)
from wmguru.helpers.utils import (
    CsvFile,
    ExpectedThreatGrid,
    ExpectedThreatGridFile,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutExpectedThreatBuilder:
    """The grid learned off the Wyscout actions, and every move valued with it."""

    def __init__(self, wyscout_data_reader: WyscoutDataReader) -> None:
        self._wyscout_data_reader = wyscout_data_reader
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
        """
        lookups = self._wyscout_data_reader.read_name_lookups()
        grid = self._learn_the_grid(lookups)
        self._grid_file.write(grid)
        print(f"  OK    grid learned, {grid.describe_the_best_cell()}")

        player_rows, team_rows = self._value_every_move(grid, lookups)
        self._player_file.write_keeping_the_other_source(player_rows)
        team_total = self._team_file.write_keeping_the_other_source(team_rows)
        print(
            f"  OK    {len(player_rows)} player rows and {len(team_rows)} team rows "
            f"from Wyscout, {team_total} team rows in all"
        )
        return team_total

    def _learn_the_grid(self, lookups: WyscoutNameLookups) -> ExpectedThreatGrid:
        """Count what happens in each cell, then solve for the value of each."""
        empty_grid = ExpectedThreatGrid(
            [0.0]
            * (ExpectedThreatFeature.COLUMN_COUNT * ExpectedThreatFeature.ROW_COUNT)
        )
        cell_count = len(empty_grid.values)
        shots = [0] * cell_count
        goals = [0] * cell_count
        moves = [0] * cell_count
        moves_to_cell = [[0] * cell_count for _ in range(cell_count)]

        for _game, actions in self._wyscout_data_reader.stream_actions_of_every_match(
            lookups
        ):
            for action in actions:
                start_cell, end_cell = self._cells_of(empty_grid, action)
                if action.kind in ExpectedThreatFeature.SHOT_KINDS:
                    shots[start_cell] += 1
                    goals[start_cell] += 1 if action.was_successful else 0
                elif self._is_a_completed_move(action):
                    moves[start_cell] += 1
                    moves_to_cell[start_cell][end_cell] += 1
        return self._solve(shots, goals, moves, moves_to_cell)

    def _solve(
        self,
        shots: list[int],
        goals: list[int],
        moves: list[int],
        moves_to_cell: list[list[int]],
    ) -> ExpectedThreatGrid:
        """Work out what each cell is worth, going round until it settles.

        A cell is worth the chance of scoring from it when the ball is shot,
        and what the cells it is moved to are worth when it is not. That is
        circular, so it is solved by passing over the grid a few times.
        """
        cell_count = len(shots)
        values = [0.0] * cell_count
        for _round in range(ExpectedThreatFeature.SOLVING_ROUNDS):
            updated = [0.0] * cell_count
            for cell in range(cell_count):
                events_in_cell = shots[cell] + moves[cell]
                if not events_in_cell:
                    continue
                scoring_chance = goals[cell] / shots[cell] if shots[cell] else 0.0
                updated[cell] = (shots[cell] / events_in_cell) * scoring_chance + (
                    moves[cell] / events_in_cell
                ) * self._value_moved_to(moves_to_cell[cell], moves[cell], values)
            values = updated
        return ExpectedThreatGrid(values)

    def _value_moved_to(
        self, moves_to_cell: list[int], move_count: int, values: list[float]
    ) -> float:
        """What the ball was worth on average after it was moved on."""
        if not move_count:
            return 0.0
        return (
            sum(
                count * values[target]
                for target, count in enumerate(moves_to_cell)
                if count
            )
            / move_count
        )

    def _value_every_move(
        self, grid: ExpectedThreatGrid, lookups: WyscoutNameLookups
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Add up what every player and team was worth, per match."""
        match_facts = self._wyscout_data_reader.read_match_facts()
        per_player: dict[tuple[str, str, str], list[float]] = {}
        per_team: dict[tuple[str, str], list[float]] = {}

        for game, actions in self._wyscout_data_reader.stream_actions_of_every_match(
            lookups
        ):
            for action in actions:
                if not self._is_a_completed_move(action):
                    continue
                start_cell, end_cell = self._cells_of(grid, action)
                gained = grid.gain_between(start_cell, end_cell)
                self._add(
                    per_player, (action.player_name, game, action.team_name), gained
                )
                self._add(per_team, (action.team_name, game), gained)
        return (
            self._build_player_rows(per_player, match_facts, lookups),
            self._build_team_rows(per_team, match_facts, lookups),
        )

    def _add(self, totals: dict[Any, list[float]], key: Any, gained: float) -> None:
        """Add one valued move to a running total."""
        total = totals.setdefault(key, [0.0, 0.0])
        total[0] += gained
        total[1] += 1

    def _build_player_rows(
        self,
        per_player: dict[tuple[str, str, str], list[float]],
        match_facts: dict[str, WyscoutMatchFacts],
        lookups: WyscoutNameLookups,
    ) -> list[dict[str, Any]]:
        """Build one row per player and match."""
        rows: list[dict[str, Any]] = []
        for (player_name, game, team_name), (gained, moves) in per_player.items():
            facts = match_facts.get(game)
            if facts is None:
                continue
            rows.append(
                {
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
                    **self._match_columns_of(facts, lookups, team_name),
                    "player": player_name,
                    "moves": int(moves),
                    "expected_threat_added": round(
                        gained, ExpectedThreatFeature.TOTAL_DECIMAL_PLACES
                    ),
                    "expected_threat_added_per_move": (
                        round(
                            gained / moves,
                            ExpectedThreatFeature.PER_MOVE_DECIMAL_PLACES,
                        )
                        if moves
                        else ""
                    ),
                }
            )
        return rows

    def _build_team_rows(
        self,
        per_team: dict[tuple[str, str], list[float]],
        match_facts: dict[str, WyscoutMatchFacts],
        lookups: WyscoutNameLookups,
    ) -> list[dict[str, Any]]:
        """Build one row per team and match, with what the other side was worth."""
        rows: list[dict[str, Any]] = []
        for (team_name, game), (gained, moves) in per_team.items():
            facts = match_facts.get(game)
            if facts is None:
                continue
            match_columns = self._match_columns_of(facts, lookups, team_name)
            conceded = per_team.get((match_columns["opponent"], game), [0.0, 0.0])[0]
            places = ExpectedThreatFeature.TOTAL_DECIMAL_PLACES
            rows.append(
                {
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
                    **match_columns,
                    "is_home": int(
                        team_name
                        == lookups.team_names.get(
                            facts.home_team_identifier, facts.home_team_identifier
                        )
                    ),
                    "moves": int(moves),
                    "expected_threat_for": round(gained, places),
                    "expected_threat_against": round(conceded, places),
                    "expected_threat_net": round(gained - conceded, places),
                }
            )
        return rows

    def _match_columns_of(
        self,
        facts: WyscoutMatchFacts,
        lookups: WyscoutNameLookups,
        team_name: str,
    ) -> dict[str, Any]:
        """Build the columns both output files have in common."""
        home_team = lookups.team_names.get(
            facts.home_team_identifier, facts.home_team_identifier
        )
        away_team = lookups.team_names.get(
            facts.away_team_identifier, facts.away_team_identifier
        )
        return {
            "date": facts.match_date,
            "competition": lookups.competition_names.get(
                facts.competition_identifier, facts.competition_identifier
            ),
            "season": facts.season_name,
            "team": team_name,
            "opponent": away_team if team_name == home_team else home_team,
        }

    def _is_a_completed_move(self, action: MatchAction) -> bool:
        """Return True when the ball was moved on and reached its target."""
        return action.kind in ExpectedThreatFeature.MOVE_KINDS and action.was_successful

    def _cells_of(
        self, grid: ExpectedThreatGrid, action: MatchAction
    ) -> tuple[int, int]:
        """Say which cell an action started in and which one it ended in."""
        return (
            grid.cell_of(action.start_x_in_metres, action.start_y_in_metres),
            grid.cell_of(action.end_x_in_metres, action.end_y_in_metres),
        )


if __name__ == "__main__":
    WyscoutExpectedThreatBuilder(
        WyscoutDataReader(TextNormalizer())
    ).build_every_match()
