# Stage 1: Ingest

Scripts come from the library-for-agents tools repo, see `_config/factory.md`.

Goal: get the EPUB under `books/<slug>/01-source/` and a reviewed `book.yaml`.

| | |
|---|---|
| Load | `_config/factory.md`, `shared/class-map-guide.md`, `_config/CONVENTIONS.md` |
| Inputs | EPUB in `inbox/` or a given path |
| Process | `python3 parse_epub.py inspect FILE.epub` to read TOC, spine, css classes. Then `parse_epub.py init FILE.epub books/<slug>` to draft `book.yaml`. Review: every `classmap` role (see `shared/class-map-guide.md`), every document marked `kind: review`, exclusions with reasons, `decorative_images`. |
| Outputs | `books/<slug>/01-source/<file>.epub`, `books/<slug>/book.yaml` with no `kind: review` left |

Checkpoint (human or lead agent): the document list matches the book; headings, callouts, bullets and pull quotes have the right roles; nothing with content is excluded.
Audit: excluded documents total few words and each has a reason (cover, part divider, licence page).
