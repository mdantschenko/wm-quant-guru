"""One squad file per tournament, out of the Wikipedia squads pages.

Those pages list every player as a structured template with shirt number,
position, name, date of birth, caps, goals, club and the country of the club.
This is the reliable source for club chemistry and the share of players playing
abroad, because the FootyStats player lists name the national team as the
current club and are useless for that question.
"""

import re

from wmguru.helpers.constant import (
    WebRequestSetting,
    WikipediaSquadSource,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
    WikipediaPageReader,
)


class WikipediaSquadDownloader:
    """The wikitext of a squads page, as a flat player file."""

    def __init__(self, wikipedia_page_reader: WikipediaPageReader) -> None:
        self._wikipedia_page_reader = wikipedia_page_reader

    def download_every_tournament(self) -> int:
        """Write one file per tournament and return how many were written."""
        WikipediaSquadSource.OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
        written_count = 0
        for (
            tournament_name,
            page_title,
        ) in WikipediaSquadSource.PAGE_TITLE_OF_TOURNAMENT.items():
            if self.download_one_tournament(tournament_name, page_title):
                written_count += 1
        return written_count

    def download_one_tournament(self, tournament_name: str, page_title: str) -> bool:
        """Return True when this page became a squad file."""
        target_file = WikipediaSquadSource.OUTPUT_FOLDER / f"{tournament_name}.csv"
        if target_file.exists():
            print(f"  SKIP  {tournament_name}")
            return False

        wikitext = self._wikipedia_page_reader.read_wikitext(page_title)
        if wikitext is None:
            print(f"  FAIL  {tournament_name} ({page_title})")
            return False

        rows = self._read_squads(wikitext)
        with CsvFile(
            target_file, WikipediaSquadSource.COLUMN_NAMES
        ).writing_writer() as writer:
            writer.writerows(rows)
        team_names = {row[1] for row in rows}
        print(
            f"  OK    {tournament_name}: {len(rows)} players, "
            f"{len(team_names)} teams"
        )
        return True

    def _read_squads(self, wikitext: str) -> list[list[str]]:
        """Read the club of every player per team, and whether it is a top league."""
        rows: list[list[str]] = []
        group_name = ""
        team_name = ""
        for line in wikitext.splitlines():
            group_heading = re.match(WikipediaSquadSource.GROUP_HEADING_PATTERN, line)
            if group_heading:
                group_name = group_heading.group(1)
                continue
            team_heading = re.match(WikipediaSquadSource.TEAM_HEADING_PATTERN, line)
            if team_heading:
                team_name = team_heading.group(1)
                continue
            player = self._read_player(line)
            if player and team_name:
                rows.append(
                    [
                        group_name,
                        team_name,
                        player["number"],
                        player["position"],
                        player["name"],
                        player["date_of_birth"],
                        player["caps"],
                        player["goals"],
                        player["club"],
                        player["club_country"],
                    ]
                )
        return rows

    def _read_player(self, line: str) -> dict[str, str] | None:
        """Read one player template. None when the line is not a player."""
        if not re.search(
            WikipediaSquadSource.PLAYER_TEMPLATE_PATTERN, line, flags=re.IGNORECASE
        ):
            return None
        pattern_of_field = WikipediaSquadSource.PATTERN_OF_SIMPLE_FIELD
        fields = {
            field_name: self._read_first_group(pattern, line)
            for field_name, pattern in pattern_of_field.items()
        }
        fields["name"] = self._strip_wiki_link(
            self._read_first_group(WikipediaSquadSource.NAME_PATTERN, line)
        )
        fields["date_of_birth"] = self._read_date_of_birth(line)
        fields["club"] = self._strip_wiki_link(
            self._read_first_group(WikipediaSquadSource.CLUB_PATTERN, line)
        )
        return fields if fields["name"] else None

    def _read_date_of_birth(self, line: str) -> str:
        """Read the date of birth out of the age segment of the template.

        The template "Birth date and age" holds one date triple, the date of
        birth. The template "Birth date and age2" holds two, a reference date
        and then the date of birth, so always take the last triple.
        """
        age_segment = self._read_first_group(
            WikipediaSquadSource.AGE_SEGMENT_PATTERN, line
        )
        triples = re.findall(WikipediaSquadSource.DATE_TRIPLE_PATTERN, age_segment)
        if not triples:
            return ""
        year, month, day = triples[-1]
        return f"{year}-{int(month):02d}-{int(day):02d}"

    def _read_first_group(self, pattern: str, line: str) -> str:
        """Read the first capture group of the pattern, or empty text."""
        found = re.search(pattern, line)
        return found.group(1) if found else ""

    def _strip_wiki_link(self, raw_text: str) -> str:
        """Turn [[target|shown]] or [[target]] into the readable part."""
        found = re.search(WikipediaSquadSource.WIKI_LINK_PATTERN, raw_text)
        readable = found.group(1) if found else raw_text
        return readable.strip().strip("}").strip()


if __name__ == "__main__":
    WikipediaSquadDownloader(
        WikipediaPageReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    WebRequestSetting.SHORT_POLITE_DELAY_IN_SECONDS
                ),
            )
        )
    ).download_every_tournament()
