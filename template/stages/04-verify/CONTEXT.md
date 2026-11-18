# Stage 4: Verify

| | |
|---|---|
| Load | `_config/quality-gates.md`, `books/<slug>/05-verify/` |
| Inputs | everything in `books/<slug>/` and its files in `index/` |
| Process | `tools/book_gate.py <slug>` runs the gates for the book's level and writes `05-verify/import-gate.json`. `ingest/check.py books/<slug>` reruns the text gates and proves a rebuild reproduces `02-text` byte for byte. Then `python3 tools/catalog.py` at the library root. |
| Outputs | `05-verify/import-gate.json`, `status` flags in `book.yaml`, refreshed `CATALOG.md` |

Checkpoint: verdict PASS or WARN (see the project's `docs/GATE.md`); `python3 tools/search.py "<a phrase from the book>"` finds the right chapter.
