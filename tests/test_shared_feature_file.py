"""Tests for the one file both event sources write into.

The old scripts each read the file, filtered the other source out by hand and
wrote everything back, in nine places. This is the one place it happens now, so
it is the one place that has to be right: a run of one source must never lose
what the other one wrote.
"""

from pathlib import Path

from wmguru.helpers.utils import CsvFile, SharedFeatureFile

COLUMN_NAMES = ("source", "competition", "season", "player")
SORT_KEY_NAMES = ("competition", "season", "player")


def make_shared_file(target_file: Path, source_name: str) -> SharedFeatureFile:
    """Build the shared file as one of the two sources sees it."""
    return SharedFeatureFile(
        CsvFile(target_file, COLUMN_NAMES), source_name, SORT_KEY_NAMES
    )


def make_row(source: str, competition: str, season: str, player: str) -> dict[str, str]:
    """Build one row of the shared file."""
    return {
        "source": source,
        "competition": competition,
        "season": season,
        "player": player,
    }


def test_a_run_of_one_source_keeps_what_the_other_wrote(tmp_path: Path):
    target_file = tmp_path / "feature.csv"
    statsbomb = make_shared_file(target_file, "statsbomb")
    wyscout = make_shared_file(target_file, "wyscout")

    statsbomb.write_keeping_the_other_source(
        [make_row("statsbomb", "Euro", "2024", "A")]
    )
    wyscout.write_keeping_the_other_source(
        [make_row("wyscout", "Serie A", "2018", "B")]
    )

    written_sources = {row["source"] for row in CsvFile(target_file).read_rows()}
    assert written_sources == {"statsbomb", "wyscout"}


def test_a_second_run_of_the_same_source_replaces_its_own_rows(tmp_path: Path):
    target_file = tmp_path / "feature.csv"
    wyscout = make_shared_file(target_file, "wyscout")

    wyscout.write_keeping_the_other_source(
        [make_row("wyscout", "Serie A", "2018", "B")]
    )
    wyscout.write_keeping_the_other_source(
        [make_row("wyscout", "Serie A", "2018", "C")]
    )

    players = [row["player"] for row in CsvFile(target_file).read_rows()]
    assert players == ["C"]


def test_the_finished_seasons_of_the_other_source_are_none_of_our_business(
    tmp_path: Path,
):
    """Otherwise one source would skip a season the other one happened to do."""
    target_file = tmp_path / "feature.csv"
    statsbomb = make_shared_file(target_file, "statsbomb")
    wyscout = make_shared_file(target_file, "wyscout")

    statsbomb.write_keeping_the_other_source(
        [make_row("statsbomb", "Euro", "2024", "A")]
    )

    assert statsbomb.read_finished_keys() == {("Euro", "2024")}
    assert wyscout.read_finished_keys() == set()


def test_nothing_is_finished_before_the_first_run(tmp_path: Path):
    shared_file = make_shared_file(tmp_path / "not_there_yet.csv", "statsbomb")

    assert shared_file.read_finished_keys() == set()
    assert shared_file.read_rows_of_the_other_source() == []
    assert shared_file.read_own_rows() == []


def test_the_file_comes_out_in_a_fixed_order(tmp_path: Path):
    """Two runs over the same data have to give two identical files."""
    target_file = tmp_path / "feature.csv"
    wyscout = make_shared_file(target_file, "wyscout")

    wyscout.write_keeping_the_other_source(
        [
            make_row("wyscout", "Serie A", "2018", "Zeta"),
            make_row("wyscout", "Bundesliga", "2018", "Alpha"),
            make_row("wyscout", "Serie A", "2017", "Beta"),
        ]
    )

    competitions = [row["competition"] for row in CsvFile(target_file).read_rows()]
    assert competitions == ["Bundesliga", "Serie A", "Serie A"]


def test_a_feature_that_writes_two_files_holds_two_of_these(tmp_path: Path):
    """The discipline feature writes a player file and a match file."""
    player_file = make_shared_file(tmp_path / "player.csv", "statsbomb")
    match_file = make_shared_file(tmp_path / "match.csv", "statsbomb")

    player_file.write_keeping_the_other_source(
        [make_row("statsbomb", "Euro", "2024", "A")]
    )
    match_file.write_keeping_the_other_source(
        [make_row("statsbomb", "Euro", "2024", "")]
    )

    assert player_file.path != match_file.path
    assert len(CsvFile(player_file.path).read_rows()) == 1
    assert len(CsvFile(match_file.path).read_rows()) == 1
