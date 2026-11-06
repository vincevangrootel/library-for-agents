# shared/ (reference material several stages use)

In ICM, `shared/` holds reference that more than one stage needs, so it is loaded on demand instead of repeated in every stage contract. Here:

| File | Used by | What |
|---|---|---|
| `class-map-guide.md` | stage 1, 2 | how css classes become roles in `book.yaml` |
| `sidecar-schema.md` | stage 3, 5 | exact format of enrichment sidecars |
| `enrichment-brief.md` | stage 3 | the brief to give each enrichment agent |
| `review-brief.md` | stage 5 | the brief for independent reviewers |

These are copies of the files in the skill's `references/` (see `_config/factory.md`). If they differ, the skill version is the source of truth: update the skill first, then copy here.

In these files `<factory>` means the `library-for-agents` project folder, see `_config/factory.md`.
