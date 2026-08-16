"""The substitution rows, out of the StatsBomb open data.

StatsBomb writes a substitution as an event that names the player who went
off, the replacement and the minute. The events are streamed and never kept on
disk, and the file is written after every competition, so a stopped run picks
up where it left off.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    StatsBombOpenDataSource,
    SubstitutionFeature,
    WebRequestSetting,
)
from wmguru.helpers.data_class import StatsBombCompetition
from wmguru.helpers.utils import (
    CsvFile,
    SharedFeatureFile,
    StatsBombOpenDataReader,
    WebFileDownloader,
)


class StatsBombSubstitutionBuilder:
    """The substitution events of every free men's competition."""

    def __init__(self, statsbomb_reader: StatsBombOpenDataReader) -> None:
        self._statsbomb_reader = statsbomb_reader
        self._output_file = SharedFeatureFile(
            CsvFile(SubstitutionFeature.OUTPUT_FILE, SubstitutionFeature.COLUMN_NAMES),
            EventSourceSetting.STATSBOMB_NAME,
            SubstitutionFeature.SORT_KEY_NAMES,
        )

    def build_every_competition(self) -> int:
        """Walk every open competition and write the file after each one.

        Returns:
            How many rows the file holds afterwards, the rows the Wyscout
            half wrote included.

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
        print(f"\nDone: the substitution file holds {total_count} rows.")
        return total_count

    def _build_rows_of_one_competition(
        self, competition: StatsBombCompetition
    ) -> list[dict[str, Any]]:
        """Build the substitution rows of every match of one season."""
        rows: list[dict[str, Any]] = []
        for match in self._statsbomb_reader.read_matches(competition):
            rows.extend(self._build_rows_of_one_match(match, competition))
        return rows

    def _build_rows_of_one_match(
        self, match: dict[str, Any], competition: StatsBombCompetition
    ) -> list[dict[str, Any]]:
        """Build one row per substitution event of one match."""
        home_team = match[StatsBombOpenDataSource.HOME_TEAM_FIELD][
            StatsBombOpenDataSource.HOME_TEAM_NAME_FIELD
        ]
        away_team = match[StatsBombOpenDataSource.AWAY_TEAM_FIELD][
            StatsBombOpenDataSource.AWAY_TEAM_NAME_FIELD
        ]
        match_date = self._statsbomb_reader.read_the_day_a_match_was_played(match)

        rows: list[dict[str, Any]] = []
        for event in self._statsbomb_reader.read_events(match):
            if (
                event.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
                    StatsBombOpenDataSource.NAME_FIELD
                )
                != SubstitutionFeature.SUBSTITUTION_EVENT_NAME
            ):
                continue
            team_name = event.get(StatsBombOpenDataSource.TEAM_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            rows.append(
                {
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                    "date": match_date,
                    "competition": competition.competition_name,
                    "season": competition.season_name,
                    "game_id": match[StatsBombOpenDataSource.MATCH_IDENTIFIER_FIELD],
                    "team": team_name,
                    "opponent": away_team if team_name == home_team else home_team,
                    "player_out": event.get(
                        StatsBombOpenDataSource.PLAYER_FIELD, {}
                    ).get(StatsBombOpenDataSource.NAME_FIELD),
                    "player_in": event.get(SubstitutionFeature.SUBSTITUTION_FIELD, {})
                    .get(SubstitutionFeature.REPLACEMENT_FIELD, {})
                    .get(StatsBombOpenDataSource.NAME_FIELD),
                    "minute": event.get(SubstitutionFeature.MINUTE_FIELD, ""),
                }
            )
        return rows


if __name__ == "__main__":
    StatsBombSubstitutionBuilder(
        StatsBombOpenDataReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    StatsBombOpenDataSource.POLITE_DELAY_IN_SECONDS
                ),
            )
        )
    ).build_every_competition()
