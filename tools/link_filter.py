#!/usr/bin/env python3
"""Rebuild cross-book links with a mutual top-3 rule.

A link a<->b survives only if b is in a's top-3 library-wide matches AND a is in b's
top-3 library-wide matches (other books only), and the score clears the threshold.
Dutch-source books use a sampled cutoff: the 90th percentile of their atoms' best
cross-book score, floored at the global threshold. Output: links/<slug>.json (same
format as book_gate s_links) plus links/_filter_report.json.
Usage: link_filter.py [slug ...]   (default: all books with atoms)"""
import json, os, sys, glob, collections
import numpy as np
import yaml

ROOT = os.environ.get('LIBRARY_ROOT', os.getcwd())
IDX = os.environ.get('LIBRARY_INDEX', os.path.join(ROOT, 'index'))
AT = IDX + '/atoms'
GLOBAL, PER_BOOK, MAX = float(os.environ.get('LIBRARY_LINK_THRESHOLD', 0.70)), 6, 40   # calibrated for qwen3-embedding-8b at 1024 dims; recalibrate per model

def lang(slug):
    try:
        return str((yaml.safe_load(open(f'{ROOT}/books/{slug}/book.yaml')) or {}).get('language', 'en')).lower()[:2]
    except Exception:
        return 'en'

slugs_all = sorted(os.path.basename(f)[:-6] for f in glob.glob(AT + '/*.jsonl'))
V, ATOMS, OWNER = [], [], []
for s in slugs_all:
    f = f'{AT}/vectors/{s}.npz'
    atoms = [json.loads(l) for l in open(f'{AT}/{s}.jsonl')]
    if not os.path.exists(f):
        continue
    v = np.load(f)['vec'].astype(np.float32)
    if len(v) != len(atoms):
        continue
    V.append(v); ATOMS += atoms; OWNER += [s] * len(atoms)
V = np.vstack(V); OWNER = np.array(OWNER)
print('atoms', len(V), 'books', len(set(OWNER)), flush=True)

def top3(q_idx):
    """top-3 library-wide matches (other books only) for atom indices q_idx -> (idx, score); chunked for memory"""
    TI, TS = [], []
    for b in range(0, len(q_idx), 128):
        qi = q_idx[b:b + 128]
        S = V[qi] @ V.T
        for r, i in enumerate(qi):
            S[r, OWNER == OWNER[i]] = -1
        t = np.argpartition(-S, 3, axis=1)[:, :3]
        sc = np.take_along_axis(S, t, 1)
        o = np.argsort(-sc, axis=1)
        TI.append(np.take_along_axis(t, o, 1)); TS.append(np.take_along_axis(sc, o, 1))
        del S
    return np.vstack(TI), np.vstack(TS)

targets = sys.argv[1:] or sorted(set(OWNER))
report = {}
os.makedirs(AT + '/links', exist_ok=True)
for slug in targets:
    mine = np.where(OWNER == slug)[0]
    if not len(mine):
        continue
    ti, ts = top3(mine)
    cut = GLOBAL
    if lang(slug) == 'nl':
        cut = max(GLOBAL, float(np.percentile(ts[:, 0], 90)))
    cand = []
    pairs = [(float(ts[r, k]), int(i), int(ti[r, k])) for r, i in enumerate(mine) for k in range(3) if ts[r, k] >= cut]
    js = sorted(set(j for _, _, j in pairs)); rev = {}
    for b in range(0, len(js), 256):
        chunk = np.array(js[b:b + 256]); rj, _ = top3(chunk)
        for q, row in zip(chunk, rj): rev[int(q)] = set(int(x) for x in row)
    cand = [(sc, i, j) for sc, i, j in pairs if i in rev[j]]
    cand.sort(key=lambda c: -c[0]); used, per, links = set(), collections.Counter(), []
    for s, i, j in cand:
        o = OWNER[j]
        if i in used or per[o] >= PER_BOOK or len(links) >= MAX:
            continue
        used.add(i); per[o] += 1
        links.append(dict(score=round(s, 3), a=f"{slug}#{ATOMS[i]['paras'][0]}", b=f"{o}#{ATOMS[j]['paras'][0]}",
                          claim_a=ATOMS[i]['claim'], claim_b=ATOMS[j]['claim']))
    if len(report) % 20 == 0: json.dump(report, open(AT + "/links/_filter_report.json", "w"), indent=1)
    json.dump(links, open(f'{AT}/links/{slug}.json', 'w'), indent=1, ensure_ascii=False)
    report[slug] = dict(lang=lang(slug), cutoff=round(cut, 3), links=len(links), mutual_candidates=len(cand))
json.dump(report, open(AT + '/links/_filter_report.json', 'w'), indent=1)
nl = [v for v in report.values() if v['lang'] == 'nl']
print('books', len(report), 'links', sum(v['links'] for v in report.values()), 'zero-link books',
      sum(1 for v in report.values() if not v['links']))
print('dutch cutoffs', sorted(set(v['cutoff'] for v in nl)))
