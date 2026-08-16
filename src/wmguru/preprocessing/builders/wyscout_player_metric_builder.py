"""The metrics of every player and match, out of the Wyscout actions.

A row is built for everybody who was on the pitch, even for somebody who
touched the ball twice, because the minutes are in the row and any filter can
still be applied later.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    PlayerMatchMetricFeature,
)
from wmguru.helpers.data_class import (
    PlayerAppearance,
    WyscoutMatchFacts,
    WyscoutNameLookups,
)
from wmguru.helpers.utils import (
    CsvFile,
    PlayerMatchMetricCalculator,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutPlayerMetricBuilder:
    """What every Wyscout player did in every match they played."""

    def __init__(
        self,
        wyscout_data_reader: WyscoutDataReader,
        player_metric_calculator: PlayerMatchMetricCalculator,
    ) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._player_metric_calculator = player_metric_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(
                PlayerMatchMetricFeature.OUTPUT_FILE,
                PlayerMatchMetricFeature.COLUMN_NAMES,
            ),
            EventSourceSetting.WYSCOUT_NAME,
            PlayerMatchMetricFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Walk the action file and write one row per player and match.

        Returns:
            How many rows the file holds afterwards, the rows the StatsBomb
            half wrote included.
        """
        roles = self._wyscout_data_reader.read_player_roles()
        counters = self._count_over_every_match(roles)
        rows = self._build_the_rows_of_every_appearance(counters, roles)
        total_count = self._output_file.write_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} player rows from Wyscout, {total_count} in all")
        return total_count

    def _count_over_every_match(
        self, roles: dict[str, str]
    ) -> dict[tuple[str, str], dict[str, float]]:
        """Count the actions of every player, per match."""
        lookups = self._wyscout_data_reader.read_name_lookups()
        counters: dict[tuple[str, str], dict[str, float]] = {}
        for (
            game_identifier,
            actions,
        ) in self._wyscout_data_reader.stream_actions_of_every_match(lookups):
            for action in actions:
                if not action.player_identifier:
                    continue
                counter = counters.setdefault(
                    (action.player_identifier, game_identifier),
                    self._player_metric_calculator.start_a_counter_at_zero(),
                )
                self._player_metric_calculator.add_one_action(
                    counter,
                    action,
                    roles.get(action.player_identifier)
                    == PlayerMatchMetricFeature.GOALKEEPER_ROLE,
                )
        return counters

    def _build_the_rows_of_every_appearance(
        self,
        counters: dict[tuple[str, str], dict[str, float]],
        roles: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Build one row per appearance, whether the player touched the ball or not."""
        appearances = self._wyscout_data_reader.read_appearances()
        match_facts = self._wyscout_data_reader.read_match_facts()
        lookups = self._wyscout_data_reader.read_name_lookups()

        rows: list[dict[str, Any]] = []
        for (player_identifier, game_identifier), appearance in appearances.items():
            facts = match_facts.get(game_identifier)
            if facts is None:
                continue
            counter = counters.get(
                (player_identifier, game_identifier),
                self._player_metric_calculator.start_a_counter_at_zero(),
            )
            rows.append(
                self._build_the_row_of_one_player(
                    appearance,
                    facts,
                    lookups,
                    counter,
                    roles.get(player_identifier, ""),
                )
            )
        return rows

    def _build_the_row_of_one_player(
        self,
        appearance: PlayerAppearance,
        facts: WyscoutMatchFacts,
        lookups: WyscoutNameLookups,
        counter: dict[str, float],
        role: str,
    ) -> dict[str, Any]:
        """Build the row of one player in one match."""
        opponent_identifier = facts.opponent_of(appearance.team_identifier)
        return {
            EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
            "date": facts.match_date,
            "competition": lookups.competition_names.get(
                facts.competition_identifier, facts.competition_identifier
            ),
            "season": facts.season_name,
            "team": lookups.team_names.get(
                appearance.team_identifier, appearance.team_identifier
            ),
            "opponent": lookups.team_names.get(
                opponent_identifier, opponent_identifier
            ),
            "player": appearance.player_name,
            "role": role,
            "minutes": appearance.minutes_played,
            **self._player_metric_calculator.build_the_columns_of_one_player(
                counter, role == PlayerMatchMetricFeature.GOALKEEPER_ROLE
            ),
        }


if __name__ == "__main__":
    WyscoutPlayerMetricBuilder(
        WyscoutDataReader(TextNormalizer()), PlayerMatchMetricCalculator()
    ).build_every_match()
