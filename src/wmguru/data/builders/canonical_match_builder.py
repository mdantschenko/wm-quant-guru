"""Every international in the canonical schema, and the open fixtures.

This is the backbone the models learn on. Everything else in the project is a
feature that gets joined onto a match of this file, so a mistake here reaches
every layer above it.

The whole build is table work: read three tables, join the shootout winner and
the tournament stage onto the results, split the played matches from the
fixtures, and derive the canonical columns in one pass.

Two files come out. A played match goes through the canonical schema and is
checked field by field. A fixture has no score yet and cannot be a match
record at all, so it is written on its own rather than dropped.
"""

from typing import Any

import numpy as np
import pandas as pd

from wmguru.helpers.constant import (
    CanonicalMatchDataset,
    CsvFileSetting,
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
        matches = self._read_results()
        matches = self._joined_with(matches, self._read_shootouts())
        matches = self._joined_with(matches, self._read_stages())
        matches = self._with_canonical_columns(matches)

        was_played = matches["was_played"]
        rows, problems = self._checked_rows(matches[was_played])
        fixtures = matches.loc[
            ~was_played, list(CanonicalMatchDataset.FIXTURE_COLUMN_NAMES)
        ]

        self._write_the_three_files(rows, fixtures, problems)
        named_stages = int(
            (matches["tournament_stage"] != CanonicalMatchDataset.UNKNOWN_STAGE).sum()
        )
        print(f"  OK    {len(rows)} matches in the canonical schema")
        print(f"  OK    {len(fixtures)} fixtures without a score yet")
        print(
            f"  INFO  {len(problems)} problems, "
            f"{named_stages} matches with a known stage"
        )
        return len(rows)

    def _read_results(self) -> pd.DataFrame:
        """Read the results file and give every match its identifier.

        Returns:
            One row per match, in the order of the file, with the join key
            and the identifier already on it.
        """
        results = pd.read_csv(
            InternationalResultSource.RESULT_FILE,
            dtype=str,
            encoding=CsvFileSetting.ENCODING,
            keep_default_na=False,
        )
        results = results.assign(
            match_day=pd.to_datetime(
                results[InternationalResultSource.DATE_COLUMN], errors="coerce"
            ),
            team_pair=self._team_pair_of(
                results[InternationalResultSource.HOME_TEAM_COLUMN],
                results[InternationalResultSource.AWAY_TEAM_COLUMN],
            ),
        )
        return self._with_match_identifier(results)

    def _read_shootouts(self) -> pd.DataFrame:
        """Read who won the shootout, for every match that went to one."""
        shootouts = pd.read_csv(
            InternationalResultSource.SHOOTOUT_FILE,
            dtype=str,
            encoding=CsvFileSetting.ENCODING,
            keep_default_na=False,
        )
        shootouts = shootouts.assign(
            match_day=pd.to_datetime(
                shootouts[InternationalResultSource.DATE_COLUMN], errors="coerce"
            ),
            team_pair=self._team_pair_of(
                shootouts[InternationalResultSource.HOME_TEAM_COLUMN],
                shootouts[InternationalResultSource.AWAY_TEAM_COLUMN],
            ),
        )
        return shootouts.rename(
            columns={
                InternationalResultSource.SHOOTOUT_WINNER_COLUMN: "shootout_winner"
            }
        )[["match_day", "team_pair", "shootout_winner"]]

    def _read_stages(self) -> pd.DataFrame:
        """Read which stage a tournament match belongs to.

        Only the tournaments with their own file carry a stage. The files
        that are no match list, the bench line ups for one, name no two
        teams and are left out.

        Returns:
            One row per tournament match, with the join key and the stage.
        """
        tournament_files = sorted(
            CanonicalMatchDataset.STAGE_SOURCE_FOLDER.glob(
                CanonicalMatchDataset.STAGE_SOURCE_PATTERN
            )
        )
        tables = [
            table
            for table in (
                pd.read_csv(
                    one,
                    dtype=str,
                    encoding=CsvFileSetting.ENCODING,
                    keep_default_na=False,
                )
                for one in tournament_files
            )
            if CanonicalMatchDataset.STAGE_COLUMN in table.columns
        ]
        stages = pd.concat(tables, ignore_index=True)
        stages = stages.assign(
            match_day=pd.to_datetime(
                stages[CanonicalMatchDataset.STAGE_DATE_COLUMN], errors="coerce"
            ),
            team_pair=self._team_pair_of(
                stages[InternationalResultSource.HOME_TEAM_COLUMN],
                stages[InternationalResultSource.AWAY_TEAM_COLUMN],
            ),
        )
        return stages.rename(
            columns={CanonicalMatchDataset.STAGE_COLUMN: "tournament_stage"}
        )[["match_day", "team_pair", "tournament_stage"]]

    def _team_pair_of(self, home_teams: pd.Series, away_teams: pd.Series) -> pd.Series:
        """Build a join key that does not care which side was named first.

        The sources disagree on who was at home, so a key built in the order
        of the file joins barely half of the tournament matches.
        """
        separator = CanonicalMatchDataset.MATCH_IDENTIFIER_SEPARATOR
        first_named = home_teams.where(home_teams < away_teams, away_teams)
        second_named = away_teams.where(home_teams < away_teams, home_teams)
        return first_named + separator + second_named

    def _with_match_identifier(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Give every match an identifier, and keep it unique.

        The source holds two matches whose day and both team names are the
        same. Numbering them within their own group is what keeps the second
        one from overwriting the first.
        """
        separator = CanonicalMatchDataset.MATCH_IDENTIFIER_SEPARATOR
        plain_identifier = (
            matches[InternationalResultSource.DATE_COLUMN]
            + separator
            + matches[InternationalResultSource.HOME_TEAM_COLUMN]
            + separator
            + matches[InternationalResultSource.AWAY_TEAM_COLUMN]
        )
        repeat_number = matches.groupby(plain_identifier).cumcount()
        return matches.assign(
            match_id=np.where(
                repeat_number == 0,
                plain_identifier,
                plain_identifier
                + CanonicalMatchDataset.REPEATED_IDENTIFIER_SEPARATOR
                + (repeat_number + 1).astype(str),
            )
        )

    def _joined_with(
        self, matches: pd.DataFrame, other_table: pd.DataFrame
    ) -> pd.DataFrame:
        """Join a table onto the matches, allowing the day to be one apart.

        One source dates a match by its kick off in UTC, the other by the
        local day, which pulls a late kick off in the Americas one day apart.
        The other table is therefore widened to every allowed day and joined
        exactly, and the nearest day wins where more than one matches.
        """
        tolerance = CanonicalMatchDataset.STAGE_TOLERANCE_IN_DAYS
        widened = pd.concat(
            [
                other_table.assign(
                    match_day=other_table["match_day"] + pd.Timedelta(days=offset),
                    day_distance=abs(offset),
                )
                for offset in range(-tolerance, tolerance + 1)
            ],
            ignore_index=True,
        )
        joined = matches.merge(widened, on=["match_day", "team_pair"], how="left")
        nearest_first = joined.sort_values("day_distance", kind="stable")
        return (
            nearest_first.drop_duplicates(subset="match_id", keep="first")
            .drop(columns="day_distance")
            .sort_index()
        )

    def _with_canonical_columns(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Derive every column of the canonical schema in one pass."""
        home_goals = matches[InternationalResultSource.HOME_SCORE_COLUMN]
        away_goals = matches[InternationalResultSource.AWAY_SCORE_COLUMN]
        venue_country = matches[InternationalResultSource.COUNTRY_COLUMN]
        home_teams = matches[InternationalResultSource.HOME_TEAM_COLUMN]
        away_teams = matches[InternationalResultSource.AWAY_TEAM_COLUMN]
        shootout_winner = matches["shootout_winner"].fillna("")

        return matches.assign(
            was_played=(home_goals != CanonicalMatchDataset.UNPLAYED_SCORE_TEXT)
            & (away_goals != CanonicalMatchDataset.UNPLAYED_SCORE_TEXT),
            match_date=matches[InternationalResultSource.DATE_COLUMN],
            home_team_name=home_teams,
            away_team_name=away_teams,
            home_team_is_host=home_teams == venue_country,
            away_team_is_host=away_teams == venue_country,
            home_goals_regular_time=home_goals,
            away_goals_regular_time=away_goals,
            home_goals_final=home_goals,
            away_goals_final=away_goals,
            is_regular_time_score_reconstructed_unreliable=shootout_winner != "",
            is_neutral_venue=matches[InternationalResultSource.NEUTRAL_VENUE_COLUMN]
            .str.strip()
            .str.upper()
            != InternationalResultSource.NOT_NEUTRAL_TEXT,
            tournament_name=matches[InternationalResultSource.TOURNAMENT_COLUMN],
            tournament_stage=matches["tournament_stage"].fillna(
                CanonicalMatchDataset.UNKNOWN_STAGE
            ),
            competition_category=self.which_kind_of_competition_each_name_is(
                matches[InternationalResultSource.TOURNAMENT_COLUMN]
            ),
            city=matches[InternationalResultSource.CITY_COLUMN],
            country=venue_country,
            shootout_winner=shootout_winner,
            home_shootout_goals=None,
            away_shootout_goals=None,
        )

    def which_kind_of_competition_each_name_is(
        self, tournament_names: pd.Series
    ) -> pd.Series:
        """Say which kind of competition every tournament name stands for.

        Args:
            tournament_names: The names as the results file writes them, two
                hundred of them.

        Returns:
            One of the five categories per row. A model can then weigh a
            World Cup match differently from an island games one without
            knowing all two hundred names. The order of the tests decides:
            a qualification names its tournament too.
        """
        return pd.Series(
            np.select(
                [
                    tournament_names == CanonicalMatchDataset.FRIENDLY_TOURNAMENT_NAME,
                    tournament_names.str.contains(
                        CanonicalMatchDataset.QUALIFICATION_MARKER, regex=False
                    ),
                    tournament_names.str.contains(
                        CanonicalMatchDataset.NATIONS_LEAGUE_MARKER, regex=False
                    ),
                    tournament_names.isin(CanonicalMatchDataset.MAJOR_TOURNAMENT_NAMES),
                ],
                [
                    CanonicalMatchDataset.FRIENDLY_CATEGORY,
                    CanonicalMatchDataset.QUALIFICATION_CATEGORY,
                    CanonicalMatchDataset.NATIONS_LEAGUE_CATEGORY,
                    CanonicalMatchDataset.MAJOR_TOURNAMENT_CATEGORY,
                ],
                default=CanonicalMatchDataset.OTHER_TOURNAMENT_CATEGORY,
            ),
            index=tournament_names.index,
        )

    def _checked_rows(
        self, played_matches: pd.DataFrame
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Put every played match through the canonical schema.

        This is the one pass that runs per record rather than over the whole
        table: the schema is a contract about a single match, and it names
        every problem of a row at once.

        Returns:
            The rows that passed, and one entry per problem of the rows that
            did not.
        """
        rows: list[dict[str, Any]] = []
        problems: list[dict[str, Any]] = []
        for raw_row in played_matches[list(CanonicalMatchDataset.COLUMN_NAMES)].to_dict(
            "records"
        ):
            record, problem_list = MatchRecord.parse_and_validate_row(raw_row)
            if record is None:
                problems.extend(
                    {"match_id": raw_row["match_id"], "problem": problem}
                    for problem in problem_list
                )
                continue
            rows.append(self._turned_back_into_a_written_row(record))
        return rows, problems

    def _turned_back_into_a_written_row(self, record: MatchRecord) -> dict[str, Any]:
        """Turn one checked record back into the row that is written."""
        written = record.model_dump()
        written["match_date"] = record.match_date.isoformat()
        return written

    def _write_the_three_files(
        self,
        rows: list[dict[str, Any]],
        fixtures: pd.DataFrame,
        problems: list[dict[str, Any]],
    ) -> None:
        """Write the three files this builder produces."""
        CsvFile(
            CanonicalMatchDataset.OUTPUT_FILE, CanonicalMatchDataset.COLUMN_NAMES
        ).write_dict_rows(rows)
        CsvFile(
            CanonicalMatchDataset.FIXTURE_OUTPUT_FILE,
            CanonicalMatchDataset.FIXTURE_COLUMN_NAMES,
        ).write_dict_rows(fixtures.to_dict("records"))
        CsvFile(
            CanonicalMatchDataset.PROBLEM_OUTPUT_FILE,
            CanonicalMatchDataset.PROBLEM_COLUMN_NAMES,
        ).write_dict_rows(problems)


if __name__ == "__main__":
    CanonicalMatchBuilder().build_every_match()
