"""Every senior national team competition FootyStats knows.

Unlike club leagues these are reachable without a login. The list holds about
67 competitions with 188 seasons, among them international friendlies from 2015
to 2026, which carry national team odds after the Beat The Bookie dataset ends,
every World Cup qualification of every confederation, the Nations League, the
Africa Cup of Nations, the Gold Cup and the Arab Cup.

The run can be stopped and started again, because a season that is already on
disk is never asked for a second time.
"""

from typing import Any

from wmguru.helpers.constant import FootyStatsInternationalSource, WebRequestSetting
from wmguru.helpers.utils import WebFileDownloader


class FootyStatsInternationalDownloader:
    """One CSV file per competition and season."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def download_every_competition(self) -> tuple[int, int]:
        """Download every season of every senior national team competition.

        A season that is already on disk is never asked for again, so the run
        can be stopped and started as often as needed.

        Returns:
            How many season files were written, and how many came back
            unusable and were skipped.

        Raises:
            SystemExit: When the league list could not be loaded, because
                without it there is nothing to walk.
        """
        competition_list = self._read_competition_list()
        written_count = 0
        failed_count = 0
        for competition in competition_list:
            competition_name = competition.get("name", "")
            if not self._is_a_senior_national_team_competition(competition_name):
                continue
            written, failed = self._download_every_season(competition, competition_name)
            written_count += written
            failed_count += failed
        return written_count, failed_count

    def _read_competition_list(self) -> list[dict[str, Any]]:
        """Ask the league list endpoint which competitions exist.

        Raises:
            SystemExit: When the list could not be loaded, because without it
                there is nothing to walk.
        """
        answer = self._web_file_downloader.download_json(
            FootyStatsInternationalSource.LEAGUE_LIST_URL,
            timeout_in_seconds=FootyStatsInternationalSource.TIMEOUT_IN_SECONDS,
        )
        if not isinstance(answer, dict):
            raise SystemExit("The FootyStats league list could not be loaded.")
        competition_list = answer.get("data", [])
        return competition_list if isinstance(competition_list, list) else []

    def _is_a_senior_national_team_competition(self, competition_name: str) -> bool:
        """Return True when a competition is a senior men national team one."""
        if not competition_name.startswith(FootyStatsInternationalSource.NAME_PREFIX):
            return False
        return not any(
            excluded_part in competition_name
            for excluded_part in FootyStatsInternationalSource.EXCLUDED_NAME_PARTS
        )

    def _download_every_season(
        self, competition: dict[str, Any], competition_name: str
    ) -> tuple[int, int]:
        """Fetch every season of one competition into its own folder."""
        folder = FootyStatsInternationalSource.OUTPUT_ROOT / competition_name.replace(
            FootyStatsInternationalSource.NAME_PREFIX, "", 1
        )
        folder.mkdir(parents=True, exist_ok=True)
        written_count = 0
        failed_count = 0
        for season in competition.get("season", []):
            season_name = self._season_label(season.get("year"))
            target_file = folder / f"{season_name}.csv"
            if target_file.exists():
                continue
            payload = self._web_file_downloader.download_bytes(
                f"{FootyStatsInternationalSource.MATCH_DOWNLOAD_BASE_URL}"
                f"{int(season['id'])}",
                timeout_in_seconds=FootyStatsInternationalSource.TIMEOUT_IN_SECONDS,
            )
            if payload is None or not self._holds_expected_header(payload):
                failed_count += 1
                print(f"  FAIL  {competition_name} {season_name}", flush=True)
                continue
            target_file.write_bytes(payload)
            written_count += 1
            match_count = payload.count(b"\n") - 1
            print(
                f"  OK    {competition_name} {season_name} ({match_count} matches)",
                flush=True,
            )
        return written_count, failed_count

    def _season_label(self, season_year: object) -> str:
        """Build the readable season name, so 2013 becomes 2013-14."""
        text = str(season_year)
        if len(text) == FootyStatsInternationalSource.LONG_SEASON_YEAR_LENGTH:
            return f"{text[:4]}-{text[4:]}"
        return text

    def _holds_expected_header(self, payload: bytes) -> bool:
        """Return True when the answer is a real CSV file and not a web page."""
        first_bytes = payload[
            : FootyStatsInternationalSource.HEADER_SEARCH_LENGTH_IN_BYTES
        ]
        return FootyStatsInternationalSource.HEADER_MARKER in first_bytes


if __name__ == "__main__":
    written, failed = FootyStatsInternationalDownloader(
        WebFileDownloader(
            user_agent=WebRequestSetting.BROWSER_USER_AGENT,
            polite_delay_in_seconds=(
                FootyStatsInternationalSource.POLITE_DELAY_IN_SECONDS
            ),
        )
    ).download_every_competition()
    print(
        f"\n{written} season files written, {failed} failed "
        f"-> {FootyStatsInternationalSource.OUTPUT_ROOT}"
    )
