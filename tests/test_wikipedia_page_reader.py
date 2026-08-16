"""Tests for WikipediaPageReader in wmguru/helpers/utils.py.

The reader gets its downloader handed in, so these tests replace it with a stub
and never touch the network.
"""

from typing import Any

from wmguru.helpers.utils import WikipediaPageReader


class DownloaderStub:
    """Stands in for WebFileDownloader and answers with a fixed value."""

    def __init__(self, answer: Any) -> None:
        self._answer = answer
        self.asked_for_url = ""

    def download_json(self, url: str, timeout_in_seconds: int | None = None) -> Any:
        """Remember which address was asked for and answer with the fixed value."""
        self.asked_for_url = url
        return self._answer


def test_the_wikitext_is_read_out_of_the_answer():
    stub = DownloaderStub({"parse": {"wikitext": "== Group A =="}})

    wikitext = WikipediaPageReader(stub).read_wikitext("2026 FIFA World Cup")

    assert wikitext == "== Group A =="


def test_the_page_title_is_put_into_the_url():
    stub = DownloaderStub({"parse": {"wikitext": ""}})

    WikipediaPageReader(stub).read_wikitext("2026 FIFA World Cup squads")

    assert "2026%20FIFA%20World%20Cup%20squads" in stub.asked_for_url


def test_a_failed_download_gives_no_wikitext():
    assert WikipediaPageReader(DownloaderStub(None)).read_wikitext("Any page") is None


def test_an_answer_without_a_parse_part_gives_no_wikitext():
    stub = DownloaderStub({"error": {"code": "missingtitle"}})

    assert WikipediaPageReader(stub).read_wikitext("Does not exist") is None


def test_an_answer_with_a_broken_wikitext_gives_no_wikitext():
    stub = DownloaderStub({"parse": {"wikitext": ["not", "a", "text"]}})

    assert WikipediaPageReader(stub).read_wikitext("Any page") is None
