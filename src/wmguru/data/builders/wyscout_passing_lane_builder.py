"""The whole passing network of every match, out of the Wyscout actions.

Wyscout does not name the player who received a pass. The next action of the
same team is taken instead, which is the usual way to read it: whoever plays
the following action had the ball.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchStyleFeature,
    PassingLaneFeature,
)
from wmguru.helpers.data_class import (
    MatchAction,
    MatchIdentity,
    WyscoutMatchFacts,
    WyscoutNameLookups,
)
from wmguru.helpers.utils import (
    CsvFile,
    PassingLaneCounter,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutPassingLaneBuilder:
    """Every pass of every Wyscout match, and who most likely received it."""

    def __init__(
        self,
        wyscout_data_reader: WyscoutDataReader,
        passing_lane_counter: PassingLaneCounter,
    ) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._passing_lane_counter = passing_lane_counter
        self._output_file = SharedFeatureFile(
            CsvFile(PassingLaneFeature.OUTPUT_FILE, PassingLaneFeature.COLUMN_NAMES),
            EventSourceSetting.WYSCOUT_NAME,
            PassingLaneFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Walk the action file and write one row per pair of players.

        Returns:
            How many rows the file holds afterwards, the rows the StatsBomb
            half wrote included.
        """
        match_facts = self._wyscout_data_reader.read_match_facts()
        lookups = self._wyscout_data_reader.read_name_lookups()

        rows: list[dict[str, Any]] = []
        for (
            game_identifier,
            actions,
        ) in self._wyscout_data_reader.stream_actions_of_every_match(lookups):
            facts = match_facts.get(game_identifier)
            if facts is None:
                continue
            rows.extend(
                self._passing_lane_counter.build_rows(
                    self._count_lanes_of_one_match(actions),
                    self._identity_of(facts, lookups),
                    EventSourceSetting.WYSCOUT_NAME,
                )
            )
        total_count = self._output_file.write_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} passing lanes from Wyscout, {total_count} in all")
        return total_count

    def _count_lanes_of_one_match(
        self, actions: list[MatchAction]
    ) -> dict[tuple[str, str, str], dict[str, float]]:
        """Count every completed pass of one match, per pair of players."""
        lanes: dict[tuple[str, str, str], dict[str, float]] = {}
        for index in range(len(actions) - 1):
            action = actions[index]
            receiver = actions[index + 1]
            if not self._is_a_pass_that_arrived(action, receiver):
                continue
            self._passing_lane_counter.add_one_pass(
                lanes,
                action.team_name,
                action.player_name,
                receiver.player_name,
                action.start_x_in_metres,
                action.end_x_in_metres,
            )
        return lanes

    def _is_a_pass_that_arrived(
        self, action: MatchAction, next_action: MatchAction
    ) -> bool:
        """Return True when this action was a pass the next player took on.

        A pass counts only when the next action belongs to the same team and
        to somebody else, otherwise the ball never left the passer or it went
        to the other side.
        """
        return (
            action.kind in MatchStyleFeature.EVERY_PASS_KIND
            and action.was_successful
            and next_action.team_name == action.team_name
            and bool(next_action.player_name)
            and next_action.player_name != action.player_name
        )

    def _identity_of(
        self, facts: WyscoutMatchFacts, lookups: WyscoutNameLookups
    ) -> MatchIdentity:
        """Say which match a row belongs to."""
        return MatchIdentity(
            game_identifier=facts.game_identifier,
            competition_name=lookups.competition_names.get(
                facts.competition_identifier, ""
            ),
            season_name=facts.season_name,
            match_date=facts.match_date,
            home_team_name=lookups.team_names.get(
                facts.home_team_identifier, facts.home_team_identifier
            ),
            away_team_name=lookups.team_names.get(
                facts.away_team_identifier, facts.away_team_identifier
            ),
        )


if __name__ == "__main__":
    WyscoutPassingLaneBuilder(
        WyscoutDataReader(TextNormalizer()), PassingLaneCounter()
    ).build_every_match()
