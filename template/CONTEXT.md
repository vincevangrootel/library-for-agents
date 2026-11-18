# Library routing (L1)

## Read and search
1. Open `CATALOG.md` to pick the book, then `books/<book>/CONTEXT.md` and `books/<book>/02-text/manifest.json` for its chapters.
2. Keyword search across books (free, no key): `python3 tools/search.py "your query" [--book <slug>] [-n 8]`. Hits give the chapter and the paragraph id range. Open the chapter file in `books/<book>/02-text/chapters/` and read around those ids. The first run builds a cached index in `.cache/` (gitignored); later runs are fast and rebuild it when any book changes. Reference sections (index, notes, bibliography) are skipped unless you add `--all-sections`.
3. Meaning search (books at level 2 or 3): `python <library-for-agents>/library.py search "your question"`.
4. Answer from the text layer. If you use an atom (level 3), check its cited paragraph ids first.

## Add a book
`python <library-for-agents>/library.py add` does all of this. The stage folders describe each step for when a book needs care.
| Stage | Folder | Result inside `books/<slug>/` |
|---|---|---|
| 1 Ingest | `stages/01-ingest/` | `01-source/`, `book.yaml` reviewed |
| 2 Parse | `stages/02-parse/` | `02-text/` passes the text gate |
| 3 Index (optional) | `stages/03-index/` | embeddings (level 2) and atoms (level 3) in `index/` |
| 4 Verify | `stages/04-verify/` | `05-verify/import-gate.json`, then `CATALOG.md` refreshed |
The scripts live in the library-for-agents project, see `_config/factory.md`. Input files wait in `inbox/`.

## Folder map
- `books/<slug>/` one folder per book: `01-source/`, `02-text/`, `05-verify/`
- `index/` embeddings, atoms and links (derived, rebuildable, cost money to build)
- `stages/` how a book gets made (the factory); `books/` is the product
- `_config/` conventions, gates and the pointer to the factory; `shared/` reference several stages use; `tools/` readers for agents
- `.cache/` local search index, never committed
