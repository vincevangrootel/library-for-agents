# Stage 2: Parse

Scripts come from the factory skill, see `_config/factory.md`.

Goal: a verbatim, id-stamped text layer that provably equals the book.

| | |
|---|---|
| Load | `books/<slug>/book.yaml`, `shared/class-map-guide.md`, `_config/quality-gates.md` |
| Inputs | `books/<slug>/01-source/`, `books/<slug>/book.yaml` |
| Process | `parse_epub.py build books/<slug>` then `verify_text.py books/<slug> --report 05-verify/text.json`. On failure fix `book.yaml` (class roles, exclusions, declared drops), never the text files. Rebuild. |
| Outputs | `02-text/chapters/*.md`, `02-text/figures/`, `manifest.json`, `figures.json` |

Checkpoint: `verify_text` reports 0 errors; spot-read two chapters beside the EPUB.
Audit: unmapped css classes in the build notes are understood; no `skipped_text` notes.
