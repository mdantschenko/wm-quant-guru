"""Tests for CsvFile in wmguru/helpers/utils.py."""

from pathlib import Path

from wmguru.helpers.utils import CsvFile

COLUMN_NAMES = ("city", "country", "latitude")


def test_a_new_file_gets_its_header_line(tmp_path: Path):
    target_file = tmp_path / "places.csv"

    CsvFile(target_file, COLUMN_NAMES).append_rows([["Doha", "Qatar", 25.29]])

    lines = target_file.read_text().splitlines()
    assert lines[0] == "city,country,latitude"
    assert lines[1] == "Doha,Qatar,25.29"


def test_a_second_run_appends_without_a_second_header(tmp_path: Path):
    target_file = tmp_path / "places.csv"
    output_file = CsvFile(target_file, COLUMN_NAMES)

    output_file.append_rows([["Doha", "Qatar", 25.29]])
    output_file.append_rows([["Lusail", "Qatar", 25.42]])

    lines = target_file.read_text().splitlines()
    assert len(lines) == 3
    assert lines.count("city,country,latitude") == 1


def test_the_folder_is_created_when_it_is_missing(tmp_path: Path):
    target_file = tmp_path / "not" / "there" / "places.csv"

    CsvFile(target_file, COLUMN_NAMES).append_rows([["Doha", "Qatar", 1]])

    assert target_file.exists()


def test_finished_values_of_one_column_are_read_back(tmp_path: Path):
    output_file = CsvFile(tmp_path / "places.csv", COLUMN_NAMES)
    output_file.append_rows([["Doha", "Qatar", 1], ["Lusail", "Qatar", 2]])

    assert output_file.read_finished_values("city") == {"Doha", "Lusail"}


def test_finished_value_pairs_are_read_back(tmp_path: Path):
    output_file = CsvFile(tmp_path / "places.csv", COLUMN_NAMES)
    output_file.append_rows([["Doha", "Qatar", 1], ["Rome", "Italy", 2]])

    assert output_file.read_finished_value_pairs("city", "country") == {
        ("Doha", "Qatar"),
        ("Rome", "Italy"),
    }


def test_a_file_that_does_not_exist_yet_has_nothing_finished(tmp_path: Path):
    output_file = CsvFile(tmp_path / "nothing.csv", COLUMN_NAMES)

    assert output_file.read_finished_values("city") == set()


def test_writing_replaces_the_file_instead_of_growing_it(tmp_path: Path):
    """The writing mode is for a file that is built completely in one run."""
    target_file = tmp_path / "places.csv"
    output_file = CsvFile(target_file, COLUMN_NAMES)

    output_file.write_rows([["Doha", "Qatar", 1]])
    output_file.write_rows([["Rome", "Italy", 2]])

    lines = target_file.read_text().splitlines()
    assert lines == ["city,country,latitude", "Rome,Italy,2"]


def test_a_file_without_column_names_gets_no_header(tmp_path: Path):
    """The closing odds extract carries the header of the source file."""
    target_file = tmp_path / "raw.csv"

    CsvFile(target_file).write_rows([["a", "b"]])

    assert target_file.read_text().splitlines() == ["a,b"]


def test_rows_written_one_by_one_survive_a_stopped_run(tmp_path: Path):
    """The streaming writer is what makes a long run repeatable."""
    target_file = tmp_path / "places.csv"
    output_file = CsvFile(target_file, COLUMN_NAMES)

    try:
        with output_file.appending_writer() as writer:
            writer.writerow(["Doha", "Qatar", 1])
            writer.writerow(["Rome", "Italy", 2])
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass

    assert output_file.read_finished_values("city") == {"Doha", "Rome"}
