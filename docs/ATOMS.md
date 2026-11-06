# Atoms: definition, method, quality

## Levels

| Level | Applies to | Contents |
|---|---|---|
| 1 | every book | Markdown text layer with paragraph ids |
| 2 | every non-fiction book | Level 1 plus paragraph embeddings |
| 3 | idea-driven non-fiction only (optional) | Level 2 plus atoms and cross-book links |

Embeddings are the baseline. Atoms are optional. In a blind comparison on plain questions, paragraph retrieval did about as well as atoms, so atoms earn their place mainly through cross-book linking in idea-driven books. Story, memoir, short-entry and quote books are usually better left at level 2: set `atoms: none` in `book.yaml` and the gate treats the atom, retrieval and link stages as N/A.

## What an atom is

A short, self-contained statement of one idea the author makes, written by a model in plain words, pointing back to the exact paragraphs where the author says it.

- An interpretation, not an excerpt. The author's literal words live only in the text layer (`books/<book>/02-text/`).
- An index card for the text, never a replacement. Search finds the atom; the citation takes you to the real paragraph.

## Quality criteria

1. **Faithful.** The cited paragraphs support it. Nothing added, nothing inferred.
2. **Self-contained.** Readable alone. No "this", "the author" or "as above" carrying the meaning.
3. **One idea.** A transferable claim, rule, finding or definition. Not an anecdote, case detail or name-dropping.
4. **Correctly cited.** Points at the 1 to 3 paragraphs that directly support it.
5. **Not duplicated** within the book.
6. **Worth keeping.** Useful out of context. When in doubt, leave it out.

Wording: own words, plain and natural. The gate flags a claim sharing 13 or more consecutive words with its cited paragraphs. For non-English books the claim is written in English with a short exact quotation in the book's language as evidence.

There is no minimum atoms-per-words density. Density is a by-product of what the book says, and a density floor forces extraction from story passages.

## Extraction pipeline (`tools/extract_atoms.py`)

1. **Chapter classifier.** One cheap call per chapter labels it `ideas`, `mixed` or `story`. Story chapters never reach the extractor. Disable with `CHAPTER_CLASSIFY=0`.
2. **Structured atoms.** Each atom has `claim` (one sentence, at most 30 words), `subject`, `kind` (`claim`, `example`, `story`), `scope` (`general` or `personal`), `paras` and `tags`. Only `kind = claim` with `scope = general` is kept. Source hedges (can, often, may) must be preserved.
3. **Deterministic filter, no model.** Rejects empty subject, over-long claims, vague pronoun openings, "the author", failed citations and copied text.
4. **Sampled audit (`tools/audit_atoms.py <slug> [n]`).** A stronger model judges a seeded sample from the claim and its cited paragraphs only: faithful, self-contained, one idea, kind, keep/fix/drop. The audit grades the build; it does not filter atoms. A low keeper rate means the pipeline settings suit that book type poorly, which is fixed at the pipeline, not atom by atom.

## Gate thresholds (stage 4)

- FAIL if more than 10% of sampled atoms are unsupported by their paragraphs.
- WARN if under 60% are keepers, over 25% are not self-contained, or over 20% are anecdotes or examples.
- Suggested practice: re-extract once if keepers are under 40%; if it stays under 40%, drop the atoms and set `atoms: none`.

## Models (all via OpenRouter, override base URL with `LIBRARY_OPENROUTER_BASE_URL`)

| Step | Model class |
|---|---|
| EPUB to Markdown | none (a model is used only for optional chapter repair, `tools/fix_chapters.py`) |
| Embeddings | one embedding model for everything, so the vector space stays consistent |
| Chapter classifier, atom extraction | a cheap "flash" tier (`ATOM_TIER=flash`) or a stronger one (`sonnet`) |
| Sampled audit | a stronger model than the extractor |

The exact model ids are constants at the top of each tool; change them there.

## Links (`tools/link_atoms.py`, `tools/link_filter.py`)

Links connect atoms across books that both have atoms: mutual top-3 neighbours plus a score threshold. Links are a targeted synthesis feature, not a general retrieval boost.

## Reproducing

1. Build Markdown with paragraph ids from your own legal copy; keep a `source_url` per book.
2. Embed every paragraph with one model (mandatory for non-fiction).
3. Optional: extract atoms for idea-driven non-fiction, audit a seeded sample, re-extract once if weak, drop if still weak.
4. Build links only between books that have atoms.
5. Run `tools/book_gate.py`. It does not modify text manifests; chapter repair needs `--repair-text`.

Embeddings, atoms and links are derived from your books. Keep them out of public repositories.
