"""EPUB reading and deterministic Markdown rendering. No LLM, no guessing: the book's own
structure and a per-book class map (book.yaml) decide what every element becomes."""
import hashlib, io, posixpath, re, zipfile
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urldefrag
from bs4 import BeautifulSoup, NavigableString, Tag, Comment, ProcessingInstruction

try:
    from PIL import Image
except Exception:  # pillow optional
    Image = None

def local(tag):
    return tag.split('}')[-1] if isinstance(tag, str) else tag

def sha256(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode('utf8')).hexdigest()

# ----------------------------------------------------------------------------- EPUB container
class Epub:
    def __init__(self, path):
        self.path = path
        self.z = zipfile.ZipFile(path)
        cont = ET.fromstring(self.z.read('META-INF/container.xml'))
        self.opf_path = next(e.get('full-path') for e in cont.iter() if local(e.tag) == 'rootfile')
        self.opf_dir = posixpath.dirname(self.opf_path)
        opf = ET.fromstring(self.z.read(self.opf_path))
        self.meta = {}
        for e in opf.iter():
            t = local(e.tag)
            if e.tag.startswith('{http://purl.org/dc/elements/1.1/}') and (e.text or '').strip():
                self.meta.setdefault(t, []).append(e.text.strip())
        self.manifest = {}
        for e in opf.iter():
            if local(e.tag) == 'item':
                self.manifest[e.get('id')] = dict(href=self.resolve(e.get('href')), type=e.get('media-type', ''),
                                                  props=e.get('properties', ''))
        self.spine = [self.manifest[e.get('idref')]['href'] for e in opf.iter()
                      if local(e.tag) == 'itemref' and e.get('idref') in self.manifest]
        self.toc = self._toc(opf)

    def resolve(self, href, base=None):
        base = self.opf_dir if base is None else base
        return posixpath.normpath(posixpath.join(base, unquote(urldefrag(href)[0])))

    def read(self, name):
        return self.z.read(name)

    def text(self, name):
        raw = self.z.read(name)
        for enc in ('utf-8-sig', 'utf-16', 'latin-1'):
            try:
                return raw.decode(enc)
            except Exception:
                pass

    def _toc(self, opf):
        """Return a tree: [{'title','href','children':[...]}], from nav.xhtml or toc.ncx."""
        nav = next((m for m in self.manifest.values() if 'nav' in m['props'].split()), None)
        ncx = next((m for m in self.manifest.values() if m['type'] == 'application/x-dtbncx+xml'), None)
        if ncx:
            root = ET.fromstring(self.z.read(ncx['href']))
            base = posixpath.dirname(ncx['href'])
            def walk(el):
                out = []
                for np in [c for c in el if local(c.tag) == 'navPoint']:
                    label = next((''.join(t.itertext()) for t in np.iter() if local(t.tag) == 'text'), '')
                    content = next((c for c in np if local(c.tag) == 'content'), None)
                    href = self.resolve(content.get('src'), base) if content is not None else None
                    out.append(dict(title=label.strip(), href=href, children=walk(np)))
                return out
            nm = next(e for e in root.iter() if local(e.tag) == 'navMap')
            return walk(nm)
        if nav:
            soup = BeautifulSoup(self.text(nav['href']), 'html.parser')
            base = posixpath.dirname(nav['href'])
            ol = (soup.find('nav', attrs={'epub:type': 'toc'}) or soup.find('nav') or soup).find('ol')
            def walk(ol):
                out = []
                for li in ol.find_all('li', recursive=False):
                    a = li.find('a')
                    sub = li.find('ol')
                    out.append(dict(title=a.get_text(' ', strip=True) if a else '',
                                    href=self.resolve(a['href'], base) if a and a.get('href') else None,
                                    children=walk(sub) if sub else []))
                return out
            return walk(ol) if ol else []
        return []

def flat_toc(tree, depth=0, parents=()):
    for n in tree:
        yield n, depth, parents
        yield from flat_toc(n['children'], depth + 1, parents + (n['title'],))

