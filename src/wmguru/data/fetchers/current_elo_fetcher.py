"""The current rating of every national team, from eloratings.net.

This one runs during the tournament. The historical dataset ends in 2025, so
this fetcher pulls the live table together with the team name mapping and
writes a snapshot stamped with its date, which can be stored before every match
day without breaking the rule that nothing may look into the future.
"""

from datetime import date

from wmguru.helpers.constant import (
    CsvFileSetting,
    NationalEloSource,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
)


class CurrentEloFetcher:
    """One dated snapshot of the live rating table."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def fetch_snapshot(self, today: date) -> int:
        """Write one dated snapshot of the live rating table.

        Args:
            today: The day the snapshot belongs to. It names the file, so a
                snapshot taken before a match day can never be mistaken for a
                later one.

        Returns:
            How many teams the table held.

        Raises:
            SystemExit: When the rating table or the name table could not be
                loaded. A half written snapshot would be worse than none.
        """
        team_names = self._read_team_names()
        rating_rows = self._read_rating_rows(team_names)

        target_file = NationalEloSource.OUTPUT_FOLDER / (
            NationalEloSource.FILE_NAME_TEMPLATE.format(today=today.isoformat())
        )
        with CsvFile(
            target_file, NationalEloSource.COLUMN_NAMES
        ).writing_writer() as writer:
            writer.writerows(rating_rows)
        print(f"{len(rating_rows)} teams (live rating) -> {target_file}")
        return len(rating_rows)

    def _read_team_names(self) -> dict[str, str]:
        """Read the readable team name that belongs to every team code."""
        team_names: dict[str, str] = {}
        for line in self._read_lines(NationalEloSource.TEAM_NAME_URL):
            parts = line.split(NationalEloSource.COLUMN_SEPARATOR)
            if len(parts) >= NationalEloSource.SMALLEST_USABLE_NAME_ROW:
                team_names[parts[0]] = parts[1]
        return team_names

    def _read_rating_rows(self, team_names: dict[str, str]) -> list[list[str]]:
        """Build one output row per team of the live table."""
        rows: list[list[str]] = []
        for line in self._read_lines(NationalEloSource.RATING_URL):
            parts = line.split(NationalEloSource.COLUMN_SEPARATOR)
            if len(parts) < NationalEloSource.SMALLEST_USABLE_RATING_ROW:
                continue
            team_code = parts[2]
            rows.append(
                [parts[0], team_code, team_names.get(team_code, team_code), parts[3]]
            )
        return rows

    def _read_lines(self, url: str) -> list[str]:
        """Read a tab separated file as a list of lines.

        Raises:
            SystemExit: When the file could not be loaded, because the whole
                run is about that one table.
        """
        payload = self._web_file_downloader.download_bytes(
            url, timeout_in_seconds=NationalEloSource.TIMEOUT_IN_SECONDS
        )
        if payload is None:
            raise SystemExit(f"The live rating table could not be loaded: {url}")
        return payload.decode(CsvFileSetting.ENCODING).splitlines()


if __name__ == "__main__":
    CurrentEloFetcher(
        WebFileDownloader(user_agent=WebRequestSetting.BROWSER_USER_AGENT)
    ).fetch_snapshot(date.today())
