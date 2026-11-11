# Where things live

Two separate places. Keep them separate.

## 1. The tools (this repository)

Code and documentation only. You clone it once, anywhere (for example `~/tools/library-for-agents`). It never contains your books or anything derived from them. Update it with `git pull`.

## 2. Your library (a folder you choose)

Created by `library.py new`. Everything about your books lives here:

```
my-library/
  inbox/            EPUBs waiting to be processed (you drop them here)
  books/<slug>/     one folder per book
    book.yaml         metadata and your chapter decisions
    01-source/        the original EPUB, hash-pinned
    02-text/          chapters as Markdown with paragraph ids, figures
    05-verify/        check results (import-gate.json)
  index/            embeddings, atoms, links (derived, large, rebuildable)
  CATALOG.md        list of books
  AGENTS.md  CONTEXT.md   how an agent should read and search this library
  .library.env      the paths used by the tools
```

## Recommended: a private Git repository

Each book is processed once, and the embeddings and atoms cost money to build. Keep the whole library, including `index/`, in a private Git repository: history, undo, and a backup on the remote. `scripts/setup_library.py` runs `git init` for you (skip with `--no-git`). Add a private remote and push.

Size: one book's embeddings are a few MB. Dozens of books are fine in plain Git. Past roughly 100 books the repo gets heavy; then use Git LFS for `index/`, or keep `index/` out of Git and use the optional file storage copy below.

A plain folder also works (no history, you arrange your own backup).

Never make a library public unless you hold the rights to every book in it. The text, embeddings and atoms are all derived from the books.

## Optional: a second copy in file storage

The derived files (`index/`) can be copied to a storage location of your choice (a cloud drive, an object store, a network disk) so another machine or agent can use them without rebuilding. Set `LIBRARY_PUBLISH_REMOTE` to an [rclone](https://rclone.org) location. The gate copies and checks sizes. Skip it if you use one machine.

## What leaves your machine

- Paragraph and chapter text is sent to OpenRouter to make embeddings and atoms.
- If you set a storage location, the derived files are copied there.
- Nothing else. The tools make no other network calls.
