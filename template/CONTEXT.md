# Library routing (L1)

## Read and search
1. Open `CATALOG.md` to pick the book, then `books/<book>/04-assemble/INDEX.md` for its chapters with summaries.
2. Search across books: `python3 tools/search.py "your query" [--book <slug>] [-n 8]`. Hits give the chapter and the paragraph id range. Open the chapter file in `04-assemble/chapters/` and read around those ids.
3. For a question about one chapter, read that chapter file front matter first (short answer, summary, key concepts, questions answered), then the text.
4. Answer from the text layer. If you use a sidecar claim, check the cited paragraph ids first.

## Add a book
Work through the stages in order. Each stage folder has its own `CONTEXT.md` contract (inputs, process, outputs, checkpoint).
| Stage | Folder | Result inside `books/<slug>/` |
|---|---|---|
| 1 Ingest | `stages/01-ingest/` | `01-source/`, `book.yaml` reviewed |
| 2 Parse | `stages/02-parse/` | `02-text/` passes the text gate |
| 3 Enrich | `stages/03-enrich/` | `03-enrich/` passes the enrichment gate |
| 4 Assemble | `stages/04-assemble/` | `04-assemble/`, `CATALOG.md` updated |
| 5 Verify | `stages/05-verify/` | `05-verify/REPORT.md`, status signed off |
The scripts live in the `book-to-library` skill, see `_config/factory.md` for where. Input files wait in `inbox/`.

## Folder map
- `books/<slug>/` one folder per book, numbered subfolders follow the stages
- `stages/` how a book gets made (the factory); `books/` is the product
- `_config/` conventions, gates and the pointer to the factory; `shared/` reference several stages use; `tools/` readers for agents
