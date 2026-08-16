"""How much the r/soccer crowd talked about every World Cup team.

For every team it counts the submissions in a fixed historical window, by
default the window of the 2022 World Cup, together with the mean score. That is
a fan attention proxy outside the betting markets and it can be used in a
backtest.

Live data is not reachable without a key: reddit.com blocks anonymous searches
with HTTP 403, and the free PullPush archive lags months behind. For live
attention the Wikipedia pageviews are used instead, real live Reddit would need
a free OAuth application.
"""

import urllib.parse
from datetime import UTC, datetime
from typing import Any

from wmguru.helpers.constant import (
    RedditActivitySource,
    TimeStampFormat,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
    WorldCupTeamNameReader,
)


class RedditActivityFetcher:
    """One attention snapshot of all teams, appended to the log."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        team_name_reader: WorldCupTeamNameReader,
        output_file: CsvFile,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._team_name_reader = team_name_reader
        self._output_file = output_file

    def fetch_every_team(self, fetched_at: datetime) -> int:
        """Append one row per team and return how many were written."""
        stamp = fetched_at.strftime(TimeStampFormat.UTC_TIME_STAMP)
        written_count = 0
        with self._output_file.appending_writer() as writer:
            for team_name in self._team_name_reader.read_team_names():
                submissions = self._read_submissions(team_name)
                if submissions is None:
                    print(f"  FAIL  {team_name}")
                    continue
                writer.writerow(
                    self._build_the_row_of_one_day(stamp, team_name, submissions)
                )
                written_count += 1
                print(f"  OK    {team_name}: {len(submissions)} posts")
        print(f"-> {self._output_file.path}")
        return written_count

    def _read_submissions(self, team_name: str) -> list[dict[str, Any]] | None:
        """Read the submissions of the window that mention the team, or return None."""
        answer = self._web_file_downloader.download_json(
            self._build_url(team_name),
            timeout_in_seconds=RedditActivitySource.TIMEOUT_IN_SECONDS,
        )
        if not isinstance(answer, dict):
            return None
        submissions = answer.get("data", [])
        return submissions if isinstance(submissions, list) else None

    def _build_url(self, team_name: str) -> str:
        """Build the address of one request."""
        window_start = self._to_seconds_since_epoch(
            RedditActivitySource.WINDOW_START_AT_THE_2022_OPENING
        )
        window_end = (
            self._to_seconds_since_epoch(
                RedditActivitySource.WINDOW_END_AT_THE_2022_FINAL
            )
            + RedditActivitySource.SECONDS_PER_DAY
        )
        return (
            f"{RedditActivitySource.API_URL}"
            f"?subreddit={RedditActivitySource.SUBREDDIT}"
            f"&q={urllib.parse.quote(team_name)}"
            f"&after={window_start}&before={window_end}"
            f"&size={RedditActivitySource.LARGEST_PAGE_SIZE_THE_ARCHIVE_ALLOWS}"
        )

    def _to_seconds_since_epoch(self, day: str) -> int:
        """Turn an ISO day into the start of that day in seconds since the epoch."""
        return int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp())

    def _build_the_row_of_one_day(
        self, stamp: str, team_name: str, submissions: list[dict[str, Any]]
    ) -> list[Any]:
        """Build one output row."""
        scores = [int(submission.get("score") or 0) for submission in submissions]
        return [
            stamp,
            team_name,
            RedditActivitySource.WINDOW_START_AT_THE_2022_OPENING,
            RedditActivitySource.WINDOW_END_AT_THE_2022_FINAL,
            len(scores),
            round(sum(scores) / len(scores), 1) if scores else 0,
            max(scores) if scores else 0,
        ]


if __name__ == "__main__":
    RedditActivityFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=WebRequestSetting.STANDARD_POLITE_DELAY_IN_SECONDS,
        ),
        WorldCupTeamNameReader(),
        CsvFile(RedditActivitySource.OUTPUT_FILE, RedditActivitySource.COLUMN_NAMES),
    ).fetch_every_team(datetime.now(UTC))
