"""The cards of every player and match, out of the StatsBomb open data.

Only a player who saw a card in a match gets a row. Where StatsBomb keeps a
card is the reader's business, this class only counts.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    PlayerCardFeature,
    StatsBombOpenDataSource,
    WebRequestSetting,
)
from wmguru.helpers.data_class import StatsBombCompetition
from wmguru.helpers.utils import (
    CsvFile,
    SharedFeatureFile,
    StatsBombOpenDataReader,
    WebFileDownloader,
)


class StatsBombPlayerCardBuilder:
    """The card events of every free men's competition."""

    def __init__(self, statsbomb_reader: StatsBombOpenDataReader) -> None:
        self._statsbomb_reader = statsbomb_reader
        self._output_file = SharedFeatureFile(
            CsvFile(PlayerCardFeature.OUTPUT_FILE, PlayerCardFeature.COLUMN_NAMES),
            EventSourceSetting.STATSBOMB_NAME,
            PlayerCardFeature.SORT_KEY_NAMES,
        )

    def build_every_competition(self) -> int:
        """Walk every open competition and write the file after each one.

        Returns:
            How many rows the file holds afterwards, the rows the Wyscout half
            wrote included.

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
        print(f"\nDone: the card file holds {total_count} rows.")
        return total_count

    def _build_rows_of_one_competition(
        self, competition: StatsBombCompetition
    ) -> list[dict[str, Any]]:
        """Build the card rows of every match of one season."""
        rows: list[dict[str, Any]] = []
        for match in self._statsbomb_reader.read_matches(competition):
            rows.extend(self._build_rows_of_one_match(match, competition))
        return rows

    def _build_rows_of_one_match(
        self, match: dict[str, Any], competition: StatsBombCompetition
    ) -> list[dict[str, Any]]:
        """Build one row per player who saw a card in one match."""
        counters = self._count_cards_of_one_match(match)
        home_team = match[StatsBombOpenDataSource.HOME_TEAM_FIELD][
            StatsBombOpenDataSource.HOME_TEAM_NAME_FIELD
        ]
        away_team = match[StatsBombOpenDataSource.AWAY_TEAM_FIELD][
            StatsBombOpenDataSource.AWAY_TEAM_NAME_FIELD
        ]
        match_date = self._statsbomb_reader.read_the_day_a_match_was_played(match)

        rows: list[dict[str, Any]] = []
        for player_name, counter in counters.items():
            team_name = counter["team"]
            rows.append(
                {
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                    "date": match_date,
                    "competition": competition.competition_name,
                    "season": competition.season_name,
                    "team": team_name,
                    "opponent": away_team if team_name == home_team else home_team,
                    "player": player_name,
                    EventSourceSetting.YELLOW_NAME: counter[
                        EventSourceSetting.YELLOW_NAME
                    ],
                    EventSourceSetting.RED_NAME: counter[EventSourceSetting.RED_NAME],
                    EventSourceSetting.SECOND_YELLOW_NAME: counter[
                        EventSourceSetting.SECOND_YELLOW_NAME
                    ],
                }
            )
        return rows

    def _count_cards_of_one_match(
        self, match: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Count the cards per player over the events of one match."""
        counters: dict[str, dict[str, Any]] = {}
        for event in self._statsbomb_reader.read_events(match):
            card_name = self._statsbomb_reader.read_card_name_of(event)
            player_name = event.get(StatsBombOpenDataSource.PLAYER_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            if card_name is None or not player_name:
                continue
            counter = counters.setdefault(
                player_name,
                {
                    "team": event.get(StatsBombOpenDataSource.TEAM_FIELD, {}).get(
                        StatsBombOpenDataSource.NAME_FIELD
                    ),
                    EventSourceSetting.YELLOW_NAME: 0,
                    EventSourceSetting.RED_NAME: 0,
                    EventSourceSetting.SECOND_YELLOW_NAME: 0,
                },
            )
            counter[card_name] += 1
        return counters


if __name__ == "__main__":
    StatsBombPlayerCardBuilder(
        StatsBombOpenDataReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    StatsBombOpenDataSource.POLITE_DELAY_IN_SECONDS
                ),
            )
        )
    ).build_every_competition()