def parse_html(raw):
    # html.parser treats <div/> as an empty element (lxml-HTML would swallow the rest of the page)
    return BeautifulSoup(raw, 'html.parser')

def source_text(soup):
    """Independent view of everything a reader would see in the document body."""
    body = soup.body or soup
    for t in body.find_all(['script', 'style']):
        t.decompose()
    return ''.join(s for s in body.strings if not isinstance(s, (Comment, ProcessingInstruction)))

# ----------------------------------------------------------------------------- rendering
INLINE = {'span', 'i', 'b', 'em', 'strong', 'a', 'sup', 'sub', 'br', 'img', 'u', 'small', 'cite', 'code', 'abbr',
          'mark', 'font', 's', 'del', 'ins', 'bdi', 'bdo', 'q', 'dfn', 'kbd', 'var', 'samp', 'time', 'tt', 'big'}
HEADINGS = {f'h{i}': i for i in range(1, 7)}
WS = re.compile(r'[ \t\r\n    ]+')

def esc(s):
    s = s.replace('\\', '\\\\')
    for ch in '*_`[]<>|':
        s = s.replace(ch, '\\' + ch)
    return s

class Run:
    __slots__ = ('t', 'b', 'i', 'href', 'sup', 'sub')
    def __init__(self, t, b=False, i=False, href=None, sup=False, sub=False):
        self.t, self.b, self.i, self.href, self.sup, self.sub = t, b, i, href, sup, sub
    def key(self):
        return (self.b, self.i, self.href, self.sup, self.sub)

class Block:
    def __init__(self, kind, text='', level=0, group=None, depth=0, fig=None, rows=None, caption=''):
        self.kind, self.text, self.level, self.group, self.depth, self.fig, self.rows, self.caption = kind, text, level, group, depth, fig, rows, caption

def parse_role(v):
    if v is None:
        return None, None
    if ':' in str(v):
        r, a = str(v).split(':', 1)
        return r, int(a) if a.isdigit() else a
    return str(v), None

