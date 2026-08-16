"""Which style of play beats which, out of the style rows.

Every team of every season gets an archetype from its standardised style
values, and every pairing of archetypes gets the expected goals it produced
and conceded. That is the rock paper scissors effect in numbers.

Two files come out: the archetype of each team, and the matrix of pairings.
The matrix rests on expected goals, so it mostly covers StatsBomb.
"""

import numpy as np
import pandas as pd

from wmguru.helpers.constant import MatchStyleFeature, StyleMatchupCalculation
from wmguru.helpers.utils import CsvFile, DecimalRounder

SEASON_KEYS = ["source", "competition", "season"]
TEAM_KEYS = [*SEASON_KEYS, "team"]


class StyleMatchupBuilder:
    """A style archetype per team, and every archetype paired off."""

    def build_the_matrix(self) -> int:
        """Write the archetype of every team and the matrix of pairings.

        Returns:
            How many pairings the matrix holds.
        """
        style_rows = self._read_style_rows()
        archetypes = self._build_archetype_rows(style_rows)
        matrix = self._build_matrix_rows(style_rows, archetypes)

        CsvFile(
            StyleMatchupCalculation.ARCHETYPE_OUTPUT_FILE,
            StyleMatchupCalculation.ARCHETYPE_COLUMN_NAMES,
        ).write_table(archetypes)
        CsvFile(
            StyleMatchupCalculation.MATRIX_OUTPUT_FILE,
            StyleMatchupCalculation.MATRIX_COLUMN_NAMES,
        ).write_table(matrix)
        print(f"  OK    {len(archetypes)} team archetypes, {len(matrix)} pairings")
        return len(matrix)

    def _read_style_rows(self) -> pd.DataFrame:
        """Read the style file, with every number turned into a number."""
        style_rows = CsvFile(MatchStyleFeature.OUTPUT_FILE).read_table()
        numeric_columns = [
            *StyleMatchupCalculation.DIMENSIONS,
            "expected_goals",
            "expected_goals_against",
        ]
        return style_rows.assign(
            **{
                name: pd.to_numeric(style_rows[name], errors="coerce")
                for name in numeric_columns
            }
        )

    def _build_archetype_rows(self, style_rows: pd.DataFrame) -> pd.DataFrame:
        """Average every team, standardise it against its season, and name it."""
        dimensions = list(StyleMatchupCalculation.DIMENSIONS)
        grouped = style_rows.groupby(TEAM_KEYS, dropna=False)
        profiles = grouped[dimensions].mean()
        profiles["matches"] = grouped.size()
        profiles = profiles.reset_index()

        standardised = self._standardised_within_the_season(profiles)
        rounder = DecimalRounder(StyleMatchupCalculation.STANDARDISED_DECIMAL_PLACES)
        named = profiles[[*TEAM_KEYS, "matches"]].assign(
            pass_share_standardised=rounder.round_every_value(
                standardised["pass_share"]
            ),
            field_tilt_standardised=rounder.round_every_value(
                standardised["field_tilt"]
            ),
            passes_per_defensive_action_standardised=rounder.round_every_value(
                standardised["passes_per_defensive_action"]
            ),
            directness_standardised=rounder.round_every_value(
                standardised["directness_in_metres"]
            ),
            defensive_action_height_standardised=rounder.round_every_value(
                standardised["defensive_action_height_in_metres"]
            ),
            archetype=self.archetype_of(standardised),
            has_empty_possession=self._has_empty_possession(standardised).astype(int),
        )
        enough_matches = named["matches"] >= StyleMatchupCalculation.MINIMUM_MATCHES
        return named[enough_matches].sort_values(TEAM_KEYS)

    def _standardised_within_the_season(self, profiles: pd.DataFrame) -> pd.DataFrame:
        """Say how far each team sits from the middle of its own league.

        A league where everybody passes a lot would otherwise make every one
        of its teams look like a possession side. A season with fewer than
        two teams has no spread, and its teams all come out in the middle.
        """
        dimensions = list(StyleMatchupCalculation.DIMENSIONS)
        grouped = profiles.groupby(SEASON_KEYS, dropna=False)[dimensions]
        middle = grouped.transform("mean")
        spread = grouped.transform(lambda values: values.std(ddof=0))
        enough_teams = grouped.transform("count") >= (
            StyleMatchupCalculation.MINIMUM_VALUES_FOR_A_SCALE
        )
        usable = enough_teams & spread.gt(0)
        return ((profiles[dimensions] - middle) / spread).where(usable, 0.0).fillna(0.0)

    def archetype_of(self, standardised: pd.DataFrame) -> pd.Series:
        """Name the style every team played, out of its standardised values.

        Args:
            standardised: How far each team sat from the middle of its league
                in each dimension, one row per team.

        Returns:
            The archetype per row. The order of the tests matters: a side
            that keeps the ball without ever getting near the box is its own
            thing and has to be caught before it is called dominant.
        """
        high = StyleMatchupCalculation.HIGH_FROM
        low = StyleMatchupCalculation.LOW_UP_TO
        return pd.Series(
            np.select(
                [
                    (standardised["pass_share"] >= high)
                    & (standardised["field_tilt"] >= high),
                    self._has_empty_possession(standardised),
                    (standardised["directness_in_metres"] >= high)
                    & (standardised["pass_share"] <= low),
                    (standardised["pass_share"] <= low)
                    & (
                        (standardised["passes_per_defensive_action"] >= high)
                        | (standardised["defensive_action_height_in_metres"] <= low)
                    ),
                ],
                [
                    StyleMatchupCalculation.POSSESSION_DOMINANCE_NAME,
                    StyleMatchupCalculation.EMPTY_POSSESSION_NAME,
                    StyleMatchupCalculation.DIRECT_AND_PHYSICAL_NAME,
                    StyleMatchupCalculation.DEEP_BLOCK_AND_COUNTER_NAME,
                ],
                default=StyleMatchupCalculation.BALANCED_NAME,
            ),
            index=standardised.index,
        )

    def _has_empty_possession(self, standardised: pd.DataFrame) -> pd.Series:
        """Return True when a team keeps the ball but gets nowhere with it."""
        return (standardised["pass_share"] >= StyleMatchupCalculation.HIGH_FROM) & (
            standardised["field_tilt"] < 0
        )

    def _build_matrix_rows(
        self, style_rows: pd.DataFrame, archetypes: pd.DataFrame
    ) -> pd.DataFrame:
        """Average the expected goals of every pairing of archetypes.

        Both sides of a match are looked up in the same archetype table, once
        on the team and once on the opponent, which is a join onto the same
        table twice.
        """
        lookup = archetypes[[*TEAM_KEYS, "archetype"]]
        with_own = style_rows.merge(lookup, on=TEAM_KEYS, how="inner")
        with_both = with_own.merge(
            lookup.rename(
                columns={"team": "opponent", "archetype": "archetype_against"}
            ),
            on=[*SEASON_KEYS, "opponent"],
            how="inner",
        ).rename(columns={"archetype": "archetype_for"})

        priced = with_both.dropna(
            subset=["expected_goals", "expected_goals_against"]
        ).assign(
            expected_goals_difference=lambda match: match["expected_goals"]
            - match["expected_goals_against"]
        )
        matrix = (
            priced.groupby(["archetype_for", "archetype_against"], dropna=False)
            .agg(
                matches=("expected_goals", "size"),
                mean_expected_goals_for=("expected_goals", "mean"),
                mean_expected_goals_against=("expected_goals_against", "mean"),
                mean_expected_goals_difference=("expected_goals_difference", "mean"),
            )
            .reset_index()
        )
        return (
            DecimalRounder(StyleMatchupCalculation.EXPECTED_GOALS_DECIMAL_PLACES)
            .round_every_column(
                matrix,
                [
                    "mean_expected_goals_for",
                    "mean_expected_goals_against",
                    "mean_expected_goals_difference",
                ],
            )
            .sort_values(["archetype_for", "archetype_against"])
        )


if __name__ == "__main__":
    StyleMatchupBuilder().build_the_matrix()
