"""The substitution rows, out of the Wyscout match files.

The Wyscout match files carry, per team, the substitutions as a list with the
player who came on, the player who went off and the minute.
"""

import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    SubstitutionFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutSubstitutionBuilder:
    """The substitution lists of every Wyscout match file."""

    def __init__(self, wyscout_data_reader: WyscoutDataReader) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._output_file = SharedFeatureFile(
            CsvFile(SubstitutionFeature.OUTPUT_FILE, SubstitutionFeature.COLUMN_NAMES),
            EventSourceSetting.WYSCOUT_NAME,
            SubstitutionFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Read every match file and write the substitutions.

        Returns:
            How many rows the file holds afterwards, the rows the StatsBomb
            half wrote included.
        """
        rows = self._build_the_rows_of_every_substitution()
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} substitutions from Wyscout, {total_count} in all")
        return total_count

    def _build_the_rows_of_every_substitution(self) -> pd.DataFrame:
        """Name the teams, the players and the competition of every substitution."""
        substitutions = self._wyscout_data_reader.read_every_substitution()
        team_names = self._wyscout_data_reader.read_team_names()
        competition_names = self._wyscout_data_reader.read_competition_names()
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
                "date": substitutions["match_date"],
                "competition": self._wyscout_data_reader.name_every_identifier(
                    substitutions["competition_identifier"], competition_names
                ),
                "season": substitutions["season_name"],
                "game_id": substitutions["game_identifier"],
                "team": self._wyscout_data_reader.name_every_identifier(
                    substitutions["team_identifier"], team_names
                ),
                "opponent": self._wyscout_data_reader.name_every_identifier(
                    substitutions["opponent_identifier"], team_names
                ),
                "player_out": self._wyscout_data_reader.name_every_substituted_player(
                    substitutions["player_out"]
                ),
                "player_in": self._wyscout_data_reader.name_every_substituted_player(
                    substitutions["player_in"]
                ),
                "minute": substitutions["minute"],
            }
        )


if __name__ == "__main__":
    WyscoutSubstitutionBuilder(WyscoutDataReader(TextNormalizer())).build_every_match()
