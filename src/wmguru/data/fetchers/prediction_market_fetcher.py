"""World Cup probabilities from the prediction markets Polymarket and Manifold.

A prediction market price is a crowd forecast outside the bookmaker markets. It
serves as a benchmark and as a divergence signal, market against crowd. Every
run appends a time stamped snapshot to an append only log, the same way the
odds are logged. Free, no key needed.
"""

import json
import urllib.parse
from datetime import UTC, datetime
from typing import Any

from wmguru.helpers.constant import (
    PredictionMarketSource,
    TimeStampFormat,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
)


class PredictionMarketFetcher:
    """One snapshot of both markets, appended to the log."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        output_file: CsvFile,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._output_file = output_file

    def fetch_both_markets(self, fetched_at: datetime) -> int:
        """Append the rows of both markets and return how many there were."""
        stamp = fetched_at.strftime(TimeStampFormat.UTC_TIME_STAMP)
        rows = self._read_polymarket_rows(stamp) + self._read_manifold_rows(stamp)
        self._output_file.append_rows(rows)
        print(f"{len(rows)} market rows appended -> {self._output_file.path}")
        return len(rows)

    def _read_polymarket_rows(self, stamp: str) -> list[list[str]]:
        """Build one row per outcome of every World Cup event on Polymarket."""
        rows: list[list[str]] = []
        seen_events: set[str] = set()
        for search_term in PredictionMarketSource.SEARCH_TERMS:
            answer = self._send_one_search_request(
                PredictionMarketSource.POLYMARKET_SEARCH_URL, search_term
            )
            if not isinstance(answer, dict):
                continue
            for event in answer.get("events", []):
                title = event.get("title", "")
                if not self._is_about_the_world_cup(title):
                    continue
                if event["id"] in seen_events:
                    continue
                seen_events.add(event["id"])
                rows.extend(self._read_polymarket_event(stamp, title, event))
        return rows

    def _read_polymarket_event(
        self, stamp: str, title: str, event: dict[str, Any]
    ) -> list[list[str]]:
        """Read the outcomes and prices of one event, packed as JSON inside JSON.

        Polymarket does not promise that both lists have the same length, so a
        pair that has no partner is dropped rather than raising.
        """
        rows: list[list[str]] = []
        for market in event.get("markets", []):
            outcomes = self._read_nested_list(market.get("outcomes"))
            prices = self._read_nested_list(market.get("outcomePrices"))
            for outcome, price in zip(outcomes, prices, strict=False):
                rows.append(
                    [
                        stamp,
                        PredictionMarketSource.POLYMARKET_NAME,
                        title,
                        market.get("question", ""),
                        outcome,
                        price,
                        str(market.get("volumeNum", "")),
                    ]
                )
        return rows

    def _read_manifold_rows(self, stamp: str) -> list[list[str]]:
        """Build one row per matching Manifold market with a plain probability.

        A market with many choices carries no single probability and would
        need one extra request per choice, so it is left out.
        """
        rows: list[list[str]] = []
        seen_markets: set[str] = set()
        for search_term in PredictionMarketSource.SEARCH_TERMS:
            answer = self._send_one_search_request(
                PredictionMarketSource.MANIFOLD_SEARCH_URL,
                search_term,
                PredictionMarketSource.MANIFOLD_LIMIT_PARAMETER,
            )
            if not isinstance(answer, list):
                continue
            for market in answer:
                question = market.get("question", "")
                if not self._is_about_the_world_cup(question):
                    continue
                if market["id"] in seen_markets:
                    continue
                seen_markets.add(market["id"])
                probability = market.get("probability")
                market_has_many_choices = probability is None
                if market_has_many_choices:
                    continue
                rows.append(
                    [
                        stamp,
                        PredictionMarketSource.MANIFOLD_NAME,
                        question,
                        question,
                        PredictionMarketSource.MANIFOLD_OUTCOME_NAME,
                        f"{probability:.4f}",
                        str(market.get("volume", "")),
                    ]
                )
        return rows

    def _send_one_search_request(
        self, base_url: str, search_term: str, suffix: str = ""
    ) -> Any:
        """Send one search request against one of the two markets."""
        return self._web_file_downloader.download_json(
            base_url + urllib.parse.quote(search_term) + suffix,
            timeout_in_seconds=PredictionMarketSource.TIMEOUT_IN_SECONDS,
        )

    def _is_about_the_world_cup(self, title: str) -> bool:
        """Return True when the title is about the World Cup, not something else."""
        return PredictionMarketSource.TITLE_FILTER in title.lower()

    def _read_nested_list(self, raw_value: Any) -> list[str]:
        """Read a list that Polymarket packed into the answer as a JSON string."""
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else []


if __name__ == "__main__":
    PredictionMarketFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=PredictionMarketSource.POLITE_DELAY_IN_SECONDS,
        ),
        CsvFile(
            PredictionMarketSource.OUTPUT_FILE, PredictionMarketSource.COLUMN_NAMES
        ),
    ).fetch_both_markets(datetime.now(UTC))
