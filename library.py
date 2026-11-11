#!/usr/bin/env python3
"""library-for-agents: one command for the whole flow.

  python library.py doctor                         check Python, packages, git, API key, models
  python library.py new DEST [--books DIR] [--no-git]
                                                   create your private library (a private Git repo by default)
  python library.py estimate [EPUB|DIR ...] [--level 1|2|3]
                                                   words, cost and disk size per book and level; spends nothing
  python library.py add [EPUB|DIR ...] [--level 1|2|3] [--yes] [--no-audit] [--no-commit] [--type nonfiction|fiction]
                                                   process books (default: everything in inbox/), gate them, commit
  python library.py status                         what is in the library, at which level, gate verdicts
  python library.py search "question" [-k 8] [--text]
                                                   semantic search when embeddings exist, else free keyword search

Levels (see README.md):
  1  Text        Markdown with paragraph IDs, keyword search.          free, local
  2  Meaning     + paragraph embeddings, semantic search.              ~$0.003 per 100k words
  3  Ideas       + atoms (one idea each, cited), audit, cross-book links  ~$0.15 to $0.90 per 100k words

Run `add` from inside the library folder, or pass --lib. Settings come from the shell, then
<library>/.library.env, then <library>/.env (gitignored; the place for OPENROUTER_API_KEY). Keys are never printed.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, 'ingest'))
PY = sys.executable

DEFAULT_MODELS = {
    'LIBRARY_EMBED_MODEL': 'voyageai/voyage-4-lite',
    'LIBRARY_ATOM_MODEL': 'deepseek/deepseek-v4.1-flash',
    'LIBRARY_JUDGE_MODEL': 'anthropic/claude-sonnet-5.5',
}
# USD per 100k words of book text. Embeddings: list price x ~135k tokens. Atoms: measured on real non-fiction
# books (full extraction incl. retries); expect +-50% per book. See docs/MODELS.md. Prices: OpenRouter, Nov 2026.
EMBED_RATE = {'voyageai/voyage-4-lite': 0.003, 'mongodb/voyage-4-lite': 0.003, 'voyageai/voyage-4': 0.008,
              'qwen/qwen3-embedding-8b': 0.0014, 'openai/text-embedding-3-small': 0.003, 'openai/text-embedding-3-large': 0.018}
ATOM_RATE = {'deepseek/deepseek-v4.1-flash': 0.16, 'anthropic/claude-sonnet-5.5': 0.89}   # measured; others unknown
AUDIT_COST = {'anthropic/claude-sonnet-5.5': 0.06}     # per book: 24 sampled atoms judged
EMBED_MB_PER_100K = 3.3                                  # float16, 1024 dims
TEXT_MB_PER_100K = 2.0                                   # 02-text + 04-assemble + chunks
LEVEL_NAME = {1: 'Text', 2: 'Meaning', 3: 'Ideas'}


# ------------------------------------------------------------------ helpers
def say(*a): print(*a, flush=True)

def load_env_file(p):
    if not os.path.exists(p): return
    for ln in open(p):
        m = re.match(r'\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$', ln)
        if m and m.group(1) not in os.environ:
            os.environ[m.group(1)] = os.path.expandvars(m.group(2).strip('"\''))

def find_root(given=None):
    if given: return os.path.abspath(os.path.expanduser(given))
    if os.environ.get('LIBRARY_ROOT'): return os.environ['LIBRARY_ROOT']
    p = os.path.abspath(os.getcwd())
    while p != '/':
        if os.path.exists(os.path.join(p, '.library.env')) or os.path.isdir(os.path.join(p, 'books')): return p
        p = os.path.dirname(p)
    sys.exit('No library found here. cd into your library folder, pass --lib PATH, or create one: python library.py new PATH')

def setup_env(root):
    load_env_file(os.path.join(root, '.library.env')); load_env_file(os.path.join(root, '.env'))
    os.environ['LIBRARY_ROOT'] = root
    os.environ.setdefault('LIBRARY_INDEX', os.path.join(root, 'index'))
    for k, v in DEFAULT_MODELS.items(): os.environ.setdefault(k, v)

def models():
    return {k: os.environ.get(k, v) for k, v in DEFAULT_MODELS.items()}

def run(args, root, quiet=False):
    r = subprocess.run([PY, '-I', *args], cwd=root, env=os.environ, capture_output=True, text=True)
    if not quiet or r.returncode:
        out = (r.stdout + r.stderr).strip()
        if out: say('    ' + out.replace('\n', '\n    ')[-3000:])
    return r

def expand(paths, root=None):
    out = []
    for p in paths or ([os.path.join(root, 'inbox')] if root else []):
        p = os.path.expanduser(p)
        out += sorted(glob.glob(os.path.join(p, '**', '*.epub'), recursive=True)) if os.path.isdir(p) else [p]
    return [f for f in out if f.lower().endswith('.epub')]

def epub_info(path):
    from epubtools import Epub, parse_html, source_text
    e = Epub(path)
    words = sum(len(source_text(parse_html(e.text(f))).split()) for f in e.spine)
    first = lambda k, d='': (e.meta.get(k) or [d])[0]
    return dict(words=words, title=first('title', os.path.basename(path)[:-5]), author=first('creator'),
                language=first('language', 'en'), mb=os.path.getsize(path) / 1e6)

def slug_for(title):
    from parse_epub import slugify
    return slugify(title, 60)

def level_cost(words, level, m, audit=True):
    k = words / 1e5
    e = EMBED_RATE.get(m['LIBRARY_EMBED_MODEL']); a = ATOM_RATE.get(m['LIBRARY_ATOM_MODEL'])
    if level == 1: return 0.0
    if e is None: return None
    if level == 2: return e * k
    if a is None: return None
    return e * k * 1.05 + a * k + (AUDIT_COST.get(m['LIBRARY_JUDGE_MODEL'], 0.10) if audit else 0)

def money(x): return 'unknown' if x is None else ('free' if x == 0 else f'${x:,.2f}' if x >= 0.01 else '<$0.01')


# ------------------------------------------------------------------ commands
def cmd_doctor(a):
    ok = True
    say(f'python      {sys.version.split()[0]}' + ('' if sys.version_info >= (3, 10) else '  (need 3.10+)'))
    for mod in ('yaml', 'bs4', 'numpy'):
        try: __import__(mod); say(f'package     {mod:8} ok')
        except ImportError: ok = False; say(f'package     {mod:8} MISSING  -> pip install -r requirements.txt')
    say('git         ' + ('ok' if shutil.which('git') else 'missing (needed for the default private-repo library)'))
    lfs = shutil.which('git-lfs') and subprocess.run(['git', 'lfs', 'version'], capture_output=True).returncode == 0
    say('git lfs     ' + ('ok' if lfs else 'not installed (only needed for large libraries, see docs/WHERE-THINGS-LIVE.md)'))
    try:
        root = find_root(a.lib); setup_env(root); say(f'library     {root}')
    except SystemExit:
        root = None; [os.environ.setdefault(k, v) for k, v in DEFAULT_MODELS.items()]; say('library     none found here (fine before `new`)')
    say('api key     ' + ('set (not shown)' if os.environ.get('OPENROUTER_API_KEY') else 'not set: needed for levels 2 and 3, not for level 1'))
    for k, v in models().items(): say(f'{k:20} {v}' + ('' if v == DEFAULT_MODELS[k] else '  (custom)'))
    say('\nready' if ok else '\nfix the MISSING items above'); return 0 if ok else 1

def cmd_new(a):
    args = [os.path.join(REPO, 'scripts', 'setup_library.py'), a.dest] + (['--books', a.books] if a.books else []) + (['--no-git'] if a.no_git else [])
    return subprocess.run([PY, *args]).returncode

def cmd_estimate(a):
    root = None
    if not a.paths:
        root = find_root(a.lib); setup_env(root)
    else:
        for k, v in DEFAULT_MODELS.items(): os.environ.setdefault(k, v)
    m = models(); files = expand(a.paths, root)
    if not files: sys.exit('no EPUB files found')
    tot = {1: 0.0, 2: 0.0, 3: 0.0}; words = mb = 0
    say(f"{'book':44} {'words':>8}   L1 Text   L2 Meaning   L3 Ideas")
    for f in files:
        i = epub_info(f); words += i['words']; mb += i['mb']
        c = {l: level_cost(i['words'], l, m, not a.no_audit) for l in (1, 2, 3)}
        for l in c: tot[l] = None if tot[l] is None or c[l] is None else tot[l] + c[l]
        say(f"{i['title'][:44]:44} {i['words']:>8,}   {money(c[1]):>7}   {money(c[2]):>10}   {money(c[3]):>8}")
    disk = {1: mb + words / 1e5 * TEXT_MB_PER_100K}; disk[2] = disk[1] + words / 1e5 * EMBED_MB_PER_100K; disk[3] = disk[2] + words / 1e5 * 0.3
    say(f"{'TOTAL (' + str(len(files)) + ' books)':44} {words:>8,}   {money(tot[1]):>7}   {money(tot[2]):>10}   {money(tot[3]):>8}")
    say(f"{'disk, approx.':44} {'':>8}   {disk[1]:>5.0f}MB   {disk[2]:>8.0f}MB   {disk[3]:>6.0f}MB")
    say(f"\nmodels: embeddings {m['LIBRARY_EMBED_MODEL']}, atoms {m['LIBRARY_ATOM_MODEL']}, audit {m['LIBRARY_JUDGE_MODEL']}" + ('' if a.no_audit else ''))
    if any(v is None for v in tot.values()):
        say('unknown = no measured rate for a custom model: process one book first and read its real cost (python library.py status).')
    if a.level: say(f'\nchosen level {a.level} ({LEVEL_NAME[a.level]}): about {money(tot[a.level])} in total. Estimates are approximate; actual spend is printed after each book.')
    if disk[3] > 1000: say('library will exceed ~1 GB: consider Git LFS for books/*/01-source and index/ (docs/WHERE-THINGS-LIVE.md).')
    return 0

def auto_resolve(bd, level, ctype):
    import yaml
    p = os.path.join(bd, 'book.yaml'); y = yaml.safe_load(open(p)); notes = []
    docs = y['documents']; seen_ch = False
    nums = {k: max([int(d['id'][2:]) for d in docs if str(d.get('id', '')).startswith(k)] or [0]) for k in ('fm', 'bm')}
    for d in docs:
        if d['kind'] == 'chapter': seen_ch = True
        if d['kind'] != 'review': continue
        if d['words'] < 150:
            d.update(kind='exclude', reason=f"auto: short page outside the table of contents ({d['words']} words)")
        else:
            k = 'bm' if seen_ch else 'fm'; nums[k] += 1
            d.update(kind='back' if seen_ch else 'front', id=f'{k}{nums[k]:02d}', reason='auto: kept, page outside the table of contents')
        notes.append(f"{d['file']} -> {d['kind']}")
    y['content_type'] = y.get('content_type') or ctype
    y['level'] = max(int(y.get('level') or 0), level)
    if y['level'] < 3 or y['content_type'] == 'fiction': y['atoms'] = 'none'
    else: y.pop('atoms', None)
    yaml.safe_dump(y, open(p, 'w'), sort_keys=False, allow_unicode=True, width=100)
    return notes

def set_level(bd, level, ctype):
    import yaml
    p = os.path.join(bd, 'book.yaml'); y = yaml.safe_load(open(p))
    y['level'] = max(int(y.get('level') or 1), level); y['content_type'] = y.get('content_type') or ctype
    if y['level'] < 3 or y['content_type'] == 'fiction': y['atoms'] = 'none'
    elif str(y.get('atoms')) == 'none' and level == 3: y.pop('atoms', None)
    yaml.safe_dump(y, open(p, 'w'), sort_keys=False, allow_unicode=True, width=100)
    return y['level'], y.get('atoms') == 'none'

def record_spend(bd, usd):
    import yaml
    p = os.path.join(bd, 'book.yaml'); y = yaml.safe_load(open(p))
    y['spend_usd'] = round(float(y.get('spend_usd') or 0) + usd, 4)
    yaml.safe_dump(y, open(p, 'w'), sort_keys=False, allow_unicode=True, width=100)

def gate(slug, stages, root, publish=False):
    args = [os.path.join(REPO, 'tools', 'book_gate.py'), slug, '--stages', stages, '--repair-text'] + ([] if publish else ['--no-publish'])
    r = run(args, root, quiet=True)
    p = os.path.join(root, 'books', slug, '05-verify', 'import-gate.json')
    return json.load(open(p)) if os.path.exists(p) else {'verdict': 'FAIL'}

def cmd_add(a):
    root = find_root(a.lib); setup_env(root); m = models()
    files = expand(a.paths, root)
    if not files: sys.exit(f'no EPUB files found. Put your EPUBs in {root}/inbox/ or pass paths.')
    if a.level >= 2 and not os.environ.get('OPENROUTER_API_KEY'):
        sys.exit('Level 2 and 3 need OPENROUTER_API_KEY. Put it in <library>/.env (gitignored) or your shell; it is never printed.')
    est = 0.0; words = 0
    for f in files:
        w = epub_info(f)['words']; words += w; c = level_cost(w, a.level, m, not a.no_audit); est = None if est is None or c is None else est + c
    say(f'{len(files)} book(s), {words:,} words, level {a.level} ({LEVEL_NAME[a.level]}), estimated cost {money(est)}')
    if a.level >= 2 and not a.yes:
        if not sys.stdin.isatty(): sys.exit('This spends money. Re-run with --yes after the owner approved the estimate above.')
        if input('Proceed? [y/N] ').strip().lower() not in ('y', 'yes'): sys.exit('cancelled, nothing spent')
    from parse_epub import slugify  # noqa
    summary = []
    for f in files:
        i = epub_info(f); slug = slug_for(i['title']); bd = os.path.join(root, 'books', slug)
        say(f"\n== {i['title'][:70]}  ->  books/{slug}")
        if not os.path.exists(os.path.join(bd, '02-text', 'manifest.json')) or a.rebuild:
            if not os.path.exists(os.path.join(bd, 'book.yaml')) or a.rebuild:
                if run([os.path.join(REPO, 'ingest', 'parse_epub.py'), 'init', f, bd], root, quiet=True).returncode: summary.append((slug, 'FAIL init')); continue
                for n in auto_resolve(bd, a.level, a.type): say('  auto: ' + n)
            say('  level 1: text layer')
            if run([os.path.join(REPO, 'ingest', 'parse_epub.py'), 'build', bd], root, quiet=True).returncode: summary.append((slug, 'FAIL build')); continue
            if run([os.path.join(REPO, 'ingest', 'verify_text.py'), bd, '--report', '05-verify/text.json'], root, quiet=True).returncode:
                summary.append((slug, 'FAIL text verification (see 05-verify/text.json)')); continue
            run([os.path.join(REPO, 'ingest', 'assemble.py'), bd], root, quiet=True)
        else:
            say('  level 1: already done')
        lvl, no_atoms = set_level(bd, a.level, a.type)
        verdict, cost = 'PASS (text verified)', 0.0
        if lvl >= 2:
            say('  level 2: embeddings + gate'); g = gate(slug, '1,2,3', root); verdict = g['verdict']
        if lvl >= 3 and not no_atoms and verdict != 'FAIL':
            say('  level 3: atoms'); g = gate(slug, '1,2,3,4', root); verdict = g['verdict']
            cost += (g['stages'].get('atoms', {}).get('evidence', {}) or {}).get('cost') or 0
            if verdict != 'FAIL' and not a.no_audit:
                say('  level 3: audit sample'); run([os.path.join(REPO, 'tools', 'audit_atoms.py'), slug], root)
            if verdict == 'FAIL':
                record_spend(bd, cost); summary.append((slug, f'FAIL at atoms, ${cost:.2f} spent; see docs/GATE.md, nothing retried')); continue
            say('  level 3: retrieval check + cross-book links')
            g = gate(slug, '1,2,3,4,5,6' + (',7' if os.environ.get('LIBRARY_PUBLISH_REMOTE') else ''), root, publish=True); verdict = g['verdict']
        elif lvl >= 3 and no_atoms:
            say('  level 3 skipped for this book: atoms: none (fiction or set by hand). Embeddings cover it.')
        if cost: record_spend(bd, cost)
        summary.append((slug, verdict + (f', atoms ${cost:.2f}' if cost else '')))
    run([os.path.join(REPO, 'ingest', 'catalog.py'), '--root', root], root, quiet=True)
    say('\nRESULT'); [say(f'  {s[:50]:50} {v}') for s, v in summary]
    say('  WARN is normal for missing cover/ISBN or a one-book library; FAIL needs a look (docs/GATE.md).')
    if os.path.isdir(os.path.join(root, '.git')) and not a.no_commit:
        subprocess.run(['git', '-C', root, 'add', '-A'], check=False)
        r = subprocess.run(['git', '-C', root, 'commit', '-q', '-m', f'Add {len(summary)} book(s) at level {a.level}'], capture_output=True, text=True)
        say('  committed to your private library repo' if r.returncode == 0 else '  not committed: ' + (r.stderr or r.stdout).strip()[:200])
        say('  push it to your PRIVATE remote when ready: git push')
    return 1 if any('FAIL' in v for _, v in summary) else 0

def cmd_status(a):
    import yaml
    root = find_root(a.lib); setup_env(root); idx = os.environ['LIBRARY_INDEX']
    rows = sorted(glob.glob(os.path.join(root, 'books', '*', 'book.yaml')))
    if not rows: say(f'library at {root} has no books yet. Next: python library.py add'); return 0
    say(f"{'book':40} {'lvl':>3} {'words':>8} {'emb':>4} {'atoms':>6} {'cost':>6}  gate")
    tw = tc = 0
    for p in rows:
        bd = os.path.dirname(p); slug = os.path.basename(bd); y = yaml.safe_load(open(p)) or {}
        w = sum(d.get('words', 0) for d in y.get('documents', []) if d.get('kind') != 'exclude'); tw += w
        emb = 'yes' if os.path.exists(f'{idx}/embeddings/{slug}.npz') else '-'
        af = f'{idx}/atoms/{slug}.jsonl'; at = sum(1 for _ in open(af)) if os.path.exists(af) else 0
        g = os.path.join(bd, '05-verify', 'import-gate.json'); g = json.load(open(g)) if os.path.exists(g) else {}
        c = float(y.get('spend_usd') or 0); tc += c
        lvl = y.get('level') or (3 if at else 2 if emb == 'yes' else 1)
        say(f"{(y.get('title') or slug)[:40]:40} {lvl:>3} {w:>8,} {emb:>4} {at or '-':>6} {('$%.2f' % c) if c else '-':>6}  {g.get('verdict', 'text only' if y.get('status', {}).get('parsed') else 'not built')}")
    say(f'\n{len(rows)} books, {tw:,} words, recorded spend (atoms) ${tc:.2f}')
    return 0

def cmd_search(a):
    root = find_root(a.lib); setup_env(root)
    sem = glob.glob(os.path.join(os.environ['LIBRARY_INDEX'], 'embeddings', '*.npz')) and os.environ.get('OPENROUTER_API_KEY') and not a.text
    if sem: return subprocess.run([PY, '-I', os.path.join(REPO, 'tools', 'search.py'), a.query, '-k', str(a.k)], cwd=root, env=os.environ).returncode
    return subprocess.run([PY, '-I', os.path.join(REPO, 'template', 'tools', 'search.py'), a.query, '--root', root, '-n', str(a.k)], cwd=root, env=os.environ).returncode

def main():
    ap = argparse.ArgumentParser(prog='library.py', description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split('\n', 1)[1])
    sp = ap.add_subparsers(dest='cmd', required=True)
    lib = argparse.ArgumentParser(add_help=False); lib.add_argument('--lib', help='library folder (default: current folder or LIBRARY_ROOT)')
    x = sp.add_parser('doctor', parents=[lib]); x.set_defaults(f=cmd_doctor)
    x = sp.add_parser('new'); x.add_argument('dest'); x.add_argument('--books'); x.add_argument('--no-git', action='store_true'); x.set_defaults(f=cmd_new)
    x = sp.add_parser('estimate', parents=[lib]); x.add_argument('paths', nargs='*'); x.add_argument('--level', type=int, choices=(1, 2, 3)); x.add_argument('--no-audit', action='store_true'); x.set_defaults(f=cmd_estimate)
    x = sp.add_parser('add', parents=[lib]); x.add_argument('paths', nargs='*'); x.add_argument('--level', type=int, choices=(1, 2, 3), default=2)
    x.add_argument('--yes', action='store_true', help='skip the cost confirmation (only after the owner approved)')
    x.add_argument('--no-audit', action='store_true'); x.add_argument('--no-commit', action='store_true'); x.add_argument('--rebuild', action='store_true')
    x.add_argument('--type', choices=('nonfiction', 'fiction'), default='nonfiction'); x.set_defaults(f=cmd_add)
    x = sp.add_parser('status', parents=[lib]); x.set_defaults(f=cmd_status)
    x = sp.add_parser('search', parents=[lib]); x.add_argument('query'); x.add_argument('-k', type=int, default=8); x.add_argument('--text', action='store_true', help='force free keyword search'); x.set_defaults(f=cmd_search)
    a = ap.parse_args(); sys.exit(a.f(a) or 0)

if __name__ == '__main__':
    main()
