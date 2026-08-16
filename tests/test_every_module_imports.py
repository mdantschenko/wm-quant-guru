"""One import of every module of the package.

This catches a typing mistake, a wrong import path or a name that does not
exist, without running anything that talks to the network. The old download
scripts had exactly such a broken import and nothing noticed.

NOT_MIGRATED_YET is the remaining work of the OOP migration, written down so
it cannot be forgotten. Every one of these still carries the `src.scripts`
import path from before the package restructure and cannot run at all today.
The list may only ever get shorter: take a name out the moment its class
exists, never add one.
"""

import importlib
import pkgutil

import wmguru

NOT_MIGRATED_YET = frozenset({})


def test_every_migrated_module_can_be_imported():
    """Every failure is collected, so one broken module does not hide the rest."""
    broken_modules = []
    for module in pkgutil.walk_packages(wmguru.__path__, f"{wmguru.__name__}."):
        if module.name in NOT_MIGRATED_YET:
            continue
        try:
            importlib.import_module(module.name)
        except Exception as import_problem:
            broken_modules.append(f"{module.name}: {import_problem}")

    assert broken_modules == []


def test_the_migration_backlog_still_matches_reality():
    """A name that no longer exists has to leave the list, not linger in it."""
    module_names = {
        module.name
        for module in pkgutil.walk_packages(wmguru.__path__, f"{wmguru.__name__}.")
    }

    assert module_names >= NOT_MIGRATED_YET
