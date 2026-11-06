# library-for-agents

Turn the EPUB books you own into a library that AI agents can search and cite: clean Markdown per chapter, paragraph embeddings, audited atomic claims, and a quality gate that tells you whether a book is ready.

This repository holds the **method and tools only**. You bring your own legally owned books. The MIT licence covers this code and documentation, not any book you process.

## What you get

For each book:

1. **Text layer**: chapters as Markdown with stable paragraph ids, figures extracted, source EPUB hash-pinned and checked for fidelity (`ingest/`).
2. **Embeddings**: one vector per paragraph (`tools/build_embeddings.py`).
3. **Atoms**: short, self-contained claims, each tied to the paragraphs it came from, then audited against the source (`tools/extract_atoms.py`, `tools/audit_atoms.py`).
4. **Links**: related atoms across books (`tools/link_atoms.py`, `tools/link_filter.py`).
5. **Gate**: one command that checks all of the above and reports PASS, WARN or FAIL per stage (`tools/book_gate.py`).
6. **Search**: `tools/search.py "your question"` returns the best-matching paragraphs with ids.

Design notes: [docs/ATOMS.md](docs/ATOMS.md), [docs/GATE.md](docs/GATE.md). Stage contracts and conventions ship in `template/` and are copied into your library.

## Requirements

- Python 3.10+
- An [OpenRouter](https://openrouter.ai) API key in `OPENROUTER_API_KEY` (embeddings and atom extraction)
- `pip install -r requirements.txt`

## Quick start (about 5 minutes, about one cent)

```bash
git clone https://github.com/vincevangrootel/library-for-agents && cd library-for-agents
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
export OPENROUTER_API_KEY=...           # your own key

# 1. a synthetic example book (original text, no rights issues)
python3 example/make_example_epub.py example/field-guide-to-keeping-notes.epub

# 2. scaffold a library next to this repo and work inside it
python3 ingest/scaffold_library.py ../my-library && cd ../my-library
export LIBRARY_ROOT=$PWD LIBRARY_INDEX=$PWD/index
TOOLS=../library-for-agents

# 3. ingest: init, resolve the title page, build, verify
python3 $TOOLS/ingest/parse_epub.py init $TOOLS/example/field-guide-to-keeping-notes.epub books/example
python3 $TOOLS/example/prep_book_yaml.py books/example
python3 $TOOLS/ingest/parse_epub.py build books/example
python3 $TOOLS/ingest/verify_text.py books/example --report 05-verify/text.json

# 4. embeddings, atoms, and the gate
python3 $TOOLS/tools/build_embeddings.py example
python3 $TOOLS/tools/extract_atoms.py example
python3 $TOOLS/tools/book_gate.py example --no-publish

# 5. ask it something
python3 $TOOLS/tools/search.py "why do note collections fail"
```

Expected: the gate ends in `GATE SUMMARY  example WARN` (stages 2 to 5 PASS). The warnings are optional metadata: cover image, ISBN, and a Calibre id. A fully filled-in book reaches PASS.

Tools read `LIBRARY_ROOT` (default: current directory) and `LIBRARY_INDEX` (default: `$LIBRARY_ROOT/index`). Real books need a human look at `book.yaml` after `init`: which documents are chapters, front or back matter, and which images are decorative. `ingest/parse_epub.py inspect BOOK.epub` shows what the EPUB contains first.

## Other settings

- `ATOM_TIER=flash|sonnet`: cheaper or stronger atom extraction.
- **File storage (optional).** Embeddings and atoms are large and derived from your books, so they are not kept in Git. If you want a copy somewhere else, for example so other machines or agents can read it, set `LIBRARY_PUBLISH_REMOTE` to a storage location (any cloud drive, object store or network disk supported by [rclone](https://rclone.org)). The gate then copies the files there and checks that the sizes match. If you only use one machine, ignore it: the stage is skipped (N/A). `--no-publish` skips it explicitly.
- Embeddings and atoms are derived from your books. Treat them as private unless you hold the rights.

## Layout

```
ingest/     EPUB to verified Markdown (parse, verify, assemble, check)
tools/      embeddings, atoms, audit, links, gate, search
template/   library scaffold: stage contracts, conventions, agent instructions
example/    synthetic EPUB generator and the helper used in the quick start
docs/       how atoms and the gate work
```

## Licence

MIT, see [LICENSE](LICENSE). Books you process remain under their own rights.
