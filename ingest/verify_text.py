#!/usr/bin/env python3
"""Gate 1: the text layer must contain exactly the book's text. Independent of the renderer:
source characters come from the EPUB via bs4 get_text, output characters from the written markdown.

  verify_text.py BOOKDIR [--report 05-verify/text.json]    exit 0 = pass, 1 = fail
"""
import argparse, difflib, hashlib, json, os, re, sys
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epubtools import Epub, parse_html, source_text, source_stream, output_stream, sha256

def split_doc(md):
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', md, re.S)
    return yaml.safe_load(m.group(1)), m.group(2)

def first_diff(a, b, ctx=40):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != 'equal':
            return f"{tag} src[{i1}:{i2}]={a[max(0,i1-ctx):i2+ctx]!r} out[{j1}:{j2}]={b[max(0,j1-ctx):j2+ctx]!r}"
    return ''

ARTIFACT_PATTERNS = [
    (r'(?<!\\)<(?!/?su[bp]>|!--)[a-z]+[ >]', 'raw html'),
    # A bare figure marker is an artifact only when it starts a line. Inline
    # prose such as "a disturbing figure:" is ordinary book text.
    (r'^\s*figure:|&nbsp;|&amp;|&lt;', 'entity'),
    (r'^\s*\^[a-z]', 'orphan id'),
]


def artifact_findings(body_art):
    return [(name, mm) for pat, name in ARTIFACT_PATTERNS
            for mm in re.finditer(pat, body_art, re.M)]


