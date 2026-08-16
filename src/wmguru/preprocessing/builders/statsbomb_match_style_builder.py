"""The style row of every team and match, out of the StatsBomb data.

The prepared actions are the same fifteen columns the Wyscout half has, so the
calculator does the rest. StatsBomb carries expected goals, which is the one
thing Wyscout cannot give.
"""

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchStyleFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    MatchStyleCalculator,
    PreparedStatsBombTables,
    SharedFeatureFile,
)


class StatsBombMatchStyleBuilder:
    """The StatsBomb actions of every free men's competition, as style rows."""

    def __init__(
        self,
        prepared_tables: PreparedStatsBombTables,
        match_style_calculator: MatchStyleCalculator,
    ) -> None:
        self._prepared_tables = prepared_tables
        self._match_style_calculator = match_style_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(MatchStyleFeature.OUTPUT_FILE, MatchStyleFeature.COLUMN_NAMES),
            EventSourceSetting.STATSBOMB_NAME,
            MatchStyleFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Group the prepared actions and write one row per team and match.

        Returns:
            How many rows the file holds afterwards, the rows the Wyscout half
            wrote included.

        Raises:
            SystemExit: When the actions have not been prepared yet.
        """
        rows = self._match_style_calculator.summarise_every_match(
            self._prepared_tables.read_the_actions(),
            self._prepared_tables.read_the_match_identities(),
            EventSourceSetting.STATSBOMB_NAME,
            has_expected_goals=True,
        )
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} team rows from StatsBomb, {total_count} in all")
        return total_count


if __name__ == "__main__":
    StatsBombMatchStyleBuilder(
        PreparedStatsBombTables(), MatchStyleCalculator()
    ).build_every_match()
