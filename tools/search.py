#!/usr/bin/env python3
"""Semantic search over the library. Returns cited paragraph IDs.
Usage: search.py "question" [-k 8] [--book SLUG_SUBSTRING] [--json] [--text-chars 300]
Needs the embedding key (to embed the query). Results contain book text: keep them private unless you own the rights."""
import argparse, glob, json, os, re, sys, urllib.request
import numpy as np
import urllib.request as _ur; _o = _ur.build_opener(); _o.addheaders = [('User-Agent', 'Mozilla/5.0 (library-tools)')]; _ur.install_opener(_o)  # UA_HEADER: default Python UA is blocked at the OpenRouter edge (error 1010)

ROOT = os.environ.get('LIBRARY_ROOT', os.getcwd())
EMB = os.path.join(os.environ.get('LIBRARY_INDEX', os.path.join(ROOT, 'index')), 'embeddings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import llm
MODEL = llm.embed_model()  # must match the model that built the index

def embed_query(q):
    v = np.array(llm.embed([q], 'query')[0][0], dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)

def para_text(slug, chapter, pid):
    for f in glob.glob(f'{ROOT}/books/{slug}/02-text/chapters/{chapter}-*.md'):
        for m in re.finditer(r'^(.*?)\s\^([a-z0-9]+-\d{3,})\s*$', open(f).read(), re.M):
            if m.group(2) == pid:
                return m.group(1).strip()
    return ''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('query'); ap.add_argument('-k', type=int, default=8)
    ap.add_argument('--book', default=''); ap.add_argument('--json', action='store_true')
    ap.add_argument('--text-chars', type=int, default=300)
    a = ap.parse_args()
    q = embed_query(a.query)
    hits = []
    for f in sorted(glob.glob(EMB + '/*.npz')):
        slug = os.path.basename(f)[:-4]
        if a.book and a.book not in slug: continue
        z = np.load(f)
        built = str(z['model']) if 'model' in z.files else MODEL
        if built != MODEL or z['vec'].shape[1] != q.shape[0]:
            sys.exit(f'{slug} was embedded with {built} ({z["vec"].shape[1]} dims) but search uses {MODEL} ({q.shape[0]} dims).\n'
                     'Set LIBRARY_EMBED_MODEL back, or rebuild: python library.py add --level 2 --rebuild')
        s = z['vec'].astype(np.float32) @ q
        for i in np.argsort(-s)[:a.k]:
            hits.append((float(s[i]), slug, str(z['chapter'][i]), str(z['para'][i])))
    hits.sort(reverse=True)
    out = []
    for sc, slug, ch, pid in hits[:a.k]:
        out.append(dict(score=round(sc, 4), book=slug, chapter=ch, paragraph=pid,
                        cite=f'{slug}#{pid}', text=para_text(slug, ch, pid)[:a.text_chars]))
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for r in out:
            print(f"{r['score']:.3f}  {r['cite']}\n       {r['text']}\n")

if __name__ == '__main__':
    main()
