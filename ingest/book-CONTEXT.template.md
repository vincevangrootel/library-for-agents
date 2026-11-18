# {title}

Author: {author}. Slug: `{slug}`. Source: `01-source/` (your own EPUB, keep it out of public places).

## Read this book
- Chapters: `02-text/manifest.json` lists every document with its title and file.
- Chapter files: `02-text/chapters/<id>-<slug>.md`. Front matter is generated metadata; the body is verbatim book text with paragraph ids.
- Keyword search (free, no key): `python3 tools/search.py "query" --book {slug}` from the library root.
- Meaning search (level 2 and up): `python <library-for-agents>/library.py search "question"`.
- Cite as `{slug} / <chapter id> / ^<paragraph id>`.

## Layers
| Folder | What | Edit? |
|---|---|---|
| `01-source/` | original EPUB, hash-pinned | never |
| `02-text/` | verbatim text layer | never by hand, rebuild only |
| `05-verify/` | gate reports (`text.json`, `import-gate.json`) | generated |

AI-made layers live outside the book folder, in `index/` at the library root: embeddings (level 2) and atoms (level 3).

## Status
See `book.yaml` status and `05-verify/import-gate.json`.