class Renderer:
    """Turns one spine document into Blocks. Roles come from cfg['classmap'] (class -> role)."""
    def __init__(self, epub, cfg, link_map, fig_register):
        self.e, self.cfg = epub, cfg
        self.classmap = cfg.get('classmap', {}) or {}
        self.link_map = link_map
        self.fig_register = fig_register
        self.min_px = cfg.get('min_figure_px', 80)
        self.deco = [re.compile(p) for p in cfg.get('decorative_images', []) or []]
        self.meta = {}
        self.unmapped = {}
        self.group_n = 0
        self.cur_file = None

    # ---- roles
    def role(self, el):
        for c in el.get('class', []) or []:
            if c in self.classmap:
                return parse_role(self.classmap[c]) + (c,)
        return None, None, None

    def note_unmapped(self, el):
        for c in el.get('class', []) or []:
            if c not in self.classmap:
                self.unmapped[c] = self.unmapped.get(c, 0) + 1

    # ---- images
    def img_info(self, img):
        src = img.get('src')
        if not src:
            return None
        path = self.e.resolve(src, posixpath.dirname(self.cur_file))
        if any(p.search(path) for p in self.deco):
            return None
        try:
            data = self.e.read(path)
        except KeyError:
            return None
        if Image is not None:
            try:
                w, h = Image.open(io.BytesIO(data)).size
                if max(w, h) < self.min_px:
                    return None
            except Exception:
                pass
        return dict(path=path, alt=(img.get('alt') or '').strip(), data=data)

    # ---- inline
    def runs(self, nodes, style, state, strip_emph=False):
        out = []
        for n in nodes:
            if isinstance(n, (Comment, ProcessingInstruction)):
                continue
            if isinstance(n, NavigableString):
                t = WS.sub(' ', str(n))
                if t:
                    out.append(Run(esc(t), **style))
                continue
            if not isinstance(n, Tag):
                continue
            name = n.name
            r, arg, _ = self.role(n)
            if r == 'skip':
                state['skipped_text'] += len(n.get_text().strip())
                continue
            if name == 'br':
                out.append(Run('\n', **style))
                continue
            if name == 'img':
                info = self.img_info(n)
                if info:
                    state['figs'].append(info)
                continue
            st = dict(style)
            if name in ('b', 'strong') and not strip_emph:
                st['b'] = True
            elif name in ('i', 'em', 'cite', 'dfn') and not strip_emph:
                st['i'] = True
            elif name == 'sup':
                st['sup'] = True
            elif name == 'sub':
                st['sub'] = True
            elif name == 'a' and n.get('href'):
                st['href'] = self.map_href(n['href'])
            if name == 'span':
                self.note_unmapped(n)
                if r == 'bold' and not strip_emph:
                    st['b'] = True
                elif r == 'italic' and not strip_emph:
                    st['i'] = True
            out.extend(self.runs(n.children, st, state, strip_emph))
        return out

    def map_href(self, href):
        if re.match(r'^(https?:|mailto:)', href):
            return href
        target = self.e.resolve(href, posixpath.dirname(self.cur_file))
        return self.link_map.get(target)  # None => drop the link, keep the text

    def render_runs(self, runs):
        # absorb whitespace-only plain runs between two runs of the same emphasis
        for k in range(1, len(runs) - 1):
            r = runs[k]
            # A hard break between runs with the same emphasis is still part
            # of that run. Keeping it plain creates adjacent markers such as
            # **one**\n**two**, which is valid-ish Markdown but needlessly
            # ambiguous for readers and downstream parsers.
            if r.t.strip() == '' and not (r.b or r.i):
                p, nx = runs[k - 1], runs[k + 1]
                if (p.b, p.i) == (nx.b, nx.i) and (p.b or p.i):
                    r.b, r.i = p.b, p.i
        merged = []
        for r in runs:
            if merged and merged[-1].key() == r.key():
                merged[-1].t += r.t
            else:
                merged.append(Run(r.t, r.b, r.i, r.href, r.sup, r.sub))
        s = ''
        for r in merged:
            t = r.t
            if t.strip() == '' and '\n' in t:
                s = s.rstrip(' ') + '  \n'
                continue
            lead, core, trail = re.match(r'^(\s*)(.*?)(\s*)$', t, re.S).groups()
            if core == '':
                s += t
                continue
            core = re.sub(r' *\n *', '  \n', core)
            if '\n' in lead:
                lead = lead.replace('\n', '').rstrip(' ') + '  \n'
            if '\n' in trail:
                trail = '  \n' + trail.replace('\n', '').lstrip(' ')
            if r.sup:
                core = f'<sup>{core}</sup>'
            if r.sub:
                core = f'<sub>{core}</sub>'
            if r.b and r.i:
                core = f'***{core}***'
            elif r.b:
                core = f'**{core}**'
            elif r.i:
                core = f'*{core}*'
            if r.href:
                # Calibre occasionally copies a prose closing paren into href.
                href = r.href
                if href.endswith(')') and not core.endswith(')'):
                    href = href[:-1]
                core = f'[{core}]({href.replace(")", r"\\)")})'
            s += lead + core + trail
        s = re.sub(r'[ ]*\n[ ]*(?!\n)', lambda m: m.group(0), s)
        s = re.sub(r'(^|\n)- ', r'\1\\- ', s)
        return re.sub(r'^[ ]+|[ ]+$', '', s.replace('\n  \n', '\n'), flags=re.M).strip()

    def inline_md(self, nodes, strip_emph=False, state=None):
        state = state if state is not None else dict(figs=[], skipped_text=0)
        md = self.render_runs(self.runs(nodes, {}, state, strip_emph))
        if strip_emph:
            md = re.sub(r'\s*\n\s*', ' ', md)
        return md, state

    # ---- blocks
    def render_doc(self, soup, file):
        self.cur_file = file
        body = soup.body or soup
        for t in body.find_all(['script', 'style']):
            t.decompose()
        blocks = []
        self.walk(body, blocks, depth=0, group=None)
        return blocks

    def walk(self, parent, blocks, depth, group):
        pending = []
        def flush():
            if pending:
                self.emit_inline(pending, blocks, depth, group, None)
                pending.clear()
        for c in parent.children:
            if isinstance(c, (Comment, ProcessingInstruction)):
                continue
            if isinstance(c, NavigableString):
                if str(c).strip():
                    pending.append(c)
                continue
            if not isinstance(c, Tag):
                continue
            if c.name in INLINE and c.name != 'br' or (c.name == 'br' and pending):
                pending.append(c)
                continue
            if c.name == 'br':
                continue
            flush()
            self.block(c, blocks, depth, group)
        flush()

    def block(self, el, blocks, depth, group):
        r, arg, cls = self.role(el)
        name = el.name
        if r == 'skip':
            if el.get_text().strip() and not self.cfg.get('allow_skip_text'):
                self.meta.setdefault('skipped_text', []).append(cls)
            return
        if name in HEADINGS:
            return self.emit_heading(el, blocks, max(2, HEADINGS[name] + 1) if r is None else arg or 3, group, depth)
        if name in ('ul', 'ol'):
            return self.render_list(el, blocks, depth, group)
        if name == 'table':
            return self.render_table(el, blocks, group)
        if name == 'hr':
            return
        if name in ('p', 'li', 'dt', 'dd', 'pre', 'figcaption', 'caption', 'td', 'th'):
            return self.render_para(el, blocks, depth, group, r, arg, cls)
        # container (div, section, blockquote ...)
        g = group
        if r in ('quote', 'callout', 'pullquote') or name == 'blockquote':
            self.group_n += 1
            g = self.group_n
        self.note_unmapped(el)
        self.walk(el, blocks, depth, g)

    def emit_heading(self, el, blocks, level, group, depth):
        md, st = self.inline_md(el.children, strip_emph=True)
        if md:
            blocks.append(Block('h', md, level=level, group=group))
        for f in st['figs']:
            blocks.append(Block('figure', fig=f))

    def render_para(self, el, blocks, depth, group, r, arg, cls):
        self.note_unmapped(el)
        kids = [k for k in el.children if not (isinstance(k, NavigableString) and not str(k).strip())]
        # a span whose class maps to a heading and that fills the whole paragraph
        if r is None and len(kids) == 1 and isinstance(kids[0], Tag):
            r2, a2, _ = self.role(kids[0])
            if r2 == 'heading':
                r, arg = r2, a2
        if r == 'chapter_title':
            parts = []
            cur = ''
            for n in el.descendants:
                if isinstance(n, NavigableString) and not isinstance(n, (Comment, ProcessingInstruction)):
                    cur += str(n)
                elif isinstance(n, Tag) and n.name == 'br':
                    parts.append(cur); cur = ''
            parts.append(cur)
            parts = [WS.sub(' ', p).strip() for p in parts if p.strip()]
            if len(parts) > 1 and parts[0].isdigit():
                self.meta['number'] = int(parts[0])
            self.meta.setdefault('heading_verbatim', [])
            self.meta['heading_verbatim'].append(' '.join(parts))
            return
        if r == 'heading':
            return self.emit_heading(el, blocks, arg or 3, group, depth)
        bullet = False
        nodes = list(el.children)
        if nodes:
            first = next((n for n in nodes if not (isinstance(n, NavigableString) and not str(n).strip())), None)
            if isinstance(first, Tag):
                r2, _, _ = self.role(first)
                if r2 == 'bullet_marker':
                    bullet = True
                    nodes = [n for n in nodes if n is not first]
        if r == 'list_item':
            bullet = True
        state = dict(figs=[], skipped_text=0)
        md, state = self.inline_md(nodes, state=state)
        if state['skipped_text'] and not self.cfg.get('allow_skip_text'):
            self.meta.setdefault('skipped_text', []).append(cls or el.name)
        if md:
            blocks.append(Block('li' if bullet else ('quote_p' if group else 'p'), md, group=group, depth=depth))
        for f in state['figs']:
            blocks.append(Block('figure', fig=f))

    def emit_inline(self, nodes, blocks, depth, group, role):
        state = dict(figs=[], skipped_text=0)
        md, state = self.inline_md(nodes, state=state)
        if md:
            blocks.append(Block('quote_p' if group else 'p', md, group=group, depth=depth))
        for f in state['figs']:
            blocks.append(Block('figure', fig=f))

    def render_list(self, el, blocks, depth, group):
        # Calibre sometimes wraps the real list in one or more list containers.
        # Descend through those wrappers rather than silently dropping all items.
        direct = [c for c in el.children if isinstance(c, Tag) and c.name == 'li']
        if not direct:
            for child in el.children:
                if not isinstance(child, Tag):
                    continue
                # Some EPUBs put the list items in a blockquote/div wrapper.
                child_items = [c for c in child.children if isinstance(c, Tag) and c.name == 'li']
                if child_items or child.name in ('ul', 'ol'):
                    self.render_list(child, blocks, depth, group)
            return
        pending_prefix = []
        for li in el.children:
            if isinstance(li, NavigableString):
                if str(li).strip():
                    pending_prefix.append(li)
                continue
            if not isinstance(li, Tag):
                continue
            if li.name in ('ul', 'ol'):
                self.render_list(li, blocks, depth + 1, group)
                continue
            if li.name != 'li':
                self.block(li, blocks, depth, group)
                continue
            pending = pending_prefix + []
            pending_prefix.clear()
            def flush():
                if not pending:
                    return
                state = dict(figs=[], skipped_text=0)
                md, state = self.inline_md(pending, state=state)
                if md:
                    blocks.append(Block('li', md, depth=depth, group=group))
                for f in state['figs']:
                    blocks.append(Block('figure', fig=f))
                pending.clear()
            for child in li.children:
                if isinstance(child, Tag) and child.name in ('ul', 'ol'):
                    flush()
                    self.render_list(child, blocks, depth + 1, group)
                else:
                    pending.append(child)
            flush()

    def render_table(self, el, blocks, group):
        rows = []
        caption = el.find('caption', recursive=False)
        caption_md = self.inline_md(caption.children)[0] if caption else ''
        for tr in el.find_all('tr'):
            cells = []
            for td in tr.find_all(['td', 'th'], recursive=False):
                md, _ = self.inline_md(td.children)
                cells.append(re.sub(r'\s*\n\s*', ' ', md).replace('|', '\\|'))
            if cells:
                rows.append(cells)
        if rows:
            blocks.append(Block('table', rows=rows, group=group, caption=caption_md))

