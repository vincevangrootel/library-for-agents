# Stage 3: Index (optional, costs money)

Scripts come from the library-for-agents project, see `_config/factory.md`.

Goal: meaning search and, for idea-driven non-fiction, cited idea atoms. The text layer is never changed.

| | |
|---|---|
| Load | `_config/quality-gates.md`, the project's `docs/MODELS.md` and `docs/ATOMS.md` |
| Inputs | `books/<slug>/02-text/` (read only) |
| Process | Level 2: `tools/build_embeddings.py <slug>`. Level 3: `tools/extract_atoms.py <slug>`, then `tools/audit_atoms.py <slug>`. `library.py add --level N` runs these after showing the cost. |
| Outputs | `index/embeddings/<slug>.npz`, `index/atoms/<slug>.jsonl`, links in `index/` |

Checkpoint: the owner approved the cost estimate before anything paid ran.
Audit: atoms are AI-written. Each cites paragraph ids; the audit samples them against the text.
