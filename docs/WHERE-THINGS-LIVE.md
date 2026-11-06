# Where things live

Two separate places. Keep them separate.

## 1. The tools (this repository)

Code and documentation only. You clone it once, anywhere (for example `~/tools/library-for-agents`). It never contains your books or anything derived from them. Update it with `git pull`.

## 2. Your library (a folder you choose)

Created by `scripts/setup_library.py`. Everything about your books lives here:

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

## Is it a Git repository?

Your choice; the tools work the same either way.

| | Plain folder | Private Git repository |
|---|---|---|
| Setup | nothing | `git init` in the folder |
| History / undo | no | yes |
| Sharing with a team | copy the folder | push to a private remote |
| Backup | yours to arrange | the remote is a backup |
| Watch out | easy to lose | keep it private; `index/` is big, so keep it out of Git or use Git LFS |

Never make a library public unless you hold the rights to every book in it. The text, embeddings and atoms are all derived from the books.

## Optional: a second copy in file storage

The derived files (`index/`) can be copied to a storage location of your choice (a cloud drive, an object store, a network disk) so another machine or agent can use them without rebuilding. Set `LIBRARY_PUBLISH_REMOTE` to an [rclone](https://rclone.org) location. The gate copies and checks sizes. Skip it if you use one machine.

## What leaves your machine

- Paragraph and chapter text is sent to OpenRouter to make embeddings and atoms.
- If you set a storage location, the derived files are copied there.
- Nothing else. The tools make no other network calls.
