#!/usr/bin/env python3
"""Gate 2: enrichment sidecars must be well formed, cite real paragraphs, and be lexically grounded.

  verify_enrich.py BOOKDIR [--report 05-verify/enrich.json] [--min-overlap 0.5]
Checks per chapter sidecar (03-enrich/chapters/<id>.yaml):
  required fields, cites resolve to paragraph ids of THAT chapter, every key concept's term (content words) appears in
  its cited paragraphs, keywords appear in the chapter text, related ids exist, no dash characters in generated text,
  figure descriptions cover every figure (03-enrich/figures.yaml), book-overview.yaml present.
Lexical grounding is a cheap tripwire, not proof: a separate verifier agent still checks meaning (see references).
"""
import argparse, json, os, re, sys
import yaml

STOP = set('the a an and or of to in on for with is are was were be been it its this that these those as at by from your you i we my our their his her they them not no do does how what why when who which can could should would will may might if then than so but about into over under up down out more most less very just also each every any all'.split())
DASH = re.compile('[\u2014\u2013\u2012\u2015]')

def words(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower().replace("’", "")) if w not in STOP and len(w) > 2]

def stem(w):
    return re.sub(r'(ing|ed|es|s|ly)$', '', w) if len(w) > 4 else w

def split_doc(md):
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', md, re.S)
    return yaml.safe_load(m.group(1)), m.group(2)

def paras(body):
    out = {}
    for blk in re.split(r'\n\s*\n', re.sub(r'<!-- figure:.*?<!-- /figure -->', '', body, flags=re.S)):
        for m in re.finditer(r'^(.*?)\s\^([a-z0-9]+-\d{3})\s*$', blk, re.M | re.S):
            out[m.group(2)] = re.sub(r'\s+', ' ', re.sub(r'[*_>#\\]', '', blk))
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('bookdir'); ap.add_argument('--report')
    ap.add_argument('--min-overlap', type=float, default=0.5); ap.add_argument('--only', help='comma separated document ids (for quick checks while enriching)')
    a = ap.parse_args(); bd = a.bookdir
    man = json.load(open(os.path.join(bd, '02-text', 'manifest.json')))
    ids = {m['id'] for m in man['documents']}
    errs, warns, stats = [], [], {}
    def err(m): errs.append(m)
    def dashes(label, obj):
        if DASH.search(json.dumps(obj, ensure_ascii=False)): err(f'{label}: contains dash characters (em/en dash), rewrite with commas or periods')
    only = set(a.only.split(',')) if a.only else None
    for m in man['documents']:
        cid = m['id']
        if only and cid not in only: continue
        p = os.path.join(bd, '03-enrich', 'chapters', f'{cid}.yaml')
        if not os.path.exists(p):
            if m['kind'] == 'chapter': err(f'{cid}: missing sidecar')
            continue
        sc = yaml.safe_load(open(p)) or {}
        fm, body = split_doc(open(os.path.join(bd, '02-text', 'chapters', m['md'])).read())
        P = paras(body)
        text_words = {stem(w) for w in words(' '.join(P.values()))}
        for k in ('summary', 'key_concepts', 'questions_answered', 'keywords'):
            if not sc.get(k): err(f'{cid}: missing {k}')
        if sc.get('id') != cid: err(f'{cid}: sidecar id mismatch')
        dashes(cid, sc)
        n_ok = n_all = 0
        def check_cites(label, cites, claim):
            nonlocal n_ok, n_all
            if not cites: err(f'{cid}: {label} has no cites'); return
            bad = [c for c in cites if c not in P]
            if bad: err(f'{cid}: {label} cites unknown paragraph ids {bad}'); return
            cited = {stem(w) for c in cites for w in words(P[c])}
            claim_w = [stem(w) for w in words(claim)]
            if claim_w:
                ov = sum(w in cited for w in claim_w) / len(claim_w)
                n_all += 1
                if ov >= a.min_overlap: n_ok += 1
                else: warns.append(f'{cid}: {label} weakly grounded (overlap {ov:.2f}): {claim[:70]!r}')
        for k in sc.get('key_concepts') or []:
            check_cites(f"concept {k.get('term')!r}", k.get('cites'), k.get('term', ''))
        for q in sc.get('questions_answered') or []:
            check_cites(f"question {q.get('q', '')[:40]!r}", q.get('cites'), q.get('q', ''))
        for s in sc.get('summary_cites') or []:
            if s not in P: err(f'{cid}: summary_cites unknown id {s}')
        if sc.get('summary') and not sc.get('summary_cites'): err(f'{cid}: summary needs summary_cites')
        for kw in sc.get('keywords') or []:
            if not all(stem(w) in text_words for w in words(kw)): warns.append(f'{cid}: keyword {kw!r} not found in chapter text')
        for r in sc.get('related') or []:
            if r.get('id') not in ids: err(f"{cid}: related id {r.get('id')} unknown")
            if r.get('id') == cid: err(f'{cid}: related to itself')
        stats[cid] = dict(grounded=n_ok, checked=n_all, concepts=len(sc.get('key_concepts') or []))
    if only:
        print(f'verify_enrich (only {sorted(only)}): {len(errs)} errors, {len(warns)} warnings')
        for x in errs[:50]: print('  FAIL', x)
        for x in warns[:30]: print('  warn', x)
        sys.exit(0 if not errs else 1)
    fg = os.path.join(bd, '03-enrich', 'figures.yaml')
    figs = json.load(open(os.path.join(bd, '02-text', 'figures.json')))
    desc = yaml.safe_load(open(fg)) if os.path.exists(fg) else {}
    for f in figs:
        d = (desc or {}).get(f['id'])
        if not d or not d.get('description'): err(f"{f['id']}: no figure description")
        else: dashes(f['id'], d)
    extra = set(desc or {}) - {f['id'] for f in figs}
    if extra: err(f'figure descriptions for unknown figures: {sorted(extra)}')
    ov = os.path.join(bd, '03-enrich', 'book-overview.yaml')
    if not os.path.exists(ov): err('missing book-overview.yaml')
    else: dashes('book-overview', yaml.safe_load(open(ov)))
    rep = dict(ok=not errs, errors=errs, warnings=warns, stats=stats)
    if a.report:
        os.makedirs(os.path.dirname(os.path.join(bd, a.report)), exist_ok=True)
        json.dump(rep, open(os.path.join(bd, a.report), 'w'), indent=1)
    print(f'verify_enrich: {len(errs)} errors, {len(warns)} warnings')
    for x in errs[:50]: print('  FAIL', x)
    for x in warns[:30]: print('  warn', x)
    sys.exit(0 if not errs else 1)

main()
