from pathlib import Path

import pytest

from ankify.anki import AnkiClient
from ankify.sync import sync

TEST_DECK_PREFIX = "ankify-test"
TEST_DECK = TEST_DECK_PREFIX


def make_test_notes(tmp_path: Path) -> tuple[Path, Path]:
    base = tmp_path / TEST_DECK
    base.mkdir()
    return base, base


@pytest.fixture
def client():
    try:
        client = AnkiClient()
        client.get_version()
        return client
    except Exception:
        pytest.skip("Anki is not running or AnkiConnect is not available")


@pytest.fixture
def cleanup_test_deck(client):
    deck_names = client.get_deck_names()
    for deck in deck_names:
        if deck.startswith(TEST_DECK):
            client._request("deleteDecks", decks=[deck], cardsToo=True)

    yield

    note_ids = client.find_notes(f'"deck:{TEST_DECK}*"')
    if note_ids:
        client.delete_notes(note_ids)

    deck_names = client.get_deck_names()
    for deck in deck_names:
        if deck.startswith(TEST_DECK):
            client._request("deleteDecks", decks=[deck], cardsToo=True)


def test_sync_creates_new_cards(client, cleanup_test_deck, tmp_path: Path):
    base, deck = make_test_notes(tmp_path)
    (deck / "test.md").write_text("""## Test Question 1

Test answer 1.

## Test Question 2

Test answer 2.
""")

    stats = sync(base, client, dry_run=False, verbose=False)

    assert stats.created == 2
    assert stats.updated == 0
    assert stats.moved == 0
    assert len(stats.errors) == 0
    assert len(client.find_notes(f'"deck:{TEST_DECK}"')) == 2


def test_sync_dry_run(client, cleanup_test_deck, tmp_path: Path):
    base, deck = make_test_notes(tmp_path)
    (deck / "test.md").write_text("""## Dry Run Question

Dry run answer.
""")

    stats = sync(base, client, dry_run=True, verbose=False)

    assert stats.created == 1
    assert len(client.find_notes(f'"deck:{TEST_DECK}"')) == 0


def test_sync_updates_changed_cards(client, cleanup_test_deck, tmp_path: Path):
    base, deck = make_test_notes(tmp_path)
    test_file = deck / "test.md"
    test_file.write_text("""## Update Test Question

Original answer.
""")
    sync(base, client, dry_run=False, verbose=False)

    test_file.write_text("""## Update Test Question

Updated answer with new content.
""")
    stats = sync(base, client, dry_run=False, verbose=False)

    assert stats.created == 0
    assert stats.updated == 1
    assert stats.moved == 0


def test_sync_moves_cards_between_decks(client, cleanup_test_deck, tmp_path: Path):
    base, deck = make_test_notes(tmp_path)
    (deck / "subdir").mkdir()
    test_file = deck / "test.md"
    test_file.write_text("""## Move Test Question

Answer.
""")
    sync(base, client, dry_run=False, verbose=False)

    test_file.rename(deck / "subdir" / "test.md")
    stats = sync(base, client, dry_run=False, verbose=False)

    assert stats.moved == 1


def test_sync_deletes_orphaned_notes(client, cleanup_test_deck, tmp_path: Path):
    base, deck = make_test_notes(tmp_path)
    test_file = deck / "test.md"
    test_file.write_text("""## Question to Delete

Answer.

## Question to Keep

Answer.
""")
    sync(base, client, dry_run=False, verbose=False)

    assert len(client.find_notes(f'"deck:{TEST_DECK}"')) == 2

    test_file.write_text("""## Question to Keep

Answer.
""")
    stats = sync(base, client, dry_run=False, verbose=False, delete=True)

    assert stats.deleted == 1
    assert len(client.find_notes(f'"deck:{TEST_DECK}"')) == 1


