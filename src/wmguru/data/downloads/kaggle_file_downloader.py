"""Named single files out of a Kaggle dataset.

Kaggle can serve one file of a public dataset directly. For a bigger file it
wraps that single file in a ZIP archive, so both cases have to be handled.
"""

from pathlib import Path

from wmguru.helpers.constant import (
    KaggleFileCatalog,
    KaggleSetting,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    WebFileDownloader,
    ZipArchiveExtractor,
)


class KaggleFileDownloader:
    """The named files of a Kaggle dataset, one by one."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        zip_archive_extractor: ZipArchiveExtractor,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._zip_archive_extractor = zip_archive_extractor

    def download_every_source(self) -> int:
        """Fetch every file of every dataset and return how many were written."""
        written_count = 0
        for source in KaggleFileCatalog.ALL_SOURCES:
            for file_name in source.FILE_NAMES:
                if self.download_one_file(source, file_name):
                    written_count += 1
        return written_count

    def download_one_file(self, source: type, file_name: str) -> bool:
        """Return True when this file was fetched and written."""
        target_file = source.OUTPUT_FOLDER / file_name
        if target_file.exists():
            print(f"  SKIP  {file_name} (already there)")
            return False

        payload = self._web_file_downloader.download_bytes(
            self._build_url(source, file_name),
            timeout_in_seconds=source.TIMEOUT_IN_SECONDS,
        )
        if payload is None:
            print(f"  FAIL  {file_name} (nothing came back)")
            return False

        self._write_file(payload, file_name, target_file)
        print(f"  OK    {file_name} ({target_file.stat().st_size / 1e6:.1f} MB)")
        return True

    def _build_url(self, source: type, file_name: str) -> str:
        """Build the address of one request."""
        return (
            f"{KaggleSetting.ARCHIVE_DOWNLOAD_BASE_URL}"
            f"{source.DATASET_REFERENCE}/{file_name}"
        )

    def _write_file(self, payload: bytes, file_name: str, target_file: Path) -> None:
        """Unpack the answer when it is an archive, otherwise write it as it is."""
        target_file.parent.mkdir(parents=True, exist_ok=True)
        if self._zip_archive_extractor.looks_like_zip_archive(payload):
            self._zip_archive_extractor.extract_one_file(
                payload, file_name, target_file
            )
        else:
            target_file.write_bytes(payload)


if __name__ == "__main__":
    KaggleFileDownloader(
        WebFileDownloader(
            user_agent=WebRequestSetting.BROWSER_USER_AGENT,
            polite_delay_in_seconds=WebRequestSetting.STANDARD_POLITE_DELAY_IN_SECONDS,
        ),
        ZipArchiveExtractor(),
    ).download_every_source()
