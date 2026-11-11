#!/usr/bin/env python3
"""Import gate: take one book from imported text to searchable, linked, published.

Stages (stop at first FAIL; every run writes books/<slug>/05-verify/import-gate.json):
  1 metadata   book.yaml identity, nonfiction, not duplicate, cover, source hash
  2 text       text gate result, chapter plausibility, body coverage (chapter tags are repaired via Sonnet only with --repair-text; otherwise reported, manifest untouched)
  3 embeddings .npz exists, aligned with the text paragraphs, finite and unit length (built if missing/stale)
  4 atoms      3-chapter trial -> full run -> fill missing chapters -> validate coverage/density/dupes/verbatim
  5 retrieval  atom claim -> cited paragraph must rank high in own book and across the library
  6 links      cross-book atom links (similar claims in other books)
  7 file storage  optional: copy the derived files (embeddings, atoms, links) to a storage location you choose (LIBRARY_PUBLISH_REMOTE), verified by size; N/A when unset

Usage: book_gate.py SLUG... [--check-only] [--redo-atoms] [--repair-text] [--no-publish] [--stages 1,2,3]
Env: OPENROUTER_API_KEY, ATOM_TIER=flash|sonnet, LIBRARY_ROOT, LIBRARY_INDEX, LIBRARY_PUBLISH_REMOTE (optional)."""
import argparse, collections, datetime, glob, hashlib, importlib.util, json, os, re, shutil, subprocess, sys
import numpy as np, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('LIBRARY_ROOT', os.getcwd())
LIB = os.environ.get('LIBRARY_INDEX', os.path.join(ROOT, 'index'))
ATOMS, EMB = f'{LIB}/atoms', f'{LIB}/embeddings'
DROP = os.environ.get('LIBRARY_PUBLISH_REMOTE', '')  # optional storage location in rclone form (any storage rclone supports), e.g. myremote:library/assets
T = dict(min_chapters=3, body_coverage=0.60, trial_min_atoms_per_para=0.10, trial_max_drop=0.20, max_malformed=0.10,
         chapter_atom_coverage=0.80, audit_max_unfaithful=0.10, audit_min_keep=0.60, audit_max_not_standalone=0.25, audit_max_anecdote=0.20, max_dupes=0.05, max_verbatim=0.10,
         retr_book_top5=0.70, retr_lib_top10=0.50, link_threshold=0.72, link_max=40, link_per_book=6)
FRONT = re.compile(r'dedicat|epigraph|acknowledg|about the|also by|other books|credits|copyright|publisher|foreword|contents|index|notes|praise|title|cover|newsletter|copyright', re.I)
BACK = re.compile(r'^\s*([A-Za-z]$|index|notes?|endnotes?|references?|bibliography|selected bibliography|list of searchable terms|illustration credits|image credits|permissions|glossary|further reading|resources)\b', re.I)
PARA = re.compile(r'^(.*?)\s\^([a-z0-9]+-\d{3,})\s*$', re.M)

def load(name, argv):
    sys.argv = ['x'] + argv
    sp = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + '.py'))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m

def manifest(slug): return json.load(open(f'{ROOT}/books/{slug}/02-text/manifest.json'))
def doc_paras(slug, d):
    fs = glob.glob(f"{ROOT}/books/{slug}/02-text/chapters/{d['id']}-*.md")
    return [(m.group(2), m.group(1).strip()) for m in PARA.finditer(open(fs[0]).read()) if len(m.group(1).strip()) >= 40] if fs else None
def sha(p):
    h = hashlib.sha256(); h.update(open(p, 'rb').read()); return h.hexdigest()
def words(s): return re.findall(r"[\w']+", s.lower())
def malformed(c): return len(c) <= 25 or c.rstrip()[-1] not in '.!?"\u201d\u2019)'
def verbatim(claim, paras):
    w = words(claim)
    return any(' '.join(w[i:i + 13]) in ' '.join(words(p)) for p in paras for i in range(max(0, len(w) - 12)))
