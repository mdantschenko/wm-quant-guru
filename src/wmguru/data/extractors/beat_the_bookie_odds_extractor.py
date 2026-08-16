"""The matches we care about, out of the Beat The Bookie odds dataset.

The dataset mixes club leagues, national teams and UEFA club competitions in
one file. Which of them a run keeps is decided by the set of competition names
that is handed in, so the same reading logic serves both the international
matches and the UEFA club matches. The old scripts had this logic twice and one
of them changed the filter of the other at run time to reuse it.

Two shapes come out:
  - closing odds 2005 to 2015, the source rows filtered and nothing else,
  - opening and closing odds for 2016, boiled down out of the hourly series.
"""

import contextlib
import csv
import gzip
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from wmguru.helpers.constant import (
    BeatTheBookieSource,
    InternationalOddsExtract,
    UefaClubOddsExtract,
)
from wmguru.helpers.data_class import OutcomeOddsSummary
from wmguru.helpers.utils import CsvFile, TextNormalizer


class BeatTheBookieOddsExtractor:
    """The dataset, filtered down to one group of competitions."""

    def __init__(self, text_normalizer: TextNormalizer) -> None:
        self._text_normalizer = text_normalizer

    def extract_closing_odds(
        self, allowed_competitions: frozenset[str], target_file: Path
    ) -> int:
        """Copy the matching rows of the closing odds file, unchanged."""
        kept_rows: list[list[str]] = []
        competition_counter: Counter[str] = Counter()
        with self._open_source(
            BeatTheBookieSource.CLOSING_ODDS_FILE,
            BeatTheBookieSource.CLOSING_ODDS_ENCODING,
        ) as reader:
            header = next(reader)
            league_position = header.index(BeatTheBookieSource.LEAGUE_COLUMN)
            for row in reader:
                if len(row) <= league_position:
                    continue
                league_name = row[league_position].strip()
                if self._is_a_wanted_competition(league_name, allowed_competitions):
                    kept_rows.append(row)
                    competition_counter[league_name] += 1

        CsvFile(target_file, tuple(header)).write_rows(kept_rows)
        self._report_what_came_out(kept_rows, header, competition_counter, target_file)
        return len(kept_rows)

    def extract_opening_and_closing_odds(
        self, allowed_competitions: frozenset[str], target_file: Path
    ) -> int:
        """Boil the hourly series of 2016 down to one row per match."""
        match_details = self._read_match_details(allowed_competitions)
        output_file = CsvFile(target_file, self._build_column_names())
        written_count = 0
        with (
            self._open_source(
                BeatTheBookieSource.SERIES_ODDS_FILE,
                BeatTheBookieSource.SERIES_ENCODING,
            ) as reader,
            output_file.writing_writer() as writer,
        ):
            columns_of_outcome = self._find_the_columns_of_every_bookmaker(next(reader))
            for row in reader:
                match_identifier = row[
                    BeatTheBookieSource.MATCH_IDENTIFIER_POSITION
                ].strip()
                details = match_details.get(match_identifier)
                if details is None:
                    continue
                summaries = {
                    outcome: self._summarise_outcome(row, columns_of_outcome[outcome])
                    for outcome in BeatTheBookieSource.OUTCOMES
                }
                if not any(summary.has_any_odds for summary in summaries.values()):
                    continue
                writer.writerow(
                    self._build_the_row_of_one_match(
                        match_identifier, details, summaries
                    )
                )
                written_count += 1
        print(f"{written_count} matches with opening and closing odds -> {target_file}")
        return written_count

    def _is_a_wanted_competition(
        self, league_name: str, allowed_competitions: frozenset[str]
    ) -> bool:
        """Return True when the competition name matches exactly, not just partly."""
        competition = self._text_normalizer.competition_out_of_league_name(league_name)
        return competition in allowed_competitions

    def _read_match_details(
        self, allowed_competitions: frozenset[str]
    ) -> dict[str, list[str]]:
        """Match identifier -> league, teams, score and kick off."""
        details: dict[str, list[str]] = {}
        with self._open_source(
            BeatTheBookieSource.SERIES_MATCH_FILE, BeatTheBookieSource.SERIES_ENCODING
        ) as reader:
            self._skip_the_header(reader)
            for row in reader:
                if len(row) < BeatTheBookieSource.SMALLEST_USABLE_MATCH_ROW:
                    continue
                league_name = row[BeatTheBookieSource.LEAGUE_POSITION].strip()
                if not self._is_a_wanted_competition(league_name, allowed_competitions):
                    continue
                details[row[BeatTheBookieSource.MATCH_IDENTIFIER_POSITION].strip()] = [
                    league_name,
                    row[BeatTheBookieSource.HOME_TEAM_POSITION].strip(),
                    row[BeatTheBookieSource.AWAY_TEAM_POSITION].strip(),
                    row[BeatTheBookieSource.SCORE_POSITION].strip(),
                    row[BeatTheBookieSource.KICK_OFF_POSITION].strip(),
                ]
        return details

    def _skip_the_header(self, reader: Any) -> None:
        """Step over the first line, which names the columns."""
        next(reader)

    def _find_the_columns_of_every_bookmaker(
        self, header: list[str]
    ) -> dict[str, list[list[int]]]:
        """Map every outcome to its column positions per bookmaker, in time order.

        A column is named like home_b3_17, that is outcome, bookmaker and hour.
        """
        hours_of_bookmaker: dict[str, dict[int, list[tuple[int, int]]]] = {
            outcome: {} for outcome in BeatTheBookieSource.OUTCOMES
        }
        for position, column_name in enumerate(header):
            parts = column_name.strip().split("_")
            if len(parts) != BeatTheBookieSource.COLUMN_NAME_PART_COUNT:
                continue
            if parts[0] not in hours_of_bookmaker:
                continue
            bookmaker = int(parts[1].lstrip(BeatTheBookieSource.BOOKMAKER_PREFIX))
            hour = int(parts[2])
            hours_of_bookmaker[parts[0]].setdefault(bookmaker, []).append(
                (hour, position)
            )
        return {
            outcome: [
                [position for _, position in sorted(hours)]
                for _, hours in sorted(bookmakers.items())
            ]
            for outcome, bookmakers in hours_of_bookmaker.items()
        }

    def _summarise_outcome(
        self, row: list[str], columns_of_bookmakers: list[list[int]]
    ) -> OutcomeOddsSummary:
        """Summarise the first and the last priced point of every bookmaker."""
        opening_odds: list[float] = []
        closing_odds: list[float] = []
        for columns in columns_of_bookmakers:
            series = self._read_the_day_and_value_pairs(row, columns)
            if series:
                opening_odds.append(series[0])
                closing_odds.append(series[-1])
        if not closing_odds:
            return OutcomeOddsSummary(None, None, None, 0)
        return OutcomeOddsSummary(
            average_opening_odds=self._rounded_average(opening_odds),
            average_closing_odds=self._rounded_average(closing_odds),
            highest_closing_odds=round(
                max(closing_odds), BeatTheBookieSource.DECIMAL_PLACES
            ),
            bookmaker_count=len(closing_odds),
        )

    def _read_the_day_and_value_pairs(
        self, row: list[str], columns: list[int]
    ) -> list[float]:
        """Read the day and value pairs, or nothing when the query gave nothing back.

        Odds of one or below are not a price, they mark an empty cell.
        """
        series = [
            float(row[position])
            for position in columns
            if position < len(row)
            and row[position] not in BeatTheBookieSource.MISSING_VALUE_TEXTS
        ]
        return [
            value
            for value in series
            if value > BeatTheBookieSource.LOWEST_POSSIBLE_ODDS
        ]

    def _rounded_average(self, values: list[float]) -> float:
        """Average over the bookmakers, cut to a readable number of digits."""
        return round(sum(values) / len(values), BeatTheBookieSource.DECIMAL_PLACES)

    def _build_column_names(self) -> tuple[str, ...]:
        """Build the base columns plus three columns per outcome."""
        return (
            BeatTheBookieSource.OPEN_CLOSE_BASE_COLUMN_NAMES
            + tuple(f"avg_open_{outcome}" for outcome in BeatTheBookieSource.OUTCOMES)
            + tuple(f"avg_close_{outcome}" for outcome in BeatTheBookieSource.OUTCOMES)
            + tuple(f"max_close_{outcome}" for outcome in BeatTheBookieSource.OUTCOMES)
        )

    def _build_the_row_of_one_match(
        self,
        match_identifier: str,
        details: list[str],
        summaries: dict[str, OutcomeOddsSummary],
    ) -> list[Any]:
        """Build one output row."""
        league_name, home_team, away_team, score, kick_off = details
        outcomes = BeatTheBookieSource.OUTCOMES
        return (
            [
                match_identifier,
                league_name,
                kick_off,
                home_team,
                away_team,
                score,
                max(summaries[outcome].bookmaker_count for outcome in outcomes),
            ]
            + [summaries[outcome].average_opening_odds for outcome in outcomes]
            + [summaries[outcome].average_closing_odds for outcome in outcomes]
            + [summaries[outcome].highest_closing_odds for outcome in outcomes]
        )

    @contextlib.contextmanager
    def _open_source(self, source_file: Path, encoding: str) -> Iterator[Any]:
        """Open one packed dataset file for reading, row by row."""
        with gzip.open(
            source_file,
            mode=BeatTheBookieSource.READ_TEXT_MODE,
            encoding=encoding,
            newline="",
        ) as file_handle:
            yield csv.reader(file_handle)

    def _report_what_came_out(
        self,
        rows: list[list[str]],
        header: list[str],
        competition_counter: Counter[str],
        target_file: Path,
    ) -> None:
        """Say what came out, split by competition and by year."""
        print(f"Filtered: {len(rows)} matches -> {target_file}")
        print("\nCompetitions:")
        for league_name, count in competition_counter.most_common():
            print(f"  {count:>6}  {league_name}")
        if BeatTheBookieSource.MATCH_DATE_COLUMN not in header:
            return
        date_position = header.index(BeatTheBookieSource.MATCH_DATE_COLUMN)
        years = Counter(
            self._read_the_year_of_the_date_column(row, date_position) for row in rows
        )
        print("\nMatches per year:")
        for year in sorted(years):
            print(f"  {year}: {years[year]}")

    def _read_the_year_of_the_date_column(
        self, row: list[str], date_position: int
    ) -> str:
        """Read the year out of the date column."""
        found = re.match(BeatTheBookieSource.YEAR_PATTERN, row[date_position])
        return found.group(1) if found else BeatTheBookieSource.UNKNOWN_YEAR


if __name__ == "__main__":
    extractor = BeatTheBookieOddsExtractor(TextNormalizer())
    print("International matches, closing odds 2005 to 2015 ...")
    extractor.extract_closing_odds(
        InternationalOddsExtract.COMPETITIONS,
        InternationalOddsExtract.CLOSING_OUTPUT_FILE,
    )
    print("\nInternational matches, opening and closing odds 2016 ...")
    extractor.extract_opening_and_closing_odds(
        InternationalOddsExtract.COMPETITIONS,
        InternationalOddsExtract.OPEN_CLOSE_OUTPUT_FILE,
    )
    print("\nUEFA club matches, closing odds 2005 to 2015 ...")
    extractor.extract_closing_odds(
        UefaClubOddsExtract.COMPETITIONS, UefaClubOddsExtract.CLOSING_OUTPUT_FILE
    )
    print("\nUEFA club matches, opening and closing odds 2016 ...")
    extractor.extract_opening_and_closing_odds(
        UefaClubOddsExtract.COMPETITIONS, UefaClubOddsExtract.OPEN_CLOSE_OUTPUT_FILE
    )
