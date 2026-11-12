#!/usr/bin/env python3
"""Atom trial: extract atomic claims per chapter (model route: tools/llm.py). Derived data: keep private.
Output: $LIBRARY_INDEX/atoms/<book>.jsonl (one atom per line). Resumable per chapter."""
import json, os, re, glob, sys, time, urllib.request, concurrent.futures

ROOT = os.environ.get('LIBRARY_ROOT', os.getcwd())
OUT = os.environ.get('ATOMS_OUT', os.path.join(os.environ.get('LIBRARY_INDEX', os.path.join(ROOT, 'index')), 'atoms'))
TIERS = {'flash': 'deepseek/deepseek-v4.1-flash', 'sonnet': 'anthropic/claude-sonnet-5.5'}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import llm
MODEL = os.environ.get('LIBRARY_ATOM_MODEL') or (TIERS[os.environ['ATOM_TIER']] if llm.ROUTE == 'openrouter' and os.environ.get('ATOM_TIER') else llm.atom_model())
import yaml
import urllib.request as _ur; _o = _ur.build_opener(); _o.addheaders = [('User-Agent', 'Mozilla/5.0 (library-tools)')]; _ur.install_opener(_o)  # UA_HEADER: default Python UA is blocked at the OpenRouter edge (error 1010)
def eligible():
    out = []
    for f in sorted(glob.glob(ROOT + '/books/*/book.yaml')):
        y = yaml.safe_load(open(f)); sl = os.path.basename(os.path.dirname(f))
        if y.get('content_type') == 'nonfiction' and not y.get('duplicate_of') and not os.path.exists(f'{OUT}/{sl}.jsonl'):
            out.append(sl)
    return out
BOOKS = sys.argv[1:] or eligible()
os.makedirs(OUT, exist_ok=True)

PROMPT = """You extract ATOMS from one book chapter. An atom is one self-contained claim, finding, rule, or definition the author makes, written as a single plain sentence. It must be readable on its own: name the subject and the context explicitly (who or what the claim is about), and never rely on 'this', 'he', 'the author', or an unexplained name or metaphor. One idea per atom.

Rules:
- Write each atom in the SAME LANGUAGE as the chapter.
- Use only what the cited paragraphs say. Do not add outside knowledge, generalise, or infer. Skip anything unsupported.
- Write in your own plain words, as you would explain the idea to a colleague. Do not copy sentences from the text (never 13 or more consecutive words) and do not swap synonyms word for word.
- Each atom cites 1-3 paragraph IDs exactly as given (like ch05-012) that directly support it.
- Skip anecdote details, navigation, headings, and filler. Prefer claims that would still be useful in another context. Quality over quantity: there is no target count. A chapter that argues something may yield several atoms; a chapter that mainly tells a story may yield few or none. Return [] for navigation-only, empty or story-only chapters.
- Give each atom 1-3 short topic tags (lowercase). Tags MUST be in the same language as the chapter text (English book: English tags; Dutch book: Dutch tags). Never use any other language.
- Skip personal anecdotes, case-study details, book recommendations and name-dropping of other works; keep only the author's own transferable claims, rules and findings.
- Do not use en dashes or em dashes.
- Label every atom with: subject (who or what the claim is about, a role or concept, never a bare first name or "the author") and kind: "claim" if the author states a transferable idea, rule, finding or definition; "example" if it only illustrates one; "story" if it narrates what happened to a person. Only "claim" atoms are kept, so write an atom only when you can honestly label it "claim". Maximum 30 words, one sentence.
- Scope: label every atom "general" only if the cited paragraphs themselves state the point as a general rule or finding. If the support is one person's experience or one event, label it "personal" and do not turn it into a universal rule. Personal atoms are dropped.
- Stay at the strength of the source. Keep hedges such as can, often, may, some. Do not add causes, reasons, outcomes or comparisons the paragraphs do not state.
Return JSON only: {"atoms":[{"claim":"...","subject":"...","kind":"claim","scope":"general","paras":["ch05-012"],"tags":["..."]}]}

CHAPTER:
"""

PROMPT_X = PROMPT.replace("- Write each atom in the SAME LANGUAGE as the chapter.",
    "- The chapter is NOT English. Write each claim in ENGLISH, and add a field quote: one short VERBATIM phrase (4-12 words, copied exactly in the chapter's own language) from a cited paragraph that supports the claim.").replace(
    "Tags MUST be in the same language as the chapter text (English book: English tags; Dutch book: Dutch tags). Never use any other language.", "Tags MUST be in English.").replace(
    '"claim":"...","subject"', '"claim":"...","quote":"...","subject"')
_LANG = {}
def is_english(slug):
    if slug not in _LANG:
        y = yaml.safe_load(open(f'{ROOT}/books/{slug}/book.yaml')) or {}
        _LANG[slug] = str(y.get('language') or 'en').lower().startswith('en')
    return _LANG[slug]
def norm(t): return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', t.lower())).strip()

def post(payload):
    return llm.chat(payload)

STOP = set("the a an and or of to in on for with is are was were be it its this that as at by from you your i we they their his her not no do does can could should would will may might if than so but about into more most very also each every any all de het een en van op te dat die zijn was voor met als aan bij uit naar om ook niet er je ik ze hij zij wat hoe kan worden wordt dan maar".split())
def words(s):
    return {re.sub(r'(ing|ed|es|s|en|e)$', '', w) if len(w) > 4 else w
            for w in re.findall(r"[a-zà-ÿ0-9]+", s.lower().replace('’', '')) if w not in STOP and len(w) > 2}

