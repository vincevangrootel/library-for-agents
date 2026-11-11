# Agent instructions

A person pointed you at this repository because they want a searchable library of their own books. Set it up with them by following **`SETUP.md`**: six steps, one question at a time.

Everything runs through one command, `library.py` (`doctor`, `new`, `estimate`, `add`, `status`, `search`). Prefer it over the scripts in `ingest/` and `tools/`; those are for manual work (`docs/MANUAL.md`).

## Rules

1. Ask one question at a time. Do not assume folders, levels or remotes.
2. Run `estimate` and show the plan before anything is created or spent. Pass `--yes` to `add` only after the user approved that estimate.
3. Books are the user's own, legally owned files. Never download or fetch books.
4. Never print, store or commit an API key. It lives in `<library>/.env` (gitignored) or the shell.
5. Never put books, text, embeddings or atoms in this tools repository.
6. The library is private. Never make its repository public.
7. If a book fails, report it in one line and continue with the others; do not retry paid stages without asking.

## Reference

- `README.md`: levels, value, cost, commands
- `docs/MODELS.md`: model choices and spend control
- `docs/WHERE-THINGS-LIVE.md`: storage and backup
- `docs/GATE.md`: what PASS, WARN and FAIL mean
- `docs/ATOMS.md`: what atoms are
- `docs/MANUAL.md`: running the stages by hand
