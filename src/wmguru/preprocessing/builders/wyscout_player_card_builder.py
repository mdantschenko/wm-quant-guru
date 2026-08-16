"""The cards of every player and match, out of the Wyscout events.

Only a player who saw a card in a match gets a row. How Wyscout marks a card
is the reader's business, this class only counts.

The event files are gigabytes, so they are streamed rather than read in.
"""

from typing import Any

from wmguru.helpers.constant import (
    EventSourceSetting,
    PlayerCardFeature,
    WyscoutEventFile,
)
from wmguru.helpers.utils import (
    CsvFile,
    SharedFeatureFile,
    TextNormalizer,
    WyscoutDataReader,
)


class WyscoutPlayerCardBuilder:
    """The cards of every Wyscout match, per player and team."""

    def __init__(self, wyscout_data_reader: WyscoutDataReader) -> None:
        self._wyscout_data_reader = wyscout_data_reader
        self._output_file = SharedFeatureFile(
            CsvFile(PlayerCardFeature.OUTPUT_FILE, PlayerCardFeature.COLUMN_NAMES),
            EventSourceSetting.WYSCOUT_NAME,
            PlayerCardFeature.SORT_KEY_NAMES,
        )

    def build_every_match(self) -> int:
        """Stream every event file and write the cards.

        Returns:
            How many rows the file holds afterwards, the rows the StatsBomb
            half wrote included.
        """
        cards = self._count_cards()
        rows = self._build_the_rows_of_every_player(cards)
        total_count = self._output_file.write_keeping_the_other_source(rows)
        print(f"  OK    {len(rows)} carded players from Wyscout, {total_count} in all")
        return total_count

    def _count_cards(self) -> dict[tuple[str, str, str], dict[str, int]]:
        """Count the cards per player, match and team over every event file.

        Returns:
            One counter per player, match and team, so a player who saw two
            cards in one match is counted twice in the right column.
        """
        cards: dict[tuple[str, str, str], dict[str, int]] = {}
        for event_file in sorted(
            WyscoutEventFile.SOURCE_FOLDER.glob(WyscoutEventFile.EVENT_FILE_PATTERN)
        ):
            for event in CsvFile(event_file).stream_rows():
                self._count_one_event(event, cards)
        return cards

    def _count_one_event(
        self, event: dict[str, str], cards: dict[tuple[str, str, str], dict[str, int]]
    ) -> None:
        """Add the cards of one event, if it carries any at all."""
        card_names = self._wyscout_data_reader.read_card_names_out_of_tag_list(
            event.get(WyscoutEventFile.TAG_LIST_COLUMN, "")
        )
        if not card_names:
            return
        key = (
            self._wyscout_data_reader.as_identifier(
                event[WyscoutEventFile.PLAYER_IDENTIFIER_COLUMN]
            ),
            self._wyscout_data_reader.as_identifier(
                event[WyscoutEventFile.MATCH_IDENTIFIER_COLUMN]
            ),
            self._wyscout_data_reader.as_identifier(
                event[WyscoutEventFile.TEAM_IDENTIFIER_COLUMN]
            ),
        )
        counter = cards.setdefault(key, self._start_a_counter_at_zero())
        for card_name in card_names:
            counter[card_name] += 1

    def _start_a_counter_at_zero(self) -> dict[str, int]:
        """Build a counter that holds a zero for every kind of card."""
        return {name: 0 for name in WyscoutEventFile.CARD_OF_TAG.values()}

    def _build_the_rows_of_every_player(
        self, cards: dict[tuple[str, str, str], dict[str, int]]
    ) -> list[dict[str, Any]]:
        """Turn the counters into output rows, naming teams and players."""
        match_facts = self._wyscout_data_reader.read_match_facts()
        lookups = self._wyscout_data_reader.read_name_lookups()

        rows: list[dict[str, Any]] = []
        for (player, game, team), counter in cards.items():
            facts = match_facts.get(game)
            if facts is None:
                continue
            opponent = facts.opponent_of(team)
            rows.append(
                {
                    EventSourceSetting.SOURCE_COLUMN: EventSourceSetting.WYSCOUT_NAME,
                    "date": facts.match_date,
                    "competition": lookups.competition_names.get(
                        facts.competition_identifier, facts.competition_identifier
                    ),
                    "season": facts.season_name,
                    "team": lookups.team_names.get(team, team),
                    "opponent": lookups.team_names.get(opponent, opponent),
                    "player": lookups.player_names.get(player, player),
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


if __name__ == "__main__":
    WyscoutPlayerCardBuilder(WyscoutDataReader(TextNormalizer())).build_every_match()
