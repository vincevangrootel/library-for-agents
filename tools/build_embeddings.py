#!/usr/bin/env python3
"""Embed paragraphs of non-fiction library books. Resumable: one .npz per book.
Derived data only; 02-text stays immutable. Output is derived from the books: keep private."""
import json, os, re, glob, sys, time, urllib.request, concurrent.futures
import numpy as np
import urllib.request as _ur; _o = _ur.build_opener(); _o.addheaders = [('User-Agent', 'Mozilla/5.0 (library-tools)')]; _ur.install_opener(_o)  # UA_HEADER: default Python UA is blocked at the OpenRouter edge (error 1010)

ROOT = os.environ.get('LIBRARY_ROOT', os.getcwd())
OUT = os.path.join(os.environ.get('LIBRARY_INDEX', os.path.join(ROOT, 'index')), 'embeddings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import llm
MODEL = llm.embed_model()  # change = re-embed everything
os.makedirs(OUT, exist_ok=True)

import yaml
def _eligible():
    out = []
    for f in sorted(glob.glob(ROOT + '/books/*/book.yaml')):
        y = yaml.safe_load(open(f)) or {}
        if not y.get('duplicate_of') and os.path.exists(os.path.dirname(f) + '/02-text/manifest.json'):
            out.append(os.path.basename(os.path.dirname(f)))
    return out
books = sys.argv[1:] or _eligible()  # default: every non-duplicate book that has a text layer

def post(texts):
    return llm.embed(texts, 'document')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sections

def paragraphs(slug):
    m = json.load(open(f'{ROOT}/books/{slug}/02-text/manifest.json'))
    out = []
    for d in m['documents']:
        fs = glob.glob(f"{ROOT}/books/{slug}/02-text/chapters/{d['id']}-*.md")
        if not fs: continue
        ps = [(mm.group(2), mm.group(1).strip()) for mm in re.finditer(r'^(.*?)\s\^([a-z0-9]+-\d{3,})\s*$', open(fs[0]).read(), re.M)
              if len(mm.group(1).strip()) >= 40]
        if sections.is_reference(d.get('title'), [t for _, t in ps]): continue   # index, notes, bibliography, ...
        out += [(d['id'], pid, t) for pid, t in ps]
    return out

def do_book(slug):
    f = f'{OUT}/{slug}.npz'
    if os.path.exists(f): return slug, 0, 0
    ps = paragraphs(slug)
    if not ps: return slug, 0, 0
    vecs, toks = [], 0
    for i in range(0, len(ps), 64):
        e, u = post([p[2][:2000] for p in ps[i:i + 64]])
        vecs += e; toks += u.get('total_tokens', 0)
    a = np.array(vecs, dtype=np.float32)
    a /= (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    tmp = f + '.tmp.npz'
    np.savez_compressed(tmp, vec=a.astype(np.float16), chapter=np.array([p[0] for p in ps]),
                        para=np.array([p[1] for p in ps]), model=MODEL)
    os.replace(tmp, f)
    return slug, len(ps), toks

if __name__ == '__main__':
    t0 = time.time(); tp = tt = 0
    print('nonfiction books', len(books), flush=True)
    with concurrent.futures.ThreadPoolExecutor(4) as ex:
        for n, (slug, np_, nt) in enumerate(ex.map(do_book, books), 1):
            tp += np_; tt += nt
            if n % 10 == 0 or n == len(books):
                print(f'{n}/{len(books)} books, {tp} paragraphs, {tt} tokens, {int(time.time()-t0)}s', flush=True)
    print('DONE', len(glob.glob(OUT + '/*.npz')), 'files', flush=True)
