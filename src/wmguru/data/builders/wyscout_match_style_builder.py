"""The style row of every team and match, out of the Wyscout actions.

The reader hands the actions over one match at a time, the calculator turns
them into two rows. Wyscout carries no expected goals, so those columns stay
empty here.
"""

from typing import Any

from wmguru.helpers.constant import EventSourceSetting, MatchStyleFeature
from wmguru.helpers.data_class import (
    MatchAction,
    MatchIdentity,
    WyscoutMatchFacts,
    WyscoutNameLookups,
)
from wmguru.helpers.utils import (
    CsvFile,
    MatchStyleCalculator,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutMatchStyleBuilder:
    """The Wyscout actions of every match, as two style rows."""

    def __init__(
        self,
        wyscout_data_reader: WyscoutDataReader,
        match_style_calculator: MatchStyleCalculator,
    ) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._match_style_calculator = match_style_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(MatchStyleFeature.OUTPUT_FILE, MatchStyleFeature.COLUMN_NAMES),
            EventSourceSetting.WYSCOUT_NAME,
            MatchStyleFeature.SORT_KEY_NAMES,
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
            rows.extend(
                self._build_rows_of_one_match(
                    game_identifier, actions, match_facts, lookups
                )
            )
        self._match_style_calculator.fill_expected_goals_against(rows)
        total_count = self._output_file.write_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} team rows from Wyscout, {total_count} in all")
        return total_count

    def _build_rows_of_one_match(
        self,
        game_identifier: str,
        actions: list[MatchAction],
        match_facts: dict[str, WyscoutMatchFacts],
        lookups: WyscoutNameLookups,
    ) -> list[dict[str, Any]]:
        """Build the rows of one match, or none when it is not in the match file."""
        facts = match_facts.get(game_identifier)
        if facts is None:
            return []
        return self._match_style_calculator.calculate_rows_of_one_match(
            actions,
            self._identity_of(facts, lookups),
            EventSourceSetting.WYSCOUT_NAME,
            has_expected_goals=False,
        )

    def _identity_of(
        self, facts: WyscoutMatchFacts, lookups: WyscoutNameLookups
    ) -> MatchIdentity:
        """Say which match a row belongs to, with both teams named."""
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
    WyscoutMatchStyleBuilder(
        WyscoutDataReader(TextNormalizer()), MatchStyleCalculator()
    ).build_every_match()
