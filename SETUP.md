# Guided setup (for agents, readable by people)

Six steps. Ask **one question at a time** and wait for the answer. Nothing is created and nothing is spent before step 5.

`L` below means `python <path-to-this-repo>/library.py`.

## 1. Check the machine

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
L doctor
```

Fix anything marked MISSING before continuing. Tell the user in one line that the tools are ready.

## 2. Ask: where are your books?

A folder of `.epub` files they legally own. Only EPUB is supported. If they have PDF or Kindle files, tell them, and suggest converting with Calibre first. Never download or fetch books.

Then run, without spending anything:

```bash
L estimate /path/to/their/epubs
```

## 3. Ask: which level?

Explain from the estimate output, in plain words and with their numbers:

- **Level 1 · Text**: clean Markdown with paragraph ids, keyword search. Free.
- **Level 2 · Meaning**: adds semantic search. Usually under a cent per book. **Recommend this as the default.**
- **Level 3 · Ideas**: adds cited idea atoms, a quality audit and cross-book links. About 20 cents per typical non-fiction book. Recommend for idea-driven non-fiction they want to think with; not for fiction or memoir.

They may mix: level 2 for everything, then level 3 for chosen books (run `add` again with those files and `--level 3`).

If they choose 2 or 3, ask whether they have an OpenRouter API key. They put it in `<library>/.env` as `OPENROUTER_API_KEY=...` themselves, or in their shell. Do not ask them to paste it into chat. Mention they can set a spending limit on the key at openrouter.ai.

Models: keep the defaults unless they ask (see `docs/MODELS.md`). If they want the stronger atom model, quote the roughly five times higher level-3 cost.

## 4. Ask: where should the library live?

Suggest `~/library`, outside this repo. Explain: it becomes a **private** Git repo, so the books and everything built from them (which cost money) are versioned. Ask where the private remote should be (GitHub private repo, a self-hosted server, none yet). If they decline Git, use `--no-git` and tell them to arrange their own backup. Past about 100 books, suggest Git LFS (`docs/WHERE-THINGS-LIVE.md`). Never make the library public.

## 5. Show the plan, get a yes

One short message:

- library folder and private remote
- number of books, total words, chosen level
- estimated cost (from `estimate`) and that it is one-time
- what leaves the machine: book text sent to OpenRouter for levels 2 and 3, nothing else

Then, only after a clear yes:

```bash
L new ~/library --books /path/to/their/epubs
cd ~/library
L add --level 2 --yes            # --yes only because the user just approved the estimate
```

For more than five books, run the first book alone (`L add inbox/ONE.epub --level N --yes`), show the result, then do the rest.

## 6. Finish

```bash
L status
L search "a question one of their books answers"
```

Show the user the search result and the spend. Push to their private remote if they gave one (`git remote add origin URL && git push -u origin HEAD`). Tell them how to add books later: drop EPUBs in `inbox/` and run `L add`.

## When something goes wrong

| Message | Do |
|---|---|
| `FAIL text ...` | The EPUB has an unusual structure. See `docs/MANUAL.md` to review `book.yaml` by hand, then `L add BOOK.epub --rebuild`. |
| `FAIL at atoms` | Nothing is retried automatically. Usually a short or unusual book; keep it at level 2, or see `docs/GATE.md`. |
| `WARN` | Normal: missing cover, ISBN, or only one book to link with. |
| `needs OPENROUTER_API_KEY` | Ask the user to add the key to `<library>/.env`. |
