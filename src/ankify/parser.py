import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

HEADING_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)


@dataclass
class MarkdownCard:
    front_raw: str
    back_raw: str
    source_hash: str
    source_file: str
    deck: str

    @staticmethod
    def compute_hash(front_raw: str) -> str:
        return hashlib.sha256(front_raw.encode("utf-8")).hexdigest()[:16]


def get_deck_from_path(file_path: Path, base_path: Path) -> str:
    relative = file_path.parent.relative_to(base_path)
    root = base_path.resolve().name or "default"
    return "::".join((root, *relative.parts))


def parse_markdown_file(file_path: Path, base_path: Path) -> list[MarkdownCard]:
    content = file_path.read_text(encoding="utf-8")
    deck = get_deck_from_path(file_path, base_path)
    relative_path = file_path.relative_to(base_path.parent)
    source_file = str(relative_path)

    matches = list(HEADING_PATTERN.finditer(content))

    cards: list[MarkdownCard] = []

    for i, match in enumerate(matches):
        front_raw = match.group(1).strip()

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        back_raw = content[start:end].strip()

        if not front_raw or not back_raw:
            continue

        source_hash = MarkdownCard.compute_hash(front_raw)

        cards.append(
            MarkdownCard(
                front_raw=front_raw,
                back_raw=back_raw,
                source_hash=source_hash,
                source_file=source_file,
                deck=deck,
            )
        )

    return cards


def parse_all(base_path: Path) -> list[MarkdownCard]:
    files = sorted(base_path.rglob("*.md"))
    return [
        card
        for file_path in files
        for card in parse_markdown_file(file_path, base_path)
    ]


def find_duplicate_fronts(cards: list[MarkdownCard]) -> list[list[MarkdownCard]]:
    groups: dict[str, list[MarkdownCard]] = {}
    for card in cards:
        groups.setdefault(card.source_hash, []).append(card)
    return [group for group in groups.values() if len(group) > 1]
