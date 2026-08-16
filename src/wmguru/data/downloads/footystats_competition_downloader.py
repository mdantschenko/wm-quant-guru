"""The tournament files of the target tournaments, from FootyStats.

Two files exist per tournament and both use the same competition identifier:
the match file with the pre match odds, and the player file with every player
who was used, including club, nationality, minutes and match rating.

The match file closes the odds gap of the younger tournaments from 2016 to
2024, which neither football-data.co.uk (club leagues only) nor the Beat The
Bookie dataset (ends in the middle of 2015) covers.
"""

from pathlib import Path

from wmguru.helpers.constant import FootyStatsSource, WebRequestSetting
from wmguru.helpers.utils import WebFileDownloader


class FootyStatsCompetitionDownloader:
    """One CSV file per tournament, from FootyStats."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def download_match_odds(self) -> int:
        """Download one match file with pre match odds per tournament."""
        return self._download_every_competition(
            FootyStatsSource.MATCH_DOWNLOAD_BASE_URL,
            FootyStatsSource.MATCH_ODDS_OUTPUT_FOLDER,
            FootyStatsSource.MATCH_ODDS_HEADER_MARKER,
        )

    def download_player_lists(self) -> int:
        """Download one player file per tournament."""
        return self._download_every_competition(
            FootyStatsSource.PLAYER_DOWNLOAD_BASE_URL,
            FootyStatsSource.PLAYER_LIST_OUTPUT_FOLDER,
            FootyStatsSource.PLAYER_LIST_HEADER_MARKER,
        )

    def _download_every_competition(
        self, base_url: str, output_folder: Path, header_marker: bytes
    ) -> int:
        """Walk the tournament list and return how many files were written."""
        output_folder.mkdir(parents=True, exist_ok=True)
        written_count = 0
        for (
            tournament_name,
            competition_identifier,
        ) in FootyStatsSource.COMPETITION_IDENTIFIER_OF_TOURNAMENT.items():
            target_file = output_folder / f"{tournament_name}.csv"
            if target_file.exists():
                print(f"  SKIP  {tournament_name} (already there)")
                continue
            payload = self._web_file_downloader.download_bytes(
                f"{base_url}{competition_identifier}",
                timeout_in_seconds=FootyStatsSource.TIMEOUT_IN_SECONDS,
            )
            if payload is None or not self._holds_expected_header(
                payload, header_marker
            ):
                print(
                    f"  FAIL  {tournament_name} "
                    f"(competition {competition_identifier}, no usable file)"
                )
                continue
            target_file.write_bytes(payload)
            written_count += 1
            line_count = payload.count(b"\n")
            print(f"  OK    {tournament_name}.csv ({line_count} lines)")
        return written_count

    def _holds_expected_header(self, payload: bytes, header_marker: bytes) -> bool:
        """Return True when the answer is a real CSV file and not a web page."""
        first_bytes = payload[: FootyStatsSource.HEADER_SEARCH_LENGTH_IN_BYTES]
        return header_marker in first_bytes


if __name__ == "__main__":
    downloader = FootyStatsCompetitionDownloader(
        WebFileDownloader(
            user_agent=WebRequestSetting.BROWSER_USER_AGENT,
            polite_delay_in_seconds=WebRequestSetting.STANDARD_POLITE_DELAY_IN_SECONDS,
        )
    )
    print("Loading the tournament odds ...")
    odds_file_count = downloader.download_match_odds()
    print("Loading the tournament player lists ...")
    player_file_count = downloader.download_player_lists()
    print(f"\nDone: {odds_file_count} odds files, {player_file_count} player files.")
