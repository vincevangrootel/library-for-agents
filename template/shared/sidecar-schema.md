# Sidecar schema

`03-enrich/chapters/<id>.yaml` (required for chapters, optional for front and back matter):
```yaml
id: ch05
summary: 3 to 5 sentences faithful to the text
summary_cites: [ch05-003, ch05-005]     # 3 to 8 ids spread across the chapter
short_answer: DO IT A LOT.              # only if the book has its own short answer; no surrounding quotes
key_concepts:
  - term: Embrace the silence
    definition: one sentence in the book's words where possible
    cites: [ch05-006, ch05-007]         # 1 to 4 ids, must support term AND definition
questions_answered:
  - q: Is silence bad in a presentation?
    cites: [ch05-007]
keywords: [filler words, silence, preparation]   # 10 to 20, each present in or a direct paraphrase of the text
related:
  - id: ch08
    why: the chapter links to it for low energy as a cause     # grounded in the text
```
`03-enrich/figures.yaml`:
```yaml
fig-ch05-01:
  description: what the image shows (colours, layout, objects)
  text_in_figure: exact legible text
  qr_link: decoded link, if a QR code
  takeaway: what the surrounding text says it is for (omit if the book is silent)
```
`03-enrich/book-overview.yaml`: `summary`, `how_to_use`, `topics`.

Rules: cites belong to the same document; point to the paragraph that states the claim, not the heading above it; no em or en dashes; no claim the book does not make; phrase questions in the reader's voice, not the author's.
