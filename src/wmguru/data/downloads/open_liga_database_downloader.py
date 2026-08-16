"""Both German Bundesliga divisions, from OpenLigaDB.

OpenLigaDB is free and needs no key. Per season it serves every match of both
divisions with the final score, the half time score and every goal with scorer,
minute, penalty flag and own goal flag. That is what football-data.co.uk does
not carry, and coverage is clean back to 2010. The result is one flat match
file and one goal file.
"""

from typing import Any

from wmguru.helpers.constant import OpenLigaDatabaseSource, WebRequestSetting
from wmguru.helpers.utils import CsvFile, WebFileDownloader


class OpenLigaDatabaseDownloader:
    """One match file and one goal file, over all leagues and seasons."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def download_every_season(self) -> tuple[int, int]:
        """Return how many matches and how many goals were written."""
        match_output = CsvFile(
            OpenLigaDatabaseSource.OUTPUT_FOLDER
            / OpenLigaDatabaseSource.MATCH_FILE_NAME,
            OpenLigaDatabaseSource.MATCH_COLUMN_NAMES,
        )
        goal_output = CsvFile(
            OpenLigaDatabaseSource.OUTPUT_FOLDER
            / OpenLigaDatabaseSource.GOAL_FILE_NAME,
            OpenLigaDatabaseSource.GOAL_COLUMN_NAMES,
        )
        match_count = 0
        goal_count = 0
        with (
            match_output.writing_writer() as match_writer,
            goal_output.writing_writer() as goal_writer,
        ):
            for league_code in OpenLigaDatabaseSource.LEAGUE_CODES:
                for season_start_year in self._season_start_years():
                    written_matches, written_goals = self._write_one_season(
                        match_writer, goal_writer, league_code, season_start_year
                    )
                    match_count += written_matches
                    goal_count += written_goals
        return match_count, goal_count

    def _season_start_years(self) -> range:
        """List every season the source covers completely."""
        return range(
            OpenLigaDatabaseSource.FIRST_SEASON_START_YEAR,
            OpenLigaDatabaseSource.LAST_SEASON_START_YEAR + 1,
        )

    def _write_one_season(
        self,
        match_writer: Any,
        goal_writer: Any,
        league_code: str,
        season_start_year: int,
    ) -> tuple[int, int]:
        """Write one league season and return its match and goal count."""
        matches = self._read_season(league_code, season_start_year)
        goal_count = 0
        for match in matches:
            match_writer.writerow(
                self._build_match_row(match, league_code, season_start_year)
            )
            for goal in match.get("goals", []):
                goal_writer.writerow(self._build_goal_row(match, goal))
                goal_count += 1
        print(
            f"  OK    {league_code}/{season_start_year}: {len(matches)} matches",
            flush=True,
        )
        return len(matches), goal_count

    def _read_season(
        self, league_code: str, season_start_year: int
    ) -> list[dict[str, Any]]:
        """Ask for one league season. Empty list when it cannot be loaded."""
        url = OpenLigaDatabaseSource.API_URL_TEMPLATE.format(
            league_code=league_code, season_start_year=season_start_year
        )
        answer = self._web_file_downloader.download_json(
            url, timeout_in_seconds=OpenLigaDatabaseSource.TIMEOUT_IN_SECONDS
        )
        return answer if isinstance(answer, list) else []

    def _build_match_row(
        self, match: dict[str, Any], league_code: str, season_start_year: int
    ) -> list[Any]:
        """Build one row of the match file."""
        home_goals, away_goals = self._read_final_score(match)
        return [
            match.get("matchID"),
            league_code,
            season_start_year,
            match.get("group", {}).get("groupOrderID", ""),
            match.get("matchDateTimeUTC", ""),
            match.get("team1", {}).get("teamName", ""),
            match.get("team2", {}).get("teamName", ""),
            home_goals,
            away_goals,
            match.get("matchIsFinished", ""),
        ]

    def _build_goal_row(self, match: dict[str, Any], goal: dict[str, Any]) -> list[Any]:
        """Build one row of the goal file."""
        return [
            match.get("matchID"),
            goal.get("matchMinute", ""),
            goal.get("goalGetterName", ""),
            goal.get("scoreTeam1", ""),
            goal.get("scoreTeam2", ""),
            goal.get("isPenalty", ""),
            goal.get("isOwnGoal", ""),
        ]

    def _read_final_score(self, match: dict[str, Any]) -> tuple[str, str]:
        """Read the final score, or empty text when the list does not carry it."""
        for result in match.get("matchResults", []):
            if (
                result.get("resultName")
                == OpenLigaDatabaseSource.FINAL_SCORE_RESULT_NAME
            ):
                return (
                    str(result.get("pointsTeam1", "")),
                    str(result.get("pointsTeam2", "")),
                )
        return "", ""


if __name__ == "__main__":
    matches_written, goals_written = OpenLigaDatabaseDownloader(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=OpenLigaDatabaseSource.POLITE_DELAY_IN_SECONDS,
        )
    ).download_every_season()
    print(
        f"{matches_written} matches, {goals_written} goals "
        f"-> {OpenLigaDatabaseSource.OUTPUT_FOLDER}"
    )
