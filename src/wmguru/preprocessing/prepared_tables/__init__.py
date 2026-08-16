"""The steps that turn a raw source into the table every builder groups over.

A step here is run by hand, not by a builder. It costs minutes, it gives the
same answer every time, and every builder that reads its output would
otherwise pay the price again. Run a step again whenever its raw source
changes, and never expect a builder to do it.
"""
