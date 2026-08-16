"""Daily Wikipedia article views for the World Cup teams and their players.

Daily article views are an attention index. A spike on a player article marks
an injury, a ban, a form hype or a scandal, often before the odds price it in.
Team series start in 2018 so a backtest has history. The player articles are
read straight out of the wikitext of the squads page, so no name guessing is
needed.

Both output files are written by appending, so a stopped run picks up where it
left off.
"""

import re
import urllib.parse
from datetime import date
from typing import Any

from wmguru.helpers.constant import (
    WebRequestSetting,
    WikipediaPageviewSource,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
    WikipediaPageReader,
    WorldCupTeamNameReader,
)


class WikipediaPageviewFetcher:
    """One row per article and day, in a team file and a player file."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        wikipedia_page_reader: WikipediaPageReader,
        team_name_reader: WorldCupTeamNameReader,
        team_output_file: CsvFile,
        player_output_file: CsvFile,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._wikipedia_page_reader = wikipedia_page_reader
        self._team_name_reader = team_name_reader
        self._team_output_file = team_output_file
        self._player_output_file = player_output_file

    def fetch_team_views(self, last_day: date) -> int:
        """Append the view series of every team article.

        A team that is already in the file is skipped, so a stopped run picks
        up where it left off.

        Args:
            last_day: The last day of the series, usually today.

        Returns:
            How many daily values were added in this run.
        """
        finished_teams = self._team_output_file.read_finished_values(
            WikipediaPageviewSource.TEAM_KEY_COLUMN
        )
        rows: list[list[Any]] = []
        missing_count = 0
        for team_name in self._team_name_reader.read_team_names():
            if team_name in finished_teams:
                continue
            article = self._article_title_of(team_name)
            series = self._read_daily_views(
                article, WikipediaPageviewSource.TEAM_SERIES_START_DAY, last_day
            )
            if series is None:
                missing_count += 1
                print(f"  SKIP team {team_name} ({article})")
                continue
            rows.extend([team_name, article, day, views] for day, views in series)
        self._team_output_file.append_rows(rows)
        print(
            f"Teams: +{len(rows)} daily values ({missing_count} missing, "
            f"{len(finished_teams)} already there)",
            flush=True,
        )
        return len(rows)

    def fetch_player_views(self, last_day: date) -> int:
        """Append the view series of every player of the 2026 squads.

        A player whose article is already in the file is skipped, so a
        stopped run picks up where it left off.

        Args:
            last_day: The last day of the series, usually today.

        Returns:
            How many daily values were added in this run.

        Raises:
            SystemExit: When the squads page could not be loaded, which is
                usually Wikipedia throttling. Run it again in a moment.
        """
        finished_articles = self._player_output_file.read_finished_values(
            WikipediaPageviewSource.ARTICLE_KEY_COLUMN
        )
        open_players = [
            (team_name, article)
            for team_name, article in self._read_squad_articles()
            if article not in finished_articles
        ]
        rows: list[list[Any]] = []
        missing_count = 0
        for position, (team_name, article) in enumerate(open_players, start=1):
            series = self._read_daily_views(
                article, WikipediaPageviewSource.PLAYER_SERIES_START_DAY, last_day
            )
            if series is None:
                missing_count += 1
                continue
            rows.extend([team_name, article, day, views] for day, views in series)
            self._report_progress(position, len(open_players))
        self._player_output_file.append_rows(rows)
        print(
            f"Players: +{len(rows)} daily values ({missing_count} missing or "
            f"without an article, {len(finished_articles)} already there)"
        )
        return len(rows)

    def _article_title_of(self, team_name: str) -> str:
        """Build the Wikipedia title of a national team, with the known exceptions."""
        return WikipediaPageviewSource.ARTICLE_TITLE_OVERRIDES.get(
            team_name,
            WikipediaPageviewSource.ARTICLE_TITLE_TEMPLATE.format(team_name=team_name),
        )

    def _read_daily_views(
        self, article: str, start_day: str, last_day: date
    ) -> list[tuple[str, int]] | None:
        """Read the day and view count pairs, or return None for an unknown article."""
        quoted_article = urllib.parse.quote(article.replace(" ", "_"), safe="")
        url = WikipediaPageviewSource.PAGEVIEW_URL_TEMPLATE.format(
            article=quoted_article,
            start_day=start_day,
            end_day=last_day.strftime(WikipediaPageviewSource.DAY_FORMAT),
        )
        answer = self._web_file_downloader.download_json(
            url, timeout_in_seconds=WikipediaPageviewSource.TIMEOUT_IN_SECONDS
        )
        if not isinstance(answer, dict):
            return None
        return [
            (item["timestamp"][:8], item["views"]) for item in answer.get("items", [])
        ]

    def _read_squad_articles(self) -> list[tuple[str, str]]:
        """Read the team and article title of every player on the squads page.

        Raises:
            SystemExit: When the page could not be loaded, which usually means
                Wikipedia is throttling this address.
        """
        wikitext = self._wikipedia_page_reader.read_wikitext(
            WikipediaPageviewSource.SQUAD_PAGE_TITLE
        )
        if wikitext is None:
            raise SystemExit(
                "The squads page could not be loaded, Wikipedia may be "
                "throttling. Please run this again."
            )
        pairs: list[tuple[str, str]] = []
        team_name = ""
        for line in wikitext.splitlines():
            team_heading = re.match(WikipediaPageviewSource.TEAM_HEADING_PATTERN, line)
            if team_heading:
                team_name = team_heading.group(1)
                continue
            article = re.search(WikipediaPageviewSource.PLAYER_ARTICLE_PATTERN, line)
            if article and team_name:
                pairs.append((team_name, article.group(1).strip()))
        return pairs

    def _report_progress(self, position: int, player_count: int) -> None:
        """Say something every now and then, there are hundreds of players."""
        every = WikipediaPageviewSource.PROGRESS_REPORT_EVERY_N_PLAYERS
        if position % every == 0:
            print(f"  ... {position}/{player_count} players", flush=True)


if __name__ == "__main__":
    shared_downloader = WebFileDownloader(
        user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
        polite_delay_in_seconds=WikipediaPageviewSource.POLITE_DELAY_IN_SECONDS,
        attempt_count=WebRequestSetting.ATTEMPT_WITH_ONE_RETRY,
    )
    fetcher = WikipediaPageviewFetcher(
        shared_downloader,
        WikipediaPageReader(shared_downloader),
        WorldCupTeamNameReader(),
        CsvFile(
            WikipediaPageviewSource.OUTPUT_FOLDER
            / WikipediaPageviewSource.TEAM_OUTPUT_FILE_NAME,
            WikipediaPageviewSource.COLUMN_NAMES,
        ),
        CsvFile(
            WikipediaPageviewSource.OUTPUT_FOLDER
            / WikipediaPageviewSource.PLAYER_OUTPUT_FILE_NAME,
            WikipediaPageviewSource.COLUMN_NAMES,
        ),
    )
    today = date.today()
    fetcher.fetch_team_views(today)
    fetcher.fetch_player_views(today)
