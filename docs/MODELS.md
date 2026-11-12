# Models and cost

All model calls go through [OpenRouter](https://openrouter.ai), so one API key covers every model. Level 1 calls no model at all.

## Recommended defaults

| Job | Level | Default model | Why | Cost per 100k words* |
|---|---|---|---|---|
| Embeddings | 2, 3 | `qwen/qwen3-embedding-8b`, cut to 1024 dims | Best paid model in our book-retrieval benchmark, open weights, very cheap | about $0.002 |
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

Embedding benchmark (atom claim to its cited paragraph, 4,536 paragraphs from English and Dutch books, 362 queries, top-1): Qwen3-Embedding 8B 0.93, OpenAI text-embedding-3-large 0.92, Voyage 4 Large 0.91, OpenAI 3-small 0.90, Voyage 4 0.88, Cohere embed-5-pro 0.86, Voyage 4 Lite 0.86. Free endpoints scored well but publish no data policy; do not send private books to them.

Rules: build and search with the same `LIBRARY_EMBED_MODEL` and `LIBRARY_EMBED_DIMS` (default 1024; vectors are cut and re-normalised). Search refuses a mismatch. Changing either means rebuilding every index (`python library.py add --level 2 --rebuild`) and recalibrating `LIBRARY_LINK_THRESHOLD` (default 0.72) before regenerating links, because cosine scales differ per model.

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
