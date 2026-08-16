"""Prepare the Wyscout actions once, in the shape every builder groups over.

The raw action file is close to three hundred megabytes of text and holds
every action of every match. Parsing it, naming the teams and the players and
turning the pitch the right way round takes the better part of a minute and
gives the very same table every time, so eight builders would otherwise each
pay for it.

This writes that table down once, together with the identity of every match.
Run it again whenever the Wyscout source changes.
"""

from pathlib import Path

from wmguru.helpers.constant import PreparedTablePath
from wmguru.helpers.utils import PreparedTableFile, TextNormalizer, WyscoutDataReader


class WyscoutActionTableBuilder:
    """The raw Wyscout files, prepared as the two tables the builders read."""

    def __init__(self, wyscout_data_reader: WyscoutDataReader) -> None:
        self._wyscout_data_reader = wyscout_data_reader

    def prepare_every_table(self) -> int:
        """Write the action table and the match identity table.

        Returns:
            How many actions the prepared table holds.
        """
        lookups = self._wyscout_data_reader.read_name_lookups()

        actions = self._wyscout_data_reader.read_every_action(lookups)
        action_file = self._table(PreparedTablePath.WYSCOUT_ACTION_FILE)
        action_file.write(actions)
        print(f"  OK    {len(actions)} actions -> {action_file.path}")

        identities = self._wyscout_data_reader.read_the_identity_of_every_match(lookups)
        identity_file = self._table(PreparedTablePath.WYSCOUT_MATCH_IDENTITY_FILE)
        identity_file.write(identities)
        print(f"  OK    {len(identities)} matches -> {identity_file.path}")
        return len(actions)

    def _table(self, target_file: Path) -> PreparedTableFile:
        """Name the file together with the command that writes it."""
        return PreparedTableFile(target_file, PreparedTablePath.WYSCOUT_PREPARE_COMMAND)


if __name__ == "__main__":
    WyscoutActionTableBuilder(WyscoutDataReader(TextNormalizer())).prepare_every_table()
