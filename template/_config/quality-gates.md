# Quality gates

A book is only `verified` when all of these pass. Run them (script location: `_config/factory.md`) with `python3 <factory>/ingest/check.py books/<slug>`.
1. Spine coverage: every document of the EPUB is included or excluded with a written reason and word count.
2. Character equality: the non-whitespace character stream of every included document equals the EPUB text (after removing generated headings, ids, markup, figure blocks and declared lifted text).
3. Immutability: body sha256 in front matter equals the manifest; a rebuild from `01-source` reproduces `02-text` byte for byte.
4. Structure: sequential unique paragraph ids, figure counts and files, internal links resolve, no markup artifacts.
5. Index (levels 2 and 3): `tools/book_gate.py` checks embeddings cover the text, atoms cite real paragraphs, a sampled audit passes and retrieval finds the book. See the project's `docs/GATE.md`.
6. Determinism: `parse_epub.py build` run twice gives identical `02-text/` output (`check.py` proves it).
