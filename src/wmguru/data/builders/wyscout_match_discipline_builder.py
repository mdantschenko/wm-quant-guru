"""The fouls and cards per player and per match, out of the Wyscout events.

This is what pairs a strict referee with an undisciplined team. It writes two
files: one row per player and match, and one row per match with both sides and
the referee.

The event files are gigabytes, so they are streamed rather than read in.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    MatchDisciplineFeature,
    WyscoutEventFile,
)
from wmguru.helpers.data_class import WyscoutMatchFacts, WyscoutNameLookups
from wmguru.helpers.utils import (
    CsvFile,
    MatchDisciplineCounter,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutMatchDisciplineBuilder:
    """The fouls and cards of every Wyscout match."""

    def __init__(
        self,
        wyscout_data_reader: WyscoutDataReader,
        discipline_counter: MatchDisciplineCounter,
    ) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._discipline_counter = discipline_counter
        self._player_file = SharedFeatureFile(
            CsvFile(
                MatchDisciplineFeature.PLAYER_OUTPUT_FILE,
                MatchDisciplineFeature.PLAYER_COLUMN_NAMES,
            ),
            EventSourceSetting.WYSCOUT_NAME,
            MatchDisciplineFeature.PLAYER_SORT_KEY_NAMES,
        )
        self._match_file = SharedFeatureFile(
            CsvFile(
                MatchDisciplineFeature.MATCH_OUTPUT_FILE,
                MatchDisciplineFeature.MATCH_COLUMN_NAMES,
            ),
            EventSourceSetting.WYSCOUT_NAME,
            MatchDisciplineFeature.MATCH_SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Stream every event file and write both output files.

        Returns:
            How many matches the match file holds afterwards, the matches the
            StatsBomb half wrote included.
        """
        counts = self._count_over_every_event_file()
        match_facts = self._wyscout_data_reader.read_match_facts()
        lookups = self._wyscout_data_reader.read_name_lookups()

        player_rows = self._build_player_rows(counts, match_facts, lookups)
        match_rows = self._build_match_rows(counts, match_facts, lookups)
        self._player_file.write_keeping_the_other_source(player_rows)
        match_total = self._match_file.write_keeping_the_other_source(match_rows)
        print(
            f"  OK    {len(player_rows)} player rows and {len(match_rows)} matches "
            f"from Wyscout, {match_total} matches in all"
        )
        return match_total

    def _count_over_every_event_file(
        self,
    ) -> dict[tuple[str, str, str], dict[str, int]]:
        """Count fouls and cards per match, player and team over every file."""
        counts: dict[tuple[str, str, str], dict[str, int]] = {}
        for event_file in sorted(
            WyscoutEventFile.SOURCE_FOLDER.glob(WyscoutEventFile.EVENT_FILE_PATTERN)
        ):
            for event in CsvFile(event_file).stream_rows():
                self._count_one_event(event, counts)
        return counts

    def _count_one_event(
        self, event: dict[str, str], counts: dict[tuple[str, str, str], dict[str, int]]
    ) -> None:
        """Add one event, if it is a foul or carries a card at all."""
        is_foul = (
            event.get(WyscoutEventFile.EVENT_NAME_COLUMN)
            == WyscoutEventFile.FOUL_EVENT_NAME
        )
        card_names = self._wyscout_data_reader.read_card_names_out_of_tag_list(
            event.get(WyscoutEventFile.TAG_LIST_COLUMN, "")
        )
        player = self._wyscout_data_reader.as_identifier(
            event.get(WyscoutEventFile.PLAYER_IDENTIFIER_COLUMN, "")
        )
        if not player or (not is_foul and not card_names):
            return
        key = (
            self._wyscout_data_reader.as_identifier(
                event.get(WyscoutEventFile.MATCH_IDENTIFIER_COLUMN, "")
            ),
            player,
            self._wyscout_data_reader.as_identifier(
                event.get(WyscoutEventFile.TEAM_IDENTIFIER_COLUMN, "")
            ),
        )
        counter = counts.setdefault(
            key, self._discipline_counter.start_a_counter_at_zero()
        )
        counter[EventSourceSetting.FOUL_NAME] += 1 if is_foul else 0
        for card_name in card_names:
            counter[card_name] += 1

    def _build_player_rows(
        self,
        counts: dict[tuple[str, str, str], dict[str, int]],
        match_facts: dict[str, WyscoutMatchFacts],
        lookups: WyscoutNameLookups,
    ) -> list[dict[str, Any]]:
        """Build one row per player who fouled or was carded in a match."""
        rows: list[dict[str, Any]] = []
        for (game, player, team), counter in counts.items():
            facts = match_facts.get(game)
            if facts is None:
                continue
            opponent = facts.opponent_of(team)
            rows.append(
                {
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
                    "team": lookups.team_names.get(team, team),
                    "opponent": lookups.team_names.get(opponent, opponent),
                    "player": lookups.player_names.get(player, player),
                    **self._the_columns_both_files_share(facts, lookups),
                    **counter,
                }
            )
        return rows

    def _build_match_rows(
        self,
        counts: dict[tuple[str, str, str], dict[str, int]],
        match_facts: dict[str, WyscoutMatchFacts],
        lookups: WyscoutNameLookups,
    ) -> list[dict[str, Any]]:
        """Build one row per match, adding both sides up."""
        counts_of_team = self._add_up_per_team(counts)
        rows: list[dict[str, Any]] = []
        for game, facts in match_facts.items():
            home_counter = counts_of_team.get(
                (game, facts.home_team_identifier),
                self._discipline_counter.start_a_counter_at_zero(),
            )
            away_counter = counts_of_team.get(
                (game, facts.away_team_identifier),
                self._discipline_counter.start_a_counter_at_zero(),
            )
            rows.append(
                {
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
                    "home": lookups.team_names.get(
                        facts.home_team_identifier, facts.home_team_identifier
                    ),
                    "away": lookups.team_names.get(
                        facts.away_team_identifier, facts.away_team_identifier
                    ),
                    **self._the_columns_both_files_share(facts, lookups),
                    **self._discipline_counter.summarise_both_sides(
                        home_counter, away_counter
                    ),
                }
            )
        return rows

    def _add_up_per_team(
        self, counts: dict[tuple[str, str, str], dict[str, int]]
    ) -> dict[tuple[str, str], dict[str, int]]:
        """Add the players of a team up, so a match has two counters left."""
        counts_of_team: dict[tuple[str, str], dict[str, int]] = {}
        for (game, _player, team), counter in counts.items():
            target = counts_of_team.setdefault(
                (game, team), self._discipline_counter.start_a_counter_at_zero()
            )
            for name, value in counter.items():
                target[name] += value
        return counts_of_team

    def _the_columns_both_files_share(
        self, facts: WyscoutMatchFacts, lookups: WyscoutNameLookups
    ) -> dict[str, Any]:
        """Build the columns both output files have in common."""
        return {
            "date": facts.match_date,
            "competition": lookups.competition_names.get(
                facts.competition_identifier, facts.competition_identifier
            ),
            "season": facts.season_name,
            "game_id": facts.game_identifier,
            "referee": lookups.referee_names.get(
                facts.referee_identifier, facts.referee_identifier
            ),
        }


if __name__ == "__main__":
    WyscoutMatchDisciplineBuilder(
        WyscoutDataReader(TextNormalizer()), MatchDisciplineCounter()
    ).build_every_match()
