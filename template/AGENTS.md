# Book Library (agent instructions)

A private knowledge library: books converted into agent-readable Markdown, searchable and citable by paragraph.
Folders carry the context. Read the `CONTEXT.md` of the folder you are working in before you act.

## Where to go
| You want to | Go to |
|---|---|
| Know what is in the library | `CATALOG.md` |
| Find or read something in a book | `CONTEXT.md`, section "Read and search" |
| Add a new book | `CONTEXT.md`, section "Add a book", then `stages/` |
| Understand the rules | `_config/CONVENTIONS.md` and `_config/quality-gates.md` |
| Find the scripts that build a book | `_config/factory.md` (the `library-for-agents` project) |

## Rules that always apply
1. The text layer `books/<book>/02-text/` is verbatim and immutable. Never edit it by hand or with an LLM. It is regenerated only by `parse_epub.py build` from `01-source/`.
2. Everything an AI wrote (summaries, concepts, figure descriptions) lives in `03-enrich/` and cites paragraph ids. Treat it as a map to the text, never as the author's words.
3. Quote and cite as `<book> / <chapter id> / ^<paragraph id>`, for example `field-guide-to-keeping-notes / ch02 / ^ch02-004`.
4. Never use em dashes or en dashes in anything you write for this library. Use commas, periods, colons.
5. Books are copyrighted. Keep this repository private.
