<div align="center">

# 📚 library-for-agents

**Turn the EPUB books you own into a private library your AI agents can search and cite.**

Clean Markdown · semantic search · audited idea atoms · one command

[MIT licence](LICENSE) · Python 3.10+ · free at level 1, under a cent per book at level 2

</div>

---

## 🤖 Let an agent do it

Give your agent this repository and say:

> *Read `AGENTS.md` in this repo and set up a library for me.*

It asks a few questions one at a time, shows a plan with the cost, and builds only after you say yes.

## 🧭 Do it yourself: four commands

```bash
git clone https://github.com/vincevangrootel/library-for-agents && cd library-for-agents
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python library.py doctor                                  # checks everything, spends nothing

python library.py new ~/library --books ~/my-epubs        # 1. create your private library
cd ~/library
python ~/library-for-agents/library.py estimate           # 2. words, cost and disk per level
python ~/library-for-agents/library.py add --level 2      # 3. build (asks before spending)
python ~/library-for-agents/library.py search "your question"   # 4. ask
```

Tip: `alias library="python $PWD/library.py"` saves typing.

## 📶 Pick a level

Each level includes the ones below it. You can start low and go up later per book without redoing anything.

| Level | You get | Good for | Cost per typical book* | Needs |
|---|---|---|---|---|
| **1 · Text** | Every chapter as clean Markdown, each paragraph with a stable id (`ch03-012`). Keyword search. | Reading, quoting, giving an agent exact text. Fiction. | **free** | nothing |
| **2 · Meaning** ⭐ | One embedding per paragraph. Search by meaning: "why do habits fail" finds the passage even if it never uses those words. | Most people. Every kind of book. | **< $0.01** | OpenRouter key |
| **3 · Ideas** | The book's claims as short, self-contained atoms, each cited to its paragraphs, a quality audit, and links between related ideas across books. | Idea-driven non-fiction you want to think with, compare and combine. | **about $0.20** | OpenRouter key |

\* An 85k-word non-fiction book with the recommended models. `estimate` calculates it for your own books. Costs are one-time: a processed book is never processed again, which is why the library is a Git repo.

**Recommendation:** level 2 for everything, level 3 for the non-fiction you care most about. Stories, memoirs and quote collections stay at level 2; atoms add little there.

Rough totals: **100 books** at level 2 ≈ $0.30; at level 3 ≈ $15 to $25. Disk: about 5 MB per book at level 2, plus the EPUB.

## 🧠 Models

One [OpenRouter](https://openrouter.ai) key covers all of them. Defaults are chosen for value; change them in `.library.env`.

| Job | Default | Stronger option |
|---|---|---|
| Embeddings (2, 3) | `qwen/qwen3-embedding-8b`, 1024 dims | `openai/text-embedding-3-large` (pick before your first book) |
| Atoms (3) | `deepseek/deepseek-v4.1-flash` | `anthropic/claude-sonnet-5.5` (≈5× cost) |
| Audit (3) | `anthropic/claude-sonnet-5.5` | `--no-audit` to skip |

Details, alternatives and spend control: [docs/MODELS.md](docs/MODELS.md).

## 🔒 Where things live

- **This repo** holds tools only. No books, ever.
- **Your library** is a folder you choose, created as a **private** Git repo: books, text, embeddings and atoms are versioned, so money spent is never lost. Push it to a private remote for backup. A plain folder works too (`--no-git`).
- Only text sent for embeddings and atoms leaves your machine, to OpenRouter.

More, including large libraries (Git LFS from about 100 books): [docs/WHERE-THINGS-LIVE.md](docs/WHERE-THINGS-LIVE.md).

## ✅ Try it with a synthetic book first (about 2 minutes, about 2 cents)

```bash
python example/make_example_epub.py /tmp/ex/field-guide-to-keeping-notes.epub
python library.py new /tmp/demo-library --books /tmp/ex && cd /tmp/demo-library
python ~/library-for-agents/library.py add --level 3      # say y
python ~/library-for-agents/library.py search "why do note collections fail"
```

Expected: verdict `WARN` (no cover, ISBN or second book to link to; all fine), about 35 atoms, the top hit is the paragraph about notes treated as storage.

## Commands

| Command | Does | Spends |
|---|---|---|
| `doctor` | Checks Python, packages, git, key, models | nothing |
| `new DEST [--books DIR] [--no-git]` | Creates the library | nothing |
| `estimate [EPUBS] [--level N]` | Words, cost and disk per book and level | nothing |
| `add [EPUBS] [--level N] [--type fiction]` | Builds, checks, commits. Default: everything in `inbox/` at level 2 | after you confirm |
| `status` | Books, levels, gate verdicts, money spent | nothing |
| `search "question" [--text]` | Semantic search, or free keyword search | a fraction of a cent per query |

`add` handles each book's table of contents automatically. Running it again skips finished work. A `WARN` is normal; a `FAIL` stops that book and says why ([docs/GATE.md](docs/GATE.md)).

## Requirements

- Python 3.10+, git
- An OpenRouter API key for levels 2 and 3, in `<library>/.env` (gitignored) or your shell
- Your own, legally owned books as `.epub`. Other formats: convert with [Calibre](https://calibre-ebook.com) first.

## Repository layout

```
library.py            the one command
AGENTS.md  SETUP.md   for agents: rules and the guided setup
docs/                 models and cost, where things live, the gate, atoms, manual steps
ingest/  tools/       the stages library.py runs (usable on their own)
template/             what a new library starts from
example/              synthetic book generator
```

## Licence

MIT, see [LICENSE](LICENSE). It covers this code and documentation only. Books you process stay under their own rights; keep text, embeddings and atoms derived from them private unless you hold those rights.
