#!/usr/bin/env python3
"""inspect / init / build for one EPUB. Deterministic: same input + same book.yaml => byte-identical output.

  parse_epub.py inspect  BOOK.epub                 show metadata, TOC, spine, CSS class table with samples
  parse_epub.py init     BOOK.epub BOOKDIR         create BOOKDIR skeleton + draft book.yaml (needs human/agent review)
  parse_epub.py build    BOOKDIR                    render 02-text from 01-source + book.yaml
"""
import argparse, collections, json, os, posixpath, re, shutil, sys
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epubtools import *

AUTO_ROLES = [  # class-name heuristics used only to draft book.yaml; a reviewer confirms them
    (r'^(h1|h1a|h2|h2a|h3|head\w*|sub\w*head)$', 'heading:2'),
    (r'^h2h$', 'heading:3'),
    (r'^(cht\d*|chap\w*title)$', 'chapter_title'),
    (r'^(box\d*|sidebar\w*|callout\w*)$', 'callout'),
    (r'^(parad\d*|pull\w*|epigraph\w*)$', 'pullquote'),
    (r'^(nnbx|bullet\w*)$', 'bullet_marker'),
    (r'^(sans|bold|strong|b)$', 'bold'),
    (r'^(ital\w*|em)$', 'italic'),
]

def slugify(s, n=40):
    s = s.lower().replace('’', '').replace("'", '')
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    if len(s) > n:
        s = s[:n].rsplit('-', 1)[0] if '-' in s[:n] else s[:n]
    return s or 'untitled'

def strip_num(t):
    return re.sub(r'^\s*(?:chapter\s+)?\d+[.:)\s]+\s*', '', t, flags=re.I).strip()

def doc_words(epub, f):
    return len(source_text(parse_html(epub.text(f))).split())

# ------------------------------------------------------------------ inspect
def cmd_inspect(a):
    e = Epub(a.epub)
    print('title:', e.meta.get('title'), '| creator:', e.meta.get('creator'), '| lang:', e.meta.get('language'))
    print('\nTOC:')
    for n, d, _ in flat_toc(e.toc):
        print('  ' * d + f"- {n['title']}  -> {n['href']}")
    print('\nSPINE (words):')
    toc_hrefs = {n['href'] for n, _, _ in flat_toc(e.toc)}
    for f in e.spine:
        print(f"  {f:40s} {doc_words(e, f):6d}  {'in TOC' if f in toc_hrefs else 'NOT IN TOC'}")
    cls = collections.defaultdict(lambda: [0, ''])
    for f in e.spine:
        for t in parse_html(e.text(f)).find_all(True):
            for c in t.get('class', []):
                k = cls[(t.name, c)]
                k[0] += 1
                if not k[1] and t.get_text().strip():
                    k[1] = ' '.join(t.get_text().split())[:60]
    print('\nCLASSES (tag.class count sample):')
    for (tg, c), (n, smp) in sorted(cls.items(), key=lambda x: -x[1][0]):
        print(f"  {tg}.{c:14s} {n:5d}  {smp}")

