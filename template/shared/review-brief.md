# Independent review brief (fresh agents, strongest model, do not show them the authors' reasoning)

You are an independent fact checker. You have not seen how these files were produced. Book folder BOOK=<abs path>. Verbatim text: `$BOOK/02-text/chapters/<id>-*.md` (paragraph ids at line ends). Metadata: `$BOOK/03-enrich/chapters/<id>.yaml`. Do not edit files. Documents: <ids>.

Read each full text, then check: (1) every key_concept: do the cited paragraphs support term AND definition; overstatements, wrong attribution, wrong numbers; (2) every question: do the cites answer it; (3) summary: unsupported statements, missing main points, relevant summary_cites; (4) short_answer equals the book's wording and sits in the right chapter; (5) keywords supported; (6) related: each why holds, no explicit cross reference missing.
Be strict but not pedantic. Output per document: id, field, exact item, what is wrong, the fix with paragraph ids; or "clean". End with a one line verdict.

Figure reviewer variant: open each image with Read, compare with `figures.yaml` (description accuracy, exact text_in_figure, takeaway vs surrounding text, QR links plausible; do not fetch them).

Apply the fixes yourself afterwards (a reviewer only reports), rerun `verify_enrich.py` and `check.py`, and record outcome in `05-verify/REPORT.md`.
