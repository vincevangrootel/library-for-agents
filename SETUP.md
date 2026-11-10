# Setup guide for agents (and people)

Goal: end with a library folder that holds the user's books and lets them (or an agent) search it.

## 1. Interview

Ask one question at a time.

1. **Where should the library live?** Suggest a folder outside this repo, for example `~/library`. It will hold the books and everything derived from them.
2. **Should that folder be a Git repository?** Recommend yes, private. Each book is processed once, and the embeddings and atoms cost money to build, so versioning and backing them up is worth it. Everything is tracked: books, text, embeddings, atoms. Ask where the private remote should be (GitHub, a self-hosted server). Mention the size caveat: one book's embeddings are a few MB, fine for dozens of books; past roughly 100 books suggest Git LFS for `index/`, or the optional file-storage copy. If they decline Git, a plain folder works and they must arrange their own backup. Never make the repo public.
3. **Where are the books?** A folder of `.epub` files. Only EPUB is supported. If they are in another format (for example PDF or Kindle), say so, and ask if they can convert them first (Calibre does this).
4. **Do they have an OpenRouter API key?** It is needed for embeddings and atoms. Ask them to put it in the `OPENROUTER_API_KEY` environment variable. Do not ask them to paste it into chat if you can avoid it.
5. **Extra copy elsewhere?** Optional. Do they want the embeddings and atoms copied to a storage location (cloud drive, network disk) so other machines or agents can use them? If yes, they need an [rclone](https://rclone.org) remote; set `LIBRARY_PUBLISH_REMOTE`. If no, skip it.
6. **Atoms or embeddings only?** Embeddings only is cheaper and enough for most books. Atoms add short audited claims and cross-book links, mainly useful for idea-driven non-fiction. Recommend embeddings first.

## 2. Prepare the machine

```bash
git clone https://github.com/vincevangrootel/library-for-agents ~/tools/library-for-agents   # or wherever
cd ~/tools/library-for-agents && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python3 scripts/setup_library.py ~/library --books ~/Downloads/my-epubs      # creates the library folder
```

`setup_library.py` creates the folder, runs `git init` (skip with `--no-git`), copies the library scaffold into it, copies the EPUBs into `inbox/`, and writes `.library.env` with the paths. It never overwrites a non-empty folder.

## 3. Show the plan, then get a yes

Tell the user, in plain words:
- the library folder, and the Git repo (private remote, if any)
- the number of EPUBs found and the stages that will run (text, embeddings, optional atoms, gate)
- a cost estimate: embeddings cost well under a cent per book; atoms roughly a cent or two per book
- that nothing leaves their machine except the text sent to OpenRouter for embeddings and atoms, and the optional storage copy if they chose it

## 4. Build, one book at a time

Run from inside the library folder, `. .library.env` first.

```bash
TOOLS=~/tools/library-for-agents
python3 $TOOLS/ingest/parse_epub.py inspect inbox/BOOK.epub          # see what is inside
python3 $TOOLS/ingest/parse_epub.py init inbox/BOOK.epub books/SLUG   # draft book.yaml
# review books/SLUG/book.yaml with the user: which documents are chapters, front or back matter, decorative images; set content_type: nonfiction|fiction
python3 $TOOLS/ingest/parse_epub.py build books/SLUG
python3 $TOOLS/ingest/verify_text.py books/SLUG --report 05-verify/text.json
python3 $TOOLS/tools/build_embeddings.py SLUG
python3 $TOOLS/tools/extract_atoms.py SLUG        # only if the user wants atoms
python3 $TOOLS/tools/book_gate.py SLUG --no-publish
```

Do the first book together with the user and check the gate result before batching the rest. A `WARN` for missing cover or ISBN is fine. A `FAIL` needs a fix before moving on (`docs/GATE.md`).

## 5. Finish

Test with `python3 $TOOLS/tools/search.py "a question the book answers"`. Then tell the user where everything is and how to add the next book. The library's own `AGENTS.md` and `CONTEXT.md` tell future agents how to read it.

A worked example with a synthetic book is in `README.md` (quick start).
