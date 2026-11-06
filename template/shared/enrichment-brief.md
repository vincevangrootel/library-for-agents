# Enrichment brief (give this to each enrichment agent, fill the placeholders)

You are completing enrichment sidecars for an agent-readable book library. Book folder: BOOK=<abs path>. Verifier: `python3 <factory>/ingest/verify_enrich.py $BOOK --only <ids>`.

YOUR DOCUMENTS: <ids>.

For each id read the verbatim text at `$BOOK/02-text/chapters/<id>-*.md` (every paragraph ends with a block id like ^ch05-012). Write `$BOOK/03-enrich/chapters/<id>.yaml` following `shared/sidecar-schema.md`. Never touch `02-text`, other documents' sidecars, or figures.yaml.

1. key_concepts: term short, definition one sentence in the book's words, cites 1 to 4 ids of paragraphs that state it (not headings).
2. questions_answered: what a reader would ask; cite the answering paragraphs.
3. summary 3 to 5 sentences, nothing the book does not say; summary_cites 3 to 8 ids spread over the chapter.
4. short_answer only if the book has its own (a pull quote near the top); exact wording, no surrounding quotes.
5. keywords 10 to 20 supported by the text.
6. related: {id, why}; include every explicit cross reference (links like [chapter 8](...)); why grounded in the text.
Hard rules: no em dash or en dash characters, no invented claims, plain YAML UTF-8.
Run the verifier until 0 errors and read every warning (weakly grounded means the cited paragraphs do not contain the term). Finish with a 3 line report: ids done, remaining warnings, anything odd in the text.

For short front or back matter (sources list, bio, copyright) a summary, 2 to 5 concepts, 2 to 4 questions and keywords are enough.
