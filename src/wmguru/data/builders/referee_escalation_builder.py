"""Whether a hard team and a strict referee together give extra cards.

Fouls come off the Wyscout actions, cards off the card tags of the events, and
the referee off the match files. Both the foul count of a team and the
strictness of a referee are standardised first, so a team of one league can be
compared with a team of another.

Two files come out: what each referee is like, and the table of foul band
against strictness band.
"""

from statistics import mean, pstdev
from typing import Any

from wmguru.helpers.constant import (
    MatchStyleFeature,
    RefereeEscalationCalculation,
    WyscoutEventFile,
)
from wmguru.helpers.utils import CsvFile, TextNormalizer, WyscoutDataReader


class RefereeEscalationBuilder:
    """The fouls and cards of every match, banded by referee."""

    def __init__(self, wyscout_data_reader: WyscoutDataReader) -> None:
        self._wyscout_data_reader = wyscout_data_reader

    def build_the_tables(self) -> int:
        """Write what each referee is like and the band table.

        Returns:
            How many band cells the table holds.
        """
        lookups = self._wyscout_data_reader.read_name_lookups()
        match_facts = self._wyscout_data_reader.read_match_facts()
        fouls_of_team = self._count_fouls(lookups)
        cards_of_team = self._count_cards()

        strictness, strictness_rows = self._measure_every_referee(
            fouls_of_team, cards_of_team, match_facts, lookups
        )
        table_rows = self._build_the_band_table(
            fouls_of_team, cards_of_team, match_facts, strictness
        )

        CsvFile(
            RefereeEscalationCalculation.STRICTNESS_OUTPUT_FILE,
            RefereeEscalationCalculation.STRICTNESS_COLUMN_NAMES,
        ).write_dict_rows(strictness_rows)
        CsvFile(
            RefereeEscalationCalculation.ESCALATION_OUTPUT_FILE,
            RefereeEscalationCalculation.ESCALATION_COLUMN_NAMES,
        ).write_dict_rows(table_rows)
        print(f"  OK    {len(strictness_rows)} referees, {len(table_rows)} band cells")
        print(f"  INFO  {self._describe_the_excess(table_rows)}")
        return len(table_rows)

    def _count_fouls(self, lookups: Any) -> dict[tuple[str, str], int]:
        """Count the fouls of each team in each match."""
        fouls_of_team: dict[tuple[str, str], int] = {}
        for (
            game_identifier,
            actions,
        ) in self._wyscout_data_reader.stream_actions_of_every_match(lookups):
            for action in actions:
                if action.kind != MatchStyleFeature.FOUL_KIND:
                    continue
                key = (game_identifier, action.team_name)
                fouls_of_team[key] = fouls_of_team.get(key, 0) + 1
        return fouls_of_team

    def _count_cards(self) -> dict[tuple[str, str], int]:
        """Count the cards of each team in each match, out of the event tags.

        The teams are named by identifier here, so the foul count has to be
        keyed the same way. It is not, so this reads the team of each card
        event as the name the action stream also uses.
        """
        team_names = self._wyscout_data_reader.read_team_names()
        cards_of_team: dict[tuple[str, str], int] = {}
        for event_file in sorted(
            WyscoutEventFile.SOURCE_FOLDER.glob(WyscoutEventFile.EVENT_FILE_PATTERN)
        ):
            for event in CsvFile(event_file).stream_rows():
                card_names = self._wyscout_data_reader.read_card_names_out_of_tag_list(
                    event.get(WyscoutEventFile.TAG_LIST_COLUMN, "")
                )
                if not card_names:
                    continue
                team_identifier = self._wyscout_data_reader.as_identifier(
                    event.get(WyscoutEventFile.TEAM_IDENTIFIER_COLUMN, "")
                )
                key = (
                    self._wyscout_data_reader.as_identifier(
                        event.get(WyscoutEventFile.MATCH_IDENTIFIER_COLUMN, "")
                    ),
                    team_names.get(team_identifier, team_identifier),
                )
                cards_of_team[key] = cards_of_team.get(key, 0) + len(card_names)
        return cards_of_team

    def _measure_every_referee(
        self,
        fouls_of_team: dict[tuple[str, str], int],
        cards_of_team: dict[tuple[str, str], int],
        match_facts: dict[str, Any],
        lookups: Any,
    ) -> tuple[dict[str, float], list[dict[str, Any]]]:
        """Work out the cards per foul of every referee.

        Returns:
            The ratio of each referee who took charge of enough matches, and
            one row per referee for the file.
        """
        fouls_of_match = self._both_teams_together(fouls_of_team)
        cards_of_match = self._both_teams_together(cards_of_team)
        totals: dict[str, list[int]] = {}
        for game_identifier, facts in match_facts.items():
            if not facts.referee_identifier:
                continue
            total = totals.setdefault(facts.referee_identifier, [0, 0, 0])
            total[0] += 1
            total[1] += fouls_of_match.get(game_identifier, 0)
            total[2] += cards_of_match.get(game_identifier, 0)

        strictness: dict[str, float] = {}
        rows: list[dict[str, Any]] = []
        for referee_identifier, (matches, fouls, cards) in totals.items():
            if matches < RefereeEscalationCalculation.MINIMUM_MATCHES or not fouls:
                continue
            strictness[referee_identifier] = cards / fouls
            rows.append(
                {
                    "referee": lookups.referee_names.get(
                        referee_identifier, referee_identifier
                    ),
                    "matches": matches,
                    "fouls": fouls,
                    "cards": cards,
                    "cards_per_foul": round(
                        cards / fouls,
                        RefereeEscalationCalculation.RATIO_DECIMAL_PLACES,
                    ),
                }
            )
        return strictness, sorted(rows, key=lambda one: -float(one["cards_per_foul"]))

    def _both_teams_together(
        self, counts: dict[tuple[str, str], int]
    ) -> dict[str, int]:
        """Add the two teams of each match into one count per match."""
        counts_of_match: dict[str, int] = {}
        for (game_identifier, _team), count in counts.items():
            counts_of_match[game_identifier] = (
                counts_of_match.get(game_identifier, 0) + count
            )
        return counts_of_match

    def _build_the_band_table(
        self,
        fouls_of_team: dict[tuple[str, str], int],
        cards_of_team: dict[tuple[str, str], int],
        match_facts: dict[str, Any],
        strictness: dict[str, float],
    ) -> list[dict[str, Any]]:
        """Average the cards over every combination of the two bands."""
        foul_scales = self._foul_scales_of_every_season(fouls_of_team, match_facts)
        strictness_scale = self._scale_of(list(strictness.values()))

        cells: dict[tuple[str, str], list[float]] = {}
        for (game_identifier, team_name), fouls in fouls_of_team.items():
            facts = match_facts.get(game_identifier)
            if facts is None or facts.referee_identifier not in strictness:
                continue
            season_key = (facts.competition_identifier, facts.season_name)
            if season_key not in foul_scales:
                continue
            cell = cells.setdefault(
                (
                    self._band_of(fouls, foul_scales[season_key]),
                    self._band_of(
                        strictness[facts.referee_identifier], strictness_scale
                    ),
                ),
                [0.0, 0.0, 0.0],
            )
            cell[0] += 1
            cell[1] += fouls
            cell[2] += cards_of_team.get((game_identifier, team_name), 0)
        return self._build_table_rows(cells)

    def _foul_scales_of_every_season(
        self,
        fouls_of_team: dict[tuple[str, str], int],
        match_facts: dict[str, Any],
    ) -> dict[tuple[str, str], tuple[float, float]]:
        """Work out the middle and spread of the team foul count per season."""
        values_of_season: dict[tuple[str, str], list[float]] = {}
        for (game_identifier, _team), fouls in fouls_of_team.items():
            facts = match_facts.get(game_identifier)
            if facts is None:
                continue
            values_of_season.setdefault(
                (facts.competition_identifier, facts.season_name), []
            ).append(float(fouls))
        return {
            season_key: self._scale_of(values)
            for season_key, values in values_of_season.items()
            if len(values) >= RefereeEscalationCalculation.MINIMUM_VALUES_FOR_A_SCALE
        }

    def _scale_of(self, values: list[float]) -> tuple[float, float]:
        """The middle and the spread a value is standardised with."""
        if len(values) < RefereeEscalationCalculation.MINIMUM_VALUES_FOR_A_SCALE:
            return 0.0, 0.0
        return mean(values), pstdev(values)

    def _band_of(self, value: float, scale: tuple[float, float]) -> str:
        """Say whether a value is high, medium or low for its season."""
        middle, spread = scale
        standardised = (value - middle) / spread if spread else 0.0
        if standardised >= RefereeEscalationCalculation.HIGH_BAND_FROM:
            return RefereeEscalationCalculation.HIGH_BAND_NAME
        if standardised <= RefereeEscalationCalculation.LOW_BAND_UP_TO:
            return RefereeEscalationCalculation.LOW_BAND_NAME
        return RefereeEscalationCalculation.MIDDLE_BAND_NAME

    def _build_table_rows(
        self, cells: dict[tuple[str, str], list[float]]
    ) -> list[dict[str, Any]]:
        """Turn the counted cells into the rows of the table."""
        rows = [
            {
                "aggression_band": aggression_band,
                "strictness_band": strictness_band,
                "team_matches": int(matches),
                "mean_fouls": round(
                    fouls / matches,
                    RefereeEscalationCalculation.FOUL_DECIMAL_PLACES,
                ),
                "mean_cards": round(
                    cards / matches,
                    RefereeEscalationCalculation.CARD_DECIMAL_PLACES,
                ),
            }
            for (aggression_band, strictness_band), (
                matches,
                fouls,
                cards,
            ) in cells.items()
        ]
        order = RefereeEscalationCalculation.BAND_ORDER
        return sorted(
            rows,
            key=lambda one: (
                order.index(one["aggression_band"]),
                order.index(one["strictness_band"]),
            ),
        )

    def _describe_the_excess(self, table_rows: list[dict[str, Any]]) -> str:
        """Compare the hardest cell with what simply adding up would predict.

        Returns:
            One line for the log. An excess above zero is the whole point of
            the feature: it says the two do not merely add up.
        """
        cards_of_cell = {
            (row["aggression_band"], row["strictness_band"]): float(row["mean_cards"])
            for row in table_rows
        }
        high = RefereeEscalationCalculation.HIGH_BAND_NAME
        observed = cards_of_cell.get((high, high))
        if observed is None:
            return "no high against high cell, nothing to compare"
        overall = mean(cards_of_cell.values())
        hard_teams = self._average_over(cards_of_cell, aggression_band=high) or overall
        strict_referees = (
            self._average_over(cards_of_cell, strictness_band=high) or overall
        )
        adding_up = hard_teams + strict_referees - overall
        return (
            f"high against high gives {observed:.3f} cards per team and match, "
            f"adding up would give {adding_up:.3f}, "
            f"excess {observed - adding_up:+.3f}"
        )

    def _average_over(
        self,
        cards_of_cell: dict[tuple[str, str], float],
        aggression_band: str | None = None,
        strictness_band: str | None = None,
    ) -> float:
        """Average the cells of one band, or zero when there are none."""
        wanted = [
            cards
            for (aggression, strictness), cards in cards_of_cell.items()
            if (aggression_band is None or aggression == aggression_band)
            and (strictness_band is None or strictness == strictness_band)
        ]
        return mean(wanted) if wanted else 0.0


if __name__ == "__main__":
    RefereeEscalationBuilder(WyscoutDataReader(TextNormalizer())).build_the_tables()
