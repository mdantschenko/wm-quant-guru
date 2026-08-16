"""Tests for ZipArchiveExtractor in wmguru/helpers/utils.py."""

import io
import zipfile
from pathlib import Path

from wmguru.helpers.utils import ZipArchiveExtractor


def make_archive_with(file_contents: dict[str, str]) -> bytes:
    """Build a ZIP archive in memory, the way a download hands one to us."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for file_name, content in file_contents.items():
            archive.writestr(file_name, content)
    return buffer.getvalue()


def test_a_zip_archive_is_recognised():
    extractor = ZipArchiveExtractor()

    assert extractor.looks_like_zip_archive(make_archive_with({"a.csv": "x"})) is True


def test_a_plain_csv_file_is_not_taken_for_an_archive():
    extractor = ZipArchiveExtractor()

    assert extractor.looks_like_zip_archive(b"Div,HomeTeam,AwayTeam\n") is False


def test_every_file_of_an_archive_is_unpacked(tmp_path: Path):
    payload = make_archive_with({"first.csv": "one", "second.csv": "two"})

    file_count = ZipArchiveExtractor().extract_all_files(payload, tmp_path)

    assert file_count == 2
    assert (tmp_path / "first.csv").read_text() == "one"
    assert (tmp_path / "second.csv").read_text() == "two"


def test_the_target_folder_is_created_when_it_is_missing(tmp_path: Path):
    target_folder = tmp_path / "not" / "there" / "yet"

    ZipArchiveExtractor().extract_all_files(
        make_archive_with({"only.csv": "value"}), target_folder
    )

    assert (target_folder / "only.csv").read_text() == "value"


def test_one_named_file_is_taken_out_of_the_archive(tmp_path: Path):
    payload = make_archive_with({"wanted.csv": "yes", "other.csv": "no"})
    target_file = tmp_path / "players.csv"

    was_written = ZipArchiveExtractor().extract_one_file(
        payload, "wanted.csv", target_file
    )

    assert was_written is True
    assert target_file.read_text() == "yes"


def test_a_file_that_is_not_in_the_archive_is_reported(tmp_path: Path):
    payload = make_archive_with({"other.csv": "no"})

    was_written = ZipArchiveExtractor().extract_one_file(
        payload, "missing.csv", tmp_path / "players.csv"
    )

    assert was_written is False
    assert not (tmp_path / "players.csv").exists()
