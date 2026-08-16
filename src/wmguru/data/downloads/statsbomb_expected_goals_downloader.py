"""One match level expected goals file per tournament, from StatsBomb.

StatsBomb publishes complete event data, including the expected goals of every
shot, for the 2018 and 2022 World Cup, Euro 2020 and 2024 and the 2024 Copa
America. This downloader streams the event file of every match, adds the shots
up to a match total and writes one compact CSV file per tournament. The raw
event files, about four megabytes per match, are not kept, because they can be
fetched again from the repository at any time.
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


class StatsBombExpectedGoalsDownloader:
    """The shots of every match, added up to a match level expected goals file."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        match_list_reader: StatsBombMatchListReader,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._match_list_reader = match_list_reader

    def download_every_tournament(self) -> int:
        """Write one file per tournament and return the total match count."""
        total_match_count = 0
        for tournament_name in StatsBombSource.TOURNAMENT_IDENTIFIER:
            print(f"Tournament: {tournament_name}", flush=True)
            total_match_count += self.download_one_tournament(tournament_name)
        return total_match_count

    def download_one_tournament(self, tournament_name: str) -> int:
        """Write the file of one tournament and return how many matches it holds."""
        matches = self._match_list_reader.read_matches(tournament_name)
        if not matches:
            print(f"  FAIL  {tournament_name}: no match list")
            return 0

        target_file = StatsBombSource.OUTPUT_FOLDER / f"{tournament_name}.csv"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        written_count = 0
        with CsvFile(
            target_file, StatsBombSource.EXPECTED_GOALS_COLUMN_NAMES
        ).writing_writer() as writer:
            for match in matches:
                row = self._build_the_row_of_one_match(match)
                if row is None:
                    continue
                writer.writerow(row)
                written_count += 1
                self._report_progress(written_count, len(matches))
        print(f"  OK    {tournament_name}: {written_count} matches -> {target_file}")
        return written_count

    def _build_the_row_of_one_match(self, match: dict[str, Any]) -> list[Any] | None:
        """Build one output row."""
        home_team_name = match["home_team"]["home_team_name"]
        away_team_name = match["away_team"]["away_team_name"]
        events = self._web_file_downloader.download_json(
            f"{StatsBombSource.BASE_URL}/events/{match['match_id']}.json",
            timeout_in_seconds=StatsBombSource.TIMEOUT_IN_SECONDS,
        )
        if not isinstance(events, list):
            print(f"    SKIP  {home_team_name} - {away_team_name} (no events)")
            return None

        home_regular, _, _ = self._add_shots_up(
            events, home_team_name, StatsBombSource.LAST_REGULAR_PERIOD
        )
        away_regular, _, _ = self._add_shots_up(
            events, away_team_name, StatsBombSource.LAST_REGULAR_PERIOD
        )
        home_total, home_shots, home_on_target = self._add_shots_up(
            events, home_team_name, StatsBombSource.LAST_EXTRA_TIME_PERIOD
        )
        away_total, away_shots, away_on_target = self._add_shots_up(
            events, away_team_name, StatsBombSource.LAST_EXTRA_TIME_PERIOD
        )
        return [
            match["match_id"],
            match.get("match_date"),
            match.get("competition_stage", {}).get("name", ""),
            home_team_name,
            away_team_name,
            match.get("home_score"),
            match.get("away_score"),
            home_regular,
            away_regular,
            home_total,
            away_total,
            home_shots,
            away_shots,
            home_on_target,
            away_on_target,
            match.get("referee", {}).get("name", ""),
            match.get("stadium", {}).get("name", ""),
            match.get("kick_off", ""),
        ]

    def _add_shots_up(
        self, events: list[dict[str, Any]], team_name: str, last_period: int
    ) -> tuple[float, int, int]:
        """Return expected goals, shots and shots on target of one team."""
        total_expected_goals = 0.0
        shot_count = 0
        on_target_count = 0
        for event in events:
            if not self._is_a_shot_of_this_team(event, team_name, last_period):
                continue
            shot = event.get("shot", {})
            total_expected_goals += float(shot.get("statsbomb_xg") or 0.0)
            shot_count += 1
            if shot.get("outcome", {}).get("name") in (
                StatsBombSource.ON_TARGET_OUTCOME_NAMES
            ):
                on_target_count += 1
        return round(total_expected_goals, 4), shot_count, on_target_count

    def _is_a_shot_of_this_team(
        self, event: dict[str, Any], team_name: str, last_period: int
    ) -> bool:
        """Return True when this is a shot of this team in a counted period."""
        if event.get("type", {}).get("name") != StatsBombSource.SHOT_EVENT_NAME:
            return False
        if event.get("team", {}).get("name") != team_name:
            return False
        period = int(event.get("period") or StatsBombSource.FIRST_PERIOD)
        return period <= last_period

    def _report_progress(self, written_count: int, match_count: int) -> None:
        """Say something every now and then, a tournament takes a few minutes."""
        if written_count % StatsBombSource.PROGRESS_REPORT_EVERY_N_MATCHES == 0:
            print(f"    ... {written_count}/{match_count} matches", flush=True)


if __name__ == "__main__":
    shared_downloader = WebFileDownloader(
        user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
        polite_delay_in_seconds=WebRequestSetting.FAST_POLITE_DELAY_IN_SECONDS,
    )
    total = StatsBombExpectedGoalsDownloader(
        shared_downloader, StatsBombMatchListReader(shared_downloader)
    ).download_every_tournament()
    print(f"\nDone: {total} matches with match level expected goals.")