# ------------------------------------------------------------------ init
def cmd_init(a):
    e = Epub(a.epub)
    bd = a.bookdir
    for d in ('01-source', '02-text', '03-enrich', '04-assemble', '05-verify'):
        os.makedirs(os.path.join(bd, d), exist_ok=True)
    dst = os.path.join(bd, '01-source', os.path.basename(a.epub))
    if not os.path.exists(dst):
        shutil.copy(a.epub, dst)
    toc = {n['href']: (n, d, p) for n, d, p in flat_toc(e.toc) if n['href']}
    cls = collections.defaultdict(int)
    for f in e.spine:
        for t in parse_html(e.text(f)).find_all(True):
            for c in t.get('class', []):
                cls[c] += 1
    classmap = {}
    for c in sorted(cls):
        role = 'plain'
        for pat, r in AUTO_ROLES:
            if re.match(pat, c, re.I):
                role = r
                break
        classmap[c] = role
    docs, chn, fm, bm, seen_ch = [], 0, 0, 0, False
    parts = []
    for f in e.spine:
        w = doc_words(e, f)
        node, depth, parents = toc.get(f, (None, None, ()))
        title = node['title'] if node else ''
        stem = posixpath.basename(f)
        d = dict(file=f, words=w, toc_title=title)
        if re.search(r'^(cover|title ?page|contents|table of contents|half[- ]?title)$', title.strip(), re.I) or \
                re.search(r'^\d*_?(cover|titlepage|half|contents|toc)\b', stem, re.I):
            d.update(kind='exclude', reason='front furniture (cover/title/contents)')
        elif node and depth == 0 and node['children']:
            parts.append(title)
            d.update(kind='exclude', reason=f'part divider, part name kept in book.yaml parts ({w} words)')
        elif node and (depth >= 1 or re.match(r'^\d+[.\s]', title)):
            chn += 1
            seen_ch = True
            d.update(kind='chapter', id=f'ch{chn:02d}', part=parents[0] if parents else None)
        elif node:
            if seen_ch:
                bm += 1; d.update(kind='back', id=f'bm{bm:02d}')
            else:
                fm += 1; d.update(kind='front', id=f'fm{fm:02d}')
        else:
            d.update(kind='review', reason='not in TOC: decide include (kind front/back + id) or exclude (+ reason)')
        docs.append(d)
    cfg = dict(
        slug=slugify(e.meta.get('title', ['book'])[0] if isinstance(e.meta.get('title'), list) else 'book', 60),
        title=(e.meta.get('title') or [''])[0], author=(e.meta.get('creator') or [''])[0],
        language=(e.meta.get('language') or ['en'])[0],
        source=f'01-source/{os.path.basename(a.epub)}', source_sha256=sha256(open(a.epub, 'rb').read()),
        min_figure_px=80, decorative_images=[], parts=parts, classmap=classmap, documents=docs,
        status=dict(parsed=False, verified=False, enriched=False))
    with open(os.path.join(bd, 'book.yaml'), 'w') as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False, allow_unicode=True, width=100)
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'book-CONTEXT.template.md')
    ctx = os.path.join(bd, 'CONTEXT.md')
    if os.path.exists(tpl) and not os.path.exists(ctx):
        open(ctx, 'w').write(open(tpl).read().format(title=cfg['title'], author=cfg['author'], slug=cfg['slug']))
    todo = [d['file'] for d in docs if d['kind'] == 'review']
    print(f'wrote {bd}/book.yaml: {chn} chapters, {len(parts)} parts, {len(todo)} documents need review: {todo}')
    print('Next: review classmap (see `inspect`), resolve kind: review, set decorative_images, then run build.')

# ------------------------------------------------------------------ build
def front_matter(d):
    return '---\n' + yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=1000) + '---\n'

