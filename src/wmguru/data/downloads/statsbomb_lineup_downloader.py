"""One flat player and match file per tournament, from StatsBomb.

The line-up files hold the complete match day squad of both teams: the starting
eleven, the substitutions with their minute, and the bench players who never
came on. Out of that come bench features the market hardly prices, such as the
value of the bench, how much a coach uses it, and how early the substitutions
come. Since the five substitution rule that lever is much bigger than it used
to be.
"""

from typing import Any

from wmguru.data.downloads.statsbomb_match_list_reader import StatsBombMatchListReader
from wmguru.helpers.constant import (
    StatsBombSource,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
)


class StatsBombLineupDownloader:
    """One row per player and match, in a single file."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        match_list_reader: StatsBombMatchListReader,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._match_list_reader = match_list_reader

    def download_every_tournament(self) -> int:
        """Write the file and return how many player rows it holds."""
        target_file = (
            StatsBombSource.OUTPUT_FOLDER / StatsBombSource.LINEUP_OUTPUT_FILE_NAME
        )
        target_file.parent.mkdir(parents=True, exist_ok=True)
        written_count = 0
        with CsvFile(
            target_file, StatsBombSource.LINEUP_COLUMN_NAMES
        ).writing_writer() as writer:
            for tournament_name in StatsBombSource.TOURNAMENT_IDENTIFIER:
                written_count += self._write_one_tournament(writer, tournament_name)
        print(f"{written_count} player rows -> {target_file}")
        return written_count

    def _write_one_tournament(self, writer: Any, tournament_name: str) -> int:
        """Walk every match of one tournament and return the row count."""
        matches = self._match_list_reader.read_matches(tournament_name)
        if not matches:
            print(f"  FAIL  {tournament_name} (no match list)")
            return 0

        written_count = 0
        match_count = 0
        for match in matches:
            teams = self._web_file_downloader.download_json(
                f"{StatsBombSource.BASE_URL}/lineups/{match['match_id']}.json",
                timeout_in_seconds=StatsBombSource.TIMEOUT_IN_SECONDS,
            )
            if not isinstance(teams, list):
                continue
            for team in teams:
                rows = self._build_rows_of_one_team(tournament_name, match, team)
                writer.writerows(rows)
                written_count += len(rows)
            match_count += 1
        print(f"  OK    {tournament_name}: {match_count} matches", flush=True)
        return written_count

    def _build_rows_of_one_team(
        self, tournament_name: str, match: dict[str, Any], team: dict[str, Any]
    ) -> list[list[Any]]:
        """Build one row per player of one team in one match."""
        rows = []
        for player in team.get("lineup", []):
            role, position, minute_on, minute_off = self._read_role_of(player)
            rows.append(
                [
                    tournament_name,
                    match["match_id"],
                    match.get("match_date", ""),
                    team.get("team_name", ""),
                    player.get("player_name", ""),
                    player.get("jersey_number", ""),
                    role,
                    position,
                    minute_on,
                    minute_off,
                ]
            )
        return rows

    def _read_role_of(self, player: dict[str, Any]) -> tuple[str, str, str, str]:
        """Say whether the player started, came on, or never left the bench."""
        positions = player.get("positions", [])
        if not positions:
            return StatsBombSource.UNUSED_BENCH_ROLE, "", "", ""

        first_position = positions[0]
        last_position = positions[-1]
        is_a_starter = (
            first_position.get("start_reason") == StatsBombSource.STARTING_ELEVEN_REASON
        )
        role = (
            StatsBombSource.STARTER_ROLE
            if is_a_starter
            else StatsBombSource.USED_SUBSTITUTE_ROLE
        )
        minute_on = (
            StatsBombSource.MATCH_START_MINUTE
            if is_a_starter
            else self._read_minute(first_position.get("from"))
        )
        return (
            role,
            first_position.get("position", ""),
            minute_on,
            self._read_minute(last_position.get("to")),
        )

    def _read_minute(self, timestamp: str | None) -> str:
        """Read the minute out of MM:SS. These are already absolute minutes."""
        if not timestamp:
            return ""
        try:
            return str(int(timestamp.split(":")[0]))
        except ValueError:
            return ""


if __name__ == "__main__":
    shared_downloader = WebFileDownloader(
        user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
        polite_delay_in_seconds=WebRequestSetting.FAST_POLITE_DELAY_IN_SECONDS,
    )
    StatsBombLineupDownloader(
        shared_downloader, StatsBombMatchListReader(shared_downloader)
    ).download_every_tournament()
