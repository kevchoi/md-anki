from dataclasses import dataclass, field
from pathlib import Path

from .anki import AnkiClient, NOTE_TYPE_NAME
from .parser import find_duplicate_fronts, parse_all
from .render import render_markdown


@dataclass
class SyncStats:
    total: int = 0
    created: int = 0
    updated: int = 0
    moved: int = 0
    deleted: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class AnkiNote:
    note_id: int
    card_ids: list[int]
    source_hash: str
    source_file: str
    deck: str
    front: str
    back: str


def _get_field(fields: dict, name: str) -> str:
    return fields.get(name, {}).get("value", "")


def get_existing_notes(client: AnkiClient) -> dict[str, AnkiNote]:
    note_ids = client.find_notes(f"note:{NOTE_TYPE_NAME}")
    notes_info = client.get_notes_info(note_ids)

    all_card_ids = [cid for info in notes_info for cid in info.get("cards", [])]

    cards_info = client.get_cards_info(all_card_ids)
    card_to_deck = {card["cardId"]: card["deckName"] for card in cards_info}

    existing: dict[str, AnkiNote] = {}

    for info in notes_info:
        fields = info.get("fields", {})
        source_hash = _get_field(fields, "SourceHash")
        source_file = _get_field(fields, "SourceFile")
        front = _get_field(fields, "Front")
        back = _get_field(fields, "Back")

        cards = info.get("cards", [])
        deck = card_to_deck.get(cards[0], "Default") if cards else "Default"

        existing[source_hash] = AnkiNote(
            note_id=info["noteId"],
            card_ids=cards,
            source_hash=source_hash,
            source_file=source_file,
            deck=deck,
            front=front,
            back=back,
        )

    return existing


def _preview(text: str) -> str:
    return text[:50]


def _belongs_to_path(note: AnkiNote, path: Path) -> bool:
    return note.source_file.startswith(path.name + "/")


def sync(
    path: Path,
    client: AnkiClient,
    dry_run: bool = False,
    verbose: bool = False,
    delete: bool = False,
) -> SyncStats:
    stats = SyncStats()

    cards = parse_all(path)

    if verbose:
        print(f"Found {len(cards)} cards in {path}")

    for group in find_duplicate_fronts(cards):
        files = ", ".join(sorted({c.source_file for c in group}))
        print(
            f"Warning: front '{_preview(group[0].front_raw)}' appears "
            f"{len(group)} times ({files}); only one note will sync."
        )

    if not dry_run:
        client.create_note_type_if_not_exists()

    existing = get_existing_notes(client)
    # path scoping is only for --delete: matching is global by hash, so a
    # renamed deck-root folder can't cause duplicate creation
    existing_for_path = {
        source_hash: note
        for source_hash, note in existing.items()
        if _belongs_to_path(note, path)
    }
    moved_from_roots: set[str] = set()

    if verbose:
        print(f"Found {len(existing)} existing notes in Anki")

    if not dry_run:
        for deck in sorted({card.deck for card in cards}):
            client.create_deck(deck)

    for card in cards:
        front_html = render_markdown(card.front_raw)
        back_html = render_markdown(card.back_raw)
        note = existing.get(card.source_hash)

        if note is None:
            if verbose:
                print(f"Creating: {_preview(card.front_raw)}")
            try:
                if not dry_run:
                    client.add_note(
                        deck=card.deck,
                        front=front_html,
                        back=back_html,
                        source_hash=card.source_hash,
                        source_file=card.source_file,
                    )
                stats.created += 1
            except Exception as e:
                stats.errors.append(
                    f"Failed to create '{_preview(card.front_raw)}': {e}"
                )
            continue

        if (
            note.front != front_html
            or note.back != back_html
            or note.source_file != card.source_file
        ):
            if verbose:
                print(f"Updating: {_preview(card.front_raw)}")
            try:
                if not dry_run:
                    client.update_note(
                        note.note_id, front_html, back_html, card.source_file
                    )
                stats.updated += 1
            except Exception as e:
                stats.errors.append(
                    f"Failed to update '{_preview(card.front_raw)}': {e}"
                )

        if note.deck != card.deck:
            if verbose:
                print(f"Moving to {card.deck}: {_preview(card.front_raw)}")
            try:
                if not dry_run and note.card_ids:
                    client.change_deck(note.card_ids, card.deck)
                stats.moved += 1
                moved_from_roots.add(note.deck.split("::", 1)[0])
            except Exception as e:
                stats.errors.append(
                    f"Failed to move '{_preview(card.front_raw)}': {e}"
                )

    if delete:
        current_hashes = {card.source_hash for card in cards}
        orphaned_notes = [
            note
            for note in existing_for_path.values()
            if note.source_hash not in current_hashes
        ]

        for note in orphaned_notes:
            if verbose:
                print(f"Deleting: {_preview(note.front)}")

        if not dry_run:
            client.delete_notes([note.note_id for note in orphaned_notes])

        stats.deleted = len(orphaned_notes)

    if not dry_run and (stats.moved > 0 or stats.deleted > 0):
        root_decks = {card.deck.split("::", 1)[0] for card in cards}
        root_decks.update(
            note.deck.split("::", 1)[0] for note in existing_for_path.values()
        )
        root_decks.update(moved_from_roots)

        for root_deck in root_decks:
            deleted_decks = client.delete_empty_decks(root_deck)
            if verbose:
                for deck in deleted_decks:
                    print(f"Removed empty deck: {deck}")

    stats.total = len(cards)

    return stats