# ----------------------------------------------------------------------------- serialisation
LINE_START = re.compile(r'^(#{1,6}\s|>|[-+]\s|\d+[.)]\s)')

def protect_line_start(s):
    if LINE_START.match(s):
        s = re.sub(r'^(\d+)([.)])', r'\1\\\2', s) if re.match(r'^\d', s) else '\\' + s
    return s

def serialize(blocks, chid, fig_ids):
    """Blocks -> markdown lines with stable paragraph ids (^chid-NNN). fig_ids: iterator of figure ids."""
    out, n, prev = [], 0, None
    def pid():
        nonlocal n
        n += 1
        return f'^{chid}-{n:03d}'
    def sep(kind, group):
        nonlocal prev
        if out:
            joined = (prev and prev[0] == 'li' and kind == 'li' and prev[1] == group)
            quoted = (prev and group and prev[1] == group and prev[0] in ('quote_p',) and kind == 'quote_p')
            if quoted:
                out.append('>')
            elif not joined:
                out.append('')
        prev = (kind, group)
    for b in blocks:
        if b.kind == 'h':
            sep('h', b.group)
            out.append(f"{'#' * b.level} {b.text} {pid()}")
        elif b.kind == 'p':
            sep('p', b.group)
            lines = [protect_line_start(line) for line in b.text.split('\n')]
            lines[-1] = lines[-1].rstrip() + ' ' + pid()
            out.extend(lines)
        elif b.kind == 'quote_p':
            sep('quote_p', b.group)
            lines = [protect_line_start(line) for line in b.text.split('\n')]
            lines[-1] = lines[-1].rstrip() + ' ' + pid()
            out.extend('> ' + l for l in lines)
        elif b.kind == 'li':
            sep('li', b.group)
            lines = b.text.split('\n')
            lines[-1] = lines[-1].rstrip() + ' ' + pid()
            out.append('  ' * b.depth + '- ' + lines[0])
            out.extend('  ' * b.depth + '  ' + l for l in lines[1:])
        elif b.kind == 'table':
            sep('table', b.group)
            if b.caption:
                out.append(b.caption)
            w = max(len(r) for r in b.rows)
            rows = [r + [''] * (w - len(r)) for r in b.rows]
            out.append('| ' + ' | '.join(rows[0]) + ' |')
            out.append('|' + '---|' * w)
            out.extend('| ' + ' | '.join(r) + ' |' for r in rows[1:])
            out.append(pid())
        elif b.kind == 'figure':
            sep('figure', None)
            fid = next(fig_ids)
            b.fig['id'] = fid
            out.append(f"<!-- figure:{fid} -->")
            ext = posixpath.splitext(b.fig['path'])[1].lower() or '.bin'
            out.append(f"![{fid}](figures/{fid}{ext})")
            out.append(f"<!-- /figure -->")
    return '\n'.join(out) + '\n', n

