"""The match list of a StatsBomb tournament.

Both StatsBomb downloaders, the one for expected goals and the one for line-ups,
start from the same match list, so the request lives in one place.
"""

from typing import Any

from wmguru.helpers.constant import StatsBombSource
from wmguru.helpers.utils import WebFileDownloader


class StatsBombMatchListReader:
    """Every match of one tournament, out of the open data repository."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def read_matches(self, tournament_name: str) -> list[dict[str, Any]]:
        """Return the matches of the tournament, sorted by date. Empty on failure."""
        competition_identifier, season_identifier = (
            StatsBombSource.TOURNAMENT_IDENTIFIER[tournament_name]
        )
        answer = self._web_file_downloader.download_json(
            f"{StatsBombSource.BASE_URL}/matches/"
            f"{competition_identifier}/{season_identifier}.json",
            timeout_in_seconds=StatsBombSource.TIMEOUT_IN_SECONDS,
        )
        if not isinstance(answer, list):
            return []
        return sorted(answer, key=lambda match: str(match.get("match_date")))
