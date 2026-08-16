"""A check that the package is installed and importable."""

import wmguru


def test_import_works():
    if wmguru is not None:
        print("OKAY")
    else:
        print("NOT OKAY")