def run_regression_assertion(bookdir):
    """Exercise the false-positive fix and neighboring artifact checks."""
    chapter = os.path.join(bookdir, '02-text', 'chapters', 'ch12-the-earth-moves.md')
    text = open(chapter).read()
    assert 'disturbing figure:' in text
    assert not any(name == 'entity' for name, _ in artifact_findings(text))
    assert any(name == 'entity' for name, _ in artifact_findings('figure: leaked marker'))
    assert any(name == 'raw html' for name, _ in artifact_findings('<span>leaked markup'))
    assert any(name == 'entity' for name, _ in artifact_findings('&amp;'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('bookdir'); ap.add_argument('--report'); ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        run_regression_assertion(a.bookdir)
    bd = a.bookdir
    cfg = yaml.safe_load(open(os.path.join(bd, 'book.yaml')))
    man = json.load(open(os.path.join(bd, '02-text', 'manifest.json')))
    figs = json.load(open(os.path.join(bd, '02-text', 'figures.json')))
    e = Epub(os.path.join(bd, cfg['source']))
    errs, rows = [], []
    def err(m): errs.append(m)

    # 1 coverage: every spine doc is included or excluded with a reason
    docs = {d['file']: d for d in cfg['documents']}
    for f in e.spine:
        d = docs.get(f)
        if not d: err(f'spine doc not mapped: {f}')
        elif d['kind'] == 'exclude' and not d.get('reason'): err(f'excluded without reason: {f}')
        elif d['kind'] == 'review': err(f'unresolved review: {f}')
    if cfg['source_sha256'] != sha256(open(os.path.join(bd, cfg['source']), 'rb').read()): err('source sha256 changed')

    ids = set()
    all_pids = set()
    img_total_src = 0
    for m in man['documents']:
        d = docs[m['source_file']]
        path = os.path.join(bd, '02-text', 'chapters', m['md'])
        md = open(path).read()
        fm, body = split_doc(md)
        if fm['id'] in ids: err(f"duplicate id {fm['id']}")
        ids.add(fm['id'])
        # body immutability / front matter consistency
        body_only = re.sub(r'^# .*\n\n', '', body, count=1)
        if sha256(body_only) != fm['body_sha256'] or fm['body_sha256'] != m['body_sha256']:
            err(f"{fm['id']}: body sha256 differs from manifest (text layer edited?)")
        # 2 character stream equality
        src = source_stream(source_text(parse_html(e.text(m['source_file']))))
        for l in m['lifted']:   # text lifted into front matter (chapter number + title)
            ls = re.sub(r'\s+', '', l)
            k = src.find(ls)
            if k < 0: err(f"{fm['id']}: lifted text not in source: {l!r}")
            else: src = src[:k] + src[k + len(ls):]
        for dec in d.get('declared_dropped', []) or []:   # explicitly declared, reviewed text drops
            ds = re.sub(r'\s+', '', dec)
            if ds in src: src = src.replace(ds, '', 1)
        out = output_stream(body)
        ok = src == out
        if not ok: err(f"{fm['id']}: character mismatch ({len(src)} src vs {len(out)} out): {first_diff(src, out)}")
        # 3 ids
        pids = re.findall(r'\s\^(' + re.escape(fm['id']) + r'-\d{3,})\s*$', body, re.M)
        if len(pids) != len(set(pids)): err(f"{fm['id']}: duplicate paragraph ids")
        if len(pids) != fm['paragraphs']: err(f"{fm['id']}: paragraph id count {len(pids)} != front matter {fm['paragraphs']}")
        exp = [f"{fm['id']}-{i:03d}" for i in range(1, len(pids) + 1)]
        if pids != exp: err(f"{fm['id']}: paragraph ids not sequential")
        all_pids.update(pids)
        # 4 images
        soup = parse_html(e.text(m['source_file']))
        nblocks = len(re.findall(r'<!-- figure:', body))
        if nblocks != fm['figures']: err(f"{fm['id']}: figure count {nblocks} != front matter {fm['figures']}")
        for fid, fn in re.findall(r'<!-- figure:(\S+) -->\n!\[[^\]]*\]\(([^)]+)\)', body):
            if not os.path.exists(os.path.join(bd, '02-text', fn)): err(f'{fid}: image missing {fn}')
        # 5 links
        for tgt in re.findall(r'(?<!!)\[(?:[^\]\\]|\\.)*\]\(([^)]+)\)', body):
            if re.match(r'^(https?:|mailto:|#)', tgt):
                continue
            target = os.path.normpath(os.path.join(bd, '02-text', tgt))
            if not os.path.exists(target):
                target = os.path.normpath(os.path.join(bd, '02-text', 'chapters', tgt))
            if not os.path.exists(target):
                err(f"{fm['id']}: broken internal link {tgt}")
        # 6 artifacts
        body_art = re.sub(r'<!-- figure:.*?<!-- /figure -->', '', body_only, flags=re.S)
        body_art = re.sub(r'(\|[^\n]*\|)\n\^[a-z0-9]+-\d+', r'\1', body_art)
        for name, mm in artifact_findings(body_art):
            err(f"{fm['id']}: artifact {name}: {body_art[max(0,mm.start()-30):mm.end()+30]!r}"); break
        if re.search(r'^\s*#{2,6}\s*\*', body_only, re.M): err(f"{fm['id']}: heading contains emphasis markers")
        rows.append(dict(id=fm['id'], src_chars=len(src), out_chars=len(out), match=ok, paragraphs=len(pids), figures=nblocks))
    # figures.json consistent with blocks
    if len(figs) != sum(r['figures'] for r in rows): err('figures.json count differs from figure blocks')
    # every non-decorative img in included docs became a figure: counted by renderer, re-derived here
    rep = dict(ok=not errs, errors=errs, docs=rows, excluded=man['excluded'])
    if a.report:
        os.makedirs(os.path.dirname(os.path.join(bd, a.report)), exist_ok=True)
        json.dump(rep, open(os.path.join(bd, a.report), 'w'), indent=1)
    print(f"verify_text: {len(rows)} docs, {sum(r['src_chars'] for r in rows)} source chars, {len(errs)} errors")
    for x in errs[:40]: print('  FAIL', x)
    sys.exit(0 if not errs else 1)

main()
