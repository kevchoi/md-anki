# ankify

Sync Markdown flashcards to Anki via AnkiConnect.

## Installation

```bash
uv add ankify
# or
pip install ankify
```

Requires Anki with [AnkiConnect](https://ankiweb.net/shared/info/2055492159) addon.

## Usage

```bash
# Check connection to Anki
ankify status

# Parse markdown files (preview cards)
ankify parse ./notes

# Sync cards to Anki
ankify sync ./notes

# Preview sync without making changes
ankify sync ./notes --dry-run

# Verbose output
ankify sync ./notes --verbose

# Delete cards from Anki that are no longer in markdown
ankify sync ./notes --delete

```

## Card Format

Cards are defined by `##` headings. The heading becomes the front, everything until the next heading becomes the back:

```markdown
## What is the capital of France?

Paris

## How do you print in Python?

​```python
print("Hello, World!")
​```
```

The sync directory becomes the top-level Anki deck. Its subdirectories become nested decks:

```
anki/
  deck/
    basics.md             → "anki::deck" deck
  interview-prep/
    systems/
      basics.md           → "anki::interview-prep::systems" deck
  scratch.md              → "anki" deck
```

## Try it out

The `examples/` directory contains test cards:

```
examples/
  programming/
    python/
      basics.md     → "examples::programming::python" deck
  languages/
    spanish.md      → "examples::languages" deck
```

```bash
ankify status               # check Anki connection
ankify parse examples/      # preview cards
ankify sync examples/ -n -v # dry run
ankify sync examples/ -v    # sync to Anki
```
