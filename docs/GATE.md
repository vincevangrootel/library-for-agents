# The gate

`tools/book_gate.py <slug>` checks one book and writes `books/<slug>/05-verify/import-gate.json`. Its goal: prove a book is correctly in the library before anything relies on it. Each stage reports PASS, WARN, FAIL or N/A.

| Stage | Question |
|---|---|
| 1 metadata | Are title, author, language, `content_type` (nonfiction or fiction) and source hash present? Does the source file still match its hash? |
| 2 text | Do chapters match the contents, and does body text sit in chapters? |
| 3 embeddings | Does every paragraph have exactly one valid vector? |
| 4 atoms | Do atoms pass the audit? (N/A for fiction and `atoms: none`) |
| 5 retrieval | Do atoms find their own paragraphs, within the book and across the library? (N/A without atoms) |
| 6 links | Are cross-book links valid? (N/A without atoms) |
| 7 file storage | Optional. Copies the derived files (embeddings, atoms, links) to a storage location you choose, so other machines or agents can use them, and checks the sizes match. Needs `LIBRARY_PUBLISH_REMOTE` (any storage supported by rclone). N/A when unset. |

Flags: `--check-only`, `--redo-atoms`, `--no-publish`, `--verify-source`, `--repair-text`.

## Common, acceptable WARNs

- **No cover / ISBN / Calibre id.** Optional metadata. Self-published and compilation files often have no ISBN; the book is identified by `source_sha256`.
- **Large untagged documents.** Appendices, colophons, epilogues. The text is present and embedded; only the chapter label is missing.
- **Few chapters.** Short books and fables with one real chapter.
- **Keeper rate under 60%.** By design a WARN. Common in self-help, anecdote, aphorism and personality-profile books. It does not mean unsupported content.
- **No cross-book links above threshold.** Normal for a library with one book.

## Edge cases worth knowing

- **Library-wide retrieval can score lower than own-book retrieval** when the library holds many near-duplicate passages on the same topic: the right paragraph is outranked by neighbours. Text and embeddings are sound; accept it if own-book retrieval is high.
- **Numbered chapter headings** ("1", "Chapter 1", "Hoofdstuk 1") are recognised deterministically by `tools/fix_chapters.py`, with no model call.
- **The gate is read-only for `02-text/manifest.json`.** Automatic model-based repair once relabelled real chapters as front matter, so repair runs only with `--repair-text`, per book.
- Atom audit rows without a judge verdict are ignored, not fatal.
- Fiction is checked on text and embeddings only.
