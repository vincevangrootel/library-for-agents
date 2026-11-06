#!/usr/bin/env python3
"""Stage 04: merge the immutable text layer (02-text) with enrichment sidecars (03-enrich) into reading copies
and search artifacts. Never writes to 02-text or 03-enrich. Deterministic and idempotent.

  assemble.py BOOKDIR
Outputs in BOOKDIR/04-assemble: chapters/*.md, INDEX.md, index.json, chunks.jsonl, book_full.md, figures/ (copy)
"""
import json, os, re, shutil, sys
import yaml

def split_doc(md):
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', md, re.S)
    return yaml.safe_load(m.group(1)), m.group(2)

def load_yaml(p):
    return yaml.safe_load(open(p)) if os.path.exists(p) else None

def inject_figures(body, figs):
    def rep(m):
        fid, mid = m.group(1), m.group(2)
        mid = re.sub(r'\n\*Figure description \(written[^\n]*', '', mid)
        mid = re.sub(r'\n\*(QR code link \(decoded\)|Text in figure|Takeaway):\*[^\n]*', '', mid)
        d = (figs or {}).get(fid)
        if d and d.get('description'):
            extra = ''.join(f"\n*{lab}:* {d[k]}" for k, lab in (('qr_link', 'QR code link (decoded)'), ('text_in_figure', 'Text in figure'), ('takeaway', 'Takeaway')) if d.get(k))
            mid = mid.rstrip('\n') + f"\n*Figure description (written by an AI reader, not book text):* {d['description']}{extra}\n"
        return f"<!-- figure:{fid} -->{mid}<!-- /figure -->"
    return re.sub(r'<!-- figure:(\S+) -->(.*?)<!-- /figure -->', rep, body, flags=re.S)

def chunks_for(fm, body, book, max_words=600):
    out, head, cur, curw, pids = [], [fm['title']], [], 0, []
    def flush():
        nonlocal cur, curw, pids
        if cur and ''.join(cur).strip():
            text = '\n\n'.join(cur)
            out.append(dict(book=book, chapter=fm['id'], chapter_title=fm['title'], heading=' > '.join(head),
                            first=pids[0] if pids else None, last=pids[-1] if pids else None,
                            words=len(text.split()), text=text))
        cur, curw, pids = [], 0, []
    body = re.sub(r'<!-- figure:.*?<!-- /figure -->', '', body, flags=re.S)
    for para in [p for p in re.split(r'\n\s*\n', body) if p.strip()]:
        if para.startswith('# '):
            continue
        m = re.match(r'^(#{2,6}) (.*?)\s*\^([a-z0-9]+-\d+)\s*$', para)
        if m:
            flush()
            lvl = len(m.group(1))
            head[:] = head[:1] if lvl <= 2 else head[:lvl - 1]
            head.append(m.group(2).strip())
            cur.append(re.sub(r'\s*\^[a-z0-9]+-\d+\s*$', '', para)); pids.append(m.group(3)); curw += len(para.split())
            continue
        ids = re.findall(r'\^([a-z0-9]+-\d{3})\s*$', para, re.M)
        w = len(para.split())
        if curw + w > max_words and cur:
            h = list(head)
            flush(); head[:] = h
        cur.append(re.sub(r'\s\^[a-z0-9]+-\d{3}\s*$', '', para, flags=re.M)); pids += ids; curw += w
    flush()
    return out

def main():
    bd = sys.argv[1]
    cfg = load_yaml(os.path.join(bd, 'book.yaml'))
    man = json.load(open(os.path.join(bd, '02-text', 'manifest.json')))
    out = os.path.join(bd, '04-assemble')
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, 'chapters'))
    shutil.copytree(os.path.join(bd, '02-text', 'figures'), os.path.join(out, 'figures'))
    overview = load_yaml(os.path.join(bd, '03-enrich', 'book-overview.yaml')) or {}
    figs_all = (load_yaml(os.path.join(bd, '03-enrich', 'figures.yaml')) or {})
    titles = {m['id']: m['title'] for m in man['documents']}
    index, chunks, full = [], [], []
    for m in man['documents']:
        fm, body = split_doc(open(os.path.join(bd, '02-text', 'chapters', m['md'])).read())
        sc = load_yaml(os.path.join(bd, '03-enrich', 'chapters', f"{m['id']}.yaml")) or {}
        body = inject_figures(body, figs_all)
        keep = ['id', 'number', 'title', 'toc_title', 'heading_verbatim', 'part', 'kind', 'book', 'author', 'words', 'paragraphs', 'figures']
        nfm = {k: fm[k] for k in keep if k in fm}
        for k in ('short_answer', 'summary', 'key_concepts', 'questions_answered', 'keywords'):
            if sc.get(k):
                nfm[k] = sc[k]
        if sc.get('related'):
            nfm['related_chapters'] = [dict(id=r['id'], title=titles.get(r['id']), why=r.get('why')) for r in sc['related']]
        nfm['enriched'] = bool(sc)
        doc = '---\n' + yaml.safe_dump(nfm, sort_keys=False, allow_unicode=True, width=1000) + '---\n' + body
        open(os.path.join(out, 'chapters', m['md']), 'w').write(doc)
        full.append(f"\n\n<!-- source: {m['md']} -->\n" + re.sub(r'^# ', '# ', body, count=1))
        chunks += chunks_for(fm, body, cfg['slug'])
        index.append(dict(id=fm['id'], file=f"chapters/{m['md']}", title=fm['title'], part=fm.get('part'), kind=fm['kind'],
                          words=fm['words'], paragraphs=fm['paragraphs'], summary=sc.get('summary'), keywords=sc.get('keywords', []),
                          short_answer=sc.get('short_answer')))
    with open(os.path.join(out, 'chunks.jsonl'), 'w') as fh:
        for i, c in enumerate(chunks):
            c['chunk'] = i
            fh.write(json.dumps(c, ensure_ascii=False) + '\n')
    json.dump(dict(book=cfg['title'], author=cfg['author'], slug=cfg['slug'], parts=cfg.get('parts', []), overview=overview, documents=index),
              open(os.path.join(out, 'index.json'), 'w'), indent=1, ensure_ascii=False)
    open(os.path.join(out, 'book_full.md'), 'w').write(f"# {cfg['title']}\n\nby {cfg['author']}\n" + ''.join(full))
    L = [f"# {cfg['title']}", f"by {cfg['author']}", '']
    if overview.get('summary'):
        L += ['## What this book is', overview['summary'].strip(), '']
    if overview.get('how_to_use'):
        L += ['## How to use this folder', overview['how_to_use'].strip(), '']
    part = object()
    L += ['## Contents', '']
    for d in index:
        if d['kind'] == 'chapter' and d['part'] != part:
            part = d['part']; L += ['', f"### {part}"]
        line = f"- [{d['id']}: {d['title']}]({d['file']}) ({d['words']} words)"
        if d['summary']:
            line += f"\n  - {' '.join(d['summary'].split())}"
        L.append(line)
    open(os.path.join(out, 'INDEX.md'), 'w').write('\n'.join(L) + '\n')
    print(f"assembled {len(index)} documents, {len(chunks)} chunks")

main()
