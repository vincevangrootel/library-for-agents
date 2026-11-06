"""Rewrite only the atoms whose claims copy 13+ consecutive words from their cited paragraphs.
Usage: rewrite_verbatim.py <slug> [--dry]   (reads/writes ATOMS_OUT/<slug>.jsonl, backs up to _prev/)
Each rewrite is accepted only if: no 13-gram copy, no run of 7+ words shared with the source, JSON valid.
Citations (paras) and tags are kept unchanged."""
import json, os, re, sys, datetime, shutil, concurrent.futures
sys.argv_keep = sys.argv; sys.argv = ['x']
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import extract_atoms as ea
ROOT = ea.ROOT; OUT = ea.OUT
def words(s): return re.findall(r"\w+['’]?\w*", s.lower())
def paras_for(slug):
    pm = {}
    man = json.load(open(f'{ROOT}/books/{slug}/02-text/manifest.json'))
    for d in man['documents']:
        for l in open(f"{ROOT}/books/{slug}/02-text/chapters/{d['md']}"):
            m = re.match(r'(.*) \^([\w-]+)$', l.rstrip('\n'))
            if m: pm.setdefault(d['id'], {})[m.group(2)] = m.group(1)
    return pm
def longest_shared(claim, src):
    c, s = words(claim), ' '.join(words(src)); best = 0
    for i in range(len(c)):
        n = best + 1
        while i + n <= len(c) and ' '.join(c[i:i + n]) in s: best = n; n += 1
    return best
RP = """Rewrite the claim below so it says the same thing in your own words. Use plain, natural words, as you would explain the idea to a colleague; do not swap synonyms word for word. Never reuse a run of 13 or more consecutive words from the paragraphs. Keep it to one sentence of at most 30 words. Keep the claim understandable alone: name the subject and context. Keep every fact, number and name. Do not add anything the paragraphs do not support. Same language as the claim. No en dashes or em dashes. One sentence.
Return JSON only: {"claim":"..."}

CLAIM: %s

SOURCE PARAGRAPHS:
%s
"""
def fix(a, pm):
    src = ' '.join(pm.get(a['chapter'], {}).get(p, '') for p in a['paras'])
    for attempt in range(2):
        try:
            r = ea.post({'model': ea.MODEL, 'messages': [{'role': 'user', 'content': RP % (a['claim'], src)}]})
            t = r['choices'][0]['message']['content']; new = json.loads(t[t.index('{'):t.rindex('}') + 1])['claim'].strip()
        except Exception as e: continue
        if new and longest_shared(new, src) <= 12 and len(words(new)) >= 5: return new
    return None
def main():
    slug = ea.sys.argv[0] if False else sys.argv_keep[1]; dry = '--dry' in sys.argv_keep
    f = f'{OUT}/{slug}.jsonl'; at = [json.loads(l) for l in open(f)]; pm = paras_for(slug)
    bad = [i for i, a in enumerate(at) if longest_shared(a['claim'], ' '.join(pm.get(a['chapter'], {}).get(p, '') for p in a['paras'])) >= 13]
    print(slug, 'atoms', len(at), 'copying', len(bad), f'({len(bad)/len(at):.1%})', flush=True)
    with concurrent.futures.ThreadPoolExecutor(6) as ex: res = list(ex.map(lambda i: fix(at[i], pm), bad))
    ok = 0; ex_pairs = []
    for i, new in zip(bad, res):
        if new:
            ok += 1
            if len(ex_pairs) < 3: ex_pairs.append((at[i]['claim'], new))
            if not dry: at[i] = dict(at[i], claim=new, rewritten=True)
    left = sum(1 for i in bad if not any(i == j and n for j, n in zip(bad, res)))
    print('rewritten', ok, 'kept old (failed verify)', len(bad) - ok)
    for o, n in ex_pairs: print('  OLD:', o[:160], '\n  NEW:', n[:160])
    if not dry:
        os.makedirs(f'{OUT}/_prev', exist_ok=True)
        shutil.copy(f, f"{OUT}/_prev/{slug}.{datetime.datetime.now():%Y%m%dT%H%M%S}.prerewrite.jsonl")
        open(f, 'w').write(''.join(json.dumps(a, ensure_ascii=False) + '\n' for a in at))
main()
