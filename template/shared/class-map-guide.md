# Class map guide

Publishers encode meaning in css class names on `p`, `span` and `div`. `book.yaml` `classmap` maps each class to a role. `init` guesses from names; you confirm by reading `inspect` output (counts and samples).

| Role | Meaning | Output |
|---|---|---|
| `heading:N` | section heading, N = 2..6 (chapter title is H1, generated) | `## text ^id`; emphasis stripped inside headings |
| `chapter_title` | the chapter number and title block | lifted to front matter `heading_verbatim`, `number` |
| `callout` | box, sidebar | blockquote (paragraphs inside the div) |
| `pullquote` | highlighted quote | blockquote |
| `bullet_marker` | span holding a bullet glyph or image at the start of a paragraph | paragraph becomes `- ` list item, marker dropped |
| `list_item` | paragraph that is a list item without marker | `- ` item |
| `bold`, `italic` | styling span the css makes bold or italic | `**`, `*` |
| `plain` | known and harmless (indent, spacing, drop caps) | text kept |
| `skip` | element whose text must not appear | text dropped, and reported (gate fails unless allow_skip_text) |

Tips
- A span class that fills a whole paragraph and is mapped to `heading:N` turns that paragraph into a heading (label lines like "EXERCISE").
- Drop caps are `plain`, never `skip`: the letter is part of a word.
- Look at 3 chapters in the output, not only the gate: structure (levels, list vs paragraph) is judgement.
- `min_figure_px` (default 80) filters bullets and ornaments; add `decorative_images` regexes for large ornaments. Everything else becomes a figure block.
- Unmapped classes are listed in the build notes. Map them or accept them as plain.
- Real asterisks, underscores, brackets and pipes in the book are escaped by the renderer and restored by the verifier.