def cmd_build(a):
    bd = a.bookdir
    cfg = yaml.safe_load(open(os.path.join(bd, 'book.yaml')))
    e = Epub(os.path.join(bd, cfg['source']))
    if sha256(open(os.path.join(bd, cfg['source']), 'rb').read()) != cfg['source_sha256']:
        sys.exit('source sha256 mismatch: 01-source changed')
    review = [d['file'] for d in cfg['documents'] if d['kind'] == 'review']
    if review:
        sys.exit(f'unresolved documents (kind: review): {review}')
    covered = {d['file'] for d in cfg['documents']}
    missing = [f for f in e.spine if f not in covered]
    if missing:
        sys.exit(f'spine documents not in book.yaml: {missing}')
    inc = [d for d in cfg['documents'] if d['kind'] in ('chapter', 'front', 'back')]
    # slugs and link map
    for d in inc:
        t = strip_num(d.get('toc_title') or '') if d['kind'] == 'chapter' else (d.get('toc_title') or posixpath.splitext(posixpath.basename(d['file']))[0])
        d['title'] = d.get('title') or t
        d['md'] = f"{d['id']}-{slugify(d['title'])}.md"
    link_map = {d['file']: d['md'] for d in inc}
    out = os.path.join(bd, '02-text')
    shutil.rmtree(os.path.join(out, 'chapters'), ignore_errors=True)
    shutil.rmtree(os.path.join(out, 'figures'), ignore_errors=True)
    os.makedirs(os.path.join(out, 'chapters'))
    os.makedirs(os.path.join(out, 'figures'))
    figures, manifest, report = [], [], []
    for d in inc:
        rn = Renderer(e, cfg, link_map, None)
        soup = parse_html(e.text(d['file']))
        blocks = rn.render_doc(soup, d['file'])
        fig_n = [0]
        def gen():
            while True:
                fig_n[0] += 1
                yield f"fig-{d['id']}-{fig_n[0]:02d}"
        body, npar = serialize(blocks, d['id'], gen())
        for b in blocks:
            if b.kind == 'figure':
                f = b.fig
                ext = posixpath.splitext(f['path'])[1].lower() or '.bin'
                fn = f'{f["id"]}{ext}'
                open(os.path.join(out, 'figures', fn), 'wb').write(f['data'])
                figures.append(dict(id=f['id'], file=f'figures/{fn}', chapter=d['id'], alt=f['alt'], source_doc=d['file'],
                                    sha256=sha256(f['data']), bytes=len(f['data'])))
        hv = rn.meta.get('heading_verbatim')
        lifted = list(hv) if hv else []
        body_sha = sha256(body)
        fm = dict(id=d['id'], number=rn.meta.get('number') or (int(d['id'][2:]) if d['kind'] == 'chapter' else None),
                  title=d['title'], toc_title=d.get('toc_title'), heading_verbatim=' '.join(hv) if hv else None,
                  part=d.get('part'), kind=d['kind'], book=cfg['title'], author=cfg['author'], source_file=d['file'],
                  words=len(source_text(soup).split()), paragraphs=npar, figures=sum(1 for b in blocks if b.kind == 'figure'),
                  body_sha256=body_sha, generated=True)
        fm = {k: v for k, v in fm.items() if v is not None}
        open(os.path.join(out, 'chapters', d['md']), 'w').write(front_matter(fm) + f"# {d['title']}\n\n" + body)
        manifest.append(dict(id=d['id'], md=d['md'], kind=d['kind'], source_file=d['file'], title=d['title'],
                             paragraphs=npar, lifted=lifted, body_sha256=body_sha, unmapped=rn.unmapped,
                             skipped=rn.meta.get('skipped_text', [])))
        if rn.unmapped or rn.meta.get('skipped_text'):
            report.append(f"{d['id']}: unmapped classes {rn.unmapped} skipped {rn.meta.get('skipped_text', [])}")
    excl = [dict(file=d['file'], reason=d['reason'], words=d['words']) for d in cfg['documents'] if d['kind'] == 'exclude']
    json.dump(dict(documents=manifest, excluded=excl, parts=cfg.get('parts', [])), open(os.path.join(out, 'manifest.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump(figures, open(os.path.join(out, 'figures.json'), 'w'), indent=1, ensure_ascii=False)
    cfg['status']['parsed'] = True
    for d in cfg['documents']:
        pass
    yaml.safe_dump(cfg, open(os.path.join(bd, 'book.yaml'), 'w'), sort_keys=False, allow_unicode=True, width=100)
    print(f'built {len(inc)} documents, {len(figures)} figures, excluded {len(excl)}')
    for r in report:
        print('  NOTE', r)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    x = sp.add_parser('inspect'); x.add_argument('epub'); x.set_defaults(f=cmd_inspect)
    x = sp.add_parser('init'); x.add_argument('epub'); x.add_argument('bookdir'); x.set_defaults(f=cmd_init)
    x = sp.add_parser('build'); x.add_argument('bookdir'); x.set_defaults(f=cmd_build)
    a = ap.parse_args()
    a.f(a)