def api_embed(texts):
    import build_embeddings as be  # loaded in main
    out = []
    for i in range(0, len(texts), 64):
        e, _ = be.post([t[:2000] for t in texts[i:i + 64]]); out += e
    a = np.array(out, dtype=np.float32); return a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)


VERIFY_SOURCE = False
def verify_source(y):
    """Check the linked source still exists at the source host and matches source_sha256. Returns a warning or None."""
    host, base = os.environ.get('LIBRARY_SOURCE_SSH'), os.environ.get('LIBRARY_SOURCE_PATH')
    if not (host and base): return 'source not verified: LIBRARY_SOURCE_SSH/LIBRARY_SOURCE_PATH not set'
    cid = (y.get('calibre') or {}).get('id')
    cmd = f"d=$(find {base!r} -maxdepth 2 -type d -name '*({cid})' | head -1); [ -n \"$d\" ] && f=$(ls \"$d\"/*.epub 2>/dev/null | head -1) && [ -n \"$f\" ] && sha256sum \"$f\" | cut -d' ' -f1"
    try:
        key = os.environ.get('LIBRARY_SOURCE_SSH_KEY'); r = subprocess.run(['ssh', *(['-i', key] if key else []), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host, cmd], capture_output=True, text=True, timeout=60)
    except Exception as e: return f'source not verified: {type(e).__name__}'
    h = r.stdout.strip()
    if r.returncode != 0 and not h: return f'source link dead: no EPUB for calibre id {cid} at library host'
    return None if h == y.get('source_sha256') else 'source changed: library EPUB hash differs from book.yaml'

# ---- 1 metadata
def s_metadata(slug, ctx):
    y = yaml.safe_load(open(f'{ROOT}/books/{slug}/book.yaml')); ev, bad, warn = {}, [], []
    for k in ('title', 'author', 'language', 'source_sha256'):
        if not y.get(k): bad.append('missing ' + k)
    if y.get('content_type') not in ('nonfiction', 'fiction'): bad.append(f"content_type={y.get('content_type')!r}, expected nonfiction or fiction")
    if y.get('duplicate_of'): bad.append('duplicate_of ' + str(y['duplicate_of']))
    if not os.path.exists(f'{ROOT}/books/{slug}/cover.jpg'): warn.append('no cover.jpg')
    cal = y.get('calibre') or {}
    if not cal.get('id'): warn.append('no calibre id')
    if not cal.get('isbn'): warn.append('no isbn')
    src = f"{ROOT}/books/{slug}/{y.get('source', '')}"
    if os.path.exists(src):
        if sha(src) != y.get('source_sha256'): bad.append('source file hash differs from book.yaml')
    elif not y.get('source_url'): warn.append('no source_url: source is not linked, locate it')
    elif VERIFY_SOURCE:
        w = verify_source(y)
        if w: warn.append(w)
    ev['source_url'] = y.get('source_url')
    ctx['lang'] = y.get('language'); ev.update(title=y.get('title'), language=y.get('language'))
    return ('FAIL' if bad else 'WARN' if warn else 'PASS'), bad + warn, ev

# ---- 2 text
def text_profile(slug):
    m = manifest(slug); ch, other = [], []
    for d in m['documents']:
        ps = doc_paras(slug, d)
        row = dict(id=d['id'], title=d['title'], kind=d['kind'], n=len(ps) if ps is not None else None, words=sum(len(words(p)) for _, p in ps or []))
        (ch if d['kind'] == 'chapter' else other).append(row)
    return ch, other

