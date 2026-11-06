"""Sonnet pass: decide which manifest documents are body chapters; rewrite `kind`, keep `kind_original`."""
import sys, os, json, re, urllib.request
import urllib.request as _ur; _o = _ur.build_opener(); _o.addheaders = [('User-Agent', 'Mozilla/5.0 (library-tools)')]; _ur.install_opener(_o)  # UA_HEADER: default Python UA is blocked at the OpenRouter edge (error 1010)
OR_BASE = os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')
ROOT = os.environ.get('LIBRARY_ROOT', os.getcwd())
KEY = os.environ['OPENROUTER_API_KEY']
def ask(prompt):
    req = urllib.request.Request(OR_BASE + '/chat/completions', json.dumps({
        'model': 'anthropic/claude-sonnet-5.5', 'temperature': 0,
        'messages': [{'role': 'user', 'content': prompt}]}).encode(),
        {'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=120))['choices'][0]['message']['content']
NUMWORDS = r'(een|twee|drie|vier|vijf|zes|zeven|acht|negen|tien|elf|twaalf|dertien|veertien|vijftien|zestien|zeventien|achttien|negentien|twintig|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)'
HEADING = re.compile(r'^\s*((chapter|hoofdstuk|part|deel|kapitel|chapitre)\s+)?(\d+|[ivxlc]+|' + NUMWORDS + r')\b[.:]?\s*$|^\s*(proloog|prologue|epiloog|epilogue)\b', re.I)
def deterministic(m):
    # Numbered/word-numbered headings are chapters; no model needed. Returns ids, or None if fewer than 5 match.
    ids = {d['id'] for d in m['documents'] if d['paragraphs'] >= 5 and HEADING.match(d['title'] or '')}
    return ids if len(ids) >= 5 else None
for slug in sys.argv[1:]:
    p = f'{ROOT}/books/{slug}/02-text/manifest.json'; m = json.load(open(p)); rows = []
    if not m['documents']: print(slug, 'SKIP no extracted documents (needs re-ingest)', flush=True); continue
    for d in m['documents']:
        try: head = open(f"{ROOT}/books/{slug}/02-text/chapters/{d['md']}").read()[:160].replace('\n', ' ')
        except Exception: head = ''
        rows.append(f"{d['id']} | {d['kind']} | {d['paragraphs']} paras | {d['title'][:50]} | {head}")
    det = deterministic(m)
    out = '[]' if det is not None else ask("Below are the documents extracted from one nonfiction ebook (id | current tag | paragraph count | title | opening text). "
              "Return ONLY a JSON list of the ids that are BODY chapters or substantive main-text sections of the book (including introduction and conclusion if they carry real content). "
              "Exclude copyright, dedication, praise, contents, landmarks, title pages, acknowledgements, about-the-author, notes, index, ads and resource lists.\n\n" + '\n'.join(rows))
    ids = det if det is not None else set(json.loads(re.search(r'\[.*\]', out, re.S).group(0)))
    ch = 0
    for d in m['documents']:
        new = 'chapter' if d['id'] in ids else 'front'
        if d['kind'] != new: d.setdefault('kind_original', d['kind']); d['kind'] = new
        ch += new == 'chapter'
    json.dump(m, open(p, 'w'), indent=1, ensure_ascii=False)
    print(slug, 'chapters', ch, 'of', len(m['documents']), flush=True)
