#!/usr/bin/env python3
"""Full-text search over every book's text layer (SQLite FTS5, cached on disk).

  search.py "filler words" [--root LIB] [--book SLUG] [-n 8] [--json] [--all-sections]
Reads books/<slug>/02-text/chapters/*.md via each book's manifest. Text is indexed in chunks of
consecutive paragraphs under one heading. Reference sections (index, notes, bibliography, ...) are
skipped, as for the vector index, unless --all-sections is given.
The index is cached in <root>/.cache/keyword-search.sqlite (gitignored) and rebuilt when any
manifest or chapter file changes; --rebuild forces it.
Each hit gives book, chapter, heading, paragraph id range and a snippet; open the chapter file and go to the ids.
"""
import argparse, glob, hashlib, json, os, re, sqlite3, sys

PARA = re.compile(r'^(.*?)\s\^([a-z0-9]+-\d{3,})\s*$')
HEAD = re.compile(r'^(#{1,6})\s+(.*)$')
CHUNK = 6   # paragraphs per chunk at most
VERSION = '1'   # bump when chunking or filtering changes

def find_root(start):
    p = os.path.abspath(start)
    while p != '/':
        if os.path.isdir(os.path.join(p, 'books')):
            return p
        p = os.path.dirname(p)
    sys.exit('no library root (a folder containing books/) found; pass --root')

def chapter_chunks(path, title):
    """Yield (heading, first_id, last_id, text) for runs of paragraphs under one heading."""
    heading, run = title, []
    body = open(path, encoding='utf-8').read()
    if body.startswith('---'):
        body = body.split('\n---', 1)[-1]
    def flush():
        if run:
            yield (heading, run[0][0], run[-1][0], ' '.join(t for _, t in run))
    for ln in body.splitlines():
        m = PARA.match(ln)
        h = HEAD.match(m.group(1) if m else ln)
        if h:
            yield from flush(); run = []
            heading = h.group(2).strip() or heading
            continue
        if m and m.group(1).strip():
            run.append((m.group(2), re.sub(r'^>\s*', '', m.group(1)).strip()))
            if len(run) >= CHUNK:
                yield from flush(); run = []
    yield from flush()

def signature(root, all_sections):
    h = hashlib.sha256(f'{VERSION}|{all_sections}'.encode())
    for f in sorted(glob.glob(os.path.join(root, 'books', '*', '02-text', 'manifest.json')) +
                    glob.glob(os.path.join(root, 'books', '*', '02-text', 'chapters', '*.md'))):
        st = os.stat(f); h.update(f'{f}|{st.st_mtime_ns}|{st.st_size}\n'.encode())
    return h.hexdigest()

def open_index(root, all_sections, rebuild):
    """Return a connection to an up-to-date cached index, building it if needed."""
    sig = signature(root, all_sections)
    cdir = os.path.join(root, '.cache'); os.makedirs(cdir, exist_ok=True)
    path = os.path.join(cdir, 'keyword-search' + ('-all' if all_sections else '') + '.sqlite')
    if not rebuild and os.path.exists(path):
        db = sqlite3.connect(path)
        try:
            if db.execute('select v from meta where k="sig"').fetchone() == (sig,):
                return db
        except sqlite3.Error:
            pass
        db.close()
    tmp = path + '.tmp'
    if os.path.exists(tmp): os.remove(tmp)
    db = sqlite3.connect(tmp)
    db.execute("create virtual table c using fts5(text, heading, chapter_title, book unindexed, chapter unindexed, first unindexed, last unindexed, tokenize='porter unicode61 remove_diacritics 2')")
    db.execute('create table meta(k primary key, v)')
    n = load(db, root, None, all_sections)
    db.execute('insert into meta values ("sig", ?)', (sig,)); db.execute('insert into meta values ("books", ?)', (n,))
    db.commit(); db.close(); os.replace(tmp, path)
    return sqlite3.connect(path)

def load(db, root, only_book, all_sections):
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sections
    except ImportError:
        sections = None
    books = 0
    for man in sorted(glob.glob(os.path.join(root, 'books', '*', '02-text', 'manifest.json'))):
        slug = man.split(os.sep)[-3]
        if only_book and slug != only_book:
            continue
        cdir = os.path.join(os.path.dirname(man), 'chapters')
        for d in json.load(open(man, encoding='utf-8')).get('documents', []):
            p = os.path.join(cdir, d.get('md') or '')
            if not d.get('md') or not os.path.isfile(p):
                continue
            title = d.get('title') or d['id']
            chunks = list(chapter_chunks(p, title))
            if not all_sections and sections and sections.is_reference(title, [c[3] for c in chunks]):
                continue
            db.executemany('insert into c values (?,?,?,?,?,?,?)',
                           [(t, h, title, slug, d['id'], f, l) for h, f, l, t in chunks])
        books += 1
    return books

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('query'); ap.add_argument('--root', default=None); ap.add_argument('--book')
    ap.add_argument('-n', type=int, default=8); ap.add_argument('--json', action='store_true')
    ap.add_argument('--all-sections', action='store_true', help='also search index, notes, bibliography and similar sections')
    ap.add_argument('--rebuild', action='store_true', help='rebuild the cached index')
    a = ap.parse_args()
    root = a.root or find_root(os.getcwd())
    db = open_index(root, a.all_sections, a.rebuild)
    if not db.execute('select v from meta where k="books"').fetchone()[0]:
        sys.exit(f'no books with 02-text/manifest.json under {root}/books')
    if a.book and not db.execute('select 1 from c where book = ? limit 1', (a.book,)).fetchone():
        sys.exit(f'no indexed text for book {a.book}')
    flt = ' and book = ?' if a.book else ''
    sql = f"select book, chapter, chapter_title, heading, first, last, snippet(c, 0, '[', ']', ' ... ', 24), bm25(c, 1.0, 3.0, 2.0) from c where c match ?{flt} order by bm25(c, 1.0, 3.0, 2.0) limit ?"
    run = lambda q: db.execute(sql, (q, a.book, a.n) if a.book else (q, a.n)).fetchall()
    q = ' '.join(f'"{w}"' for w in re.findall(r'\w+', a.query)) if not re.search(r'["*]|\b(AND|OR|NOT)\b', a.query) else a.query
    rows = run(q) if q else []
    if not rows and q and ' OR ' not in q and len(q.split()) > 1:   # no chunk has every word: fall back to any word
        q = ' OR '.join(q.split())
        rows = run(q)
    if a.json:
        print(json.dumps([dict(zip(('book', 'chapter', 'chapter_title', 'heading', 'first', 'last', 'snippet', 'score'), r)) for r in rows], ensure_ascii=False, indent=1))
        return
    for i, (b, ch, ct, h, f, l, sn, sc) in enumerate(rows, 1):
        print(f"{i}. {b} / {ch}: {ct}\n   {h}\n   ids {f} to {l}\n   {' '.join(sn.split())}\n")
    if not rows:
        print('no hits; try fewer or different words')

main()
