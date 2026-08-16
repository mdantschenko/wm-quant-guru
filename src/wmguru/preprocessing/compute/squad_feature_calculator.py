"""Club chemistry and the share of players in the strong leagues.

Club chemistry is the Herfindahl index over the clubs of a national squad. A
value near zero means the players are spread over many clubs, a high value
means a block, for example the Bayern block of the 2014 German squad.

The source is the Wikipedia squad list, which names the real club of a player.
The FootyStats squad list is useless here, because its current club is the
national team itself.
"""

from pathlib import Path

import pandas as pd

from wmguru.helpers.constant import SquadFeatureCalculation
from wmguru.helpers.utils import CsvFile, DecimalRounder

TEAM_KEYS = ["tournament", "team"]
CLUB_KEYS = [*TEAM_KEYS, "club"]


class SquadFeatureCalculator:
    """One row per team and tournament, with its squad features."""

    def calculate_every_tournament(self) -> int:
        """Write the file and return how many team rows it holds."""
        every_tournament = pd.concat(
            [
                self.calculate_one_tournament(squad_file)
                for squad_file in sorted(
                    SquadFeatureCalculation.SQUAD_FOLDER.glob("*.csv")
                )
            ],
            ignore_index=True,
        )
        output_file = CsvFile(
            SquadFeatureCalculation.OUTPUT_FILE, SquadFeatureCalculation.COLUMN_NAMES
        )
        output_file.write_table(every_tournament)
        print(f"{len(every_tournament)} team and tournament rows -> {output_file.path}")
        return len(every_tournament)

    def calculate_one_tournament(self, squad_file: Path) -> pd.DataFrame:
        """Calculate one row per team of one tournament."""
        players = self._read_squads(squad_file)
        per_club = self._count_the_players_of_every_club(players)
        return self._describe_every_squad(players, per_club)

    def _read_squads(self, squad_file: Path) -> pd.DataFrame:
        """Read the club of every player, and whether it plays in a top league.

        Other files live in the same folder, so a file that names neither a
        team nor a club is no squad list and is skipped.
        """
        squad_list = CsvFile(squad_file).read_table()
        if not {
            SquadFeatureCalculation.TEAM_COLUMN,
            SquadFeatureCalculation.CLUB_COLUMN,
        } <= set(squad_list.columns):
            return pd.DataFrame(
                columns=[*CLUB_KEYS, "plays_in_a_top_league"], dtype=object
            )
        team = squad_list[SquadFeatureCalculation.TEAM_COLUMN].str.strip()
        club = squad_list[SquadFeatureCalculation.CLUB_COLUMN].str.strip()
        named = squad_list.assign(
            tournament=squad_file.stem,
            team=team,
            club=club,
            plays_in_a_top_league=squad_list[
                SquadFeatureCalculation.CLUB_COUNTRY_COLUMN
            ]
            .str.upper()
            .isin(SquadFeatureCalculation.TOP_FIVE_LEAGUE_CODES),
        )
        return named[(team != "") & (club != "")].reset_index(drop=True)

    def _count_the_players_of_every_club(self, players: pd.DataFrame) -> pd.DataFrame:
        """Count how many players of a squad play for the same club.

        The clubs keep the order they first turn up in the file, so the
        biggest one of two equally big clubs is the one that was named first.
        """
        return (
            players.rename_axis("row_in_the_file")
            .reset_index()
            .groupby(CLUB_KEYS, sort=False)
            .agg(
                players=("row_in_the_file", "size"),
                first_named=("row_in_the_file", "min"),
            )
            .reset_index()
        )

    def _describe_every_squad(
        self, players: pd.DataFrame, per_club: pd.DataFrame
    ) -> pd.DataFrame:
        """Sum every squad up, dropping the lists that are too short to judge."""
        squad_size = per_club.groupby(TEAM_KEYS)["players"].transform("sum")
        club_share = per_club["players"] / squad_size
        shared = per_club.assign(
            squad_size=squad_size, squared_club_share=club_share**2
        )
        summed = shared.groupby(TEAM_KEYS, sort=True).agg(
            players=("squad_size", "first"),
            clubs=("club", "size"),
            club_concentration=("squared_club_share", "sum"),
        )
        biggest = self._biggest_club_of_every_squad(shared)
        top_league_share = players.groupby(TEAM_KEYS, sort=True)[
            "plays_in_a_top_league"
        ].mean()

        index_rounder = DecimalRounder(SquadFeatureCalculation.INDEX_DECIMAL_PLACES)
        share_rounder = DecimalRounder(SquadFeatureCalculation.SHARE_DECIMAL_PLACES)
        described = summed.assign(
            club_concentration=index_rounder.round_every_value(
                summed["club_concentration"]
            ),
            biggest_club=biggest["club"],
            biggest_club_share=share_rounder.round_every_value(
                biggest["players"] / summed["players"]
            ),
            top_five_league_share=share_rounder.round_every_value(top_league_share),
        ).reset_index()
        return described[
            described["players"] >= SquadFeatureCalculation.SMALLEST_USABLE_SQUAD
        ]

    def _biggest_club_of_every_squad(self, per_club: pd.DataFrame) -> pd.DataFrame:
        """Name the club that sends the most players, ties going to the first."""
        most_players_first = per_club.sort_values(
            [*TEAM_KEYS, "players", "first_named"],
            ascending=[True, True, False, True],
            kind="stable",
        )
        return most_players_first.groupby(TEAM_KEYS, sort=True).first()


if __name__ == "__main__":
    SquadFeatureCalculator().calculate_every_tournament()
