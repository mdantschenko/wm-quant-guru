"""The style row of every team and match, out of the Wyscout actions.

The actions come from the prepared table rather than from the raw file, so
this reads a shape it can group over straight away. Wyscout carries no
expected goals, so those columns stay empty here.
"""

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchStyleFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    MatchStyleCalculator,
    PreparedWyscoutTables,
    SharedFeatureFile,
)


class WyscoutMatchStyleBuilder:
    """The Wyscout actions of every match, as two style rows."""

    def __init__(
        self,
        prepared_tables: PreparedWyscoutTables,
        match_style_calculator: MatchStyleCalculator,
    ) -> None:
        self._prepared_tables = prepared_tables
        self._match_style_calculator = match_style_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(MatchStyleFeature.OUTPUT_FILE, MatchStyleFeature.COLUMN_NAMES),
            EventSourceSetting.WYSCOUT_NAME,
            MatchStyleFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Read the prepared actions and write one row per team and match.

        Returns:
            How many rows the file holds afterwards, the rows the StatsBomb
            half wrote included.

        Raises:
            SystemExit: When the actions have not been prepared yet.
        """
        rows = self._match_style_calculator.summarise_every_match(
            self._prepared_tables.read_the_actions(),
            self._prepared_tables.read_the_match_identities(),
            EventSourceSetting.WYSCOUT_NAME,
            has_expected_goals=False,
        )
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} team rows from Wyscout, {total_count} in all")
        return total_count


if __name__ == "__main__":
    WyscoutMatchStyleBuilder(
        PreparedWyscoutTables(), MatchStyleCalculator()
    ).build_every_match()