def s_text(slug, ctx):
    t = json.load(open(f'{ROOT}/books/{slug}/05-verify/text.json')); notes = []
    if not t.get('ok'): return 'FAIL', ['text gate (05-verify/text.json) not ok'], {}
    for attempt in (0, 1):
        ch, other = text_profile(slug)
        body = sum(r['n'] or 0 for r in ch); tot = body + sum(r['n'] or 0 for r in other if not BACK.search(r['title']))
        cov = body / tot if tot else 0
        big = [r for r in other if (r['n'] or 0) >= 40 and not FRONT.search(r['title']) and not BACK.search(r['title'])]
        if (len(ch) < T['min_chapters'] or cov < T['body_coverage'] or big) and attempt == 0 and not ctx['check_only'] and ctx.get('repair_text'):
            ctx['repaired'] = True
            subprocess.run([sys.executable, '-I', f'{HERE}/fix_chapters.py', slug], check=False, env=os.environ, cwd=ROOT)
            continue
        break
    ev = dict(chapters=len(ch), body_paras=body, total_paras=tot, body_coverage=round(cov, 3), repaired=ctx.get('repaired', False))
    bad = []
    if not ch: bad.append('0 chapters')
    if any(r['n'] is None for r in ch): bad.append('chapter file missing for ' + ','.join(r['id'] for r in ch if r['n'] is None))
    if cov < T['body_coverage']: bad.append(f'only {cov:.0%} of paragraphs sit in chapters')
    if len(ch) < T['min_chapters']: notes.append(f'only {len(ch)} chapters')
    if big: notes.append('large untagged docs: ' + ', '.join(r['title'][:25] for r in big))
    ctx['chapters'] = ch
    return ('FAIL' if bad else 'WARN' if notes else 'PASS'), bad + notes, ev

# ---- 3 embeddings
def book_rows(slug, chapters_only=False):
    return [(d['id'], pid) for d in manifest(slug)['documents'] if not chapters_only or d['kind'] == 'chapter'
            for pid, _ in (doc_paras(slug, d) or [])]
def s_embeddings(slug, ctx):
    f, rows, need = f'{EMB}/{slug}.npz', book_rows(slug), book_rows(slug, True)
    def ok():
        if not os.path.exists(f): return 'missing'
        z = np.load(f); v = z['vec'].astype(np.float32); have = list(zip(z['chapter'].tolist(), z['para'].tolist()))
        if len(have) != len(v): return 'vector count differs from index'
        if set(have) - set(rows): return f'{len(set(have) - set(rows))} embedded paragraphs no longer in the text'
        if set(need) - set(have): return f'{len(set(need) - set(have))} chapter paragraphs not embedded'
        if len(set(have)) != len(have): return 'duplicate rows'
        if not np.isfinite(v).all() or abs(np.linalg.norm(v, axis=1) - 1).max() > 0.02: return 'non-finite or not unit length'
        return ''
    why = ok(); built = False
    if why and not ctx['check_only']:
        if os.path.exists(f): os.replace(f, f + '.stale')
        ctx['be'].do_book(slug); built = True; why = ok()
        if not why and os.path.exists(f + '.stale'): os.remove(f + '.stale')
    return ('FAIL' if why else 'PASS'), ([why] if why else []), dict(paragraphs=len(rows), chapter_paragraphs=len(need), built=built,
        model=ctx['be'].MODEL, bytes=os.path.getsize(f) if os.path.exists(f) else 0)

