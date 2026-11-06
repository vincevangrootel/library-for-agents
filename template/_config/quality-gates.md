# Quality gates

A book is only `verified` when all of these pass. Run them (script location: `_config/factory.md`) with `python3 <factory>/ingest/check.py books/<slug>`.
1. Spine coverage: every document of the EPUB is included or excluded with a written reason and word count.
2. Character equality: the non-whitespace character stream of every included document equals the EPUB text (after removing generated headings, ids, markup, figure blocks and declared lifted text).
3. Immutability: body sha256 in front matter equals the manifest; a rebuild from `01-source` reproduces `02-text` byte for byte.
4. Structure: sequential unique paragraph ids, figure counts and files, internal links resolve, no markup artifacts.
5. Enrichment: schema complete, every cite exists in its own document, concept terms lexically grounded in cited paragraphs, no dash characters, every figure described.
6. Independent review: a fresh reviewer (agent or human) who did not write the sidecars checks claims against cited paragraphs and figure descriptions against the images. Findings are fixed and the gates rerun.
7. Determinism: `assemble.py` run twice gives identical output.
