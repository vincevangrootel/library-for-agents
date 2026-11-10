<div align="center">

# 📚 library-for-agents

**Turn the EPUB books you own into a library your AI agents can search and cite.**

Clean Markdown · paragraph embeddings · audited atoms · a quality gate

[MIT licence](LICENSE) · Python 3.10+ · about a cent per book

</div>

---

## 🤖 Just want an agent to do it?

Give your agent this repository and say:

> *Read `AGENTS.md` and `SETUP.md` in this repo and set up a library for me.*

It will interview you (where to save it, which private Git remote, where your books are), show a plan and a cost estimate, and only then build. Nothing is created before you say yes.

## What you get

For every book:

| Step | Result | Tool |
|---|---|---|
| 1. Text | Chapters as Markdown with stable paragraph ids, checked against the source EPUB | `ingest/` |
| 2. Embeddings | One vector per paragraph, so search finds meaning, not just words | `tools/build_embeddings.py` |
| 3. Atoms *(optional)* | Short self-contained claims, each tied to its source paragraphs and audited | `tools/extract_atoms.py`, `tools/audit_atoms.py` |
| 4. Links *(optional)* | Related ideas connected across books | `tools/link_atoms.py` |
| 5. Gate | One command that says PASS, WARN or FAIL per stage | `tools/book_gate.py` |
| 6. Search | Ask a question, get the best paragraphs with ids | `tools/search.py` |

## How it is organised

Two separate places:

- **This repo** holds the tools only. No books, ever.
- **Your library** is a folder you choose. Books, text, embeddings and atoms live there. It is meant to be a private Git repo, so books and everything built from them are versioned and backed up.

Full picture, including backup and what leaves your machine: [docs/WHERE-THINGS-LIVE.md](docs/WHERE-THINGS-LIVE.md).

## Requirements

- Python 3.10+
- An [OpenRouter](https://openrouter.ai) API key in `OPENROUTER_API_KEY` (used for embeddings and atoms)
- Your own legally owned books as `.epub` files

## Quick start with a synthetic book (about 5 minutes, about one cent)

```bash
git clone https://github.com/vincevangrootel/library-for-agents && cd library-for-agents
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
export OPENROUTER_API_KEY=...                    # your own key

# an original example book, no rights issues
python3 example/make_example_epub.py example/field-guide-to-keeping-notes.epub

# create a library folder next to this repo and step inside
python3 scripts/setup_library.py ../my-library --books example     # also runs git init
cd ../my-library && . .library.env
T=$LIBRARY_TOOLS

# text
python3 $T/ingest/parse_epub.py init inbox/field-guide-to-keeping-notes.epub books/example
python3 $T/example/prep_book_yaml.py books/example     # real books: review book.yaml by hand
python3 $T/ingest/parse_epub.py build books/example
python3 $T/ingest/verify_text.py books/example --report 05-verify/text.json

# embeddings, atoms, check
python3 $T/tools/build_embeddings.py example
python3 $T/tools/extract_atoms.py example
python3 $T/tools/book_gate.py example --no-publish

# ask something
python3 $T/tools/search.py "why do note collections fail"
```

Expected: gate summary `WARN` (stages 2 to 5 PASS). The warnings are optional metadata: cover, ISBN, Calibre id.

For real books, run `python3 $T/ingest/parse_epub.py inspect BOOK.epub` first, then check `book.yaml` after `init`: which documents are chapters, front or back matter, and which images are decorative.

## Settings

| Variable | Meaning |
|---|---|
| `OPENROUTER_API_KEY` | Required for embeddings and atoms |
| `LIBRARY_ROOT` / `LIBRARY_INDEX` | Library folder and index folder (written to `.library.env`) |
| `ATOM_TIER` | `flash` (cheaper) or `sonnet` (stronger) atom extraction |
| `LIBRARY_PUBLISH_REMOTE` | Optional file storage: copy embeddings, atoms and links to a storage location you choose so other machines or agents can use them. Skip it on a single machine. |

## Repository layout

```
AGENTS.md  SETUP.md   start here if you are an agent
scripts/              setup_library.py creates your library folder
ingest/               EPUB to verified Markdown
tools/                embeddings, atoms, audit, links, gate, search
template/             what a new library starts from
example/              synthetic book generator
docs/                 where things live, atoms, the gate
```

## Licence

MIT, see [LICENSE](LICENSE). It covers this code and documentation only. Books you process stay under their own rights; keep text, embeddings and atoms derived from them private unless you hold those rights.
