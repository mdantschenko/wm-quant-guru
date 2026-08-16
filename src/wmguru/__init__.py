"""The forecasting and decision system for the 2026 World Cup.

The layers follow section 11 of the concept (docs/konzept.tex): data reads the
sources, models turn features into a scoreline distribution, market removes the
bookmaker margin, pricing turns the distribution into prices, decision turns it
into an action, backtest replays it over history and evaluation scores it.
"""
