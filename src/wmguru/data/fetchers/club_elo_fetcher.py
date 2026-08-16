"""The club strength ratings of clubelo.com.

Club Elo rates club strength day by day, back to the 1940s. It serves as
context for player profiles, that is the quality of the club a player abroad
plays in. One snapshot per year on the first of June holds about 630 clubs,
plus the state of today.
"""

from datetime import date

from wmguru.helpers.constant import ClubEloSource, WebRequestSetting
from wmguru.helpers.utils import WebFileDownloader


class ClubEloFetcher:
    """One rating snapshot per year, and the state of today."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def fetch_every_snapshot(self, today: date) -> int:
        """Fetch every snapshot that is not on disk yet, return the file count."""
        ClubEloSource.OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
        written_count = 0
        for snapshot_day in self._snapshot_days(today):
            if self.fetch_one_snapshot(snapshot_day):
                written_count += 1
        print(f"-> {ClubEloSource.OUTPUT_FOLDER}")
        return written_count

    def fetch_one_snapshot(self, snapshot_day: str) -> bool:
        """Return True when the ranking of this day was fetched and written."""
        target_file = ClubEloSource.OUTPUT_FOLDER / (
            ClubEloSource.FILE_NAME_TEMPLATE.format(snapshot_day=snapshot_day)
        )
        if target_file.exists():
            return False

        payload = self._web_file_downloader.download_bytes(
            ClubEloSource.API_BASE_URL + snapshot_day,
            timeout_in_seconds=ClubEloSource.TIMEOUT_IN_SECONDS,
        )
        if payload is None or not payload.startswith(ClubEloSource.CSV_HEADER_MARKER):
            print(f"  FAIL  {snapshot_day}")
            return False

        target_file.write_bytes(payload)
        club_count = payload.count(b"\n") - 1
        print(f"  OK    {snapshot_day} ({club_count} clubs)")
        return True

    def _snapshot_days(self, today: date) -> list[str]:
        """List one day per year, plus today when it is not one of them anyway."""
        days = [
            f"{year}-{ClubEloSource.SNAPSHOT_MONTH_AND_DAY}"
            for year in range(ClubEloSource.FIRST_SNAPSHOT_YEAR, today.year + 1)
        ]
        if today.isoformat() not in days:
            days.append(today.isoformat())
        return days


if __name__ == "__main__":
    ClubEloFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=WebRequestSetting.STANDARD_POLITE_DELAY_IN_SECONDS,
        )
    ).fetch_every_snapshot(date.today())
