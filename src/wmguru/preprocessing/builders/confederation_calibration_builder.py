"""What the Elo ratings get wrong between the confederations.

National teams play mostly inside their own confederation, so how the
confederations stand against each other is barely in the ratings. That is
exactly the comparison a World Cup turns on.

Three files come out: the residual of every pair and era, the estimated Elo
offset of every confederation, and an audit of which team was put where.
"""

import math

import numpy as np
import pandas as pd

from wmguru.helpers.constant import (
    ConfederationCalibration,
    CrowdTipPriorCalculation,
    InternationalResultSource,
    ResidualFeatureCalculation,
)
from wmguru.helpers.utils import (
    ConfederationLookup,
    CsvFile,
    DecimalRounder,
    TextNormalizer,
)

PAIR_KEYS = ["era", "home_confederation", "away_confederation"]


class ConfederationCalibrationBuilder:
    """The rating bias between confederations, per era."""

    def __init__(self, confederation_lookup: ConfederationLookup) -> None:
        self._confederation_lookup = confederation_lookup

    def build_the_calibration(self) -> int:
        """Write the pair residuals, the offsets and the team audit.

        Returns:
            How many matches across confederations carried a rating.
        """
        every_result = self._read_every_result()
        matches = self._only_the_matches_between_two_confederations(every_result)

        pair_rows = self._build_pair_rows(matches)
        offset_rows = self._build_offset_rows(matches)
        team_rows = self._build_team_rows(every_result)

        CsvFile(
            ConfederationCalibration.PAIR_OUTPUT_FILE,
            ConfederationCalibration.PAIR_COLUMN_NAMES,
        ).write_table(pair_rows)
        CsvFile(
            ConfederationCalibration.OFFSET_OUTPUT_FILE,
            ConfederationCalibration.OFFSET_COLUMN_NAMES,
        ).write_table(offset_rows)
        CsvFile(
            ConfederationCalibration.TEAM_MAP_OUTPUT_FILE,
            ConfederationCalibration.TEAM_MAP_COLUMN_NAMES,
        ).write_table(team_rows)

        unmapped = (
            team_rows["confederation"] == ConfederationCalibration.UNMAPPED_NAME
        ).sum()
        print(f"  OK    {len(matches)} cross confederation matches with a rating")
        print(f"  OK    {len(pair_rows)} pair rows, {len(offset_rows)} offset rows")
        print(f"  INFO  {unmapped} teams without a confederation")
        return len(matches)

    def _read_every_result(self) -> pd.DataFrame:
        """Read every international with the confederation of both sides on it.

        Every row is kept, played or not, because the audit file counts what
        each team turns up in at all.

        Four fixtures are listed twice on the same day against the same
        opponent, and only the later rating of such a pair is kept, so the
        join cannot multiply a match out into several rows.
        """
        results = CsvFile(CrowdTipPriorCalculation.RESULT_FILE).read_table()
        ratings = (
            CsvFile(CrowdTipPriorCalculation.ELO_HISTORY_FILE)
            .read_table()
            .drop_duplicates(subset=["date", "home_team", "away_team"], keep="last")
        )
        home_team = results[InternationalResultSource.HOME_TEAM_COLUMN]
        away_team = results[InternationalResultSource.AWAY_TEAM_COLUMN]

        return results.assign(
            home_team_name=home_team,
            away_team_name=away_team,
            home_confederation=self._confederation_lookup.confederation_of_every_team(
                home_team
            ),
            away_confederation=self._confederation_lookup.confederation_of_every_team(
                away_team
            ),
            home_goals=pd.to_numeric(results["home_score"], errors="coerce"),
            away_goals=pd.to_numeric(results["away_score"], errors="coerce"),
        ).merge(
            ratings.assign(
                home_rating=pd.to_numeric(ratings["elo_home_pre"]),
                away_rating=pd.to_numeric(ratings["elo_away_pre"]),
            )[["date", "home_team", "away_team", "home_rating", "away_rating"]],
            left_on=[
                InternationalResultSource.DATE_COLUMN,
                InternationalResultSource.HOME_TEAM_COLUMN,
                InternationalResultSource.AWAY_TEAM_COLUMN,
            ],
            right_on=["date", "home_team", "away_team"],
            how="left",
        )

    def _only_the_matches_between_two_confederations(
        self, every_result: pd.DataFrame
    ) -> pd.DataFrame:
        """Keep the played matches whose two sides come from different tables."""
        both_are_known = (
            every_result["home_confederation"].notna()
            & every_result["away_confederation"].notna()
        )
        is_a_crossing = (
            every_result["home_confederation"] != every_result["away_confederation"]
        )
        was_played = (
            every_result[["home_goals", "away_goals", "home_rating"]]
            .notna()
            .all(axis="columns")
        )
        crossings = every_result[both_are_known & is_a_crossing & was_played]

        return crossings.assign(
            era=self._era_of(crossings[InternationalResultSource.DATE_COLUMN]),
            was_neutral=crossings[InternationalResultSource.NEUTRAL_VENUE_COLUMN]
            .str.strip()
            .str.upper()
            == ResidualFeatureCalculation.NEUTRAL_TEXT,
            home_points=self._home_points_of(crossings),
            goal_difference=(crossings["home_goals"] - crossings["away_goals"]).astype(
                int
            ),
        )

    def _era_of(self, match_dates: pd.Series) -> pd.Series:
        """Say which era every match belongs to, out of the year it was played."""
        year = match_dates.str.slice(0, 4).astype(int)
        return pd.Series(
            np.select(
                [
                    year < last_year
                    for last_year, _ in ConfederationCalibration.ERA_EDGES
                ],
                [name for _, name in ConfederationCalibration.ERA_EDGES],
                default=ConfederationCalibration.LATEST_ERA_NAME,
            ),
            index=match_dates.index,
        )

    def _home_points_of(self, matches: pd.DataFrame) -> pd.Series:
        """Read what the home side took out of every match."""
        return pd.Series(
            np.select(
                [
                    matches["home_goals"] > matches["away_goals"],
                    matches["home_goals"] == matches["away_goals"],
                ],
                [
                    ResidualFeatureCalculation.WIN_POINTS,
                    ResidualFeatureCalculation.DRAW_POINTS,
                ],
                default=ResidualFeatureCalculation.LOSS_POINTS,
            ),
            index=matches.index,
        )

    def _what_the_rating_expected_of_the_home_side(
        self,
        home_rating: pd.Series,
        away_rating: pd.Series,
        was_neutral: pd.Series,
    ) -> pd.Series:
        """What the rating said the home side would take out of each match."""
        advantage = np.where(was_neutral, 0.0, CrowdTipPriorCalculation.HOME_ADVANTAGE)
        rating_gap = home_rating + advantage - away_rating
        return 1.0 / (
            1.0
            + CrowdTipPriorCalculation.LOGISTIC_BASE
            ** (-rating_gap / CrowdTipPriorCalculation.RATING_SCALE)
        )

    def _once_per_era_and_once_for_all_of_them(
        self, matches: pd.DataFrame
    ) -> pd.DataFrame:
        """Copy every match into its own era and into the row that holds them all."""
        return pd.concat(
            [
                matches,
                matches.assign(era=ConfederationCalibration.EVERY_ERA_NAME),
            ],
            ignore_index=True,
        )

    def _build_pair_rows(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Average the residual of every pair of confederations, per era."""
        expectation = self._what_the_rating_expected_of_the_home_side(
            matches["home_rating"], matches["away_rating"], matches["was_neutral"]
        )
        scored = self._once_per_era_and_once_for_all_of_them(
            matches.assign(
                elo_expected=expectation,
                result_residual=matches["home_points"] - expectation,
            )
        )
        pairs = (
            scored.groupby(PAIR_KEYS, dropna=False)
            .agg(
                matches=("result_residual", "size"),
                mean_result_residual=("result_residual", "mean"),
                mean_elo_expected=("elo_expected", "mean"),
                mean_goal_difference=("goal_difference", "mean"),
            )
            .reset_index()
            .sort_values(PAIR_KEYS)
            .rename(
                columns={
                    "home_confederation": "confederation_home",
                    "away_confederation": "confederation_away",
                }
            )
        )
        residual_rounder = DecimalRounder(
            ConfederationCalibration.RESIDUAL_DECIMAL_PLACES
        )
        goal_rounder = DecimalRounder(ConfederationCalibration.GOAL_DECIMAL_PLACES)
        return residual_rounder.round_every_column(
            pairs, ["mean_result_residual", "mean_elo_expected"]
        ).assign(
            mean_goal_difference=goal_rounder.round_every_value(
                pairs["mean_goal_difference"]
            )
        )

    def _build_offset_rows(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Estimate the offsets of every era that has enough matches."""
        per_era = self._once_per_era_and_once_for_all_of_them(matches)
        matches_in_era = per_era.groupby("era")["home_points"].transform("size")
        big_enough = per_era[
            matches_in_era >= ConfederationCalibration.MINIMUM_MATCHES_FOR_A_FIT
        ]

        fitted = [
            self._fit_offsets(era_matches)
            .rename(ConfederationCalibration.OFFSET_COLUMN)
            .rename_axis("confederation")
            .reset_index()
            .assign(era=era, matches_in_era=len(era_matches))
            for era, era_matches in big_enough.groupby("era", sort=True)
        ]
        return pd.concat(fitted, ignore_index=True).sort_values(
            ["era", "confederation"]
        )

    def _fit_offsets(self, matches: pd.DataFrame) -> pd.Series:
        """Find the rating offsets that explain these matches best.

        The step divides by the curvature rather than by a fixed rate,
        because one Elo point barely moves a probability and a plain gradient
        step would crawl. The reference confederation is held at zero, the
        offsets only mean anything against each other.

        The rounds are a fitting loop and not a walk over the matches: every
        round works on the whole table at once.
        """
        confederations = pd.Index(
            sorted(
                set(matches["home_confederation"]) | set(matches["away_confederation"])
            )
        )
        offsets = pd.Series(0.0, index=confederations)
        sensitivity_scale = (
            math.log(CrowdTipPriorCalculation.LOGISTIC_BASE)
            / CrowdTipPriorCalculation.RATING_SCALE
        )
        is_the_reference = (
            confederations == ConfederationCalibration.REFERENCE_CONFEDERATION
        )

        for _round in range(ConfederationCalibration.FITTING_ROUNDS):
            expectation = self._what_the_rating_expected_of_the_home_side(
                matches["home_rating"] + matches["home_confederation"].map(offsets),
                matches["away_rating"] + matches["away_confederation"].map(offsets),
                matches["was_neutral"],
            )
            steepness = expectation * (1.0 - expectation) * sensitivity_scale
            error = (expectation - matches["home_points"]) * steepness

            slope = self._added_up_on_both_sides(matches, error, -1.0, confederations)
            curvature = self._added_up_on_both_sides(
                matches, steepness * steepness, 1.0, confederations
            )
            step = (
                slope / (curvature + ConfederationCalibration.SMALLEST_USABLE_CURVATURE)
            ).where(~is_the_reference, 0.0)
            offsets = offsets - step

        return DecimalRounder(
            ConfederationCalibration.OFFSET_DECIMAL_PLACES
        ).round_every_value(offsets)

    def _added_up_on_both_sides(
        self,
        matches: pd.DataFrame,
        value_of_match: pd.Series,
        away_sign: float,
        confederations: pd.Index,
    ) -> pd.Series:
        """Add a value onto the home confederation and onto the away one.

        Args:
            matches: The matches the value was measured on, in the same
                order, so both confederations of a match are known.
            value_of_match: What the match contributes, one entry per match.
            away_sign: Minus one where the away side pulls the other way, as
                it does for the slope, and plus one where both sides push the
                same way, as they do for the curvature.
            confederations: Every confederation the result must hold a row
                for, so one that never played at home still turns up.
        """
        at_home = value_of_match.groupby(matches["home_confederation"]).sum()
        away = value_of_match.groupby(matches["away_confederation"]).sum()
        return at_home.add(away_sign * away, fill_value=0.0).reindex(
            confederations, fill_value=0.0
        )

    def _build_team_rows(self, every_result: pd.DataFrame) -> pd.DataFrame:
        """Build the audit rows, the busiest team first.

        Every appearance counts, played or not, so a team that fell out of
        the calibration is easy to spot.
        """
        as_the_home_team = every_result[
            ["home_team_name", "home_confederation"]
        ].rename(
            columns={"home_team_name": "team", "home_confederation": "confederation"}
        )
        as_the_away_team = every_result[
            ["away_team_name", "away_confederation"]
        ].rename(
            columns={"away_team_name": "team", "away_confederation": "confederation"}
        )
        every_appearance = (
            pd.concat([as_the_home_team, as_the_away_team], keys=[0, 1])
            .swaplevel()
            .sort_index(level=0, kind="stable")
        )
        first_seen = every_appearance.drop_duplicates(subset="team", keep="first")

        return (
            first_seen.assign(
                confederation=first_seen["confederation"].fillna(
                    ConfederationCalibration.UNMAPPED_NAME
                ),
                matches=first_seen["team"].map(every_appearance["team"].value_counts()),
            )
            .sort_values("matches", ascending=False, kind="stable")
            .reset_index(drop=True)
        )


if __name__ == "__main__":
    ConfederationCalibrationBuilder(
        ConfederationLookup(TextNormalizer())
    ).build_the_calibration()
