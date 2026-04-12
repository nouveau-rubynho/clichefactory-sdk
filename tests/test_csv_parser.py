from __future__ import annotations

from clichefactory._engine.parsers.csv_parser import CsvParser


def _parse(csv_text: str, filename: str = "test.csv"):
    parser = CsvParser()
    doc = parser.parse(csv_text.encode("utf-8"), filename)
    return doc


def test_csv_comma_delimiter_header_detection():
    text = "name,amount\nAlice,10\nBob,20\n"
    doc = _parse(text)

    md = doc.get_markdown()
    assert "| name | amount |" in md
    assert "| --- | --- |" in md
    assert "| Alice | 10 |" in md
    assert "| Bob | 20 |" in md

    as_json = doc.get_json()
    assert as_json == [
        {"name": "Alice", "amount": "10"},
        {"name": "Bob", "amount": "20"},
    ]


def test_csv_semicolon_delimiter_detection():
    text = "name;amount\nAlice;10\nBob;20\n"
    doc = _parse(text)

    md = doc.get_markdown()
    assert "| name | amount |" in md
    assert "| Alice | 10 |" in md
    assert "| Bob | 20 |" in md


def test_csv_no_header_synthetic_columns():
    text = "1;2;3\n4;5;6\n"
    # Force filename to check heading/title behavior
    doc = _parse(text, filename="numbers.csv")

    md = doc.get_markdown()
    # In no-header cases we still expect a markdown table with two data rows
    assert "| 1 | 2 | 3 |" in md
    assert "| 4 | 5 | 6 |" in md

    # get_json(header=False) should treat first row as data
    rows = doc.get_json(header=False)
    assert rows == [
        {"col_0": "1", "col_1": "2", "col_2": "3"},
        {"col_0": "4", "col_1": "5", "col_2": "6"},
    ]

