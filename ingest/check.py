#!/usr/bin/env python3
"""Run every automatic gate for one book and write 05-verify/REPORT.md. Sets status flags in book.yaml.

  check.py BOOKDIR [--no-enrich]
Gates: text equality (verify_text), rebuild reproducibility (rebuild from 01-source into a temp copy and compare 02-text
byte for byte), enrichment (verify_enrich), assemble determinism (two runs, identical tree hash).
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, datetime
import yaml
H = os.path.dirname(os.path.abspath(__file__))

def run(*a):
    p = subprocess.run([sys.executable, *a], capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()

def tree_hash(root):
    h = hashlib.sha256()
    for dp, dn, fn in sorted(os.walk(root)):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f)
            h.update(os.path.relpath(p, root).encode()); h.update(open(p, 'rb').read())
    return h.hexdigest()

def main():
    bd = os.path.abspath(sys.argv[1]); skip_enrich = '--no-enrich' in sys.argv
    cfg = yaml.safe_load(open(os.path.join(bd, 'book.yaml')))
    res = {}
    os.makedirs(os.path.join(bd, '05-verify'), exist_ok=True)
    rc, out = run(os.path.join(H, 'verify_text.py'), bd, '--report', '05-verify/text.json'); res['text equality'] = (rc == 0, out.splitlines()[0] if out else '')
    with tempfile.TemporaryDirectory() as t:
        tb = os.path.join(t, 'b'); os.makedirs(tb)
        shutil.copytree(os.path.join(bd, '01-source'), os.path.join(tb, '01-source')); shutil.copy(os.path.join(bd, 'book.yaml'), tb)
        rc2, out2 = run(os.path.join(H, 'parse_epub.py'), 'build', tb)
        same = rc2 == 0 and tree_hash(os.path.join(tb, '02-text')) == tree_hash(os.path.join(bd, '02-text'))
        res['rebuild reproduces 02-text byte for byte'] = (same, '' if same else out2[-200:])
    if not skip_enrich:
        rc, out = run(os.path.join(H, 'verify_enrich.py'), bd, '--report', '05-verify/enrich.json'); res['enrichment'] = (rc == 0, out.splitlines()[0] if out else '')
    run(os.path.join(H, 'assemble.py'), bd); h1 = tree_hash(os.path.join(bd, '04-assemble'))
    run(os.path.join(H, 'assemble.py'), bd); h2 = tree_hash(os.path.join(bd, '04-assemble'))
    res['assemble deterministic'] = (h1 == h2, h1[:12])
    ok = all(v[0] for v in res.values())
    cfg['status'] = dict(parsed=True, verified=ok and res['text equality'][0], enriched=(not skip_enrich) and res.get('enrichment', (False,))[0])
    yaml.safe_dump(cfg, open(os.path.join(bd, 'book.yaml'), 'w'), sort_keys=False, allow_unicode=True, width=100)
    man = json.load(open(os.path.join(bd, '02-text', 'manifest.json')))
    L = [f"# Verification report: {cfg['title']}", '', f"Generated {datetime.date.today()} by check.py. Do not edit.", '',
         '| Gate | Result | Detail |', '|---|---|---|']
    for k, (g, d) in res.items():
        L.append(f"| {k} | {'PASS' if g else 'FAIL'} | {d} |")
    tx = json.load(open(os.path.join(bd, '05-verify', 'text.json')))
    L += ['', f"Documents: {len(tx['docs'])}. Source characters compared: {sum(r['src_chars'] for r in tx['docs'])}.", '', '## Excluded documents', '', '| File | Words | Reason |', '|---|---|---|']
    L += [f"| {e['file']} | {e['words']} | {e['reason']} |" for e in man['excluded']]
    if os.path.exists(os.path.join(bd, '05-verify', 'enrich.json')) and not skip_enrich:
        en = json.load(open(os.path.join(bd, '05-verify', 'enrich.json')))
        L += ['', '## Enrichment warnings (tripwires, reviewed)', ''] + [f'- {w}' for w in en['warnings']]
    L += ['', '## Independent review', '', 'Record reviewer, date and outcome here by hand after stage 5 review.', '']
    old = os.path.join(bd, '05-verify', 'REPORT.md')
    keep = ''
    if os.path.exists(old):
        t = open(old).read()
        if '## Independent review' in t:
            keep = t.split('## Independent review', 1)[1].split('\n', 1)[1].strip()
    if keep and 'Record reviewer' not in keep:
        L[-2:] = [keep, '']
    open(old, 'w').write('\n'.join(L))
    for k, (g, d) in res.items(): print(('PASS ' if g else 'FAIL ') + k, d)
    sys.exit(0 if ok else 1)

main()
