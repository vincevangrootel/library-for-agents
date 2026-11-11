# Models and cost

All model calls go through [OpenRouter](https://openrouter.ai), so one API key covers every model. Level 1 calls no model at all.

## Recommended defaults

| Job | Level | Default model | Why | Cost per 100k words* |
|---|---|---|---|---|
| Embeddings | 2, 3 | `voyageai/voyage-4-lite` | Strong retrieval quality for books, 1024 dims, very cheap | about $0.003 |
| Atom extraction | 3 | `deepseek/deepseek-v4.1-flash` | Follows the citation rules well at a fraction of the price | about $0.16 (measured) |
| Atom audit (sample of 24) | 3 | `anthropic/claude-sonnet-5.5` | A stronger, different model judges the cheap one | about $0.06 per book |

\* A typical non-fiction book is 60k to 120k words. `python library.py estimate` computes it for your actual books.

**Typical book (85k words):** level 2 about $0.003, level 3 about $0.20. **100 books at level 3:** about $15 to $25.

## Alternatives

| Want | Set | Effect |
|---|---|---|
| Highest atom quality | `LIBRARY_ATOM_MODEL=anthropic/claude-sonnet-5.5` | About 5x the atom cost (measured about $0.89 per 100k words). Worth it for a few books you rely on heavily. |
| Cheapest audit | `--no-audit` on `add` | Saves about $0.06 per book. You lose the independent quality sample. |
| Another embedding model | `LIBRARY_EMBED_MODEL=...` | Must be set **before** the first book. Changing it later means re-embedding every book, because vectors from different models cannot be compared. |
| Another atom model | `LIBRARY_ATOM_MODEL=...` | Any OpenRouter chat model works technically. Prompts were tuned on the two models above; check the gate and audit on one book before batching. `estimate` shows "unknown" cost for unmeasured models. |

Embedding models that work through OpenRouter's `/embeddings` endpoint include `mongodb/voyage-4` (stronger, about 3x price), `qwen/qwen3-embedding-8b` (cheapest, 4096 dims, about 4x the disk), and `openai/text-embedding-3-small`. Only `voyage-4-lite` is tested end to end with the gate's thresholds.

## Where to set them

In `<library>/.library.env` (written by `library.py new`, local to the machine, not committed) or in your shell. Keys go in `<library>/.env`, which is gitignored:

```bash
# <library>/.env   (never committed)
OPENROUTER_API_KEY=sk-or-...
```

`python library.py doctor` shows which models are active, without showing the key.

## Spend control

- `estimate` and `add` print the expected cost before anything is spent; `add` asks for confirmation (agents pass `--yes` only after the owner approved).
- Real cost per book is recorded in `books/<book>/05-verify/import-gate.json` and summed by `library.py status`.
- Set a spending limit on the OpenRouter key itself. That is the hard cap; the estimates are guidance.

Prices are OpenRouter list prices, November 2026. They change; the measured rates in `library.py` (`EMBED_RATE`, `ATOM_RATE`) are easy to update.
