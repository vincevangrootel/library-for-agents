"""Sampled quality audit of atoms against ATOMS.md criteria, judged by a stronger model.
Usage: audit_atoms.py <slug> [n=24]   Writes ATOMS_OUT/_audit/<slug>.json and prints a summary.
Sample is seeded and spread across chapters. Judge sees the claim and its cited paragraphs only."""
import json, os, re, sys, random, collections, concurrent.futures
slug = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 24
sys.argv = ['x']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_atoms as ea
JUDGE = ea.llm.judge_model()
at = [json.loads(l) for l in open(f'{ea.OUT}/{slug}.jsonl')]
pm = {}
for d in json.load(open(f'{ea.ROOT}/books/{slug}/02-text/manifest.json'))['documents']:
    for l in open(f"{ea.ROOT}/books/{slug}/02-text/chapters/{d['md']}"):
        m = re.match(r'(.*) \^([\w-]+)$', l.rstrip('\n'))
        if m: pm.setdefault(d['id'], {})[m.group(2)] = m.group(1)
random.seed(int(os.environ.get("AUDIT_SEED", "7"))); by = collections.defaultdict(list)
for a in at: by[a['chapter']].append(a)
pool = []; chs = sorted(by)
while len(pool) < min(N, len(at)):
    for c in chs:
        if by[c] and len(pool) < N: pool.append(by[c].pop(random.randrange(len(by[c]))))
P = """You audit one "atom" from a book index. An atom is a short, self-contained statement of one idea the author makes, written in plain words, citing the paragraphs where the author says it.
Judge strictly. Return JSON only:
{"faithful":"yes|partly|no","self_contained":"yes|no","one_idea":"yes|no","kind":"idea|anecdote|example|name_drop|recommendation|other","worth_keeping":"yes|no","verdict":"keep|fix|drop","note":"max 15 words"}
faithful: do the paragraphs support the claim, nothing added? self_contained: readable alone, no 'this/the author/he' doing the work. kind=anecdote/example/name_drop/recommendation means the claim is a story detail or a pointer, not a transferable idea. worth_keeping: useful out of context.

CLAIM: %s

PARAGRAPHS:
%s
"""
def judge(a):
    src = '\n'.join(pm.get(a['chapter'], {}).get(p, '') for p in a['paras'])
    for _ in range(2):
        try:
            r = ea.post({'model': JUDGE, 'messages': [{'role': 'user', 'content': P % (a['claim'], src)}]})
            t = r['choices'][0]['message']['content']; j = json.loads(t[t.index('{'):t.rindex('}') + 1])
            return dict(a, judge=j)
        except Exception: pass
    return dict(a, judge=None)
with concurrent.futures.ThreadPoolExecutor(ea.llm.workers(6)) as ex: res = list(ex.map(judge, pool))
os.makedirs(f'{ea.OUT}/_audit', exist_ok=True)
json.dump(res, open(f'{ea.OUT}/_audit/{slug}.json', 'w'), ensure_ascii=False, indent=1)
ok = [r['judge'] for r in res if r['judge']]
c = lambda k, v: sum(1 for j in ok if j.get(k) == v)
print(f"{slug}: judged {len(ok)}/{len(res)} of {len(at)} atoms")
print(f"  verdict keep {c('verdict','keep')} fix {c('verdict','fix')} drop {c('verdict','drop')}")
print(f"  faithful yes {c('faithful','yes')} partly {c('faithful','partly')} no {c('faithful','no')}; self-contained no {c('self_contained','no')}; not-one-idea {c('one_idea','no')}")
print('  kinds', dict(collections.Counter(j.get('kind') for j in ok)))
for r in res:
    j = r['judge']
    if j and j['verdict'] != 'keep': print(f"  [{j['verdict']}/{j.get('kind')}/{j['faithful']}] {r['claim'][:110]} | {j.get('note','')}")
