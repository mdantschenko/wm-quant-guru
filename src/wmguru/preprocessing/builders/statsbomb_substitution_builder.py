"""The substitution rows, out of the StatsBomb open data.

StatsBomb writes a substitution as an event that names the player who went
off, the replacement and the minute, so the prepared event table already holds
everything a row needs.
"""

import pandas as pd

from wmguru.helpers.constant import (
    EventSourceSetting,
    SubstitutionFeature,
)
from wmguru.helpers.utils import (
    CsvFile,
    PreparedStatsBombTables,
    SharedFeatureFile,
)


class StatsBombSubstitutionBuilder:
    """The substitution events of every free men's competition."""

    def __init__(self, prepared_tables: PreparedStatsBombTables) -> None:
        self._prepared_tables = prepared_tables
        self._output_file = SharedFeatureFile(
            CsvFile(SubstitutionFeature.OUTPUT_FILE, SubstitutionFeature.COLUMN_NAMES),
            EventSourceSetting.STATSBOMB_NAME,
            SubstitutionFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Keep the substitution events and write one row each.

        Returns:
            How many rows the file holds afterwards, the rows the Wyscout
            half wrote included.

        Raises:
            SystemExit: When the events have not been prepared yet.
        """
        rows = self._build_the_rows_of_every_substitution()
        total_count = self._output_file.write_the_table_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} substitutions from StatsBomb, {total_count} in all")
        return total_count

    def _build_the_rows_of_every_substitution(self) -> pd.DataFrame:
        """Put the match around every substitution event."""
        events = self._prepared_tables.read_the_events()
        substitutions = events[
            events["event_name"] == SubstitutionFeature.SUBSTITUTION_EVENT_NAME
        ]
        of_named_matches = substitutions.merge(
            self._prepared_tables.read_the_match_identities(), on="game_identifier"
        )
        plays_at_home = (
            of_named_matches["team_name"] == of_named_matches["home_team_name"]
        )
        return pd.DataFrame(
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                "date": of_named_matches["match_date"],
                "competition": of_named_matches["competition_name"],
                "season": of_named_matches["season_name"],
                "game_id": of_named_matches["game_identifier"],
                "team": of_named_matches["team_name"],
                "opponent": of_named_matches["away_team_name"].where(
                    plays_at_home, of_named_matches["home_team_name"]
                ),
                "player_out": of_named_matches["player_name"],
                "player_in": of_named_matches["replacement_player_name"],
                "minute": of_named_matches["minute_in_match"],
            }
        )


if __name__ == "__main__":
    StatsBombSubstitutionBuilder(PreparedStatsBombTables()).build_every_match()
