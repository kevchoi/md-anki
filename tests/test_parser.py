from pathlib import Path

from ankify.parser import (
    MarkdownCard,
    find_duplicate_fronts,
    get_deck_from_path,
    parse_markdown_file,
    parse_all,
)


def test_compute_hash():
    hash1 = MarkdownCard.compute_hash("What is Python?")
    hash2 = MarkdownCard.compute_hash("What is Python?")
    hash3 = MarkdownCard.compute_hash("What is Java?")

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 16


def test_get_deck_from_path_root():
    base = Path("/notes")
    file = Path("/notes/test.md")
    assert get_deck_from_path(file, base) == "notes"


def test_get_deck_from_path_nested():
    base = Path("/notes")
    file = Path("/notes/python/basics/test.md")
    assert get_deck_from_path(file, base) == "notes::python::basics"


def test_parse_markdown_file(tmp_path: Path):
    file = tmp_path / "test.md"
    file.write_text("""# Title

## What is Python?

A programming language.

## How do you print?

```python
print("hello")
```
""")
    cards = parse_markdown_file(file, tmp_path)

    assert len(cards) == 2

    assert cards[0].front_raw == "What is Python?"
    assert cards[0].back_raw == "A programming language."
    assert cards[0].deck == tmp_path.name

    assert cards[1].front_raw == "How do you print?"
    assert "print" in cards[1].back_raw


def test_parse_markdown_file_empty_back(tmp_path: Path):
    file = tmp_path / "test.md"
    file.write_text("""## Question with no answer

## Another question

Has an answer.
""")
    cards = parse_markdown_file(file, tmp_path)

    assert len(cards) == 1
    assert cards[0].front_raw == "Another question"


def test_parse_all(tmp_path: Path):
    (tmp_path / "topic1").mkdir()
    (tmp_path / "topic1" / "file.md").write_text("## Q1\n\nA1")

    (tmp_path / "topic2").mkdir()
    (tmp_path / "topic2" / "file.md").write_text("## Q2\n\nA2")

    cards = parse_all(tmp_path)

    assert len(cards) == 2
    decks = {c.deck for c in cards}
    assert f"{tmp_path.name}::topic1" in decks
    assert f"{tmp_path.name}::topic2" in decks


def test_find_duplicate_fronts(tmp_path: Path):
    (tmp_path / "a.md").write_text("## Same front\n\nAnswer A")
    (tmp_path / "b.md").write_text("## Same front\n\nAnswer B")
    (tmp_path / "c.md").write_text("## Unique front\n\nAnswer C")

    duplicates = find_duplicate_fronts(parse_all(tmp_path))

    assert len(duplicates) == 1
    assert len(duplicates[0]) == 2
    assert {c.front_raw for c in duplicates[0]} == {"Same front"}


def test_find_duplicate_fronts_none():
    cards = [
        MarkdownCard("Q1", "A1", "h1", "f.md", "deck"),
        MarkdownCard("Q2", "A2", "h2", "f.md", "deck"),
    ]
    assert find_duplicate_fronts(cards) == []
