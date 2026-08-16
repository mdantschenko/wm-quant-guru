"""The substitution rows, out of the Wyscout match files.

The Wyscout match files carry, per team, the substitutions as a list with the
player who came on, the player who went off and the minute.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    StatsBombOpenDataSource,
    SubstitutionFeature,
    WyscoutEventFile,
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
        team_names = self._wyscout_data_reader.read_team_names()
        player_names = self._wyscout_data_reader.read_player_names()
        competition_names = self._wyscout_data_reader.read_competition_names()

        rows: list[dict[str, Any]] = []
        for match_file in sorted(
            WyscoutEventFile.SOURCE_FOLDER.glob(WyscoutEventFile.MATCH_FILE_PATTERN)
        ):
            for match in CsvFile(match_file).read_rows():
                rows.extend(
                    self._build_rows_of_one_match(
                        match, team_names, player_names, competition_names
                    )
                )
        total_count = self._output_file.write_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} substitutions from Wyscout, {total_count} in all")
        return total_count

    def _build_rows_of_one_match(
        self,
        match: dict[str, str],
        team_names: dict[str, str],
        player_names: dict[str, str],
        competition_names: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Build the substitution rows of both teams of one match."""
        rows: list[dict[str, Any]] = []
        for team_column, list_column, opponent_column in SubstitutionFeature.TEAM_SIDES:
            team_identifier = self._wyscout_data_reader.as_identifier(
                match.get(team_column, "")
            )
            opponent_identifier = self._wyscout_data_reader.as_identifier(
                match.get(opponent_column, "")
            )
            for substitution in self._wyscout_data_reader.read_list_out_of_one_cell(
                match.get(list_column, "")
            ):
                rows.append(
                    self._build_row(
                        match,
                        substitution,
                        team_names.get(team_identifier, team_identifier),
                        team_names.get(opponent_identifier, opponent_identifier),
                        player_names,
                        competition_names,
                    )
                )
        return rows

    def _build_row(
        self,
        match: dict[str, str],
        substitution: dict[str, Any],
        team_name: str,
        opponent_name: str,
        player_names: dict[str, str],
        competition_names: dict[str, str],
    ) -> dict[str, Any]:
        """Build one output row for one substitution."""
        competition_identifier = self._wyscout_data_reader.as_identifier(
            match.get(WyscoutEventFile.COMPETITION_IDENTIFIER_COLUMN, "")
        )
        return {
            EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
            "date": match.get(WyscoutEventFile.MATCH_DATE_COLUMN, "")[
                : StatsBombOpenDataSource.DATE_LENGTH
            ],
            "competition": competition_names.get(
                competition_identifier, competition_identifier
            ),
            "season": match.get(WyscoutEventFile.SEASON_IDENTIFIER_COLUMN, ""),
            "game_id": self._wyscout_data_reader.as_identifier(
                match.get(WyscoutEventFile.IDENTIFIER_COLUMN, "")
            ),
            "team": team_name,
            "opponent": opponent_name,
            "player_out": self._player_name_of(
                substitution.get(SubstitutionFeature.PLAYER_OUT_FIELD), player_names
            ),
            "player_in": self._player_name_of(
                substitution.get(SubstitutionFeature.PLAYER_IN_FIELD), player_names
            ),
            "minute": substitution.get(SubstitutionFeature.MINUTE_FIELD, ""),
        }

    def _player_name_of(self, raw_identifier: Any, player_names: dict[str, str]) -> Any:
        """Read the name of a player, or keep the identifier when it is unknown."""
        identifier = self._wyscout_data_reader.as_identifier(str(raw_identifier))
        return player_names.get(identifier, raw_identifier)


if __name__ == "__main__":
    WyscoutSubstitutionBuilder(WyscoutDataReader(TextNormalizer())).build_every_match()
