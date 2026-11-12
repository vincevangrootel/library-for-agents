
import json,os,glob,urllib.request,numpy as np,collections,re
import urllib.request as _ur; _o = _ur.build_opener(); _o.addheaders = [('User-Agent', 'Mozilla/5.0 (library-tools)')]; _ur.install_opener(_o)  # UA_HEADER: default Python UA is blocked at the OpenRouter edge (error 1010)
ROOT=os.environ.get('LIBRARY_ROOT', os.getcwd())
D=os.environ.get('LIBRARY_INDEX', os.path.join(ROOT,'index'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import llm
atoms=[]
for f in sorted(glob.glob(D+'/atoms/*.jsonl')):
    atoms+=[json.loads(l) for l in open(f)]
print('atoms',len(atoms))
# tag language sanity: share of tags with non-ascii vs book language
bad=collections.Counter()
for a in atoms:
    for t in a['tags']:
        if re.search(r'(sesgo|avali|estado|deporte)',t): bad[a['book']]+=1
print('suspect foreign tags',dict(bad))
def emb(texts):
    out=[]
    for i in range(0,len(texts),64): out+=llm.embed(texts[i:i+64],'document')[0]
    a=np.array(out,dtype=np.float32); return a/np.linalg.norm(a,axis=1,keepdims=True)
E=emb([a['claim'] for a in atoms])
np.save(D+'/atoms/atom_vectors.npy',E.astype(np.float16))
books=[a['book'] for a in atoms]
S=E@E.T
pairs=[]
for i in range(len(atoms)):
    for j in range(i+1,len(atoms)):
        if books[i]!=books[j]: pairs.append((float(S[i,j]),i,j))
pairs.sort(reverse=True)
# mutual-best, one per atom, diversify by book pair
seen=set();sel=[];bp=collections.Counter()
for s,i,j in pairs:
    if i in seen or j in seen: continue
    k=tuple(sorted((books[i],books[j])))
    if bp[k]>=8: continue
    sel.append((s,i,j));seen|={i,j};bp[k]+=1
links=[dict(score=round(s,3),a=f"{atoms[i]['book']}#{atoms[i]['paras'][0]}",b=f"{atoms[j]['book']}#{atoms[j]['paras'][0]}",claim_a=atoms[i]['claim'],claim_b=atoms[j]['claim']) for s,i,j in sel]
json.dump(links,open(D+'/atoms/links_candidates.json','w'),indent=1,ensure_ascii=False)
print('cross-book pairs >0.75:',sum(1 for p in pairs if p[0]>0.75),' >0.70:',sum(1 for p in pairs if p[0]>0.70),' bookpairs',dict(bp))
step=max(1,len(links)//20)
for l in links[:60:3][:20]:
    print(f"\n{l['score']}  {l['a'].split('#')[0][:18]} <> {l['b'].split('#')[0][:18]}\n A: {l['claim_a'][:200]}\n B: {l['claim_b'][:200]}")
