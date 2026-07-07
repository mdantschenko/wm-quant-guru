
"""
In this file we set up the canonical data model from the concept in chapter 4.1.
These are the rows from our datasets. Our datasets won't fit this model from the start, but this
is our desired state for each dataset.
"""

from dataclasses import dataclass
from typing import Any
from datetime import datetime

@dataclass(frozen=True)
class MatchRecord:
    match_id: str 
    match_date: str 
    home_team_id: str
    away_team_id: str 
    home_goals_regular_time: int 
    away_goals_regular_time: int 
    home_goals_final: int 
    away_goals_final: int 
    is_regular_time_score_reconstructed_unreliable: bool 
    is_neutral_venue: bool 
    tournament_name: str 
    competition_category: str 
    city: str = ""
    country: str = ""
    home_shootout_goals: int | None = None
    away_shootout_goals: int | None = None

    @staticmethod
    def _check_if_value_is_empty_or_missing(column_name: str, column_value: Any):
        """
        This is a helper function that detects if a cell is empty or not provided.
        """
        error_message = ""

        if column_value == "":
                error_message = f"The value from the column {column_name} is empty."
                return True, error_message
        if column_value == "NOT_PROVIDED":
                error_message = f"The value from the column {column_name} was not found."
                return True, error_message
        if column_value is None:
                error_message = f"The value from the column {column_name} is not provided."
                return True, error_message
        
        return False, ""

    @classmethod
    def parse_and_validate_row(cls, row_from_csv: dict):
        """
        Construct a MatchRecord from a raw CSV row. Before constructing a MatchRecord object, we need to make sure that the types are correct.
        """
        error_list = []
        correct_type_values_from_csv = {}

        string_column_test = ("match_id", "match_date", "home_team_id", "away_team_id", "tournament_name", "competition_category")
        optional_string_column_test = ("city", "country")
        integer_column_test = ("home_goals_regular_time", "away_goals_regular_time", "home_goals_final", "away_goals_final")
        optional_integer_column_test = ("home_shootout_goals", "away_shootout_goals")
        bool_column_test = ("is_regular_time_score_reconstructed_unreliable", "is_neutral_venue")

        # Here we test the formats of the string values
        for column_name in string_column_test:
            column_value = row_from_csv.get(column_name, "NOT_PROVIDED")
            is_column_value_not_okay, error_message = cls._check_if_value_is_empty_or_missing(column_name, column_value)

            if is_column_value_not_okay:
                error_list.append(error_message)
            else:
                correct_type_values_from_csv[column_name] = column_value
        
        # Here we test the formats of the optional string values
        for column_name in optional_string_column_test:
            column_value = row_from_csv.get(column_name, "")
            correct_type_values_from_csv[column_name] = column_value

        # Here we test the formats of the integer values
        for column_name in integer_column_test:
            column_value = row_from_csv.get(column_name, "NOT_PROVIDED")
            is_column_value_not_okay, error_message = cls._check_if_value_is_empty_or_missing(column_name, column_value)

            if is_column_value_not_okay:
                error_list.append(error_message)
            else:
                try:
                    column_value = int(column_value)
                    if column_value >= 0:
                        correct_type_values_from_csv[column_name] = column_value
                    else:
                        error_list.append(f"The value {column_value} from the column {column_name} must not be negative.")
                except ValueError:
                    error_list.append(f"The value {column_value} from the column {column_name} is not an integer.")

        # Here we test the formats of the optional integer values
        for column_name in optional_integer_column_test:
            column_value = row_from_csv.get(column_name, None)
            
            if column_value == "" or column_value is None:
                column_value = None
                correct_type_values_from_csv[column_name] = column_value
                continue
            try:
                column_value = int(column_value)
                if column_value >= 0:
                    correct_type_values_from_csv[column_name] = column_value
                else:
                    error_list.append(f"The value {column_value} from the column {column_name} must not be negative.")
            except ValueError:
                    error_list.append(f"The value {column_value} from the column {column_name} is not an integer.")

        # Here we test the formats of the bool values
        for column_name in bool_column_test:
            column_value = row_from_csv.get(column_name, "NOT_PROVIDED")
            is_column_value_not_okay, error_message = cls._check_if_value_is_empty_or_missing(column_name, column_value)

            if is_column_value_not_okay:
                error_list.append(error_message)
            else:
                try:
                    column_value = int(column_value)
                    if column_value == 0 or column_value == 1:
                        column_value = bool(column_value)
                        correct_type_values_from_csv[column_name] = column_value
                    else:
                        error_list.append(f"The value {column_value} from the column {column_name} is not a bool.")
                except ValueError:
                    error_list.append(f"The value {column_value} from the column {column_name} is not a bool.")

        # Here we test the data format
        match_date = row_from_csv.get("match_date", "NOT_PROVIDED")
        try:
            datetime.strptime(match_date, "%Y-%m-%d")
        except ValueError:
            error_list.append(f"Invalid date format {match_date} from column match_date.")
        
        # Here we test the team_id format
        home_team_id = row_from_csv.get("home_team_id", "NOT_PROVIDED")
        away_team_id = row_from_csv.get("away_team_id", "NOT_PROVIDED")
        if home_team_id == away_team_id:
            error_list.append(f"The ids home_team_id={home_team_id} and away_team_id={away_team_id} must not be equal.")
        
        # Here we test the end scores.
        keys_for_validating_goals = ["is_regular_time_score_reconstructed_unreliable", "home_goals_regular_time", "away_goals_regular_time", "home_goals_final", "away_goals_final"]
        if all(key in correct_type_values_from_csv for key in keys_for_validating_goals):
            is_regular_time_score_reconstructed_unreliable = correct_type_values_from_csv["is_regular_time_score_reconstructed_unreliable"]
            home_goals_regular_time = correct_type_values_from_csv["home_goals_regular_time"]
            away_goals_regular_time = correct_type_values_from_csv["away_goals_regular_time"]
            home_goals_final = correct_type_values_from_csv["home_goals_final"]
            away_goals_final = correct_type_values_from_csv["away_goals_final"]

            if not is_regular_time_score_reconstructed_unreliable:
                if home_goals_regular_time > home_goals_final:
                    error_list.append("The goal-count reached in regular time must be less than or equal to the goal count reached after the extra time.")
                if away_goals_regular_time > away_goals_final:
                    error_list.append("The goal-count reached in regular time must be less than or equal to the goal count reached after the extra time.")

        # Here we test the shootout-values.
        keys_for_validating_shootout = ["home_shootout_goals", "away_shootout_goals", "home_goals_final", "away_goals_final"]
        if all(key in correct_type_values_from_csv for key in keys_for_validating_shootout):
            home_shootout_goals = correct_type_values_from_csv["home_shootout_goals"]
            away_shootout_goals = correct_type_values_from_csv["away_shootout_goals"]
            home_goals_final = correct_type_values_from_csv["home_goals_final"]
            away_goals_final = correct_type_values_from_csv["away_goals_final"]

            if (home_shootout_goals is None and away_shootout_goals is not None) or (home_shootout_goals is not None and away_shootout_goals is None):
                error_list.append(f"If one of the shootout-values is None, so must be the other. Values: 1) home_shootout_goals={home_shootout_goals} 2) away_shootout_goals={away_shootout_goals}.")
            if home_shootout_goals is not None and away_shootout_goals is not None:
                if home_shootout_goals == away_shootout_goals:
                    error_list.append(f"After the shootout, either home_shootout_goals={home_shootout_goals} or away_shootout_goals={away_shootout_goals} must be larger.")
                if home_goals_final != away_goals_final:
                    error_list.append(f"If there were shootouts, there must be a draw after regular time and after extra time.")

        if len(error_list) == 0:
            #      This is the validated data for one row
            return cls(**correct_type_values_from_csv), error_list
        else:
            return None, error_list



