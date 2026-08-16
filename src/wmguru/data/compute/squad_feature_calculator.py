"""Club chemistry and the share of players in the strong leagues.

Club chemistry is the Herfindahl index over the clubs of a national squad. A
value near zero means the players are spread over many clubs, a high value
means a block, for example the Bayern block of the 2014 German squad.

The source is the Wikipedia squad list, which names the real club of a player.
The FootyStats squad list is useless here, because its current club is the
national team itself.
"""

from collections import Counter
from pathlib import Path
from typing import Any

from wmguru.helpers.constant import SquadFeatureCalculation
from wmguru.helpers.utils import CsvFile


class SquadFeatureCalculator:
    """One row per team and tournament, with its squad features."""

    def calculate_every_tournament(self) -> int:
        """Write the file and return how many team rows it holds."""
        rows: list[list[Any]] = []
        for squad_file in sorted(SquadFeatureCalculation.SQUAD_FOLDER.glob("*.csv")):
            rows.extend(self.calculate_one_tournament(squad_file))

        output_file = CsvFile(
            SquadFeatureCalculation.OUTPUT_FILE, SquadFeatureCalculation.COLUMN_NAMES
        )
        output_file.write_rows(rows)
        print(f"{len(rows)} team and tournament rows -> {output_file.path}")
        return len(rows)

    def calculate_one_tournament(self, squad_file: Path) -> list[list[Any]]:
        """Calculate one row per team of one tournament."""
        clubs_of_team, top_league_flags_of_team = self._read_squads(squad_file)
        rows: list[list[Any]] = []
        for team_name, clubs in sorted(clubs_of_team.items()):
            if self._squad_list_is_incomplete(clubs):
                continue
            rows.append(
                self._build_row(
                    squad_file.stem,
                    team_name,
                    clubs,
                    top_league_flags_of_team[team_name],
                )
            )
        return rows

    def _squad_list_is_incomplete(self, clubs: list[str]) -> bool:
        """Return True when the squad list is too short to give a meaningful index."""
        return len(clubs) < SquadFeatureCalculation.SMALLEST_USABLE_SQUAD

    def _read_squads(
        self, squad_file: Path
    ) -> tuple[dict[str, list[str]], dict[str, list[bool]]]:
        """Read the club of every player per team, and whether it is a top league."""
        clubs_of_team: dict[str, list[str]] = {}
        top_league_flags_of_team: dict[str, list[bool]] = {}
        for player in CsvFile(squad_file).read_rows():
            team_name = player[SquadFeatureCalculation.TEAM_COLUMN].strip()
            club_name = player[SquadFeatureCalculation.CLUB_COLUMN].strip()
            if not team_name or not club_name:
                continue
            clubs_of_team.setdefault(team_name, []).append(club_name)
            top_league_flags_of_team.setdefault(team_name, []).append(
                player[SquadFeatureCalculation.CLUB_COUNTRY_COLUMN].upper()
                in SquadFeatureCalculation.TOP_FIVE_LEAGUE_CODES
            )
        return clubs_of_team, top_league_flags_of_team

    def _build_row(
        self,
        tournament_name: str,
        team_name: str,
        clubs: list[str],
        top_league_flags: list[bool],
    ) -> list[Any]:
        """Build one output row."""
        players_per_club = Counter(clubs)
        player_count = sum(players_per_club.values())
        biggest_club, players_of_biggest_club = players_per_club.most_common(1)[0]
        return [
            tournament_name,
            team_name,
            player_count,
            len(players_per_club),
            self._herfindahl_index(players_per_club, player_count),
            biggest_club,
            self._as_share(players_of_biggest_club / player_count),
            self._as_share(sum(top_league_flags) / len(top_league_flags)),
        ]

    def _herfindahl_index(
        self, players_per_club: Counter[str], player_count: int
    ) -> float:
        """Add the squared club shares of one squad up.

        One single club for the whole squad gives one, a squad spread evenly
        over many clubs gives a value near zero.
        """
        return round(
            sum((players / player_count) ** 2 for players in players_per_club.values()),
            SquadFeatureCalculation.INDEX_DECIMAL_PLACES,
        )

    def _as_share(self, share: float) -> float:
        """Cut a share down to a readable number of digits."""
        return round(share, SquadFeatureCalculation.SHARE_DECIMAL_PLACES)


if __name__ == "__main__":
    SquadFeatureCalculator().calculate_every_tournament()
