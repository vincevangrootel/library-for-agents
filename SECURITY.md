# Security

## Reporting a problem

Please report security issues privately through GitHub's **Report a vulnerability** button on the Security tab, not in a public issue.

## What this project does to keep your library private

- This repository holds code and documentation only. Your books, extracted text, embeddings and atoms live in a separate library folder you choose, which is a private Git repository by default.
- `library.py new` writes a `.gitignore` that keeps `.env` and `.library.env` (where API keys and settings go) out of Git, and installs a pre-push check that refuses to push the library to this public tools repository.
- EPUB files are treated as untrusted input: archives with unsafe paths or that unpack to absurd sizes are refused.
- The tools never download books. You supply EPUBs you legally own.
- API keys are read from the environment or `.env` and are never printed or written to reports.

## What you still need to do

- Keep your library's Git remote **private**.
- Set a spending limit on your API key at your provider.
