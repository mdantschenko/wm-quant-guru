"""The whole passing network of every match, out of the StatsBomb data.

StatsBomb names the player who received a pass, so nothing has to be guessed
here. Every completed pass counts, out of open play and off a set piece, or
the network would have holes in it.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchStyleFeature,
    PassingLaneFeature,
    PitchGeometry,
    StatsBombOpenDataSource,
    WebRequestSetting,
)
from wmguru.helpers.data_class import MatchIdentity, StatsBombCompetition
from wmguru.helpers.utils import (
    CsvFile,
    PassingLaneCounter,
    SharedFeatureFile,
    StatsBombOpenDataReader,
    WebFileDownloader,
)


class StatsBombPassingLaneBuilder:
    """The passes of every free men's competition, and who received them."""

    def __init__(
        self,
        statsbomb_reader: StatsBombOpenDataReader,
        passing_lane_counter: PassingLaneCounter,
    ) -> None:
        self._statsbomb_reader = statsbomb_reader
        self._passing_lane_counter = passing_lane_counter
        self._output_file = SharedFeatureFile(
            CsvFile(PassingLaneFeature.OUTPUT_FILE, PassingLaneFeature.COLUMN_NAMES),
            EventSourceSetting.STATSBOMB_NAME,
            PassingLaneFeature.SORT_KEY_NAMES,
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
        print(f"\nDone: the passing lane file holds {total_count} rows.")
        return total_count

    def _build_rows_of_one_competition(
        self, competition: StatsBombCompetition
    ) -> list[dict[str, Any]]:
        """Build the passing lanes of every match of one season."""
        rows: list[dict[str, Any]] = []
        for match in self._statsbomb_reader.read_matches(competition):
            lanes: dict[tuple[str, str, str], dict[str, float]] = {}
            for event in self._statsbomb_reader.read_events(match):
                self._add_one_event(lanes, event)
            rows.extend(
                self._passing_lane_counter.build_the_rows_of_every_lane(
                    lanes,
                    self._which_match_this_row_belongs_to(match, competition),
                    EventSourceSetting.STATSBOMB_NAME,
                )
            )
        return rows

    def _add_one_event(
        self,
        lanes: dict[tuple[str, str, str], dict[str, float]],
        event: dict[str, Any],
    ) -> None:
        """Add one event, if it is a pass that reached somebody else."""
        if (
            event.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            != MatchStyleFeature.PASS_EVENT_NAME
        ):
            return
        pass_details = event.get(StatsBombOpenDataSource.PASS_FIELD, {})
        if StatsBombOpenDataSource.OUTCOME_FIELD in pass_details:
            return
        receiver_name = pass_details.get(
            StatsBombOpenDataSource.RECIPIENT_FIELD, {}
        ).get(StatsBombOpenDataSource.NAME_FIELD)
        passer_name = event.get(StatsBombOpenDataSource.PLAYER_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        team_name = event.get(StatsBombOpenDataSource.TEAM_FIELD, {}).get(
            StatsBombOpenDataSource.NAME_FIELD
        )
        start_location = event.get(StatsBombOpenDataSource.LOCATION_FIELD)
        end_location = pass_details.get(StatsBombOpenDataSource.END_LOCATION_FIELD)
        if not (
            receiver_name
            and passer_name
            and team_name
            and start_location
            and end_location
        ):
            return
        if receiver_name == passer_name:
            return
        self._passing_lane_counter.add_one_pass(
            lanes,
            team_name,
            passer_name,
            receiver_name,
            self._length_on_our_pitch_in_metres(start_location[0]),
            self._length_on_our_pitch_in_metres(end_location[0]),
        )

    def _length_on_our_pitch_in_metres(self, distance_along_the_pitch: float) -> float:
        """Convert a length off the StatsBomb pitch onto the one used everywhere."""
        return (
            distance_along_the_pitch
            / StatsBombOpenDataSource.PITCH_LENGTH
            * PitchGeometry.LENGTH_IN_METRES
        )

    def _which_match_this_row_belongs_to(
        self, match: dict[str, Any], competition: StatsBombCompetition
    ) -> MatchIdentity:
        """Say which match a row belongs to."""
        return MatchIdentity(
            game_identifier=str(match[StatsBombOpenDataSource.MATCH_IDENTIFIER_FIELD]),
            competition_name=competition.competition_name,
            season_name=competition.season_name,
            match_date=self._statsbomb_reader.read_the_day_a_match_was_played(match),
            home_team_name=match[StatsBombOpenDataSource.HOME_TEAM_FIELD][
                StatsBombOpenDataSource.HOME_TEAM_NAME_FIELD
            ],
            away_team_name=match[StatsBombOpenDataSource.AWAY_TEAM_FIELD][
                StatsBombOpenDataSource.AWAY_TEAM_NAME_FIELD
            ],
        )


if __name__ == "__main__":
    StatsBombPassingLaneBuilder(
        StatsBombOpenDataReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    StatsBombOpenDataSource.POLITE_DELAY_IN_SECONDS
                ),
            )
        ),
        PassingLaneCounter(),
    ).build_every_competition()