def test_sync_delete_dry_run(client, cleanup_test_deck, tmp_path: Path):
    base, deck = make_test_notes(tmp_path)
    test_file = deck / "test.md"
    test_file.write_text("""## Question to Delete

Answer.
""")
    sync(base, client, dry_run=False, verbose=False)

    assert len(client.find_notes(f'"deck:{TEST_DECK}"')) == 1

    test_file.write_text("")
    stats = sync(base, client, dry_run=True, verbose=False, delete=True)

    assert stats.deleted == 1
    assert len(client.find_notes(f'"deck:{TEST_DECK}"')) == 1


def test_sync_removes_empty_deck_after_move(client, cleanup_test_deck, tmp_path: Path):
    base, deck = make_test_notes(tmp_path)
    (deck / "subdir").mkdir()
    test_file = deck / "subdir" / "test.md"
    test_file.write_text("""## Question

Answer.
""")
    sync(base, client, dry_run=False, verbose=False)

    subdir_deck = f"{TEST_DECK}::subdir"
    assert subdir_deck in client.get_deck_names()

    test_file.rename(deck / "test.md")
    (deck / "subdir").rmdir()
    sync(base, client, dry_run=False, verbose=False)

    assert subdir_deck not in client.get_deck_names()


def test_sync_keeps_non_empty_deck_after_move(
    client, cleanup_test_deck, tmp_path: Path
):
    base, deck = make_test_notes(tmp_path)
    (deck / "subdir").mkdir()
    (deck / "subdir" / "test1.md").write_text("""## Question 1

Answer 1.
""")
    (deck / "subdir" / "test2.md").write_text("""## Question 2

Answer 2.
""")
    sync(base, client, dry_run=False, verbose=False)

    (deck / "subdir" / "test1.md").rename(deck / "test1.md")
    sync(base, client, dry_run=False, verbose=False)

    assert f"{TEST_DECK}::subdir" in client.get_deck_names()


def test_sync_removes_empty_deck_after_delete(
    client, cleanup_test_deck, tmp_path: Path
):
    base, deck = make_test_notes(tmp_path)
    (deck / "subdir").mkdir()
    test_file = deck / "subdir" / "test.md"
    test_file.write_text("""## Question

Answer.
""")
    sync(base, client, dry_run=False, verbose=False)

    subdir_deck = f"{TEST_DECK}::subdir"
    assert subdir_deck in client.get_deck_names()

    test_file.unlink()
    (deck / "subdir").rmdir()
    sync(base, client, dry_run=False, verbose=False, delete=True)

    assert subdir_deck not in client.get_deck_names()


def test_sync_removes_root_deck_after_delete(client, cleanup_test_deck, tmp_path: Path):
    base, deck = make_test_notes(tmp_path)
    test_file = deck / "test.md"
    test_file.write_text("""## Question

Answer.
""")
    sync(base, client, dry_run=False, verbose=False)

    assert TEST_DECK in client.get_deck_names()

    test_file.write_text("")
    sync(base, client, dry_run=False, verbose=False, delete=True)

    assert TEST_DECK not in client.get_deck_names()


def test_sync_matches_by_hash_after_root_rename(
    client, cleanup_test_deck, tmp_path: Path
):
    base, deck = make_test_notes(tmp_path)
    (deck / "test.md").write_text("""## Rename Test Question

Same answer.
""")
    sync(base, client, dry_run=False, verbose=False)

    renamed_deck = f"{TEST_DECK}-renamed"
    renamed_base = tmp_path / renamed_deck
    base.rename(renamed_base)
    stats = sync(renamed_base, client, dry_run=False, verbose=False)

    assert stats.created == 0
    assert stats.updated == 1
    assert stats.moved == 1
    assert len(client.find_notes(f'"deck:{renamed_deck}"')) == 1
    assert TEST_DECK not in client.get_deck_names()

    stats = sync(renamed_base, client, dry_run=False, verbose=False)
    assert stats.created == 0
    assert stats.updated == 0
    assert stats.moved == 0
