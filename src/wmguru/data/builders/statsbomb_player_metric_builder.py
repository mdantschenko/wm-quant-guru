"""The metrics of every player and match, out of the StatsBomb data.

StatsBomb has no minutes column, so who was on the pitch and for how long is
read out of the starting line up and the substitutions. A match that ran into
extra time therefore ends when its last event does, not after ninety minutes.

The file is written after every competition, so a stopped run picks up where it
left off.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    PlayerMatchMetricFeature,
    StatsBombOpenDataSource,
    SubstitutionFeature,
    WebRequestSetting,
)
from wmguru.helpers.data_class import PlayerAppearance, StatsBombCompetition
from wmguru.helpers.utils import (
    CsvFile,
    PlayerMatchMetricCalculator,
    SharedFeatureFile,
    StatsBombOpenDataReader,
    WebFileDownloader,
)


class StatsBombPlayerMetricBuilder:
    """What every StatsBomb player did in every match they played."""

    def __init__(
        self,
        statsbomb_reader: StatsBombOpenDataReader,
        player_metric_calculator: PlayerMatchMetricCalculator,
    ) -> None:
        self._statsbomb_reader = statsbomb_reader
        self._player_metric_calculator = player_metric_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(
                PlayerMatchMetricFeature.OUTPUT_FILE,
                PlayerMatchMetricFeature.COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            PlayerMatchMetricFeature.SORT_KEY_NAMES,
        )

    def build_every_competition(self) -> int:
        """Walk every open competition and write the file after each one.

        Returns:
            How many rows the file holds afterwards, the rows the Wyscout half
            wrote included.

        Raises:
            SystemExit: When the competition list could not be loaded.
        """
        own_rows = self._output_file.read_own_rows()
        open_competitions = self._statsbomb_reader.read_open_competitions(
            self._output_file.read_finished_keys()
        )
        print(f"Open competitions {len(open_competitions)}", flush=True)

        total_count = len(own_rows) + len(
            self._output_file.read_rows_of_the_other_source()
        )
        for competition in open_competitions:
            for match in self._statsbomb_reader.read_matches(competition):
                own_rows.extend(self._build_rows_of_one_match(match, competition))
            total_count = self._output_file.write_keeping_the_other_source(own_rows)
            print(
                f"  SAVED  {competition.competition_name} "
                f"{competition.season_name} (file now {total_count})",
                flush=True,
            )
        print(f"\nDone: the player metric file holds {total_count} rows.")
        return total_count

    def _build_rows_of_one_match(
        self, match: dict[str, Any], competition: StatsBombCompetition
    ) -> list[dict[str, Any]]:
        """Build one row per player who was on the pitch in one match."""
        events = self._statsbomb_reader.read_events(match)
        appearances, roles = self._read_line_up(events)
        counters = self._count_over_one_match(events, roles)

        home_team = match[StatsBombOpenDataSource.HOME_TEAM_FIELD][
            StatsBombOpenDataSource.HOME_TEAM_NAME_FIELD
        ]
        away_team = match[StatsBombOpenDataSource.AWAY_TEAM_FIELD][
            StatsBombOpenDataSource.AWAY_TEAM_NAME_FIELD
        ]
        match_date = self._statsbomb_reader.date_of(match)

        rows: list[dict[str, Any]] = []
        for player_identifier, appearance in appearances.items():
            role = roles.get(player_identifier, "")
            rows.append(
                {
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                    "date": match_date,
                    "competition": competition.competition_name,
                    "season": competition.season_name,
                    "team": appearance.team_identifier,
                    "opponent": (
                        away_team
                        if appearance.team_identifier == home_team
                        else home_team
                    ),
                    "player": appearance.player_name,
                    "role": role,
                    "minutes": appearance.minutes_played,
                    **self._player_metric_calculator.build_row(
                        counters.get(
                            player_identifier,
                            self._player_metric_calculator.empty_counter(),
                        ),
                        role == PlayerMatchMetricFeature.GOALKEEPER_ROLE,
                    ),
                }
            )
        return rows

    def _count_over_one_match(
        self, events: list[dict[str, Any]], roles: dict[str, str]
    ) -> dict[str, dict[str, float]]:
        """Count the actions of every player over the events of one match."""
        counters: dict[str, dict[str, float]] = {}
        for event in events:
            action = self._statsbomb_reader.read_one_action(event)
            if action is None or not action.player_identifier:
                continue
            counter = counters.setdefault(
                action.player_identifier,
                self._player_metric_calculator.empty_counter(),
            )
            self._player_metric_calculator.add_one_action(
                counter,
                action,
                roles.get(action.player_identifier)
                == PlayerMatchMetricFeature.GOALKEEPER_ROLE,
            )
        return counters

    def _read_line_up(
        self, events: list[dict[str, Any]]
    ) -> tuple[dict[str, PlayerAppearance], dict[str, str]]:
        """Read who played and in which position, out of the events.

        Returns:
            One appearance per player who was on the pitch, and the role of
            each of them. A substitute gets the minutes from when they came
            on, the player they replaced the minutes up to that moment.
        """
        last_minute = self._last_minute_of(events)
        appearances: dict[str, PlayerAppearance] = {}
        roles: dict[str, str] = {}
        for event in events:
            self._add_the_starters(event, last_minute, appearances, roles)
        for event in events:
            self._apply_one_substitution(event, last_minute, appearances, roles)
        return {
            identifier: appearance
            for identifier, appearance in appearances.items()
            if appearance.minutes_played > 0
        }, roles

    def _last_minute_of(self, events: list[dict[str, Any]]) -> int:
        """Read the minute the match ended in, extra time included."""
        return max(
            (
                event.get(StatsBombOpenDataSource.MINUTE_FIELD, 0) or 0
                for event in events
            ),
            default=PlayerMatchMetricFeature.FULL_MATCH_MINUTES,
        )

    def _add_the_starters(
        self,
        event: dict[str, Any],
        last_minute: int,
        appearances: dict[str, PlayerAppearance],
        roles: dict[str, str],
    ) -> None:
        """Put the eleven players of one starting line up on the pitch."""
        if (
            event.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            != PlayerMatchMetricFeature.STARTING_LINE_UP_EVENT_NAME
        ):
            return
        team_name = event.get(StatsBombOpenDataSource.TEAM_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        for entry in event.get(PlayerMatchMetricFeature.TACTICS_FIELD, {}).get(
            PlayerMatchMetricFeature.LINE_UP_FIELD, []
        ):
            player = entry.get(StatsBombOpenDataSource.PLAYER_FIELD, {})
            identifier = player.get(PlayerMatchMetricFeature.IDENTIFIER_FIELD)
            if identifier is None:
                continue
            roles[str(identifier)] = self.role_of_position(
                entry.get(PlayerMatchMetricFeature.POSITION_FIELD, {}).get(
                    StatsBombOpenDataSource.NAME_FIELD, ""
                )
            )
            appearances[str(identifier)] = PlayerAppearance(
                player_name=player.get(StatsBombOpenDataSource.NAME_FIELD, ""),
                team_identifier=team_name,
                minutes_played=last_minute,
            )

    def _apply_one_substitution(
        self,
        event: dict[str, Any],
        last_minute: int,
        appearances: dict[str, PlayerAppearance],
        roles: dict[str, str],
    ) -> None:
        """Take one player off and put their replacement on."""
        if (
            event.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            != SubstitutionFeature.SUBSTITUTION_EVENT_NAME
        ):
            return
        minute = event.get(StatsBombOpenDataSource.MINUTE_FIELD, 0) or 0
        player_out = str(
            event.get(StatsBombOpenDataSource.PLAYER_FIELD, {}).get(
                PlayerMatchMetricFeature.IDENTIFIER_FIELD, ""
            )
        )
        if player_out in appearances:
            appearances[player_out] = PlayerAppearance(
                player_name=appearances[player_out].player_name,
                team_identifier=appearances[player_out].team_identifier,
                minutes_played=minute,
            )
        replacement = event.get(SubstitutionFeature.SUBSTITUTION_FIELD, {}).get(
            SubstitutionFeature.REPLACEMENT_FIELD, {}
        )
        identifier = replacement.get(PlayerMatchMetricFeature.IDENTIFIER_FIELD)
        if identifier is None:
            return
        roles.setdefault(str(identifier), "")
        appearances[str(identifier)] = PlayerAppearance(
            player_name=replacement.get(StatsBombOpenDataSource.NAME_FIELD, ""),
            team_identifier=event.get(StatsBombOpenDataSource.TEAM_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            ),
            minutes_played=max(0, last_minute - minute),
        )

    def role_of_position(self, position_name: str) -> str:
        """Read the role out of a position name.

        Args:
            position_name: What StatsBomb calls the position, such as Right
                Center Back or Left Wing.

        Returns:
            The two letter role, or an empty one for a position none of the
            words fit.
        """
        for word, role in PlayerMatchMetricFeature.ROLE_OF_POSITION_WORD:
            if word in position_name:
                return role
        return ""


if __name__ == "__main__":
    StatsBombPlayerMetricBuilder(
        StatsBombOpenDataReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    StatsBombOpenDataSource.POLITE_DELAY_IN_SECONDS
                ),
            )
        ),
        PlayerMatchMetricCalculator(),
    ).build_every_competition()
