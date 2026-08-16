"""The fouls and cards per player and per match, out of the StatsBomb data.

Fouls come off the foul events, cards off the reader, which knows that one
shown without a foul sits somewhere else. The referee comes with the match.

The file is written after every competition, so a stopped run picks up where it
left off.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchDisciplineFeature,
    StatsBombOpenDataSource,
    WebRequestSetting,
)
from wmguru.helpers.data_class import StatsBombCompetition
from wmguru.helpers.utils import (
    CsvFile,
    MatchDisciplineCounter,
    SharedFeatureFile,
    StatsBombOpenDataReader,
    WebFileDownloader,
)


class StatsBombMatchDisciplineBuilder:
    """The fouls and cards of every free men's competition."""

    def __init__(
        self,
        statsbomb_reader: StatsBombOpenDataReader,
        discipline_counter: MatchDisciplineCounter,
    ) -> None:
        self._statsbomb_reader = statsbomb_reader
        self._discipline_counter = discipline_counter
        self._player_file = SharedFeatureFile(
            CsvFile(
                MatchDisciplineFeature.PLAYER_OUTPUT_FILE,
                MatchDisciplineFeature.PLAYER_COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            MatchDisciplineFeature.PLAYER_SORT_KEY_NAMES,
        )
        self._match_file = SharedFeatureFile(
            CsvFile(
                MatchDisciplineFeature.MATCH_OUTPUT_FILE,
                MatchDisciplineFeature.MATCH_COLUMN_NAMES,
            ),
            EventSourceSetting.STATSBOMB_NAME,
            MatchDisciplineFeature.MATCH_SORT_KEY_NAMES,
        )

    def build_every_competition(self) -> int:
        """Walk every open competition and write both files after each one.

        Returns:
            How many matches the match file holds afterwards, the matches the
            Wyscout half wrote included.

        Raises:
            SystemExit: When the competition list could not be loaded.
        """
        own_player_rows = self._player_file.read_own_rows()
        own_match_rows = self._match_file.read_own_rows()
        open_competitions = self._statsbomb_reader.read_open_competitions(
            self._match_file.read_finished_keys()
        )
        print(f"Open competitions {len(open_competitions)}", flush=True)

        match_total = len(own_match_rows) + len(
            self._match_file.read_rows_of_the_other_source()
        )
        for competition in open_competitions:
            for match in self._statsbomb_reader.read_matches(competition):
                player_rows, match_row = self._build_rows_of_one_match(
                    match, competition
                )
                own_player_rows.extend(player_rows)
                own_match_rows.append(match_row)
            self._player_file.write_keeping_the_other_source(own_player_rows)
            match_total = self._match_file.write_keeping_the_other_source(
                own_match_rows
            )
            print(
                f"  SAVED  {competition.competition_name} "
                f"{competition.season_name} (file now {match_total} matches)",
                flush=True,
            )
        print(f"\nDone: the match file holds {match_total} matches.")
        return match_total

    def _build_rows_of_one_match(
        self, match: dict[str, Any], competition: StatsBombCompetition
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Build the player rows and the one match row of one match.

        Returns:
            One row per player who fouled or was carded, and the row that
            sums both sides up.
        """
        counters = self._count_over_one_match(match)
        home_team = match[StatsBombOpenDataSource.HOME_TEAM_FIELD][
            StatsBombOpenDataSource.HOME_TEAM_NAME_FIELD
        ]
        away_team = match[StatsBombOpenDataSource.AWAY_TEAM_FIELD][
            StatsBombOpenDataSource.AWAY_TEAM_NAME_FIELD
        ]
        shared_columns = self._the_columns_both_files_share(match, competition)

        player_rows = [
            {
                EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
                "team": counter["team"],
                "opponent": away_team if counter["team"] == home_team else home_team,
                "player": player_name,
                **shared_columns,
                **{
                    name: counter[name] for name in MatchDisciplineFeature.COUNTED_NAMES
                },
            }
            for player_name, counter in counters.items()
        ]
        match_row = {
            EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.STATSBOMB_NAME,
            "home": home_team,
            "away": away_team,
            **shared_columns,
            **self._discipline_counter.summarise_both_sides(
                self._add_up_one_side(counters, home_team),
                self._add_up_one_side(counters, away_team),
            ),
        }
        return player_rows, match_row

    def _count_over_one_match(self, match: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Count the fouls and cards per player over the events of one match."""
        counters: dict[str, dict[str, Any]] = {}
        for event in self._statsbomb_reader.read_events(match):
            player_name = event.get(StatsBombOpenDataSource.PLAYER_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            )
            if not player_name:
                continue
            is_foul = (
                event.get(StatsBombOpenDataSource.TYPE_FIELD, {}).get(
                    StatsBombOpenDataSource.NAME_FIELD
                )
                == StatsBombOpenDataSource.FOUL_EVENT_NAME
            )
            card_name = self._statsbomb_reader.read_card_name_of(event)
            if not is_foul and card_name is None:
                continue
            counter = counters.setdefault(
                player_name, self._start_a_counter_for_the_player_of(event)
            )
            counter[EventSourceSetting.FOUL_NAME] += 1 if is_foul else 0
            if card_name is not None:
                counter[card_name] += 1
        return counters

    def _start_a_counter_for_the_player_of(
        self, event: dict[str, Any]
    ) -> dict[str, Any]:
        """Build the counter of the player of one event, with their team."""
        return {
            "team": event.get(StatsBombOpenDataSource.TEAM_FIELD, {}).get(
                StatsBombOpenDataSource.NAME_FIELD
            ),
            **self._discipline_counter.start_a_counter_at_zero(),
        }

    def _add_up_one_side(
        self, counters: dict[str, dict[str, Any]], team_name: str
    ) -> dict[str, int]:
        """Add the players of one team up into a single counter."""
        total = self._discipline_counter.start_a_counter_at_zero()
        for counter in counters.values():
            if counter["team"] != team_name:
                continue
            for name in MatchDisciplineFeature.COUNTED_NAMES:
                total[name] += counter[name]
        return total

    def _the_columns_both_files_share(
        self, match: dict[str, Any], competition: StatsBombCompetition
    ) -> dict[str, Any]:
        """Build the columns both output files have in common."""
        return {
            "date": self._statsbomb_reader.read_the_day_a_match_was_played(match),
            "competition": competition.competition_name,
            "season": competition.season_name,
            "game_id": match[StatsBombOpenDataSource.MATCH_IDENTIFIER_FIELD],
            "referee": (match.get(StatsBombOpenDataSource.REFEREE_FIELD) or {}).get(
                StatsBombOpenDataSource.NAME_FIELD, ""
            ),
        }


if __name__ == "__main__":
    StatsBombMatchDisciplineBuilder(
        StatsBombOpenDataReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    StatsBombOpenDataSource.POLITE_DELAY_IN_SECONDS
                ),
            )
        ),
        MatchDisciplineCounter(),
    ).build_every_competition()
