"""The passing network of every StatsBomb team and match, summarised.

Only a pass out of open play counts, no cross and no set piece, so the number
means the same thing as it does on the Wyscout side. StatsBomb names the
player who received the pass itself.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchStyleFeature,
    PassingNetworkFeature,
    PitchGeometry,
    StatsBombOpenDataSource,
    WebRequestSetting,
)
from wmguru.helpers.data_class import StatsBombCompetition, TeamPass
from wmguru.helpers.utils import (
    CsvFile,
    PassingNetworkCalculator,
    SharedFeatureFile,
    StatsBombOpenDataReader,
    WebFileDownloader,
)


class StatsBombPassingNetworkBuilder:
    """The open play passes of every free men's competition."""

    def __init__(
        self,
        statsbomb_reader: StatsBombOpenDataReader,
        passing_network_calculator: PassingNetworkCalculator,
    ) -> None:
        self._statsbomb_reader = statsbomb_reader
        self._passing_network_calculator = passing_network_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(
                PassingNetworkFeature.OUTPUT_FILE,
                PassingNetworkFeature.COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            PassingNetworkFeature.SORT_KEY_NAMES,
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
            own_rows.extend(self._build_rows_of_one_competition(competition))
            total_count = self._output_file.write_keeping_the_other_source(own_rows)
            print(
                f"  SAVED  {competition.competition_name} "
                f"{competition.season_name} (file now {total_count})",
                flush=True,
            )
        print(f"\nDone: the passing network file holds {total_count} rows.")
        return total_count

    def _build_rows_of_one_competition(
        self, competition: StatsBombCompetition
    ) -> list[dict[str, Any]]:
        """Build the network rows of every match of one season."""
        rows: list[dict[str, Any]] = []
        for match in self._statsbomb_reader.read_matches(competition):
            rows.extend(self._build_rows_of_one_match(match, competition))
        return rows

    def _build_rows_of_one_match(
        self, match: dict[str, Any], competition: StatsBombCompetition
    ) -> list[dict[str, Any]]:
        """Build the row of each team that played a pass in one match."""
        passes_of_team = self._read_passes_per_team(match)
        home_team = match[StatsBombOpenDataSource.HOME_TEAM_FIELD][
            StatsBombOpenDataSource.HOME_TEAM_NAME_FIELD
        ]
        away_team = match[StatsBombOpenDataSource.AWAY_TEAM_FIELD][
            StatsBombOpenDataSource.AWAY_TEAM_NAME_FIELD
        ]

        rows: list[dict[str, Any]] = []
        for team_name, opponent_name in (
            (home_team, away_team),
            (away_team, home_team),
        ):
            passes = passes_of_team.get(team_name)
            if not passes:
                continue
            rows.append(
                {
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                    "game_id": match[StatsBombOpenDataSource.MATCH_IDENTIFIER_FIELD],
                    "competition": competition.competition_name,
                    "season": competition.season_name,
                    "date": self._statsbomb_reader.read_the_day_a_match_was_played(
                        match
                    ),
                    "team": team_name,
                    "opponent": opponent_name,
                    "is_home": int(team_name == home_team),
                    **self._passing_network_calculator.summarise(passes),
                }
            )
        return rows

    def _read_passes_per_team(self, match: dict[str, Any]) -> dict[str, list[TeamPass]]:
        """Collect the open play passes of one match, per team."""
        passes_of_team: dict[str, list[TeamPass]] = {}
        for event in self._statsbomb_reader.read_events(match):
            team_name, one_pass = self._read_one_pass(event)
            if one_pass is not None:
                passes_of_team.setdefault(team_name, []).append(one_pass)
        return passes_of_team

    def _read_one_pass(self, event: dict[str, Any]) -> tuple[str, TeamPass | None]:
        """Read one event as an open play pass, if that is what it is.

        Returns:
            The team and the pass, or the team and None for anything that is
            no open play pass, and for a pass the source placed nowhere.
        """
        if (
            event.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            != MatchStyleFeature.PASS_EVENT_NAME
        ):
            return "", None
        pass_details = event.get(StatsBombOpenDataSource.PASS_FIELD, {})
        pass_type = pass_details.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        if pass_type in MatchStyleFeature.SET_PIECE_PASS_NAMES:
            return "", None
        if pass_details.get(StatsBombOpenDataSource.CROSS_FIELD):
            return "", None

        start_location = event.get(StatsBombOpenDataSource.LOCATION_FIELD)
        end_location = pass_details.get(StatsBombOpenDataSource.END_LOCATION_FIELD)
        passer_name = event.get(StatsBombOpenDataSource.PLAYER_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        team_name = event.get(StatsBombOpenDataSource.TEAM_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        if not (start_location and end_location and passer_name and team_name):
            return "", None

        was_successful = StatsBombOpenDataSource.OUTCOME_FIELD not in pass_details
        return team_name, TeamPass(
            passer_name=passer_name,
            receiver_name=self._receiver_name_of(pass_details, was_successful),
            start_x_in_metres=self._length_on_our_pitch(start_location[0]),
            start_y_in_metres=self._width_on_our_pitch(start_location[1]),
            end_x_in_metres=self._length_on_our_pitch(end_location[0]),
            end_y_in_metres=self._width_on_our_pitch(end_location[1]),
            was_successful=was_successful,
        )

    def _receiver_name_of(
        self, pass_details: dict[str, Any], was_successful: bool
    ) -> str:
        """Name who received the pass, or nobody when it never arrived."""
        if not was_successful:
            return ""
        return (
            pass_details.get(StatsBombOpenDataSource.RECIPIENT_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            or ""
        )

    def _length_on_our_pitch(self, distance: float) -> float:
        """Convert a length onto the pitch everything else is counted on."""
        return (
            distance
            / StatsBombOpenDataSource.PITCH_LENGTH
            * PitchGeometry.LENGTH_IN_METRES
        )

    def _width_on_our_pitch(self, distance: float) -> float:
        """Convert a width onto the pitch everything else is counted on."""
        return (
            distance
            / StatsBombOpenDataSource.PITCH_WIDTH
            * PitchGeometry.WIDTH_IN_METRES
        )


if __name__ == "__main__":
    StatsBombPassingNetworkBuilder(
        StatsBombOpenDataReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    StatsBombOpenDataSource.POLITE_DELAY_IN_SECONDS
                ),
            )
        ),
        PassingNetworkCalculator(),
    ).build_every_competition()
