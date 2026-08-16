"""Every international in the canonical schema, and the open fixtures.

This is the backbone the models learn on. Everything else in the project is a
feature that gets joined onto a match of this file, so a mistake here reaches
every layer above it.

Two files come out. A played match goes through the canonical schema and is
checked field by field. A fixture has no score yet and cannot be a match
record at all, so it is written on its own rather than dropped.
"""

from datetime import date
from typing import Any

from wmguru.helpers.constant import (
    CanonicalMatchDataset,
    InternationalResultSource,
)
from wmguru.helpers.data_class import MatchRecord
from wmguru.helpers.utils import CsvFile


class CanonicalMatchBuilder:
    """The canonical match dataset, out of the international results file."""

    def build_every_match(self) -> int:
        """Write the played matches, the open fixtures and any problem found.

        Returns:
            How many matches passed the schema.
        """
        stage_of_match = self._read_the_stages()
        shootout_winner_of_match = self._read_the_shootout_winners()

        rows: list[dict[str, Any]] = []
        fixtures: list[dict[str, Any]] = []
        problems: list[dict[str, Any]] = []
        used_identifiers: set[str] = set()

        for result_row in CsvFile(InternationalResultSource.RESULT_FILE).read_rows():
            match_identifier = self._identifier_of(result_row, used_identifiers)
            if not self._was_played(result_row):
                fixtures.append(
                    self._build_fixture(result_row, match_identifier, stage_of_match)
                )
                continue
            record, problem_list = MatchRecord.parse_and_validate_row(
                self._build_row(
                    result_row,
                    match_identifier,
                    stage_of_match,
                    shootout_winner_of_match,
                )
            )
            if record is None:
                problems.extend(
                    {"match_id": match_identifier, "problem": problem}
                    for problem in problem_list
                )
                continue
            rows.append(self._as_written_row(record))

        self._write(rows, fixtures, problems)
        print(f"  OK    {len(rows)} matches in the canonical schema")
        print(f"  OK    {len(fixtures)} fixtures without a score yet")
        print(
            f"  INFO  {len(problems)} problems, {self._named_stage_count(rows)} "
            f"matches with a known stage"
        )
        return len(rows)

    def _read_the_stages(self) -> dict[tuple[date, frozenset[str]], str]:
        """Read which stage a tournament match belongs to.

        Only the tournaments with their own file carry a stage. They are
        joined on the two team names without their order, because the source
        files disagree on which side was at home.

        Returns:
            The stage of every match that has one, keyed by day and by the
            pair of teams.
        """
        stage_of_match: dict[tuple[date, frozenset[str]], str] = {}
        for tournament_file in sorted(
            CanonicalMatchDataset.STAGE_SOURCE_FOLDER.glob(
                CanonicalMatchDataset.STAGE_SOURCE_PATTERN
            )
        ):
            for row in CsvFile(tournament_file).read_rows():
                if CanonicalMatchDataset.STAGE_COLUMN not in row:
                    break
                match_day = self._as_day(row[CanonicalMatchDataset.STAGE_DATE_COLUMN])
                if match_day is None:
                    continue
                stage_of_match[
                    (match_day, frozenset((row["home_team"], row["away_team"])))
                ] = row[CanonicalMatchDataset.STAGE_COLUMN]
        return stage_of_match

    def _read_the_shootout_winners(self) -> dict[tuple[date, frozenset[str]], str]:
        """Read who won the shootout, for every match that went to one."""
        winner_of_match: dict[tuple[date, frozenset[str]], str] = {}
        for row in CsvFile(InternationalResultSource.SHOOTOUT_FILE).read_rows():
            match_day = self._as_day(row[InternationalResultSource.DATE_COLUMN])
            if match_day is None:
                continue
            winner_of_match[
                (
                    match_day,
                    frozenset(
                        (
                            row[InternationalResultSource.HOME_TEAM_COLUMN],
                            row[InternationalResultSource.AWAY_TEAM_COLUMN],
                        )
                    ),
                )
            ] = row[InternationalResultSource.SHOOTOUT_WINNER_COLUMN]
        return winner_of_match

    def _build_row(
        self,
        result_row: dict[str, str],
        match_identifier: str,
        stage_of_match: dict[tuple[date, frozenset[str]], str],
        shootout_winner_of_match: dict[tuple[date, frozenset[str]], str],
    ) -> dict[str, Any]:
        """Build one row of the canonical schema out of one result row."""
        shootout_winner = self._looked_up(result_row, shootout_winner_of_match, "")
        went_to_extra_time = bool(shootout_winner)
        home_goals = result_row[InternationalResultSource.HOME_SCORE_COLUMN]
        away_goals = result_row[InternationalResultSource.AWAY_SCORE_COLUMN]
        return {
            **self._shared_columns(result_row, match_identifier, stage_of_match),
            "home_goals_regular_time": home_goals,
            "away_goals_regular_time": away_goals,
            "home_goals_final": home_goals,
            "away_goals_final": away_goals,
            "is_regular_time_score_reconstructed_unreliable": went_to_extra_time,
            "shootout_winner": shootout_winner,
        }

    def _build_fixture(
        self,
        result_row: dict[str, str],
        match_identifier: str,
        stage_of_match: dict[tuple[date, frozenset[str]], str],
    ) -> dict[str, Any]:
        """Build one row for a match that has not been played yet."""
        return self._shared_columns(result_row, match_identifier, stage_of_match)

    def _shared_columns(
        self,
        result_row: dict[str, str],
        match_identifier: str,
        stage_of_match: dict[tuple[date, frozenset[str]], str],
    ) -> dict[str, Any]:
        """Build the columns a played match and a fixture have in common."""
        venue_country = result_row[InternationalResultSource.COUNTRY_COLUMN]
        home_team = result_row[InternationalResultSource.HOME_TEAM_COLUMN]
        away_team = result_row[InternationalResultSource.AWAY_TEAM_COLUMN]
        return {
            "match_id": match_identifier,
            "match_date": result_row[InternationalResultSource.DATE_COLUMN],
            "home_team_name": home_team,
            "home_team_is_host": home_team == venue_country,
            "away_team_name": away_team,
            "away_team_is_host": away_team == venue_country,
            "is_neutral_venue": (
                result_row[InternationalResultSource.NEUTRAL_VENUE_COLUMN]
                .strip()
                .upper()
                != InternationalResultSource.NOT_NEUTRAL_TEXT
            ),
            "tournament_name": result_row[InternationalResultSource.TOURNAMENT_COLUMN],
            "tournament_stage": self._looked_up(
                result_row, stage_of_match, CanonicalMatchDataset.UNKNOWN_STAGE
            ),
            "competition_category": self.category_of(
                result_row[InternationalResultSource.TOURNAMENT_COLUMN]
            ),
            "city": result_row[InternationalResultSource.CITY_COLUMN],
            "country": venue_country,
        }

    def category_of(self, tournament_name: str) -> str:
        """Say which kind of competition a tournament name stands for.

        Args:
            tournament_name: The name as the results file writes it, one of
                two hundred.

        Returns:
            One of the five categories. A model can then weigh a World Cup
            match differently from an island games one without knowing all
            two hundred names.
        """
        if tournament_name == CanonicalMatchDataset.FRIENDLY_TOURNAMENT_NAME:
            return CanonicalMatchDataset.FRIENDLY_CATEGORY
        if CanonicalMatchDataset.QUALIFICATION_MARKER in tournament_name:
            return CanonicalMatchDataset.QUALIFICATION_CATEGORY
        if CanonicalMatchDataset.NATIONS_LEAGUE_MARKER in tournament_name:
            return CanonicalMatchDataset.NATIONS_LEAGUE_CATEGORY
        if tournament_name in CanonicalMatchDataset.MAJOR_TOURNAMENT_NAMES:
            return CanonicalMatchDataset.MAJOR_TOURNAMENT_CATEGORY
        return CanonicalMatchDataset.OTHER_TOURNAMENT_CATEGORY

    def _was_played(self, result_row: dict[str, str]) -> bool:
        """Return True when the row carries a score rather than a placeholder."""
        return (
            result_row[InternationalResultSource.HOME_SCORE_COLUMN]
            != CanonicalMatchDataset.UNPLAYED_SCORE_TEXT
            and result_row[InternationalResultSource.AWAY_SCORE_COLUMN]
            != CanonicalMatchDataset.UNPLAYED_SCORE_TEXT
        )

    def _identifier_of(
        self, result_row: dict[str, str], used_identifiers: set[str]
    ) -> str:
        """Build the identifier of one match, and keep it unique.

        Args:
            result_row: One row of the results file.
            used_identifiers: Every identifier handed out so far. The source
                holds two matches whose day and teams are the same, and one
                of them would otherwise overwrite the other.

        Returns:
            The day and both teams, and a running number where that is not
            enough to tell two rows apart.
        """
        separator = CanonicalMatchDataset.MATCH_IDENTIFIER_SEPARATOR
        identifier = separator.join(
            (
                result_row[InternationalResultSource.DATE_COLUMN],
                result_row[InternationalResultSource.HOME_TEAM_COLUMN],
                result_row[InternationalResultSource.AWAY_TEAM_COLUMN],
            )
        )
        if identifier not in used_identifiers:
            used_identifiers.add(identifier)
            return identifier
        repeat = 2
        while (
            f"{identifier}{CanonicalMatchDataset.REPEATED_IDENTIFIER_SEPARATOR}{repeat}"
            in used_identifiers
        ):
            repeat += 1
        identifier = (
            f"{identifier}"
            f"{CanonicalMatchDataset.REPEATED_IDENTIFIER_SEPARATOR}{repeat}"
        )
        used_identifiers.add(identifier)
        return identifier

    def _looked_up(
        self,
        result_row: dict[str, str],
        value_of_match: dict[tuple[date, frozenset[str]], str],
        when_missing: str,
    ) -> str:
        """Look one match up by its day and its two teams.

        The days of two sources can be one apart, because one dates a match
        by its kick off in UTC and the other by the local day, so the days
        around it are tried as well.

        Returns:
            The value, or what the caller asked for when no source knows the
            match.
        """
        match_day = self._as_day(result_row[InternationalResultSource.DATE_COLUMN])
        if match_day is None:
            return when_missing
        teams = frozenset(
            (
                result_row[InternationalResultSource.HOME_TEAM_COLUMN],
                result_row[InternationalResultSource.AWAY_TEAM_COLUMN],
            )
        )
        tolerance = CanonicalMatchDataset.STAGE_TOLERANCE_IN_DAYS
        for offset in range(-tolerance, tolerance + 1):
            found = value_of_match.get(
                (match_day.fromordinal(match_day.toordinal() + offset), teams)
            )
            if found:
                return found
        return when_missing

    def _as_day(self, written_date: str) -> date | None:
        """Read a written day, or None when the cell holds no day at all."""
        try:
            return date.fromisoformat(written_date)
        except ValueError:
            return None

    def _as_written_row(self, record: MatchRecord) -> dict[str, Any]:
        """Turn one checked record back into the row that is written."""
        written = record.model_dump()
        written["match_date"] = record.match_date.isoformat()
        return written

    def _named_stage_count(self, rows: list[dict[str, Any]]) -> int:
        """Count the matches whose stage a tournament file could name."""
        return sum(
            1
            for row in rows
            if row["tournament_stage"] != CanonicalMatchDataset.UNKNOWN_STAGE
        )

    def _write(
        self,
        rows: list[dict[str, Any]],
        fixtures: list[dict[str, Any]],
        problems: list[dict[str, Any]],
    ) -> None:
        """Write the three files this builder produces."""
        CsvFile(
            CanonicalMatchDataset.OUTPUT_FILE, CanonicalMatchDataset.COLUMN_NAMES
        ).write_dict_rows(rows)
        CsvFile(
            CanonicalMatchDataset.FIXTURE_OUTPUT_FILE,
            CanonicalMatchDataset.FIXTURE_COLUMN_NAMES,
        ).write_dict_rows(fixtures)
        CsvFile(
            CanonicalMatchDataset.PROBLEM_OUTPUT_FILE,
            CanonicalMatchDataset.PROBLEM_COLUMN_NAMES,
        ).write_dict_rows(problems)


if __name__ == "__main__":
    CanonicalMatchBuilder().build_every_match()
