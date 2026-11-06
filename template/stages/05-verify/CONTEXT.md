# Stage 5: Verify

| | |
|---|---|
| Load | `_config/quality-gates.md`, `shared/review-brief.md`, `books/<slug>/05-verify/` |
| Inputs | everything in `books/<slug>/` |
| Process | `check.py books/<slug>` runs all automatic gates and writes `05-verify/REPORT.md`. Then independent reviewers (fresh agents, strongest model available) check sidecar claims against cited paragraphs and figure descriptions against the images; fix findings, rerun. |
| Outputs | `05-verify/REPORT.md`, `status` flags in `book.yaml` set to true, book `CONTEXT.md` status line |

Checkpoint: automatic gates green and reviewers report clean or fixed.
