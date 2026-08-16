"""Fetchers that ask an endpoint once per team, city, match or day.

Unlike a download, a fetcher builds its output file itself out of many small
answers, which is why most of them can be stopped and started again.
"""
