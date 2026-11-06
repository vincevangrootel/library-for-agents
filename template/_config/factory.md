# Factory: where the process lives

This repository holds the books. The scripts that make a book live in the `library-for-agents` project, so they can improve without touching the books.

| | |
|---|---|
| Project | `library-for-agents` (https://github.com/vincevangrootel/library-for-agents) |
| Ingest scripts | `ingest/`: `parse_epub.py` (inspect, init, build), `verify_text.py`, `verify_enrich.py`, `assemble.py`, `check.py`, `catalog.py` |
| Vector tools | `tools/`: embeddings, atoms, audit, gate, search |
| Embedded here on purpose | `tools/search.py` and `tools/catalog.py`, so reading and searching work without the project |

## How stage contracts refer to it
A stage says "run `parse_epub.py build ...`". Resolve the script as `<project>/ingest/parse_epub.py`. Never rewrite the scripts from memory: the gates are only trustworthy when they are the tested ones.

## Keeping them in step
- Improve a script or brief in the project, then recopy `shared/` and `tools/` into the library.
- Rebuilding an old book with a newer version is safe: `check.py` proves the text layer is still identical.
