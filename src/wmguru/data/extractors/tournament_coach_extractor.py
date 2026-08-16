"""The head coach of every squad, out of the Wikipedia squads pages.

That is the base for coach features, that is a coach from abroad and how long a
coach stays across tournaments. A coach counts as foreign when the country on
the flag next to the name is not the country of the team.
"""

import re

from wmguru.helpers.constant import (
    TournamentCoachExtract,
    WebRequestSetting,
    WikipediaSquadSource,
)
from wmguru.helpers.utils import CsvFile, WebFileDownloader, WikipediaPageReader


class TournamentCoachExtractor:
    """One row per team and tournament, with its head coach."""

    def __init__(self, wikipedia_page_reader: WikipediaPageReader) -> None:
        self._wikipedia_page_reader = wikipedia_page_reader

    def extract_every_tournament(self) -> int:
        """Write the file and return how many coaches were found."""
        output_file = CsvFile(
            TournamentCoachExtract.OUTPUT_FILE, TournamentCoachExtract.COLUMN_NAMES
        )
        written_count = 0
        with output_file.writing_writer() as writer:
            for (
                tournament_name,
                page_title,
            ) in WikipediaSquadSource.PAGE_TITLE_OF_TOURNAMENT.items():
                wikitext = self._wikipedia_page_reader.read_wikitext(page_title)
                if wikitext is None:
                    print(f"  FAIL  {tournament_name}")
                    continue
                coaches = self._read_coaches(wikitext)
                for team_name, coach_name, coach_country in coaches:
                    writer.writerow(
                        [
                            tournament_name,
                            team_name,
                            coach_name,
                            coach_country,
                            int(self._is_from_abroad(team_name, coach_country)),
                        ]
                    )
                written_count += len(coaches)
                print(f"  OK    {tournament_name}: {len(coaches)} coaches")
        print(f"-> {output_file.path}")
        return written_count

    def _read_coaches(self, wikitext: str) -> list[tuple[str, str, str]]:
        """Read team, coach and the country on the flag, for one squads page."""
        coaches: list[tuple[str, str, str]] = []
        team_name = ""
        for line in wikitext.splitlines():
            team_heading = re.match(TournamentCoachExtract.TEAM_HEADING_PATTERN, line)
            if team_heading:
                team_name = team_heading.group(1)
                continue
            coach = self._read_coach_of_one_line(line, team_name)
            if coach is not None:
                coaches.append(coach)
        return coaches

    def _read_coach_of_one_line(
        self, line: str, team_name: str
    ) -> tuple[str, str, str] | None:
        """Read one coach line, or return None when the line does not carry a coach.

        Without a wiki link there is no reliable name behind the word Coach,
        so such a line is dropped.
        """
        if not team_name:
            return None
        coach_line = re.match(TournamentCoachExtract.COACH_LINE_PATTERN, line)
        if coach_line is None:
            return None
        behind_the_word = coach_line.group(1)
        linked_name = re.search(
            TournamentCoachExtract.WIKI_LINK_PATTERN, behind_the_word
        )
        if linked_name is None:
            return None
        country_flag = re.search(
            TournamentCoachExtract.COUNTRY_FLAG_PATTERN, behind_the_word
        )
        return (
            team_name,
            self._strip_wiki_link(linked_name.group(0)),
            country_flag.group(1) if country_flag else "",
        )

    def _strip_wiki_link(self, raw_text: str) -> str:
        """Turn [[target|shown]] or [[target]] into the readable part."""
        found = re.search(TournamentCoachExtract.READABLE_LINK_PATTERN, raw_text)
        readable = found.group(1) if found else raw_text
        return readable.strip().strip("}").strip()

    def _is_from_abroad(self, team_name: str, coach_country: str) -> bool:
        """Return True when the flag names a country other than the team."""
        if not coach_country:
            return False
        return coach_country.lower() != team_name.lower()


if __name__ == "__main__":
    TournamentCoachExtractor(
        WikipediaPageReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    WebRequestSetting.SHORT_POLITE_DELAY_IN_SECONDS
                ),
            )
        )
    ).extract_every_tournament()
