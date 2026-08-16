"""How much a team's style swings from match to match.

Reads the style rows both event sources wrote and, per competition and season,
standardises every dimension so a share and a distance in metres can be
compared at all. The swing of a team is then the average spread of those
standardised values over its matches.

Two group by passes do the whole thing: one over the season to get the scale,
one over the team to get its average and its swing.
"""

import numpy as np
import pandas as pd

from wmguru.helpers.constant import (
    MatchStyleFeature,
    TeamStyleStabilityCalculation,
)
from wmguru.helpers.utils import CsvFile, DecimalRounder

SEASON_KEYS = ["source", "competition", "season"]
TEAM_KEYS = [*SEASON_KEYS, "team"]


class TeamStyleStabilityBuilder:
    """The style rows of every match, as one row per team and season."""

    def build_every_team(self) -> int:
        """Write one row per team that played enough matches to judge.

        Returns:
            How many teams the file holds.
        """
        style_rows = self._read_style_rows()
        standardised = self._standardised_within_the_season(style_rows)
        rows = self._summarise_every_team(style_rows, standardised)

        CsvFile(
            TeamStyleStabilityCalculation.OUTPUT_FILE,
            TeamStyleStabilityCalculation.COLUMN_NAMES,
        ).write_table(rows)
        print(
            f"  OK    {len(rows)} team rows with at least "
            f"{TeamStyleStabilityCalculation.MINIMUM_MATCHES} matches"
        )
        return len(rows)

    def _read_style_rows(self) -> pd.DataFrame:
        """Read the style file, with every dimension turned into a number.

        A style column is left empty where the match gave nothing to divide
        by, and an empty cell must never be read as a zero.
        """
        style_rows = CsvFile(MatchStyleFeature.OUTPUT_FILE).read_table()
        dimensions = TeamStyleStabilityCalculation.DIMENSIONS
        return style_rows.assign(
            **{
                name: pd.to_numeric(style_rows[name], errors="coerce")
                for name in dimensions
            }
        )

    def _standardised_within_the_season(self, style_rows: pd.DataFrame) -> pd.DataFrame:
        """Say how far each match sits from the middle of its own season.

        A share and a distance in metres cannot be compared as they are. A
        season that gave fewer than two values for a dimension has no spread
        to standardise against, and those stay empty.
        """
        dimensions = list(TeamStyleStabilityCalculation.DIMENSIONS)
        grouped = style_rows.groupby(SEASON_KEYS, dropna=False)[dimensions]
        middle = grouped.transform("mean")
        spread = grouped.transform(lambda values: values.std(ddof=0))
        enough_values = grouped.transform("count") >= (
            TeamStyleStabilityCalculation.MINIMUM_VALUES_FOR_A_SCALE
        )
        usable = enough_values & spread.gt(0)
        return ((style_rows[dimensions] - middle) / spread).where(usable)

    def _summarise_every_team(
        self, style_rows: pd.DataFrame, standardised: pd.DataFrame
    ) -> pd.DataFrame:
        """Average every dimension per team, and measure how much it swung."""
        dimensions = list(TeamStyleStabilityCalculation.DIMENSIONS)
        rounder = DecimalRounder(TeamStyleStabilityCalculation.DECIMAL_PLACES)
        keys = style_rows[TEAM_KEYS]

        grouped_rows = style_rows.groupby(TEAM_KEYS, dropna=False)
        averages = rounder.round_every_column(
            grouped_rows[dimensions].mean(), dimensions
        )
        swings = rounder.round_every_column(
            standardised.join(keys)
            .groupby(TEAM_KEYS, dropna=False)[dimensions]
            .agg(lambda values: values.std(ddof=0)),
            dimensions,
        )
        match_counts = grouped_rows.size().rename("matches")

        summary = pd.concat(
            [
                match_counts,
                averages.add_suffix(TeamStyleStabilityCalculation.MEAN_SUFFIX),
                swings.add_suffix(TeamStyleStabilityCalculation.VOLATILITY_SUFFIX),
            ],
            axis="columns",
        )
        summary["style_volatility"] = rounder.round_every_value(
            swings.mean(axis="columns")
        )
        enough_matches = (
            summary["matches"] >= TeamStyleStabilityCalculation.MINIMUM_MATCHES
        )
        return summary[enough_matches].reset_index().sort_values(TEAM_KEYS)

    def swing_of(self, values: pd.Series, scale: tuple[float, float] | None) -> float:
        """Measure how much one dimension of one team swung.

        Args:
            values: What the team did in that dimension, one entry per match.
            scale: The middle and the spread of the whole season, or None
                when the season gave too few values to say.

        Returns:
            The spread of the standardised values, or not a number when the
            season could not be standardised at all.
        """
        if scale is None or not scale[1]:
            return np.nan
        middle, spread = scale
        return float(((values - middle) / spread).std(ddof=0))


if __name__ == "__main__":
    TeamStyleStabilityBuilder().build_every_team()