CLASSIFY = """Classify this book chapter for knowledge extraction. Answer with JSON only: {"type":"ideas"|"mixed"|"story"}.
ideas = the author argues, explains, teaches or defines things. mixed = ideas interleaved with stories or examples. story = mainly narrative about events or people, with little transferable teaching. Front matter, acknowledgements, dedications, notes and indexes count as story.

CHAPTER (excerpt):
"""
CLASSIFY_ON = os.environ.get('CHAPTER_CLASSIFY', '1') == '1'
def classify(paras):
    sample = '\n\n'.join(list(paras.values())[:40])[:9000]
    try:
        r = post({'model': MODEL, 'messages': [{'role': 'user', 'content': CLASSIFY + sample}], 'max_tokens': 60})
        t = (r['choices'][0]['message']['content'] or '')
        m = re.search(r'ideas|mixed|story', t)
        return m.group(0) if m else 'mixed', r['usage'].get('cost', 0)
    except Exception:
        return 'mixed', 0
VAGUE = re.compile(r"^(they|he|she|it|this|these|those|both|the author|the authors|the writer|we|i)\b", re.I)
def structured_ok(a, claim):
    if str(a.get('kind', 'claim')).lower() != 'claim': return False
    if str(a.get('scope', 'general')).lower() != 'general': return False
    if len((a.get('subject') or '').strip()) < 3: return False
    if len(claim.split()) > 35 or VAGUE.match(claim) or re.search(r'\bthe (author|writer)\b', claim, re.I): return False
    return True

def job(args):
    slug, d = args
    fs = glob.glob(f"{ROOT}/books/{slug}/02-text/chapters/{d['id']}-*.md")
    if not fs: return slug, d['id'], [], 0, 0, 'nofile'
    paras = {m.group(2): m.group(1).strip() for m in re.finditer(r'^(.*?)\s\^([a-z0-9]+-\d{3,})\s*$', open(fs[0]).read(), re.M)}
    paras = {k: v for k, v in paras.items() if len(v) >= 40}
    if not paras: return slug, d['id'], [], 0, 0, 'empty'
    cost0 = 0
    if CLASSIFY_ON:
        ctype, cc = classify(paras); cost0 += cc
        if ctype == 'story': return slug, d['id'], [], 0, cost0, 'story'
    items = list(paras.items()); W = 150
    chunks = [dict(items[i:i + W]) for i in range(0, len(items), W)]
    if len(chunks) > 1 and len(chunks[-1]) < 40: chunks[-2].update(chunks.pop())
    atoms = []
    for ck in chunks:
        text = '\n\n'.join(f'[{k}] {v}' for k, v in ck.items())
        for attempt in range(3):
            r = post({'model': MODEL, 'messages': [{'role': 'user', 'content': (PROMPT if is_english(slug) else PROMPT_X) + text}]})
            cost0 += r['usage'].get('cost', 0)
            t = (r['choices'][0]['message']['content'] or '').strip()
            t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t)
            try:
                atoms += json.loads(re.search(r'\{.*\}', t, re.S).group(0))['atoms']; break
            except Exception:
                if attempt == 2: raise
    kept, dropped = [], 0
    for a in atoms:
        ps = [p for p in a.get('paras', []) if p in paras]
        claim = (a.get('claim') or '').replace('\u2014', ', ').replace('\u2013', '-').strip()
        cw = words(claim)
        if not structured_ok(a, claim):
            dropped += 1; continue
        src = set().union(*[words(paras[p]) for p in ps]) if ps else set()
        if is_english(slug):
            if not ps or not claim or not cw or len(cw & src) / len(cw) < 0.5:
                dropped += 1; continue
            kept.append(dict(book=slug, chapter=d['id'], claim=claim, subject=a.get('subject','').strip(), paras=ps, tags=a.get('tags', [])[:3]))
        else:
            q = (a.get('quote') or '').strip()
            if not ps or not claim or len(q.split()) < 3 or norm(q) not in ' '.join(norm(paras[p]) for p in ps):
                dropped += 1; continue
            kept.append(dict(book=slug, chapter=d['id'], claim=claim, subject=a.get('subject','').strip(), quote=q, lang='nl', paras=ps, tags=a.get('tags', [])[:3]))
    return slug, d['id'], kept, dropped, cost0, 'ok'

if __name__ == '__main__':
    jobs = []
    for slug in BOOKS:
        m = json.load(open(f'{ROOT}/books/{slug}/02-text/manifest.json'))
        jobs += [(slug, d) for d in m['documents'] if d.get('kind') == 'chapter']
    print('chapters', len(jobs), flush=True)
    res = {s: [] for s in BOOKS}; cost = drop = nat = 0; stat = {}
    with concurrent.futures.ThreadPoolExecutor(llm.workers(4)) as ex:
        futs = {ex.submit(job, j): j for j in jobs}
        for n, f in enumerate(concurrent.futures.as_completed(futs), 1):
            try:
                slug, cid, kept, dr, c, st = f.result()
            except Exception as e:
                slug, cid = futs[f][0], futs[f][1]['id']; kept, dr, c, st = [], 0, 0, 'ERR ' + repr(e)[:100]
            res[slug] += kept; cost += c; drop += dr; nat += len(kept); stat[st] = stat.get(st, 0) + 1
            if n % 20 == 0: print(n, 'done, atoms', nat, 'cost', round(cost, 3), flush=True)
    for s, atoms in res.items():
        atoms.sort(key=lambda a: (a['chapter'], a['paras'][0]))
        with open(f'{OUT}/{s}.jsonl', 'w') as fh:
            for a in atoms: fh.write(json.dumps(a, ensure_ascii=False) + '\n')
        print(s, len(atoms), 'atoms')
    print('DONE atoms', nat, 'dropped by precheck', drop, 'cost', round(cost, 4), stat, flush=True)
