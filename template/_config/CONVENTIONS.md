# Conventions

## Book folder
```
books/<author-surname>-<short-title>/
  CONTEXT.md        what this book is, status, how to read it
  book.yaml         metadata, css class map, document list with kind and exclusion reasons, status
  01-source/        original EPUB (never modified), sha256 recorded in book.yaml
  02-text/          verbatim text layer: chapters/, figures/, manifest.json, figures.json
  03-enrich/        AI written sidecars: chapters/<id>.yaml, figures.yaml, book-overview.yaml
  04-assemble/      generated reading copies: chapters/, INDEX.md, index.json, chunks.jsonl, book_full.md, figures/
  05-verify/        text.json, enrich.json, REPORT.md
```
## Ids
- Documents: `ch01`..`chNN` chapters, `fm01`.. front matter, `bm01`.. back matter.
- Paragraphs: trailing block reference ` ^ch05-012`, sequential per document, never reused.
- Figures: `fig-ch05-01`.
## File names
`<id>-<slug-of-toc-title>.md`, slug lower case, apostrophes dropped, cut at a word boundary near 40 characters. The title in the file is the title of the book, the slug is only a handle.
## Text layer format
Front matter (id, number, title, toc_title, heading_verbatim, part, kind, words, paragraphs, figures, body_sha256, generated: true), a generated `# title` line, then the body. Headings are level 2 or deeper. Callouts and pull quotes are blockquotes. Figures are fenced by `<!-- figure:ID -->` and `<!-- /figure -->`.
## Sidecars
See the skill reference `sidecar-schema.md`. Every claim carries paragraph ids from its own document.
## Writing rules
No em dashes or en dashes in generated text. Quote the book exactly or paraphrase and cite. Never present an AI statement as the author's.