# ----------------------------------------------------------------------------- verification view of the output
UNESC = re.compile(r'\\([\\`*_{}\[\]<>()#+\-.!|])')

def output_stream(md_body):
    """Strip everything the renderer adds (ids, markup, generated blocks) and return the bare character
    stream, whitespace removed. Escaped characters are restored first so a real '*' is not lost."""
    s = re.sub(r'<!-- figure:.*?<!-- /figure -->', '', md_body, flags=re.S)
    lines = []
    literal_hash_candidate = False
    literal_hash_pending = False
    for ln in s.split('\n'):
        if re.match(r'^#\s+\^[a-z0-9]+-\d+$', ln.strip()):
            # A source-authored leading hash may follow a standalone first ID;
            # do not infer one when the first body paragraph is ordinary text.
            literal_hash_pending = literal_hash_candidate
            continue
        if re.match(r'^# ', ln):            # generated title line
            literal_hash_candidate = ' # ' in ln
            continue
        if literal_hash_pending and ln.strip():
            ln = '#' + ln
            literal_hash_pending = False
        if re.match(r'^\^[a-z0-9]+-\d+$', ln.strip()):
            continue
        if re.match(r'^\|(---\|)+$', ln.strip()):
            continue
        ln = re.sub(r'\s\^[a-z0-9]+-\d{3,}\s*$', '', ln)
        ln = re.sub(r'^\s*>\s?', '', ln)
        ln = re.sub(r'^(\s*)#{2,6}\s', r'\1', ln)
        ln = re.sub(r'^(\s*)-\s', r'\1', ln)
        lines.append(ln)
    s = '\n'.join(lines)
    # URLs in DOI links commonly contain one level of parentheses. A plain
    # [^)]* pattern leaves the tail of those URLs in the text stream.
    url = r'((?:\\.|[^()]|\([^()]*\))*)'
    s = re.sub(r'!\[[^\]]*\]\((?:[^()]|\([^()]*\))*figures/[^()]*\)', '', s)
    s = re.sub(r'(?<!\\)\[((?:[^\]\\]|\\.)*)\]\(' + url + r'\)', r'\1', s)
    s = re.sub(r'</?su[bp]>', '', s)
    s = s.replace('\\\\|', '\u0003')
    s = s.replace('\\\\', '\u0002').replace('\\*', '\u0001')
    s = re.sub(r'(?<!\\)\*+', '', s)
    s = re.sub(r'(?<!\\)\|', '', s)
    s = UNESC.sub(r'\1', s)
    s = s.replace('\u0001', '*').replace('\u0002', '\\').replace('\u0003', '|')
    return re.sub(r'\s+', '', s.replace(' ', ' '))

def source_stream(text):
    return re.sub(r'\s+', '', text.replace(' ', ' '))
