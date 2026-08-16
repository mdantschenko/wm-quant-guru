"""The style row of every team and match, out of the StatsBomb data.

The reader turns the events into the same actions the Wyscout half produces
and the calculator does the rest. StatsBomb carries expected goals, which is
the one thing Wyscout cannot give.

The file is written after every competition, so a stopped run picks up where it
left off.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchStyleFeature,
    StatsBombOpenDataSource,
    WebRequestSetting,
)
from wmguru.helpers.data_class import MatchIdentity, StatsBombCompetition
from wmguru.helpers.utils import (
    CsvFile,
    MatchStyleCalculator,
    SharedFeatureFile,
    StatsBombOpenDataReader,
    WebFileDownloader,
)


class StatsBombMatchStyleBuilder:
    """The StatsBomb events of every free men's competition, as style rows."""

    def __init__(
        self,
        statsbomb_reader: StatsBombOpenDataReader,
        match_style_calculator: MatchStyleCalculator,
    ) -> None:
        self._statsbomb_reader = statsbomb_reader
        self._match_style_calculator = match_style_calculator
        self._output_file = SharedFeatureFile(
            CsvFile(MatchStyleFeature.OUTPUT_FILE, MatchStyleFeature.COLUMN_NAMES),
            EventSourceSetting.STATSBOMB_NAME,
            MatchStyleFeature.SORT_KEY_NAMES,
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
            self._match_style_calculator.fill_expected_goals_against(own_rows)
            total_count = self._output_file.write_keeping_the_other_source(own_rows)
            print(
                f"  SAVED  {competition.competition_name} "
                f"{competition.season_name} (file now {total_count})",
                flush=True,
            )
        print(f"\nDone: the style file holds {total_count} rows.")
        return total_count

    def _build_rows_of_one_competition(
        self, competition: StatsBombCompetition
    ) -> list[dict[str, Any]]:
        """Build the style rows of every match of one season."""
        rows: list[dict[str, Any]] = []
        for match in self._statsbomb_reader.read_matches(competition):
            actions = [
                action
                for action in (
                    self._statsbomb_reader.read_one_action(event)
                    for event in self._statsbomb_reader.read_events(match)
                )
                if action is not None
            ]
            rows.extend(
                self._match_style_calculator.calculate_rows_of_one_match(
                    actions,
                    self._identity_of(match, competition),
                    EventSourceSetting.STATSBOMB_NAME,
                    has_expected_goals=True,
                )
            )
        return rows

    def _identity_of(
        self, match: dict[str, Any], competition: StatsBombCompetition
    ) -> MatchIdentity:
        """Say which match a row belongs to."""
        return MatchIdentity(
            game_identifier=str(match[StatsBombOpenDataSource.MATCH_IDENTIFIER_FIELD]),
            competition_name=competition.competition_name,
            season_name=competition.season_name,
            match_date=self._statsbomb_reader.date_of(match),
            home_team_name=match[StatsBombOpenDataSource.HOME_TEAM_FIELD][
                StatsBombOpenDataSource.HOME_TEAM_NAME_FIELD
            ],
            away_team_name=match[StatsBombOpenDataSource.AWAY_TEAM_FIELD][
                StatsBombOpenDataSource.AWAY_TEAM_NAME_FIELD
            ],
        )


if __name__ == "__main__":
    StatsBombMatchStyleBuilder(
        StatsBombOpenDataReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    StatsBombOpenDataSource.POLITE_DELAY_IN_SECONDS
                ),
            )
        ),
        MatchStyleCalculator(),
    ).build_every_competition()
