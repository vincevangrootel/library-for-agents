# Stage 3: Enrich

Scripts come from the library-for-agents tools repo, see `_config/factory.md`.

Goal: navigation aids written by an AI reader, every claim anchored to paragraph ids.

| | |
|---|---|
| Load | `shared/sidecar-schema.md`, `shared/enrichment-brief.md`, the chapter text in `02-text/` (one chapter at a time) |
| Inputs | `02-text/` (read only) |
| Process | One agent per few chapters using the brief in `shared/enrichment-brief.md`. They write `03-enrich/chapters/<id>.yaml`, `figures.yaml` (view each image), and the lead writes `book-overview.yaml`. Run `verify_enrich.py` until 0 errors, read all warnings. |
| Outputs | `03-enrich/` complete |

Checkpoint: `verify_enrich` 0 errors; warnings explained.
Audit: stage 5 uses fresh reviewers, never the authors.
