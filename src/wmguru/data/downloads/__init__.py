"""Downloaders that fetch a whole dataset and put it on disk unchanged.

Every one of them skips what is already there, so a stopped run is cheap to
repeat. Turning a source into the canonical schema is a later step.
"""
