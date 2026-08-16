"""The historical club league odds and results of football-data.co.uk.

The original CSV files are stored unchanged in readable folders. Mapping them
onto the canonical match schema is a later step of the pipeline and is not part
of the download.

Two limits of this source matter (they are repeated in the README that is
written next to the data): it covers national club leagues only and holds no
World Cup or European Championship odds, and closing odds exist only in the
younger seasons.
"""

from pathlib import Path

from wmguru.helpers.constant import (
    FootballDataSource,
    WebRequestSetting,
)
from wmguru.helpers.utils import WebFileDownloader


class FootballDataDownloader:
    """One CSV file per league and season, from football-data.co.uk."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def download_every_league(self) -> int:
        """Fetch main and extra leagues and return how many files were written."""
        FootballDataSource.OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        self._write_read_me()
        print("Loading the main leagues ...", flush=True)
        main_league_count = self.download_main_leagues()
        print("Loading the extra leagues ...", flush=True)
        extra_league_count = self.download_extra_leagues()
        return main_league_count + extra_league_count

    def download_main_leagues(self) -> int:
        """Download one file per league and season, skipping what is on disk."""
        written_count = 0
        season_start_years = range(
            FootballDataSource.OLDEST_SEASON_START_YEAR_ON_THE_SITE,
            FootballDataSource.RUNNING_SEASON_START_YEAR + 1,
        )
        for (
            league_code,
            folder_name,
        ) in FootballDataSource.FOLDER_NAME_OF_MAIN_LEAGUE.items():
            league_folder = (
                FootballDataSource.OUTPUT_ROOT
                / FootballDataSource.MAIN_LEAGUE_FOLDER_NAME
                / folder_name
            )
            league_folder.mkdir(parents=True, exist_ok=True)
            for season_start_year in season_start_years:
                target_file = (
                    league_folder / f"{self._season_label(season_start_year)}.csv"
                )
                url = (
                    f"{FootballDataSource.MAIN_LEAGUE_BASE_URL}/"
                    f"{self._season_code(season_start_year)}/{league_code}.csv"
                )
                if self._download_into(url, target_file, check_header=True):
                    written_count += 1
        return written_count

    def download_extra_leagues(self) -> int:
        """Download one combined file per league, in the other column layout."""
        extra_league_folder = (
            FootballDataSource.OUTPUT_ROOT / FootballDataSource.EXTRA_LEAGUE_FOLDER_NAME
        )
        extra_league_folder.mkdir(parents=True, exist_ok=True)
        written_count = 0
        for (
            league_code,
            file_name,
        ) in FootballDataSource.FILE_NAME_OF_EXTRA_LEAGUE.items():
            target_file = extra_league_folder / f"{file_name}.csv"
            url = f"{FootballDataSource.EXTRA_LEAGUE_BASE_URL}/{league_code}.csv"
            if self._download_into(url, target_file, check_header=False):
                written_count += 1
        return written_count

    def _download_into(self, url: str, target_file: Path, check_header: bool) -> bool:
        """Return True when the file was fetched and written.

        A file that is already on disk is not asked for a second time, which is
        what makes a stopped run cheap to repeat.
        """
        if target_file.exists():
            return False
        payload = self._web_file_downloader.download_bytes(
            url, timeout_in_seconds=FootballDataSource.TIMEOUT_IN_SECONDS
        )
        if payload is None or not self._looks_like_a_usable_file(payload, check_header):
            return False
        target_file.write_bytes(payload)
        print(f"  {target_file.name}  ({target_file.parent.name})", flush=True)
        return True

    def _looks_like_a_usable_file(self, payload: bytes, check_header: bool) -> bool:
        """Return True when the answer is a real file, not a tiny page.

        Some seasons arrive with a byte order marker in front of the header,
        which is why it is stripped before the header is checked.
        """
        if len(payload) <= FootballDataSource.MINIMUM_PLAUSIBLE_FILE_SIZE_IN_BYTES:
            return False
        if not check_header:
            return True
        first_bytes = payload.lstrip(FootballDataSource.BYTE_ORDER_MARKER).lstrip()
        return first_bytes.startswith(FootballDataSource.CSV_HEADER_MARKER)

    def _season_code(self, season_start_year: int) -> str:
        """Build the season code the site uses in its paths, so 2013 becomes 1314."""
        return f"{season_start_year % 100:02d}{(season_start_year + 1) % 100:02d}"

    def _season_label(self, season_start_year: int) -> str:
        """Build the readable season name, so 2013 becomes 2013-14."""
        return f"{season_start_year}-{(season_start_year + 1) % 100:02d}"

    def _write_read_me(self) -> None:
        """Explain the source and its column layout next to the data."""
        first_year = FootballDataSource.OLDEST_SEASON_START_YEAR_ON_THE_SITE
        last_year = FootballDataSource.RUNNING_SEASON_START_YEAR
        text = (
            "Football Betting Odds - football-data.co.uk\n"
            "===========================================\n\n"
            "Source: https://www.football-data.co.uk (free, static CSV files).\n"
            f"Seasons: {first_year}/{(first_year + 1) % 100:02d}"
            f" to {last_year}/{(last_year + 1) % 100:02d}.\n\n"
            "Folders:\n"
            "  main_leagues/  European top leagues, one CSV per season. The column\n"
            "                 layout differs slightly per season, the number of odds\n"
            "                 columns grows over the years.\n"
            "  extra_leagues/ The other leagues, one combined CSV over all seasons,\n"
            "                 with ANOTHER column layout than main_leagues.\n\n"
            "Important columns (main_leagues):\n"
            "  Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR   result after 90 minutes.\n"
            "  PSH/PSD/PSA       Pinnacle 1X2 opening odds, the sharpest market.\n"
            "  PSCH/PSCD/PSCA    Pinnacle 1X2 closing odds, needed for closing line\n"
            "                    value.\n"
            "  AvgH/D/A, AvgCH.. market average, opening and closing.\n"
            "  MaxH/D/A          best available offer, opening.\n"
            "  A column with a C in its name holds closing odds and exists only in\n"
            "  the younger seasons.\n\n"
            "IMPORTANT: this source holds NO World Cup or European Championship odds,\n"
            "only club leagues. For tournament odds see FootyStats, concept 4.2.\n"
        )
        read_me_file = (
            FootballDataSource.OUTPUT_ROOT / FootballDataSource.READ_ME_FILE_NAME
        )
        read_me_file.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    written = FootballDataDownloader(
        WebFileDownloader(
            user_agent=WebRequestSetting.BROWSER_USER_AGENT,
            polite_delay_in_seconds=WebRequestSetting.SHORT_POLITE_DELAY_IN_SECONDS,
            attempt_count=WebRequestSetting.ATTEMPT_WITH_ONE_RETRY,
        )
    ).download_every_league()
    print(f"\nDone: {written} files written.", flush=True)
