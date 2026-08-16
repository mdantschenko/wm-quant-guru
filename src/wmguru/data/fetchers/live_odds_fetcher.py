"""Live odds from The Odds API, logged so nothing can be rewritten.

This one runs during the tournament, for mode A of the concept: take an odds
snapshot at a defined moment and log it before kick off. Every run stores the
raw answer as a time stamped JSON file and appends the 1X2 odds of every
bookmaker to an append only log.

The key is free at the-odds-api.com, its free tier allows 500 requests a month.
It belongs in an environment variable, never in the code and never in git.

Two modes:
    python -m wmguru.data.fetchers.live_odds_fetcher sports  list competitions
    python -m wmguru.data.fetchers.live_odds_fetcher odds    take a snapshot
"""

import json
import sys
from datetime import UTC, datetime
from typing import Any

from wmguru.helpers.constant import (
    CsvFileSetting,
    LiveOddsSource,
    TimeStampFormat,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    ApiKeyReader,
    CsvFile,
    WebFileDownloader,
)

SIGN_UP_URL = "https://the-odds-api.com"


class LiveOddsFetcher:
    """One odds snapshot, or the list of competitions the endpoint knows."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        api_key_reader: ApiKeyReader,
        output_file: CsvFile,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._api_key_reader = api_key_reader
        self._output_file = output_file

    def list_competitions(self) -> int:
        """Print every football competition the endpoint knows.

        Run this before the tournament to check the sport key, the endpoint
        renames a competition now and then.

        Returns:
            How many competitions were printed.

        Raises:
            SystemExit: When no API key is set up.
        """
        answer = self._ask(f"sports?all=true&apiKey={self._read_key()}")
        competitions = answer if isinstance(answer, list) else []
        shown_count = 0
        for competition in competitions:
            key = str(competition.get("key", ""))
            if key.startswith(LiveOddsSource.SOCCER_KEY_PREFIX):
                print(f"  {key:<40} {competition.get('title', '')}")
                shown_count += 1
        self._report_quota()
        return shown_count

    def fetch_odds_snapshot(self, fetched_at: datetime) -> int:
        """Take one odds snapshot and log it so it cannot be rewritten later.

        Args:
            fetched_at: The moment of the snapshot. It is stamped into every
                log row and into the name of the raw file, so a backtest can
                tell how long before kick off the odds were taken.

        Returns:
            How many odds rows were appended, that is one per match and
            bookmaker.

        Raises:
            SystemExit: When no API key is set up, or when the endpoint did
                not answer with a match list.
        """
        stamp = fetched_at.strftime(TimeStampFormat.UTC_TIME_STAMP)
        events = self._ask(
            f"sports/{LiveOddsSource.SPORT_KEY}/odds"
            f"?regions={LiveOddsSource.REGIONS}&markets={LiveOddsSource.MARKETS}"
            f"&oddsFormat={LiveOddsSource.ODDS_FORMAT}&apiKey={self._read_key()}"
        )
        if not isinstance(events, list):
            raise SystemExit("The odds endpoint did not answer with a match list.")

        raw_file = self._store_raw_answer(events, stamp)
        rows = [row for event in events for row in self._flatten_event(event, stamp)]
        self._output_file.append_rows(rows)

        print(
            f"{len(events)} matches, {len(rows)} odds rows -> {self._output_file.path}"
        )
        print(f"Raw snapshot: {raw_file}")
        self._report_quota()
        return len(rows)

    def _read_key(self) -> str:
        """Read the key that every request to this endpoint needs.

        Raises:
            SystemExit: When no key is set up, with the message that says how
                to set one up.
        """
        key = self._api_key_reader.read_key(LiveOddsSource.API_KEY_ENVIRONMENT_VARIABLE)
        if not key:
            raise SystemExit(
                self._api_key_reader.explain_how_to_set_the_key(
                    LiveOddsSource.API_KEY_ENVIRONMENT_VARIABLE, SIGN_UP_URL
                )
            )
        return key

    def _ask(self, path_with_parameters: str) -> Any:
        """Send one request against the endpoint."""
        return self._web_file_downloader.download_json(
            f"{LiveOddsSource.BASE_URL}/{path_with_parameters}",
            timeout_in_seconds=LiveOddsSource.TIMEOUT_IN_SECONDS,
        )

    def _store_raw_answer(self, events: list[Any], stamp: str) -> Any:
        """Keep the untouched answer, so a later reading can be checked."""
        raw_folder = LiveOddsSource.OUTPUT_FOLDER / LiveOddsSource.RAW_SUBFOLDER_NAME
        raw_folder.mkdir(parents=True, exist_ok=True)
        raw_file = raw_folder / LiveOddsSource.RAW_FILE_NAME_TEMPLATE.format(
            sport_key=LiveOddsSource.SPORT_KEY,
            stamp=stamp.replace(":", "").replace("-", ""),
        )
        raw_file.write_text(
            json.dumps(events, indent=1), encoding=CsvFileSetting.ENCODING
        )
        return raw_file

    def _flatten_event(self, event: dict[str, Any], stamp: str) -> list[list[str]]:
        """Build one log row per bookmaker of one match."""
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")
        rows: list[list[str]] = []
        for bookmaker in event.get("bookmakers", []):
            price_of = self._read_prices(bookmaker)
            rows.append(
                [
                    stamp,
                    LiveOddsSource.SPORT_KEY,
                    event.get("commence_time", ""),
                    home_team,
                    away_team,
                    bookmaker.get("key", ""),
                    price_of.get(home_team, ""),
                    price_of.get(LiveOddsSource.DRAW_OUTCOME_NAME, ""),
                    price_of.get(away_team, ""),
                ]
            )
        return rows

    def _read_prices(self, bookmaker: dict[str, Any]) -> dict[str, str]:
        """Read the price of every outcome of the plain win draw win market."""
        prices: dict[str, str] = {}
        for market in bookmaker.get("markets", []):
            if market.get("key") != LiveOddsSource.MARKETS:
                continue
            for outcome in market.get("outcomes", []):
                prices[outcome.get("name", "")] = str(outcome.get("price", ""))
        return prices

    def _report_quota(self) -> None:
        """Print how many requests the endpoint says are left."""
        headers = self._web_file_downloader.headers_of_the_last_answer
        remaining = headers.get("x-requests-remaining", "?")
        print(f"Quota: {remaining} requests left (free tier: 500 a month).")


if __name__ == "__main__":
    fetcher = LiveOddsFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=0,
        ),
        ApiKeyReader(),
        CsvFile(
            LiveOddsSource.OUTPUT_FOLDER / LiveOddsSource.LOG_FILE_NAME,
            LiveOddsSource.COLUMN_NAMES,
        ),
    )
    chosen_mode = sys.argv[1] if len(sys.argv) > 1 else LiveOddsSource.ODDS_MODE
    if chosen_mode == LiveOddsSource.SPORTS_MODE:
        fetcher.list_competitions()
    else:
        fetcher.fetch_odds_snapshot(datetime.now(UTC))
