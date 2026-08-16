"""The coach history of every national team, from Wikidata.

Wikidata keeps the head coach of every national team with a start and an end
date. That is the cleanest free source for coach features: time in office at
the start of a tournament, how often the coach changed, and caretaker spells.

The team identifiers are resolved over the Wikipedia articles in batches, after
that one single query returns every coach of every team.
"""

import csv
import urllib.parse
from typing import Any

from wmguru.helpers.constant import (
    CoachHistorySource,
    ComputedFeaturePath,
    CsvFileSetting,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
)


class CoachHistoryFetcher:
    """One row per team and spell in office."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def fetch_every_coach(self) -> int:
        """Write the file and return how many spells it holds."""
        article_titles = self._build_article_titles()
        team_identifiers = self._resolve_team_identifiers(article_titles)
        self._report_countries_without_an_identifier(article_titles, team_identifiers)

        rows = self._read_coach_spells(team_identifiers)
        rows.sort(key=lambda row: (row[0], row[2]))

        with CsvFile(
            CoachHistorySource.OUTPUT_FILE, CoachHistorySource.COLUMN_NAMES
        ).writing_writer() as writer:
            writer.writerows(rows)
        print(
            f"{len(rows)} spells in office for {len(team_identifiers)} teams "
            f"-> {CoachHistorySource.OUTPUT_FILE}"
        )
        return len(rows)

    def _build_article_titles(self) -> dict[str, str]:
        """Build the Wikipedia article title of the national team of every country."""
        with ComputedFeaturePath.COUNTRY_CLIMATE_FILE.open(
            encoding=CsvFileSetting.ENCODING, newline=CsvFileSetting.NEW_LINE
        ) as file_handle:
            countries = sorted(row["country"] for row in csv.DictReader(file_handle))
        return {
            country: CoachHistorySource.ARTICLE_TITLE_OVERRIDES.get(
                country,
                CoachHistorySource.ARTICLE_TITLE_TEMPLATE.format(country=country),
            )
            for country in countries
        }

    def _resolve_team_identifiers(
        self, article_titles: dict[str, str]
    ) -> dict[str, str]:
        """Resolve every country to its Wikidata identifier, in batches.

        A title that Wikipedia redirects is followed, so the country behind the
        original title is the one that gets the identifier.
        """
        title_to_country = {title: country for country, title in article_titles.items()}
        all_titles = list(title_to_country)
        team_identifiers: dict[str, str] = {}
        for start in range(
            0,
            len(all_titles),
            CoachHistorySource.LARGEST_TITLE_BATCH_THE_ENDPOINT_TAKES,
        ):
            batch = all_titles[
                start : start
                + CoachHistorySource.LARGEST_TITLE_BATCH_THE_ENDPOINT_TAKES
            ]
            answer = self._web_file_downloader.download_json(
                self._build_identifier_url(batch),
                timeout_in_seconds=CoachHistorySource.TIMEOUT_IN_SECONDS,
            )
            team_identifiers.update(
                self._read_identifiers_of_one_batch(answer, title_to_country)
            )
        return team_identifiers

    def _build_identifier_url(self, batch: list[str]) -> str:
        """Ask the Wikipedia endpoint for the Wikidata item of many titles."""
        joined_titles = urllib.parse.quote("|".join(batch))
        return (
            f"{CoachHistorySource.WIKIPEDIA_API_URL}?action=query&prop=pageprops"
            f"&ppprop=wikibase_item&redirects=1&format=json&formatversion=2"
            f"&titles={joined_titles}"
        )

    def _read_identifiers_of_one_batch(
        self, answer: Any, title_to_country: dict[str, str]
    ) -> dict[str, str]:
        """Read the identifiers out of one answer, undoing the redirects."""
        if not isinstance(answer, dict):
            return {}
        query_result = answer.get("query", {})
        redirected_from = {
            redirect["to"]: redirect["from"]
            for redirect in query_result.get("redirects", [])
        }
        identifiers: dict[str, str] = {}
        for page in query_result.get("pages", []):
            identifier = page.get("pageprops", {}).get("wikibase_item")
            title = page.get("title", "")
            asked_title = redirected_from.get(title, title)
            country = title_to_country.get(asked_title)
            if identifier and country:
                identifiers[country] = identifier
        return identifiers

    def _read_coach_spells(self, team_identifiers: dict[str, str]) -> list[list[str]]:
        """Read every coach with start and end for every team, in one query."""
        if not team_identifiers:
            return []
        identifier_to_country = {
            identifier: country for country, identifier in team_identifiers.items()
        }
        query = CoachHistorySource.SPARQL_QUERY_TEMPLATE.format(
            team_identifiers=" ".join(
                f"wd:{identifier}" for identifier in team_identifiers.values()
            )
        )
        answer = self._web_file_downloader.download_json(
            f"{CoachHistorySource.SPARQL_URL}?format=json"
            f"&query={urllib.parse.quote(query)}",
            timeout_in_seconds=CoachHistorySource.TIMEOUT_IN_SECONDS,
        )
        return self._read_spell_rows(answer, identifier_to_country)

    def _read_spell_rows(
        self, answer: Any, identifier_to_country: dict[str, str]
    ) -> list[list[str]]:
        """Build one row per statement of the query answer."""
        if not isinstance(answer, dict):
            return []
        rows: list[list[str]] = []
        for statement in answer.get("results", {}).get("bindings", []):
            identifier = statement["team"]["value"].rsplit("/", 1)[-1]
            rows.append(
                [
                    identifier_to_country.get(identifier, identifier),
                    statement.get("coachLabel", {}).get("value", ""),
                    statement.get("start", {}).get("value", "")[
                        : CoachHistorySource.DATE_LENGTH
                    ],
                    statement.get("end", {}).get("value", "")[
                        : CoachHistorySource.DATE_LENGTH
                    ],
                ]
            )
        return rows

    def _report_countries_without_an_identifier(
        self, article_titles: dict[str, str], team_identifiers: dict[str, str]
    ) -> None:
        """Name the countries whose article could not be resolved."""
        missing = sorted(set(article_titles) - set(team_identifiers))
        if not missing:
            return
        shown = missing[: CoachHistorySource.REPORTED_MISSING_COUNTRY_COUNT]
        print(f"  Without an identifier ({len(missing)}): {', '.join(shown)} ...")


if __name__ == "__main__":
    CoachHistoryFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=WebRequestSetting.STANDARD_POLITE_DELAY_IN_SECONDS,
        )
    ).fetch_every_coach()
