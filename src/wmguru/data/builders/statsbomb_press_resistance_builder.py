"""How well every player kept the ball under pressure.

StatsBomb marks an action as played under pressure, so this can be read off
rather than guessed. Passes, carries and take ons are counted with and without
pressure, together with the two ways of simply losing the ball.

The file is written after every competition, so a stopped run picks up where it
left off.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    ExpectedThreatFeature,
    MatchStyleFeature,
    PressResistanceFeature,
    StatsBombOpenDataSource,
    WebRequestSetting,
)
from wmguru.helpers.data_class import StatsBombCompetition
from wmguru.helpers.utils import (
    CsvFile,
    SharedFeatureFile,
    StatsBombOpenDataReader,
    WebFileDownloader,
)


class StatsBombPressResistanceBuilder:
    """The pressured actions of every player of every free competition."""

    def __init__(self, statsbomb_reader: StatsBombOpenDataReader) -> None:
        self._statsbomb_reader = statsbomb_reader
        self._output_file = SharedFeatureFile(
            CsvFile(
                PressResistanceFeature.OUTPUT_FILE,
                PressResistanceFeature.COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            PressResistanceFeature.SORT_KEY_NAMES,
        )

    def build_every_competition(self) -> int:
        """Walk every open competition and write the file after each one.

        Returns:
            How many rows the file holds afterwards.

        Raises:
            SystemExit: When the competition list could not be loaded.
        """
        own_rows = self._output_file.read_own_rows()
        open_competitions = self._statsbomb_reader.read_open_competitions(
            self._output_file.read_finished_keys()
        )
        print(f"Open competitions {len(open_competitions)}", flush=True)

        total_count = len(own_rows)
        for competition in open_competitions:
            for match in self._statsbomb_reader.read_matches(competition):
                own_rows.extend(self._build_rows_of_one_match(match, competition))
            total_count = self._output_file.write_keeping_the_other_source(own_rows)
            print(
                f"  SAVED  {competition.competition_name} "
                f"{competition.season_name} (file now {total_count})",
                flush=True,
            )
        print(f"\nDone: the press resistance file holds {total_count} rows.")
        return total_count

    def _build_rows_of_one_match(
        self, match: dict[str, Any], competition: StatsBombCompetition
    ) -> list[dict[str, Any]]:
        """Build one row per player who touched the ball in one match."""
        counters: dict[str, dict[str, float]] = {}
        team_of_player: dict[str, str] = {}
        for event in self._statsbomb_reader.read_events(match):
            player_name = event.get(StatsBombOpenDataSource.PLAYER_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            if not player_name:
                continue
            self._add_one_event(
                counters.setdefault(player_name, self._empty_counter()), event
            )
            team_of_player[player_name] = event.get(
                StatsBombOpenDataSource.TEAM_FIELD, {}
            ).get(StatsBombOpenDataSource.NAME_FIELD)

        home_team = match[StatsBombOpenDataSource.HOME_TEAM_FIELD][
            StatsBombOpenDataSource.HOME_TEAM_NAME_FIELD
        ]
        away_team = match[StatsBombOpenDataSource.AWAY_TEAM_FIELD][
            StatsBombOpenDataSource.AWAY_TEAM_NAME_FIELD
        ]
        return [
            self._build_one_row(
                player_name,
                counter,
                team_of_player.get(player_name, ""),
                home_team,
                away_team,
                self._statsbomb_reader.date_of(match),
                competition,
            )
            for player_name, counter in counters.items()
        ]

    def _empty_counter(self) -> dict[str, float]:
        """Build a counter that holds a zero for everything that is counted."""
        return {
            name: 0.0
            for name in (
                "passes",
                "completed_passes",
                "pressured_passes",
                "completed_pressured_passes",
                "carries",
                "pressured_carries",
                "take_ons",
                "take_ons_won",
                "times_dispossessed",
                "miscontrols",
            )
        }

    def _add_one_event(self, counter: dict[str, float], event: dict[str, Any]) -> None:
        """Add one event, counting it once and under pressure where it applies."""
        event_name = event.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        was_under_pressure = bool(
            event.get(PressResistanceFeature.UNDER_PRESSURE_FIELD)
        )
        if event_name == MatchStyleFeature.PASS_EVENT_NAME:
            self._add_one_pass(counter, event, was_under_pressure)
        elif event_name == ExpectedThreatFeature.CARRY_EVENT_NAME:
            counter["carries"] += 1
            counter["pressured_carries"] += 1 if was_under_pressure else 0
        elif event_name == MatchStyleFeature.DRIBBLE_EVENT_NAME:
            counter["take_ons"] += 1
            counter["take_ons_won"] += 1 if self._was_won(event) else 0
        elif event_name == PressResistanceFeature.DISPOSSESSED_EVENT_NAME:
            counter["times_dispossessed"] += 1
        elif event_name == PressResistanceFeature.MISCONTROL_EVENT_NAME:
            counter["miscontrols"] += 1

    def _add_one_pass(
        self,
        counter: dict[str, float],
        event: dict[str, Any],
        was_under_pressure: bool,
    ) -> None:
        """Add a pass, and again separately when it was played under pressure."""
        was_completed = StatsBombOpenDataSource.OUTCOME_FIELD not in event.get(
            StatsBombOpenDataSource.PASS_FIELD, {}
        )
        counter["passes"] += 1
        counter["completed_passes"] += 1 if was_completed else 0
        if not was_under_pressure:
            return
        counter["pressured_passes"] += 1
        counter["completed_pressured_passes"] += 1 if was_completed else 0

    def _was_won(self, event: dict[str, Any]) -> bool:
        """Return True when the player got past their opponent."""
        outcome = event.get(StatsBombOpenDataSource.DRIBBLE_FIELD, {}).get(
            StatsBombOpenDataSource.OUTCOME_FIELD, {}
        )
        return (
            outcome.get(StatsBombOpenDataSource.NAME_FIELD)
            == MatchStyleFeature.COMPLETED_DRIBBLE_NAME
        )

    def _build_one_row(
        self,
        player_name: str,
        counter: dict[str, float],
        team_name: str,
        home_team: str,
        away_team: str,
        match_date: str,
        competition: StatsBombCompetition,
    ) -> dict[str, Any]:
        """Turn the counter of one player into their row."""
        return {
            EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
            "date": match_date,
            "competition": competition.competition_name,
            "season": competition.season_name,
            "team": team_name,
            "opponent": away_team if team_name == home_team else home_team,
            "player": player_name,
            **{name: int(value) for name, value in counter.items()},
            "pressured_pass_completion": self._share(
                counter["completed_pressured_passes"], counter["pressured_passes"]
            ),
            "pressured_share": self._share(
                counter["pressured_passes"], counter["passes"]
            ),
        }

    def _share(self, part: float, whole: float) -> Any:
        """Divide, or give an empty cell when there is nothing to divide by.

        Returns:
            The rounded share, or an empty string. A zero would claim the
            player failed under pressure when they were never put under any.
        """
        if not whole:
            return ""
        return round(part / whole, PressResistanceFeature.RATE_DECIMAL_PLACES)


if __name__ == "__main__":
    StatsBombPressResistanceBuilder(
        StatsBombOpenDataReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    StatsBombOpenDataSource.POLITE_DELAY_IN_SECONDS
                ),
            )
        )
    ).build_every_competition()
