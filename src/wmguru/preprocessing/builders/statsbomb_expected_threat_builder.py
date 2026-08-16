"""The learned expected threat grid, applied to the StatsBomb data.

The grid comes out of the file the Wyscout builder wrote, so a move is worth
the same in both halves. A move here is a completed pass or a carry, which is
StatsBomb's own event for running with the ball.

The files are written after every competition, so a stopped run picks up where
it left off.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    ExpectedThreatFeature,
    MatchStyleFeature,
    StatsBombOpenDataSource,
    WebRequestSetting,
)
from wmguru.helpers.data_class import StatsBombCompetition
from wmguru.helpers.utils import (
    CsvFile,
    ExpectedThreatGrid,
    ExpectedThreatGridFile,
    SharedFeatureFile,
    StatsBombOpenDataReader,
    WebFileDownloader,
)


class StatsBombExpectedThreatBuilder:
    """Every StatsBomb move, valued with the grid the Wyscout half learned."""

    def __init__(self, statsbomb_reader: StatsBombOpenDataReader) -> None:
        self._statsbomb_reader = statsbomb_reader
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

    def build_every_competition(self) -> int:
        """Walk every open competition and write both files after each one.

        Returns:
            How many team rows the team file holds afterwards, the rows the
            Wyscout half wrote included.

        Raises:
            SystemExit: When the grid was never learned, or when the
                competition list could not be loaded.
        """
        grid = self._grid_file.read()
        own_player_rows = self._player_file.read_own_rows()
        own_team_rows = self._team_file.read_own_rows()
        open_competitions = self._statsbomb_reader.read_open_competitions(
            self._team_file.read_finished_keys()
        )
        print(f"Open competitions {len(open_competitions)}", flush=True)

        team_total = len(own_team_rows) + len(
            self._team_file.read_rows_of_the_other_source()
        )
        for competition in open_competitions:
            for match in self._statsbomb_reader.read_matches(competition):
                player_rows, team_rows = self._build_rows_of_one_match(
                    match, competition, grid
                )
                own_player_rows.extend(player_rows)
                own_team_rows.extend(team_rows)
            self._player_file.write_keeping_the_other_source(own_player_rows)
            team_total = self._team_file.write_keeping_the_other_source(own_team_rows)
            print(
                f"  SAVED  {competition.competition_name} "
                f"{competition.season_name} (file now {team_total} team rows)",
                flush=True,
            )
        print(f"\nDone: the team file holds {team_total} rows.")
        return team_total

    def _build_rows_of_one_match(
        self,
        match: dict[str, Any],
        competition: StatsBombCompetition,
        grid: ExpectedThreatGrid,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Build the player rows and the team rows of one match."""
        per_player: dict[tuple[str, str], list[float]] = {}
        per_team: dict[str, list[float]] = {}
        for event in self._statsbomb_reader.read_events(match):
            self._add_one_event(event, grid, per_player, per_team)

        home_team = match[StatsBombOpenDataSource.HOME_TEAM_FIELD][
            StatsBombOpenDataSource.HOME_TEAM_NAME_FIELD
        ]
        away_team = match[StatsBombOpenDataSource.AWAY_TEAM_FIELD][
            StatsBombOpenDataSource.AWAY_TEAM_NAME_FIELD
        ]
        shared_columns = {
            "date": self._statsbomb_reader.read_the_day_a_match_was_played(match),
            "competition": competition.competition_name,
            "season": competition.season_name,
        }
        return (
            self._build_player_rows(per_player, shared_columns, home_team, away_team),
            self._build_team_rows(per_team, shared_columns, home_team, away_team),
        )

    def _add_one_event(
        self,
        event: dict[str, Any],
        grid: ExpectedThreatGrid,
        per_player: dict[tuple[str, str], list[float]],
        per_team: dict[str, list[float]],
    ) -> None:
        """Add what one move was worth to the player and to the team."""
        cells = self._which_cells_the_move_ran_between(event, grid)
        if cells is None:
            return
        gained = grid.gain_between(cells[0], cells[1])
        team_name = event.get(StatsBombOpenDataSource.TEAM_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        player_name = event.get(StatsBombOpenDataSource.PLAYER_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        if player_name and team_name:
            self._count_one_valued_move(per_player, (player_name, team_name), gained)
        if team_name:
            self._count_one_valued_move(per_team, team_name, gained)

    def _which_cells_the_move_ran_between(
        self, event: dict[str, Any], grid: ExpectedThreatGrid
    ) -> tuple[int, int] | None:
        """Say which cells a completed move ran between, or None if it was none.

        Returns:
            The cell it started in and the cell it ended in, or None for
            anything that is not a completed pass or a carry.
        """
        start_location = event.get(StatsBombOpenDataSource.LOCATION_FIELD)
        if not start_location:
            return None
        end_location = self._end_location_of(event)
        if not end_location:
            return None
        start_point = self._statsbomb_reader.point_on_our_pitch_in_metres(
            start_location
        )
        end_point = self._statsbomb_reader.point_on_our_pitch_in_metres(end_location)
        return (
            grid.which_cell_the_place_falls_into(start_point[0], start_point[1]),
            grid.which_cell_the_place_falls_into(end_point[0], end_point[1]),
        )

    def _end_location_of(self, event: dict[str, Any]) -> list[float] | None:
        """Read where a completed move ended, or None when it is no move."""
        event_name = event.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        if event_name == MatchStyleFeature.PASS_EVENT_NAME:
            pass_details = event.get(StatsBombOpenDataSource.PASS_FIELD, {})
            if StatsBombOpenDataSource.OUTCOME_FIELD in pass_details:
                return None
            return pass_details.get(StatsBombOpenDataSource.END_LOCATION_FIELD)
        if event_name == ExpectedThreatFeature.CARRY_EVENT_NAME:
            return event.get(ExpectedThreatFeature.CARRY_FIELD, {}).get(
                StatsBombOpenDataSource.END_LOCATION_FIELD
            )
        return None

    def _count_one_valued_move(
        self, totals: dict[Any, list[float]], key: Any, gained: float
    ) -> None:
        """Add one valued move to a running total."""
        total = totals.setdefault(key, [0.0, 0.0])
        total[0] += gained
        total[1] += 1

    def _build_player_rows(
        self,
        per_player: dict[tuple[str, str], list[float]],
        shared_columns: dict[str, Any],
        home_team: str,
        away_team: str,
    ) -> list[dict[str, Any]]:
        """Build one row per player of one match."""
        return [
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                **shared_columns,
                "team": team_name,
                "opponent": away_team if team_name == home_team else home_team,
                "player": player_name,
                "moves": int(moves),
                "expected_threat_added": round(
                    gained, ExpectedThreatFeature.TOTAL_DECIMAL_PLACES
                ),
                "expected_threat_added_per_move": (
                    round(gained / moves, ExpectedThreatFeature.PER_MOVE_DECIMAL_PLACES)
                    if moves
                    else ""
                ),
            }
            for (player_name, team_name), (gained, moves) in per_player.items()
        ]

    def _build_team_rows(
        self,
        per_team: dict[str, list[float]],
        shared_columns: dict[str, Any],
        home_team: str,
        away_team: str,
    ) -> list[dict[str, Any]]:
        """Build one row per team of one match, with what the other side was worth."""
        places = ExpectedThreatFeature.TOTAL_DECIMAL_PLACES
        rows: list[dict[str, Any]] = []
        for team_name, (gained, moves) in per_team.items():
            opponent_name = away_team if team_name == home_team else home_team
            conceded = per_team.get(opponent_name, [0.0, 0.0])[0]
            rows.append(
                {
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                    **shared_columns,
                    "team": team_name,
                    "opponent": opponent_name,
                    "is_home": int(team_name == home_team),
                    "moves": int(moves),
                    "expected_threat_for": round(gained, places),
                    "expected_threat_against": round(conceded, places),
                    "expected_threat_net": round(gained - conceded, places),
                }
            )
        return rows


if __name__ == "__main__":
    StatsBombExpectedThreatBuilder(
        StatsBombOpenDataReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    StatsBombOpenDataSource.POLITE_DELAY_IN_SECONDS
                ),
            )
        )
    ).build_every_competition()
