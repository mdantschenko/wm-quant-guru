"""The Kaggle datasets that come as one ZIP archive and are unpacked whole.

This replaces ten near identical scripts. The only thing that differed between
them was the dataset reference, the target folder and the file pattern that says
"already downloaded", and all three now live in constant.py. Kaggle serves
public datasets without an account, so no token is needed.
"""

from wmguru.helpers.constant import (
    KaggleArchiveCatalog,
    KaggleSetting,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    WebFileDownloader,
    ZipArchiveExtractor,
)


class KaggleArchiveDownloader:
    """A Kaggle dataset as a ZIP archive, unpacked into its folder."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        zip_archive_extractor: ZipArchiveExtractor,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._zip_archive_extractor = zip_archive_extractor

    def download_every_source(self) -> int:
        """Fetch every dataset of the catalog and return how many were written."""
        written_count = 0
        for source in KaggleArchiveCatalog.ALL_SOURCES:
            if self.download_one_source(source):
                written_count += 1
        return written_count

    def download_one_source(self, source: type) -> bool:
        """Return True when this dataset was fetched and unpacked."""
        if self._is_already_on_disk(source):
            print(f"  SKIP  {source.DATASET_REFERENCE} (already there)")
            return False

        url = KaggleSetting.ARCHIVE_DOWNLOAD_BASE_URL + source.DATASET_REFERENCE
        payload = self._web_file_downloader.download_bytes(
            url, timeout_in_seconds=source.TIMEOUT_IN_SECONDS
        )
        if payload is None or not self._zip_archive_extractor.looks_like_zip_archive(
            payload
        ):
            print(f"  FAIL  {source.DATASET_REFERENCE} (no archive came back)")
            return False

        file_count = self._zip_archive_extractor.extract_all_files(
            payload, source.OUTPUT_FOLDER
        )
        print(
            f"  OK    {source.DATASET_REFERENCE}: {file_count} files "
            f"-> {source.OUTPUT_FOLDER}"
        )
        return True

    def _is_already_on_disk(self, source: type) -> bool:
        """Return True when the folder already holds the expected files."""
        if not source.OUTPUT_FOLDER.exists():
            return False
        return any(source.OUTPUT_FOLDER.glob(source.ALREADY_DOWNLOADED_PATTERN))


if __name__ == "__main__":
    KaggleArchiveDownloader(
        WebFileDownloader(
            user_agent=WebRequestSetting.BROWSER_USER_AGENT,
            polite_delay_in_seconds=WebRequestSetting.STANDARD_POLITE_DELAY_IN_SECONDS,
        ),
        ZipArchiveExtractor(),
    ).download_every_source()
