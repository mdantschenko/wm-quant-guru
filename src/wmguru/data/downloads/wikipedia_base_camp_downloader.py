"""The 2026 World Cup team base camps, out of the main Wikipedia article.

The section "Team base camps" names the training quarter of every team. That is
the base for a realistic travel model, that is base camp to venue and back
again, instead of stadium to stadium.
"""

import re

from wmguru.helpers.constant import (
    WebRequestSetting,
    WikipediaBaseCampSource,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
    WikipediaPageReader,
)


class WikipediaBaseCampDownloader:
    """The base camp table of the article, as a small CSV file."""

    def __init__(self, wikipedia_page_reader: WikipediaPageReader) -> None:
        self._wikipedia_page_reader = wikipedia_page_reader

    def download_base_camps(self) -> int:
        """Write the file and return how many base camps were found."""
        wikitext = self._wikipedia_page_reader.read_wikitext(
            WikipediaBaseCampSource.PAGE_TITLE
        )
        if wikitext is None:
            print(f"  FAIL  {WikipediaBaseCampSource.PAGE_TITLE} could not be loaded")
            return 0

        rows = self._read_rows(self._cut_out_section(wikitext))
        target_file = WikipediaBaseCampSource.OUTPUT_FILE
        with CsvFile(
            target_file, WikipediaBaseCampSource.COLUMN_NAMES
        ).writing_writer() as writer:
            writer.writerows(sorted(rows))
        print(f"{len(rows)} base camps -> {target_file}")
        return len(rows)

    def _cut_out_section(self, wikitext: str) -> str:
        """Cut out everything between the base camp heading and the next heading."""
        found = re.search(WikipediaBaseCampSource.SECTION_PATTERN, wikitext, re.DOTALL)
        return found.group(1) if found else ""

    def _read_rows(self, section: str) -> list[tuple[str, str, str]]:
        """Read team code, accommodation and training site out of the table.

        Every team starts with a line that holds its three letter FIFA code,
        followed by two cell lines, the hotel and the training ground.
        """
        rows: list[tuple[str, str, str]] = []
        team_code = ""
        cells: list[str] = []
        for line in section.splitlines():
            found_code = re.search(WikipediaBaseCampSource.TEAM_CODE_PATTERN, line)
            if found_code:
                self._remember_team(rows, team_code, cells)
                team_code = found_code.group(1)
                cells = []
                continue
            if line.startswith(WikipediaBaseCampSource.TABLE_ROW_MARKERS):
                continue
            if team_code and line.startswith(WikipediaBaseCampSource.CELL_MARKER):
                cell = self._clean_cell(line)
                if cell:
                    cells.append(cell)
        self._remember_team(rows, team_code, cells)
        return rows

    def _remember_team(
        self, rows: list[tuple[str, str, str]], team_code: str, cells: list[str]
    ) -> None:
        """Close off the team that was being read, if there was one."""
        if team_code and cells:
            rows.append((team_code, cells[0], cells[1] if len(cells) > 1 else ""))

    def _clean_cell(self, raw_cell: str) -> str:
        """Take references, templates, links and table markup out of a cell."""
        without_references = re.sub(
            WikipediaBaseCampSource.REFERENCE_PATTERN, "", raw_cell, flags=re.DOTALL
        )
        without_templates = re.sub(
            WikipediaBaseCampSource.TEMPLATE_PATTERN, "", without_references
        )
        readable = re.sub(
            WikipediaBaseCampSource.WIKI_LINK_PATTERN, r"\1", without_templates
        ).strip()
        return readable.strip(WikipediaBaseCampSource.CELL_TRIM_CHARACTERS)


if __name__ == "__main__":
    WikipediaBaseCampDownloader(
        WikipediaPageReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    WebRequestSetting.SHORT_POLITE_DELAY_IN_SECONDS
                ),
            )
        )
    ).download_base_camps()