# ---- 4 atoms
def pick_trial(ch):
    c = sorted([r for r in ch if (r['n'] or 0) >= 10], key=lambda r: r['n']) \
        or sorted([r for r in ch if (r['n'] or 0) >= 3], key=lambda r: r['n'])  # short books: smaller chapters
    ids = []
    for i in (len(c) // 2, len(c) * 3 // 4, len(c) // 4):
        if c and c[min(i, len(c) - 1)]['id'] not in ids: ids.append(c[min(i, len(c) - 1)]['id'])
    return ids
def read_atoms(slug):
    f = f'{ATOMS}/{slug}.jsonl'
    return [json.loads(l) for l in open(f)] if os.path.exists(f) else []
def validate_atoms(slug, ch):
    atoms, bad, warn = read_atoms(slug), [], []
    if not atoms: return 'FAIL', ['no atoms'], {}
    byc = collections.Counter(a['chapter'] for a in atoms)
    subst = [r for r in ch if (r['n'] or 0) >= 8]; miss = [r['id'] for r in subst if not byc[r['id']]]
    covr = 1 - len(miss) / len(subst) if subst else 1
    wds = sum(r['words'] for r in ch); dens = len(atoms) / (wds / 1000) if wds else 0
    norm = collections.Counter(re.sub(r'\W+', ' ', a['claim'].lower()).strip() for a in atoms)
    dup = sum(v - 1 for v in norm.values()) / len(atoms)
    pm = {d['id']: dict(doc_paras(slug, d) or []) for d in manifest(slug)['documents']}
    unresolved = sum(1 for a in atoms for p in a['paras'] if p not in pm.get(a['chapter'], {}))
    verb = sum(1 for a in atoms if verbatim(a['claim'], [pm.get(a['chapter'], {}).get(p, '') for p in a['paras']])) / len(atoms)
    mal = sum(malformed(a['claim']) for a in atoms) / len(atoms)
    if covr < T['chapter_atom_coverage']: bad.append(f'{len(miss)} substantive chapters have no atoms ({covr:.0%} covered)')
    if dup > T['max_dupes']: bad.append(f'{dup:.0%} duplicate claims')
    if unresolved: bad.append(f'{unresolved} citations do not resolve')
    if mal > T['max_malformed']: bad.append(f'{mal:.0%} malformed claims')
    if verb > T['max_verbatim']: warn.append(f'{verb:.0%} claims copy 13+ words')
    aud = os.path.join(os.environ.get('ATOMS_OUT', os.path.join(LIB, 'atoms')), '_audit', slug + '.json')
    if os.path.exists(aud):
        js = [x['judge'] for x in json.load(open(aud)) if x.get('judge') and x['judge'].get('verdict')]
        if js:
            keep = sum(j['verdict'] == 'keep' for j in js) / len(js); sc = sum(j['self_contained'] == 'no' for j in js) / len(js)
            anec = sum(j['kind'] in ('anecdote', 'example', 'name_drop') for j in js) / len(js); fa = sum(j['faithful'] == 'no' for j in js) / len(js)
            if fa > T['audit_max_unfaithful']: bad.append(f'audit: {fa:.0%} sampled atoms not supported by their paragraphs')
            if keep < T['audit_min_keep']: warn.append(f'audit: only {keep:.0%} of sampled atoms are keepers')
            if sc > T['audit_max_not_standalone']: warn.append(f'audit: {sc:.0%} sampled atoms not self-contained')
            if anec > T['audit_max_anecdote']: warn.append(f'audit: {anec:.0%} sampled atoms are anecdotes or examples')
    return ('FAIL' if bad else 'WARN' if warn else 'PASS'), bad + warn, dict(atoms=len(atoms), chapters_without_atoms=miss,
        coverage=round(covr, 3), atoms_per_1k_words=round(dens, 2), dupes=round(dup, 3), malformed=round(mal, 3), verbatim=round(verb, 3))

def atoms_none(slug):
    return str((yaml.safe_load(open(f'{ROOT}/books/{slug}/book.yaml')) or {}).get('atoms')) == 'none' or (yaml.safe_load(open(f'{ROOT}/books/{slug}/book.yaml')) or {}).get('content_type') == 'fiction'

def s_atoms(slug, ctx):
    if atoms_none(slug): return 'N/A', ['atoms: none in book.yaml (embeddings only)'], {}
    ch, ea, cost = ctx['chapters'], ctx['ea'], 0.0
    prev = f'{ATOMS}/{slug}.jsonl'
    def fill(cost):
        for _ in range(2):  # fill chapters the model or API missed
            have = {a['chapter'] for a in read_atoms(slug)}
            todo = [r_ for r_ in ch if (r_['n'] or 0) >= 8 and r_['id'] not in have]
            if not todo: break
            with open(prev, 'a') as fh:
                for r_ in todo:
                    d = next(d for d in manifest(slug)['documents'] if d['id'] == r_['id'])
                    try: _, _, k, _, c, _ = ea.job((slug, d)); cost += c
                    except Exception: continue
                    for a in k: fh.write(json.dumps(a, ensure_ascii=False) + '\n')
        return cost
    if read_atoms(slug) and not ctx['redo']:
        st, notes, ev = validate_atoms(slug, ch)
        if st == 'FAIL' and not ctx['check_only'] and ev.get('chapters_without_atoms'):
            cost = fill(0.0); st, notes, ev = validate_atoms(slug, ch); ev['fill_cost'] = round(cost, 4); notes = ['gap-filled missing chapters'] + notes
        if st != 'FAIL' or ctx['check_only']: return st, ['existing atoms kept'] + notes, ev
        return st, ['existing atoms kept; gaps not the cause, use --redo-atoms'] + notes, ev
    if ctx['check_only']: return 'FAIL', ['no atoms (check-only)'], {}
    kept = drop = mal = paras = 0; per = []
    for cid in pick_trial(ch):
        d = next(d for d in manifest(slug)['documents'] if d['id'] == cid)
        _, _, k, dr, c, _ = ea.job((slug, d)); cost += c; kept += len(k); drop += dr; mal += sum(malformed(a['claim']) for a in k)
        n = next(r['n'] for r in ch if r['id'] == cid); paras += n; per.append(f'{cid}:{n}p->{len(k)}a/{dr}d')
    tot = kept + drop; why = []
    if kept < max(3, T['trial_min_atoms_per_para'] * paras): why.append(f'trial gave {kept} atoms for {paras} paragraphs')
    ov = (yaml.safe_load(open(f'{ROOT}/books/{slug}/book.yaml')) or {}).get('gate_override') or {}
    lim = ov.get('trial_max_drop', T['trial_max_drop']) if ov.get('reason') else T['trial_max_drop']
    if paras < 40 and not ov.get('reason'): lim = max(lim, 0.30)  # small trial samples are noisy
    if tot >= 10 and drop / tot >= lim: why.append(f'trial citation drops {drop}/{tot}')
    if kept and mal / kept > T['max_malformed']: why.append(f'trial malformed claims {mal}/{kept}')
    trial = dict(chapters=per, cost=round(cost, 4))
    if why: return 'FAIL', ['trial failed: ' + '; '.join(why)], trial
    if os.path.exists(prev):
        os.makedirs(f'{ATOMS}/_prev', exist_ok=True)
        shutil.copy(prev, f"{ATOMS}/_prev/{slug}.{datetime.datetime.now():%Y%m%dT%H%M%S}.jsonl"); os.remove(prev)
    r = subprocess.run([sys.executable, '-I', f'{HERE}/extract_atoms.py', slug], capture_output=True, text=True, cwd=ROOT, env=os.environ)
    mm = re.search(r'cost ([\d.]+)', r.stdout); cost += float(mm.group(1)) if mm else 0
    cost = fill(cost)
    st, notes, ev = validate_atoms(slug, ch); ev.update(trial=trial, cost=round(cost, 4), tier=os.environ.get('ATOM_TIER', 'flash'), model=ea.MODEL)
    return st, notes, ev

# ---- 5 retrieval
def s_retrieval(slug, ctx):
    atoms = read_atoms(slug)
    if not atoms: return 'FAIL', ['no atoms to test'], {}
    rng = np.random.default_rng(7); pick = [atoms[i] for i in rng.choice(len(atoms), min(30, len(atoms)), replace=False)]
    Q = api_embed([a['claim'] for a in pick]); z = np.load(f'{EMB}/{slug}.npz')
    idx = {(c, p): i for i, (c, p) in enumerate(zip(z['chapter'].tolist(), z['para'].tolist()))}
    own = Q @ z['vec'].astype(np.float32).T
    b5 = l10 = 0
    others = [np.load(f)['vec'].astype(np.float32) for f in sorted(glob.glob(EMB + '/*.npz')) if os.path.basename(f) != slug + '.npz']
    for qi, a in enumerate(pick):
        rows = [idx[(a['chapter'], p)] for p in a['paras'] if (a['chapter'], p) in idx]
        if not rows: continue
        best = max(rows, key=lambda r: own[qi, r]); sc = own[qi, best]; rb = int((own[qi] > sc).sum())
        rl = rb + sum(int((v @ Q[qi] > sc).sum()) for v in others)
        b5 += rb < 5; l10 += rl < 10
    n = len(pick); ev = dict(sampled=n, own_book_top5=round(b5 / n, 2), library_top10=round(l10 / n, 2))
    bad = []
    if b5 / n < T['retr_book_top5']: bad.append(f"own-book top5 {ev['own_book_top5']}")
    if l10 / n < T['retr_lib_top10']: bad.append(f"library top10 {ev['library_top10']}")
    return ('FAIL' if bad else 'PASS'), bad, ev

# ---- 6 links
def atom_vecs(slug):
    f, atoms = f'{ATOMS}/vectors/{slug}.npz', read_atoms(slug)
    os.makedirs(f'{ATOMS}/vectors', exist_ok=True)
    if os.path.exists(f) and len(np.load(f)['vec']) == len(atoms): return np.load(f)['vec'].astype(np.float32), atoms
    v = api_embed([a['claim'] for a in atoms]) if atoms else np.zeros((0, 1024), np.float32)
    np.savez_compressed(f, vec=v.astype(np.float16)); return v, atoms
def s_links(slug, ctx):
    A, atoms = atom_vecs(slug); cand = []
    for f in sorted(glob.glob(ATOMS + '/*.jsonl')):
        o = os.path.basename(f)[:-6]
        if o == slug: continue
        B, oa = atom_vecs(o)
        if not len(B): continue
        S = A @ B.T; j = S.argmax(1)
        cand += [(float(S[i, j[i]]), i, o, int(j[i]), oa) for i in range(len(A)) if S[i, j[i]] >= T['link_threshold']]
    cand.sort(key=lambda c: -c[0]); used, per, links = set(), collections.Counter(), []
    for s, i, o, j, oa in cand:
        if i in used or per[o] >= T['link_per_book'] or len(links) >= T['link_max']: continue
        used.add(i); per[o] += 1; b = oa[j]
        links.append(dict(score=round(s, 3), a=f"{slug}#{atoms[i]['paras'][0]}", b=f"{o}#{b['paras'][0]}", claim_a=atoms[i]['claim'], claim_b=b['claim']))
    os.makedirs(f'{ATOMS}/links', exist_ok=True)
    json.dump(links, open(f'{ATOMS}/links/{slug}.json', 'w'), indent=1, ensure_ascii=False)
    return ('PASS' if links else 'WARN'), ([] if links else ['no cross-book links above threshold']), dict(links=len(links), candidates=len(cand), books=dict(per))

# ---- 7 publish
def rc(*a): return subprocess.run(['rclone', *a], capture_output=True, text=True)
def s_publish(slug, ctx):
    if not DROP: return 'N/A', ['LIBRARY_PUBLISH_REMOTE not set'], {}
    ev, bad = {}, []
    for local, remote in ((f'{EMB}/{slug}.npz', 'embeddings'), (f'{ATOMS}/{slug}.jsonl', 'atoms'), (f'{ATOMS}/links/{slug}.json', 'atoms/links')):
        if not os.path.exists(local): continue
        r = rc('copyto', local, f'{DROP}/{remote}/{os.path.basename(local)}')
        j = rc('lsjson', f'{DROP}/{remote}/{os.path.basename(local)}')
        size = json.loads(j.stdout)[0]['Size'] if j.returncode == 0 and j.stdout.strip() != '[]' else -1
        ev[remote] = size
        if r.returncode or size != os.path.getsize(local): bad.append(f'{remote}: upload not verified')
    if not bad:
        m = json.loads(rc('cat', f'{DROP}/embeddings/manifest.json').stdout)
        y = yaml.safe_load(open(f'{ROOT}/books/{slug}/book.yaml'))
        m['books'][slug] = dict(bytes=os.path.getsize(f'{EMB}/{slug}.npz'), source_sha256=y['source_sha256'], sha256=sha(f'{EMB}/{slug}.npz'), paragraphs=len(book_rows(slug)), atoms=len(read_atoms(slug)))
        open(f'{ctx["tmp"]}/manifest.json', 'w').write(json.dumps(m, indent=1))
        if rc('copyto', f'{ctx["tmp"]}/manifest.json', f'{DROP}/embeddings/manifest.json').returncode: bad.append('manifest update failed')
    return ('FAIL' if bad else 'PASS'), bad, ev

STAGES = [(1, 'metadata', s_metadata), (2, 'text', s_text), (3, 'embeddings', s_embeddings), (4, 'atoms', s_atoms),
          (5, 'retrieval', s_retrieval), (6, 'links', s_links), (7, 'file storage', s_publish)]

def run(slug, a, mods):
    ctx = dict(check_only=a.check_only, redo=a.redo_atoms, repair_text=a.repair_text, ea=mods['ea'], be=mods['be'], tmp=os.environ.get('TMPDIR', '/tmp'))
    want = {int(x) for x in a.stages.split(',')} if a.stages else {1, 2, 3, 4, 5, 6, 7}
    if a.no_publish or a.check_only: want.discard(7)
    rep = dict(slug=slug, date=datetime.date.today().isoformat(), tier=os.environ.get('ATOM_TIER', 'flash'), stages={}); verdict = 'PASS'
    for n, name, fn in STAGES:
        if n not in want: continue
        if n >= 4 and 'chapters' not in ctx: ctx['chapters'] = text_profile(slug)[0]
        if n in (5, 6) and atoms_none(slug): st, notes, ev = 'N/A', ['no atoms'], {}
        elif n == 7 and atoms_none(slug): st, notes, ev = 'N/A', ['publish handled with embeddings only'], {}
        else:
          try: st, notes, ev = fn(slug, ctx)
          except Exception as e: st, notes, ev = 'FAIL', [f'error {e!r}'[:200]], {}
        rep['stages'][name] = dict(status=st, notes=notes, evidence=ev); print(f'  {n} {name:10} {st:5} {"; ".join(notes)[:160]}', flush=True)
        if st == 'FAIL': verdict = 'FAIL'; break
        if st == 'WARN' and verdict == 'PASS': verdict = 'WARN'
    rep['verdict'] = verdict
    if not a.check_only:
        json.dump(rep, open(f'{ROOT}/books/{slug}/05-verify/import-gate.json', 'w'), indent=1, ensure_ascii=False)
    return rep

def main():
    global VERIFY_SOURCE
    ap = argparse.ArgumentParser(); ap.add_argument('slugs', nargs='+')
    ap.add_argument('--check-only', action='store_true'); ap.add_argument('--redo-atoms', action='store_true'); ap.add_argument('--repair-text', action='store_true')
    ap.add_argument('--no-publish', action='store_true'); ap.add_argument('--verify-source', action='store_true'); ap.add_argument('--stages', default='')
    a = ap.parse_args(); VERIFY_SOURCE = a.verify_source; keep = sys.argv
    sys.path.insert(0, HERE)
    be = load('build_embeddings', []); ea = load('extract_atoms', ['x']); sys.modules['build_embeddings'] = be; sys.argv = keep
    res = {}
    for s in a.slugs:
        print(s, flush=True); res[s] = run(s, a, dict(be=be, ea=ea))['verdict']
    print('GATE SUMMARY'); [print(' ', k[:48], v) for k, v in res.items()]
    sys.exit(1 if 'FAIL' in res.values() else 0)

if __name__ == '__main__':
    main()
