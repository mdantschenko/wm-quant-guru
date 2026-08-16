"""News volume and news tone per World Cup team, from the GDELT index.

GDELT indexes news from all over the world. Its endpoint answers with a time
series of the article volume and of the mean tone for a search query. A
negative tone spike around a national team, such as an association crisis, a
scandal or a sacked coach, is a signal outside the betting markets.

The endpoint allows one request every five seconds. When it throttles, it
answers with plain text instead of JSON, and the run stops straight away
instead of writing 96 empty series.
"""

import json
import urllib.parse
from typing import Any

from wmguru.helpers.constant import (
    NewsToneSource,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
    WorldCupTeamNameReader,
)


class NewsToneFetcher:
    """One row per team and day, with volume and tone."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        team_name_reader: WorldCupTeamNameReader,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._team_name_reader = team_name_reader

    def fetch_every_team(self) -> int:
        """Fetch the volume and the tone series of all 48 teams.

        Returns:
            How many rows the file holds, that is one per team and day that
            either series covers.

        Raises:
            SystemExit: When the endpoint throttles this address. It then
                answers plain text instead of JSON and the cooldown lasts
                hours, so the run stops rather than writing empty series.
        """
        team_names = self._team_name_reader.read_team_names()
        NewsToneSource.OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        written_count = 0
        with CsvFile(
            NewsToneSource.OUTPUT_FILE, NewsToneSource.COLUMN_NAMES
        ).writing_writer() as writer:
            for team_name in team_names:
                written_count += self._write_one_team(writer, team_name)
        print(f"{written_count} rows -> {NewsToneSource.OUTPUT_FILE}")
        return written_count

    def _write_one_team(self, writer: Any, team_name: str) -> int:
        """Write both series of one team, joined by day."""
        query = NewsToneSource.QUERY_TEMPLATE.format(team_name=team_name)
        volume_series = self._read_the_day_and_value_pairs(
            query, NewsToneSource.VOLUME_MODE
        )
        tone_series = self._read_the_day_and_value_pairs(
            query, NewsToneSource.TONE_MODE
        )
        written_count = 0
        for day in sorted(set(volume_series) | set(tone_series)):
            writer.writerow(
                [
                    team_name,
                    day,
                    volume_series.get(day, ""),
                    tone_series.get(day, ""),
                ]
            )
            written_count += 1
        print(
            f"  OK    {team_name}: {len(volume_series)} volume points, "
            f"{len(tone_series)} tone points",
            flush=True,
        )
        return written_count

    def _read_the_day_and_value_pairs(self, query: str, mode: str) -> dict[str, float]:
        """Read the day and value pairs, or nothing when the query gave nothing back."""
        url = (
            f"{NewsToneSource.API_URL}?query={urllib.parse.quote(query)}"
            f"&mode={mode}&timespan={NewsToneSource.TIME_SPAN}&format=json"
        )
        payload = self._web_file_downloader.download_bytes(
            url, timeout_in_seconds=NewsToneSource.TIMEOUT_IN_SECONDS
        )
        if payload is None:
            return {}
        self._stop_when_the_endpoint_throttles(payload)
        return self._read_points(payload)

    def _stop_when_the_endpoint_throttles(self, payload: bytes) -> None:
        """Check that the endpoint answered with JSON rather than plain text.

        Raises:
            SystemExit: When it answered with plain text, which is how this
                endpoint says it is throttling this address.
        """
        if payload.lstrip()[:1] not in NewsToneSource.JSON_FIRST_CHARACTERS:
            raise SystemExit(
                "GDELT is still throttling this address, it answered with plain "
                "text. Wait a few hours and run this again."
            )

    def _read_points(self, payload: bytes) -> dict[str, float]:
        """Pull the day and value pairs out of the answer."""
        try:
            answer = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        series: dict[str, float] = {}
        for timeline in answer.get("timeline", []):
            for point in timeline.get("data", []):
                series[point["date"][: NewsToneSource.DATE_LENGTH]] = float(
                    point["value"]
                )
        return series


if __name__ == "__main__":
    NewsToneFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=NewsToneSource.RATE_LIMIT_IN_SECONDS,
        ),
        WorldCupTeamNameReader(),
    ).fetch_every_team()
