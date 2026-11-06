# Stage 4: Assemble

| | |
|---|---|
| Load | `books/<slug>/04-assemble/INDEX.md` after running, `CATALOG.md` |
| Inputs | `02-text/`, `03-enrich/` |
| Process | `assemble.py books/<slug>` then `python3 tools/catalog.py` at the library root |
| Outputs | `04-assemble/` (chapters, INDEX.md, index.json, chunks.jsonl, book_full.md, figures), updated `CATALOG.md` |

Checkpoint: `INDEX.md` reads well; `python3 tools/search.py "<a phrase from the book>"` finds the right chapter.
Audit: this folder is generated, never edited by hand.
