#!/usr/bin/env python3
"""Full-text search over every assembled book in a library (SQLite FTS5, built in memory each run).

  search.py "filler words" [--root LIB] [--book SLUG] [-n 8] [--json]
Each hit gives book, chapter, heading path, paragraph id range and a snippet; open the chapter file and go to the ids.
"""
import argparse, glob, json, os, re, sqlite3, sys

def find_root(start):
    p = os.path.abspath(start)
    while p != '/':
        if os.path.isdir(os.path.join(p, 'books')):
            return p
        p = os.path.dirname(p)
    sys.exit('no library root (a folder containing books/) found; pass --root')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('query'); ap.add_argument('--root', default=None); ap.add_argument('--book')
    ap.add_argument('-n', type=int, default=8); ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    root = a.root or find_root(os.getcwd())
    db = sqlite3.connect(':memory:')
    db.execute("create virtual table c using fts5(text, heading, chapter_title, book unindexed, chapter unindexed, first unindexed, last unindexed, tokenize='porter unicode61 remove_diacritics 2')")
    for p in glob.glob(os.path.join(root, 'books', '*', '04-assemble', 'chunks.jsonl')):
        for ln in open(p):
            r = json.loads(ln)
            if a.book and r['book'] != a.book:
                continue
            db.execute('insert into c values (?,?,?,?,?,?,?)', (r['text'], r['heading'], r['chapter_title'], r['book'], r['chapter'], r['first'], r['last']))
    q = ' '.join(f'"{w}"' for w in re.findall(r'\w+', a.query)) if not re.search(r'["*]|\b(AND|OR|NOT)\b', a.query) else a.query
    rows = db.execute("select book, chapter, chapter_title, heading, first, last, snippet(c, 0, '[', ']', ' ... ', 24), bm25(c, 1.0, 3.0, 2.0) from c where c match ? order by bm25(c, 1.0, 3.0, 2.0) limit ?", (q, a.n)).fetchall()
    if not rows and ' OR ' not in q and len(q.split()) > 1:   # no chapter has every word: fall back to any word
        q = ' OR '.join(q.split())
        rows = db.execute("select book, chapter, chapter_title, heading, first, last, snippet(c, 0, '[', ']', ' ... ', 24), bm25(c, 1.0, 3.0, 2.0) from c where c match ? order by bm25(c, 1.0, 3.0, 2.0) limit ?", (q, a.n)).fetchall()
    if a.json:
        print(json.dumps([dict(zip(('book', 'chapter', 'chapter_title', 'heading', 'first', 'last', 'snippet', 'score'), r)) for r in rows], ensure_ascii=False, indent=1))
        return
    for i, (b, ch, ct, h, f, l, sn, sc) in enumerate(rows, 1):
        print(f"{i}. {b} / {ch}: {ct}\n   {h}\n   ids {f} to {l}\n   {' '.join(sn.split())}\n")
    if not rows:
        print('no hits; try fewer or different words')

main()
