"""Prepare the StatsBomb events once, in the shape every builder groups over.

StatsBomb hands its events over as JSON documents, one per match, fetched over
the network with a polite delay. Two and a half thousand matches of about four
megabytes each take the better part of an hour, and eight builders would
otherwise each pay for it and each walk the documents again.

This walks them once and writes four tables down: the actions in the same
fifteen columns the Wyscout half has, one row per event for everything the
action shape throws away, the identity of every match, and who started where.
Run it again whenever StatsBomb publishes a new season.

A season is written the moment it is done, so a stopped run picks up where it
left off rather than fetching everything again.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd

from wmguru.helpers.constant import (
    PreparedTablePath,
    StatsBombOpenDataSource,
    WebRequestSetting,
)
from wmguru.helpers.data_class import PreparedStatsBombRows, StatsBombCompetition
from wmguru.helpers.utils import (
    PreparedTableFile,
    StatsBombOpenDataReader,
    WebFileDownloader,
)


class StatsBombEventTableBuilder:
    """The StatsBomb open data, prepared as the four tables the builders read."""

    def __init__(self, statsbomb_reader: StatsBombOpenDataReader) -> None:
        self._statsbomb_reader = statsbomb_reader
        self._action_file = self._table(PreparedTablePath.STATSBOMB_ACTION_FILE)
        self._event_file = self._table(PreparedTablePath.STATSBOMB_EVENT_FILE)
        self._identity_file = self._table(
            PreparedTablePath.STATSBOMB_MATCH_IDENTITY_FILE
        )
        self._line_up_file = self._table(PreparedTablePath.STATSBOMB_LINE_UP_FILE)

    def prepare_every_table(self) -> int:
        """Fetch every open competition and write all four tables after each one.

        Returns:
            How many matches the identity table holds afterwards.

        Raises:
            SystemExit: When the competition list could not be loaded.
        """
        prepared = self._read_what_an_earlier_run_prepared()
        for competition in self._seasons_still_to_do(prepared):
            prepared = self._prepare_one_competition(competition).stacked_under(
                prepared
            )
            self._write_every_table(prepared)
            print(
                f"  SAVED  {competition.competition_name} "
                f"{competition.season_name} "
                f"(tables now {len(prepared.identities)} matches)",
                flush=True,
            )
        print(
            f"\nDone: the prepared tables hold {len(prepared.identities)} matches "
            f"and {len(prepared.events)} events."
        )
        return len(prepared.identities)

    def _read_what_an_earlier_run_prepared(self) -> PreparedStatsBombRows:
        """Read the four tables of an earlier run, empty ones on the first run."""
        return PreparedStatsBombRows(
            actions=self._read_or_empty(self._action_file),
            events=self._read_or_empty(self._event_file),
            identities=self._read_or_empty(self._identity_file),
            line_ups=self._read_or_empty(self._line_up_file),
        )

    def _read_or_empty(self, prepared_file: PreparedTableFile) -> pd.DataFrame:
        """Read one prepared table, or an empty one when it does not exist yet."""
        if not prepared_file.path.exists():
            return pd.DataFrame()
        return prepared_file.read()

    def _seasons_still_to_do(
        self, prepared: PreparedStatsBombRows
    ) -> list[StatsBombCompetition]:
        """Name the seasons an earlier run has not written yet.

        Raises:
            SystemExit: When the competition list could not be loaded.
        """
        open_competitions = self._statsbomb_reader.read_open_competitions(
            self._seasons_already_written(prepared.identities)
        )
        print(f"Open competitions {len(open_competitions)}", flush=True)
        return open_competitions

    def _seasons_already_written(
        self, identities: pd.DataFrame
    ) -> set[tuple[str, str]]:
        """Read which competition and season an earlier run finished."""
        if identities.empty:
            return set()
        return set(
            zip(
                identities["competition_name"],
                identities["season_name"],
                strict=True,
            )
        )

    def _prepare_one_competition(
        self, competition: StatsBombCompetition
    ) -> PreparedStatsBombRows:
        """Fetch every match of one season and turn it into the four tables.

        The loop is over the match documents the endpoint hands over one at a
        time, not over the events inside them: those are turned into rows and
        stacked once at the end, and every builder afterwards groups over all
        of them at once.
        """
        matches = self._statsbomb_reader.read_matches(competition)
        of_every_match = [self._prepare_one_match(match) for match in matches]
        return PreparedStatsBombRows(
            actions=self._stacked(prepared.actions for prepared in of_every_match),
            events=self._stacked(prepared.events for prepared in of_every_match),
            identities=pd.DataFrame(
                [
                    self._statsbomb_reader.read_the_identity_of_one_match(
                        match, competition
                    )
                    for match in matches
                ]
            ),
            line_ups=self._stacked(prepared.line_ups for prepared in of_every_match),
        )

    def _prepare_one_match(self, match: dict[str, Any]) -> PreparedStatsBombRows:
        """Fetch the events of one match once and read three tables out of them.

        Returns:
            The actions, the events and the starting line ups. The identity of
            a match needs no events at all, so it is built next to these.
        """
        events = self._statsbomb_reader.read_events(match)
        return PreparedStatsBombRows(
            actions=self._statsbomb_reader.read_the_actions_out_of(events, match),
            events=self._statsbomb_reader.read_the_events_out_of(events, match),
            identities=pd.DataFrame(),
            line_ups=self._statsbomb_reader.read_the_starting_line_ups_out_of(
                events, match
            ),
        )

    def _stacked(self, tables: Iterator[pd.DataFrame]) -> pd.DataFrame:
        """Put the tables of every match of one season on top of each other.

        An empty table carries no column types, and stacking one onto a full
        table turns a whole column back into something untyped.
        """
        with_rows = [table for table in tables if not table.empty]
        if not with_rows:
            return pd.DataFrame()
        return pd.concat(with_rows, ignore_index=True)

    def _write_every_table(self, prepared: PreparedStatsBombRows) -> None:
        """Write all four tables, so a stopped run never loses a whole season."""
        self._action_file.write(prepared.actions)
        self._event_file.write(prepared.events)
        self._identity_file.write(prepared.identities)
        self._line_up_file.write(prepared.line_ups)

    def _table(self, target_file: Path) -> PreparedTableFile:
        """Name the file together with the command that writes it."""
        return PreparedTableFile(
            target_file, PreparedTablePath.STATSBOMB_PREPARE_COMMAND
        )


if __name__ == "__main__":
    StatsBombEventTableBuilder(
        StatsBombOpenDataReader(
            WebFileDownloader(
                user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
                polite_delay_in_seconds=(
                    StatsBombOpenDataSource.POLITE_DELAY_IN_SECONDS
                ),
            )
        )
    ).prepare_every_table()
