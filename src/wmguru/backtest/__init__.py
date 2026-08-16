"""The walk forward engine that replays a model over past tournaments.

It refits and predicts along the time axis and never lets a later fact reach
an earlier prediction, which is what makes a backtest result mean anything.
"""
