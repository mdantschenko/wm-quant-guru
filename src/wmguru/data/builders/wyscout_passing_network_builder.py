"""The passing network of every Wyscout team and match, summarised.

Only a pass out of open play counts. Wyscout names no receiver, so the next
action of the same team is taken as the player who got the ball.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchStyleFeature,
    PassingNetworkFeature,
)
from wmguru.helpers.data_class import (
    MatchAction,
    TeamPass,
    WyscoutMatchFacts,
    WyscoutNameLookups,
)
from wmguru.helpers.utils import (
    CsvFile,
    PassingNetworkCalculator,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutPassingNetworkBuilder:
    """The open play passes of every Wyscout match, as two rows."""

    def __init__(
        self,
        wyscout_data_reader: WyscoutDataReader,
        passing_network_calculator: PassingNetworkCalculator,
    ) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._passing_network_calculator = passing_network_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(
                PassingNetworkFeature.OUTPUT_FILE,
                PassingNetworkFeature.COLUMN_NAMES,
            ),
            EventSourceSetting.WYSCOUT_NAME,
            PassingNetworkFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Walk the action file and write one row per team and match.

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
            rows.extend(self._build_rows_of_one_match(actions, facts, lookups))
        total_count = self._output_file.write_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} team rows from Wyscout, {total_count} in all")
        return total_count

    def _build_rows_of_one_match(
        self,
        actions: list[MatchAction],
        facts: WyscoutMatchFacts,
        lookups: WyscoutNameLookups,
    ) -> list[dict[str, Any]]:
        """Build the row of each team that played a pass in one match."""
        passes_of_team = self._read_passes_per_team(actions)
        home_team = lookups.team_names.get(
            facts.home_team_identifier, facts.home_team_identifier
        )
        away_team = lookups.team_names.get(
            facts.away_team_identifier, facts.away_team_identifier
        )

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
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
                    "game_id": facts.game_identifier,
                    "competition": lookups.competition_names.get(
                        facts.competition_identifier, facts.competition_identifier
                    ),
                    "season": facts.season_name,
                    "date": facts.match_date,
                    "team": team_name,
                    "opponent": opponent_name,
                    "is_home": int(team_name == home_team),
                    **self._passing_network_calculator.summarise(passes),
                }
            )
        return rows

    def _read_passes_per_team(
        self, actions: list[MatchAction]
    ) -> dict[str, list[TeamPass]]:
        """Collect the open play passes of one match, per team."""
        passes_of_team: dict[str, list[TeamPass]] = {}
        for index, action in enumerate(actions):
            if action.kind != MatchStyleFeature.OPEN_PASS_KIND:
                continue
            passes_of_team.setdefault(action.team_name, []).append(
                TeamPass(
                    passer_name=action.player_name,
                    receiver_name=self._receiver_name_of(actions, index),
                    start_x_in_metres=action.start_x_in_metres,
                    start_y_in_metres=action.start_y_in_metres,
                    end_x_in_metres=action.end_x_in_metres,
                    end_y_in_metres=action.end_y_in_metres,
                    was_successful=action.was_successful,
                )
            )
        return passes_of_team

    def _receiver_name_of(self, actions: list[MatchAction], index: int) -> str:
        """Read who played the next action, if the same team kept the ball.

        Returns:
            The name of the player who most likely received the pass, or an
            empty name when the ball went to the other side or the pass was
            the last action of the match.
        """
        action = actions[index]
        if not action.was_successful or index + 1 >= len(actions):
            return ""
        next_action = actions[index + 1]
        if next_action.team_name != action.team_name:
            return ""
        return next_action.player_name


if __name__ == "__main__":
    WyscoutPassingNetworkBuilder(
        WyscoutDataReader(TextNormalizer()), PassingNetworkCalculator()
    ).build_every_match()
