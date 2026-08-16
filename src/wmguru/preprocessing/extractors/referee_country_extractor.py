"""The country of the referee, out of the StatsBomb match lists.

This is the base for a confederation bias feature. A referee from South America
statistically allows a different game than one from Europe, and the pairing of
referee confederation with team confederation is in hardly any model.
"""

from typing import Any

from wmguru.helpers.constant import (
    RefereeCountryExtract,
    StatsBombSource,
    WebRequestSetting,
)
from wmguru.helpers.utils import CsvFile, WebFileDownloader
from wmguru.preprocessing.downloads.statsbomb_match_list_reader import (
    StatsBombMatchListReader,
)


class RefereeCountryExtractor:
    """One row per match, with the referee and the country."""

    def __init__(self, match_list_reader: StatsBombMatchListReader) -> None:
        self._match_list_reader = match_list_reader

    def extract_every_tournament(self) -> int:
        """Write the file and return how many matches it holds."""
        output_file = CsvFile(
            RefereeCountryExtract.OUTPUT_FILE, RefereeCountryExtract.COLUMN_NAMES
        )
        written_count = 0
        with output_file.writing_writer() as writer:
            for tournament_name in StatsBombSource.TOURNAMENT_IDENTIFIER:
                matches = self._match_list_reader.read_matches(tournament_name)
                if not matches:
                    print(f"  FAIL  {tournament_name}")
                    continue
                for match in matches:
                    writer.writerow(
                        self._build_the_row_of_one_match(tournament_name, match)
                    )
                    written_count += 1
                print(f"  OK    {tournament_name}")
        print(f"{written_count} matches with a referee country -> {output_file.path}")
        return written_count

    def _build_the_row_of_one_match(
        self, tournament_name: str, match: dict[str, Any]
    ) -> list[Any]:
        """Build one output row."""
        referee = match.get("referee") or {}
        country = referee.get("country") or {}
        return [
            tournament_name,
            match.get("match_id"),
            match.get("match_date"),
            referee.get("name", ""),
            country.get("name", ""),
        ]


if __name__ == "__main__":
    RefereeCountryExtractor(
        StatsBombMatchListReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=WebRequestSetting.FAST_POLITE_DELAY_IN_SECONDS,
            )
        )
    ).extract_every_tournament()
