# Running the stages by hand

`library.py add` runs all of this for you. Use the stages directly when a book needs care: an unusual table of contents, a failed text check, or a re-run of one stage.

Run from inside the library folder after `. .library.env` (and your key in the shell for paid stages).

```bash
T=$LIBRARY_TOOLS
python3 $T/ingest/parse_epub.py inspect inbox/BOOK.epub                # what is inside
python3 $T/ingest/parse_epub.py init inbox/BOOK.epub books/SLUG        # draft book.yaml
#   edit books/SLUG/book.yaml: each document is chapter, front, back or exclude;
#   'review' means the tool could not decide. Set content_type: nonfiction|fiction,
#   and atoms: none for books that should stop at level 2.
python3 $T/ingest/parse_epub.py build books/SLUG                       # level 1: Markdown + paragraph ids
python3 $T/ingest/verify_text.py books/SLUG --report 05-verify/text.json
python3 $T/ingest/assemble.py books/SLUG                               # single-file and chunked views
python3 $T/tools/build_embeddings.py SLUG                              # level 2
python3 $T/tools/extract_atoms.py SLUG                                 # level 3
python3 $T/tools/audit_atoms.py SLUG                                   # level 3: sampled audit
python3 $T/tools/book_gate.py SLUG --no-publish                        # checks everything, writes 05-verify/import-gate.json
python3 $T/ingest/catalog.py --root .                                  # refresh the catalogue
```

After a manual fix, `library.py add inbox/BOOK.epub --level N` picks up where the book is: finished stages are skipped.
