"""Everything the system needs shortly before kick off, for one match day.

For one day it bundles the time critical information the system needs right
before a tip or a bet goes in:
  - the confirmed line-ups, that is starting eleven, bench, formation and coach,
  - the injuries and bans per team,
  - the weather at kick off at the venue.

Odds are deliberately not part of this, LiveOddsFetcher covers them.

API-Football needs a free key, its free tier allows 100 requests a day, which is
enough for one World Cup match day. The key goes into the environment variable
API_FOOTBALL_KEY or into the key file. League and season can be set through the
environment variables API_FOOTBALL_LEAGUE and API_FOOTBALL_SEASON.

    python -m wmguru.preprocessing.fetchers.prematch_fetcher [YYYY-MM-DD]

Without a date it uses today in UTC.
"""

import json
import os
import sys
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wmguru.helpers.constant import (
    CsvFileSetting,
    OpenMeteoSource,
    PrematchSource,
    TimeStampFormat,
    WebRequestSetting,
)
from wmguru.helpers.utils import (
    ApiKeyReader,
    CsvFile,
    WebFileDownloader,
)

SIGN_UP_URL = "https://api-sports.io"


class PrematchFetcher:
    """Line-ups, injuries and weather for every match of one day."""

    def __init__(
        self,
        web_file_downloader: WebFileDownloader,
        api_key_reader: ApiKeyReader,
    ) -> None:
        self._web_file_downloader = web_file_downloader
        self._api_key_reader = api_key_reader
        self._api_key = ""

    def fetch_match_day(self, match_day: str) -> int:
        """Collect line-ups, injuries and weather for every match of one day.

        Args:
            match_day: The day as YYYY-MM-DD. It also names the output files,
                so one day never overwrites another.

        Returns:
            How many matches went into the snapshot. Zero when the league had
            no match that day.

        Raises:
            SystemExit: When no API-Football key is set up.
        """
        self._api_key = self._read_the_api_key()
        fixtures = self._ask_api_football(
            PrematchSource.FIXTURE_PATH,
            {
                "date": match_day,
                "league": os.environ.get(
                    PrematchSource.LEAGUE_ENVIRONMENT_VARIABLE,
                    PrematchSource.WORLD_CUP_LEAGUE_IDENTIFIER,
                ),
                "season": os.environ.get(
                    PrematchSource.SEASON_ENVIRONMENT_VARIABLE,
                    PrematchSource.DEFAULT_SEASON,
                ),
            },
        )
        print(f"  {len(fixtures)} matches on {match_day}", flush=True)

        snapshots = [self._build_snapshot(fixture) for fixture in fixtures]
        self._write_files(snapshots, match_day)
        print(
            f"  OK    snapshot of {len(snapshots)} matches "
            f"-> {PrematchSource.OUTPUT_FOLDER}"
        )
        return len(snapshots)

    def _read_the_api_key(self) -> str:
        """Read the key that every request to this endpoint needs.

        Raises:
            SystemExit: When no key is set up, with the message that says how
                to set one up.
        """
        key = self._api_key_reader.read_key(
            PrematchSource.API_KEY_ENVIRONMENT_VARIABLE, PrematchSource.API_KEY_FILE
        )
        if not key:
            raise SystemExit(
                self._api_key_reader.explain_how_to_set_the_key(
                    PrematchSource.API_KEY_ENVIRONMENT_VARIABLE, SIGN_UP_URL
                )
                + f"\n  or write it into {PrematchSource.API_KEY_FILE}"
            )
        return key

    def _build_snapshot(self, fixture: dict[str, Any]) -> dict[str, Any]:
        """Collect the line-ups, the injuries and the weather of one match."""
        fixture_details = fixture["fixture"]
        fixture_id = fixture_details["id"]
        venue = fixture_details.get("venue", {})
        home_team = fixture["teams"]["home"]["name"]
        away_team = fixture["teams"]["away"]["name"]
        kick_off = fixture_details.get("date", "")

        return {
            "fixture_id": fixture_id,
            "kickoff": kick_off,
            "status": fixture_details.get("status", {}).get("short"),
            "venue": {"name": venue.get("name"), "city": venue.get("city")},
            "home": home_team,
            "away": away_team,
            "lineups": self._read_lineups(fixture_id),
            "injuries": self._read_injuries(fixture_id, home_team, away_team),
            "weather": self._read_weather(venue, kick_off),
        }

    def _read_lineups(self, fixture_id: int) -> dict[str, Any]:
        """Read the line-up of every team of one match."""
        lineups: dict[str, Any] = {}
        for team_block in self._ask_api_football(
            PrematchSource.LINEUP_PATH, {"fixture": fixture_id}
        ):
            lineup = self._read_one_lineup(team_block)
            lineups[lineup["team"]] = lineup
        return lineups

    def _read_one_lineup(self, team_block: dict[str, Any]) -> dict[str, Any]:
        """Build the line-up of one team in the shape the output files expect."""
        return {
            "team": team_block.get("team", {}).get("name"),
            "formation": team_block.get("formation"),
            "coach": team_block.get("coach", {}).get("name"),
            "start_xi": self._read_players(team_block.get("startXI")),
            "substitutes": self._read_players(team_block.get("substitutes")),
        }

    def _read_players(self, entries: list[Any] | None) -> list[dict[str, Any]]:
        """Read the players of one group, that is the starters or the bench."""
        return [
            {
                "player": entry["player"].get("name"),
                "number": entry["player"].get("number"),
                "position": entry["player"].get("pos"),
                "grid": entry["player"].get("grid"),
            }
            for entry in entries or []
        ]

    def _read_injuries(
        self, fixture_id: int, home_team: str, away_team: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Read the players who are out, per team."""
        injuries: dict[str, list[dict[str, Any]]] = {home_team: [], away_team: []}
        for entry in self._ask_api_football(
            PrematchSource.INJURY_PATH, {"fixture": fixture_id}
        ):
            team_name = entry.get("team", {}).get("name")
            player = entry.get("player", {})
            injuries.setdefault(team_name, []).append(
                {
                    "player": player.get("name"),
                    "type": player.get("type"),
                    "reason": player.get("reason"),
                }
            )
        return injuries

    def _read_weather(
        self, venue: dict[str, Any], kick_off: str
    ) -> dict[str, Any] | None:
        """Read the weather at kick off, or return None when the venue is unknown."""
        place_name = venue.get("city") or venue.get("name") or ""
        point = self._turn_a_venue_name_into_coordinates(place_name)
        if point is None:
            return None
        return self._read_forecast(point[0], point[1], kick_off)

    def _turn_a_venue_name_into_coordinates(
        self, place_name: str
    ) -> tuple[float, float] | None:
        """Turn a venue name into coordinates."""
        if not place_name:
            return None
        parameters = urllib.parse.urlencode({"name": place_name, "count": 1})
        answer = self._web_file_downloader.download_json(
            f"{OpenMeteoSource.GEOCODING_URL}?{parameters}",
            timeout_in_seconds=PrematchSource.TIMEOUT_IN_SECONDS,
        )
        places = answer.get("results") if isinstance(answer, dict) else None
        if not places:
            return None
        return places[0]["latitude"], places[0]["longitude"]

    def _read_forecast(
        self, latitude: float, longitude: float, kick_off: str
    ) -> dict[str, Any] | None:
        """Read the forecast values of the hour the match starts."""
        day = kick_off[: PrematchSource.DAY_PREFIX_LENGTH]
        parameters = urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": PrematchSource.HOURLY_VARIABLES,
                "start_date": day,
                "end_date": day,
                "timezone": PrematchSource.WEATHER_TIMEZONE,
            }
        )
        answer = self._web_file_downloader.download_json(
            f"{OpenMeteoSource.WEATHER_FORECAST_URL}?{parameters}",
            timeout_in_seconds=PrematchSource.TIMEOUT_IN_SECONDS,
        )
        hourly_values = answer.get("hourly") if isinstance(answer, dict) else None
        if not hourly_values or not hourly_values.get("time"):
            return None
        position = self._position_of_the_kick_off_hour(hourly_values["time"], kick_off)
        return {
            "time": hourly_values["time"][position],
            "temperature_c": hourly_values["temperature_2m"][position],
            "precipitation_mm": hourly_values["precipitation"][position],
            "wind_kmh": hourly_values["wind_speed_10m"][position],
            "humidity_pct": hourly_values["relative_humidity_2m"][position],
        }

    def _position_of_the_kick_off_hour(self, hours: list[str], kick_off: str) -> int:
        """Find where the kick off hour sits, or fall back to the first hour."""
        wanted_hour = kick_off[: PrematchSource.HOUR_PREFIX_LENGTH]
        return next(
            (
                position
                for position, hour in enumerate(hours)
                if hour[: PrematchSource.HOUR_PREFIX_LENGTH] == wanted_hour
            ),
            0,
        )

    def _ask_api_football(
        self, path: str, parameters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Send one request against API-Football, which wraps its answer in a field."""
        url = (
            f"{PrematchSource.API_BASE_URL}/{path}?{urllib.parse.urlencode(parameters)}"
        )
        answer = self._web_file_downloader.download_json(
            url,
            timeout_in_seconds=PrematchSource.TIMEOUT_IN_SECONDS,
            extra_headers={PrematchSource.API_KEY_HEADER_NAME: self._api_key},
        )
        if not isinstance(answer, dict):
            print(f"  WARN  {url.split('?')[0]} gave nothing back", flush=True)
            return []
        answer_list = answer.get("response", [])
        return answer_list if isinstance(answer_list, list) else []

    def _write_files(self, snapshots: list[dict[str, Any]], match_day: str) -> None:
        """Write one JSON snapshot plus a flat line-up file and a flat injury file."""
        PrematchSource.OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
        snapshot_file = PrematchSource.OUTPUT_FOLDER / (
            PrematchSource.SNAPSHOT_FILE_NAME_TEMPLATE.format(match_day=match_day)
        )
        snapshot_file.write_text(
            json.dumps(
                snapshots, ensure_ascii=False, indent=PrematchSource.JSON_INDENT
            ),
            encoding=CsvFileSetting.ENCODING,
        )
        self._write_csv_file(
            PrematchSource.OUTPUT_FOLDER
            / PrematchSource.LINEUP_FILE_NAME_TEMPLATE.format(match_day=match_day),
            PrematchSource.LINEUP_COLUMN_NAMES,
            self._build_lineup_rows(snapshots),
        )
        self._write_csv_file(
            PrematchSource.OUTPUT_FOLDER
            / PrematchSource.INJURY_FILE_NAME_TEMPLATE.format(match_day=match_day),
            PrematchSource.INJURY_COLUMN_NAMES,
            self._build_injury_rows(snapshots),
        )

    def _build_lineup_rows(self, snapshots: list[dict[str, Any]]) -> list[list[Any]]:
        """Build one row per player of every line-up of the day."""
        rows: list[list[Any]] = []
        for snapshot in snapshots:
            for is_home, team_name in ((1, snapshot["home"]), (0, snapshot["away"])):
                lineup = snapshot["lineups"].get(team_name)
                if not lineup:
                    continue
                for role, players in (
                    (PrematchSource.STARTER_ROLE, lineup["start_xi"]),
                    (PrematchSource.SUBSTITUTE_ROLE, lineup["substitutes"]),
                ):
                    for player in players:
                        rows.append(
                            [
                                snapshot["fixture_id"],
                                snapshot["kickoff"],
                                team_name,
                                is_home,
                                lineup["formation"],
                                lineup["coach"],
                                role,
                                player["player"],
                                player["number"],
                                player["position"],
                            ]
                        )
        return rows

    def _build_injury_rows(self, snapshots: list[dict[str, Any]]) -> list[list[Any]]:
        """Build one row per player who is out, over every match of the day."""
        rows: list[list[Any]] = []
        for snapshot in snapshots:
            for team_name in (snapshot["home"], snapshot["away"]):
                for injury in snapshot["injuries"].get(team_name, []):
                    rows.append(
                        [
                            snapshot["fixture_id"],
                            team_name,
                            injury["player"],
                            injury["type"],
                            injury["reason"],
                        ]
                    )
        return rows

    def _write_csv_file(
        self, target_file: Path, column_names: tuple[str, ...], rows: list[list[Any]]
    ) -> None:
        """Write one flat file with its header."""
        with CsvFile(target_file, column_names).writing_writer() as writer:
            writer.writerows(rows)


if __name__ == "__main__":
    chosen_day = (
        sys.argv[1]
        if len(sys.argv) > 1
        else datetime.now(UTC).strftime(TimeStampFormat.ISO_DAY)
    )
    PrematchFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=WebRequestSetting.STANDARD_POLITE_DELAY_IN_SECONDS,
        ),
        ApiKeyReader(),
    ).fetch_match_day(chosen_day)
