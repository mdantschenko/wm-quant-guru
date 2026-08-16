"""The free Football Manager player databases on Kaggle.

Sports Interactive runs one of the largest scouting networks in the world. Its
databases carry about fifty attributes per player, among them the mental scale
(determination, composure, leadership, decisions) that the EA ratings do not
show at all. Each edition is a ZIP archive from which exactly one player file
is taken.
"""

from wmguru.helpers.constant import (
    FootballManagerSource,
    KaggleSetting,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    WebFileDownloader,
    ZipArchiveExtractor,
)


class FootballManagerDownloader:
    """One player file per Football Manager edition."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        zip_archive_extractor: ZipArchiveExtractor,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._zip_archive_extractor = zip_archive_extractor

    def download_every_edition(self) -> int:
        """Fetch every edition and return how many player files were written."""
        written_count = 0
        for edition_name in FootballManagerSource.DATASET_REFERENCE_OF_EDITION:
            if self.download_one_edition(edition_name):
                written_count += 1
        return written_count

    def download_one_edition(self, edition_name: str) -> bool:
        """Return True when this edition was fetched and written."""
        target_file = self._build_target_file(edition_name)
        if target_file.exists():
            print(f"  SKIP  {edition_name} (already there)")
            return False

        url = (
            KaggleSetting.ARCHIVE_DOWNLOAD_BASE_URL
            + FootballManagerSource.DATASET_REFERENCE_OF_EDITION[edition_name]
        )
        payload = self._web_file_downloader.download_bytes(
            url, timeout_in_seconds=FootballManagerSource.TIMEOUT_IN_SECONDS
        )
        if payload is None:
            print(f"  FAIL  {edition_name} (nothing came back)")
            return False

        name_inside_archive = (
            FootballManagerSource.PLAYER_FILE_NAME_INSIDE_ARCHIVE_OF_EDITION[
                edition_name
            ]
        )
        if not self._zip_archive_extractor.extract_one_file(
            payload, name_inside_archive, target_file
        ):
            print(f"  FAIL  {edition_name} ({name_inside_archive} not in the archive)")
            return False

        print(
            f"  OK    {edition_name}: {target_file} "
            f"({target_file.stat().st_size / 1e6:.1f} MB)"
        )
        return True

    def _build_target_file(self, edition_name: str):
        """Build the path of one edition, in its own folder under a readable name."""
        file_name = FootballManagerSource.PLAYER_FILE_NAME_TEMPLATE.format(
            edition_name_in_lower_case=edition_name.lower()
        )
        return FootballManagerSource.OUTPUT_ROOT / edition_name / file_name


if __name__ == "__main__":
    FootballManagerDownloader(
        WebFileDownloader(
            user_agent=WebRequestSetting.BROWSER_USER_AGENT,
            polite_delay_in_seconds=WebRequestSetting.STANDARD_POLITE_DELAY_IN_SECONDS,
        ),
        ZipArchiveExtractor(),
    ).download_every_edition()
