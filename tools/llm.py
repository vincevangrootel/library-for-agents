"""One place for every model call. Pick a route with LIBRARY_LLM; every caller gets an
OpenAI-style response {'choices':[{'message':{'content':...}}], 'usage':{'cost':USD}}.

  LIBRARY_LLM      key / login it needs                    billed as
  openrouter       OPENROUTER_API_KEY (default)            pay per token
  anthropic        ANTHROPIC_API_KEY                       pay per token
  openai           OPENAI_API_KEY                          pay per token
  claude-code      `claude` CLI logged in (Pro/Max)        your Claude subscription quota
  codex            `codex` CLI logged in (ChatGPT plan)    your ChatGPT subscription quota

Embeddings are a separate route (LIBRARY_EMBED_PROVIDER: openrouter | voyage | openai), because
subscriptions do not include an embeddings endpoint.
"""
import json, os, re, subprocess, tempfile, time, urllib.request

ROUTE = os.environ.get('LIBRARY_LLM', 'openrouter').strip().lower()
ROUTES = ('openrouter', 'anthropic', 'openai', 'claude-code', 'codex')
UA = {'User-Agent': 'Mozilla/5.0 (library-tools)'}

# Recommended models per route: (atoms, judge). Atoms = cheap and careful; judge = stronger, different.
DEFAULTS = {
    'openrouter':  ('deepseek/deepseek-v4.1-flash', 'anthropic/claude-sonnet-5.5'),
    'anthropic':   ('claude-haiku-5-5', 'claude-sonnet-5-5'),
    'openai':      ('gpt-5.6-luna', 'gpt-5.6-terra'),
    'claude-code': ('haiku', 'sonnet'),
    'codex':       ('', ''),          # empty = the model set in your Codex config
}
# USD per 1M tokens (input, output), list prices November 2026, used only for estimates and API cost records.
PRICES = {
    'deepseek/deepseek-v4.1-flash': (0.051, 0.567), 'anthropic/claude-haiku-5.5': (0.10, 0.50),
    'anthropic/claude-sonnet-5.5': (2.0, 10.0), 'anthropic/claude-opus-5.5': (4.0, 20.0),
    'claude-haiku-5-5': (0.10, 0.50), 'claude-sonnet-5-5': (2.0, 10.0), 'claude-opus-5-5': (4.0, 20.0),
    'gpt-5.6-luna': (0.20, 1.20), 'gpt-5.6-terra': (2.0, 12.0), 'gpt-5.6-sol': (4.0, 20.0),
    'openai/gpt-5.6-luna': (0.20, 1.20), 'openai/gpt-5.6-terra': (2.0, 12.0),
}
SUBSCRIPTION = ROUTE in ('claude-code', 'codex')

def atom_model(): return os.environ.get('LIBRARY_ATOM_MODEL') or DEFAULTS[ROUTE][0]
def judge_model(): return os.environ.get('LIBRARY_JUDGE_MODEL') or DEFAULTS[ROUTE][1]

def _http(url, body, headers, timeout=300):
    req = urllib.request.Request(url, json.dumps(body).encode(), {**UA, 'Content-Type': 'application/json', **headers})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def _price(model, i, o):
    p = PRICES.get(model); return (i * p[0] + o * p[1]) / 1e6 if p else 0.0

def _wrap(text, cost): return {'choices': [{'message': {'content': text}}], 'usage': {'cost': cost}}

def _prompt(msgs): return '\n\n'.join(m['content'] for m in msgs if m['role'] != 'system')

def _system(msgs): return '\n\n'.join(m['content'] for m in msgs if m['role'] == 'system')

def _call(p):
    model = p.get('model') or atom_model(); msgs = p['messages']; mx = p.get('max_tokens')
    if ROUTE == 'openrouter':
        base = os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')
        return _http(base + '/chat/completions', {**p, 'model': model}, {'Authorization': 'Bearer ' + os.environ['OPENROUTER_API_KEY']})
    if ROUTE == 'anthropic':
        b = {'model': model, 'max_tokens': mx or 8000, 'messages': [m for m in msgs if m['role'] != 'system']}
        if _system(msgs): b['system'] = _system(msgs)
        if 'temperature' in p: b['temperature'] = p['temperature']
        r = _http('https://api.anthropic.com/v1/messages', b, {'x-api-key': os.environ['ANTHROPIC_API_KEY'], 'anthropic-version': '2023-06-01'})
        u = r.get('usage', {}); text = ''.join(c.get('text', '') for c in r.get('content', []))
        return _wrap(text, _price(model, u.get('input_tokens', 0), u.get('output_tokens', 0)))
    if ROUTE == 'openai':
        b = {'model': model, 'messages': msgs}
        if mx: b['max_completion_tokens'] = max(mx, 2000)   # reasoning models need headroom
        r = _http('https://api.openai.com/v1/chat/completions', b, {'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']})
        u = r.get('usage', {})
        return _wrap(r['choices'][0]['message'].get('content') or '', _price(model, u.get('prompt_tokens', 0), u.get('completion_tokens', 0)))
    if ROUTE == 'claude-code':
        cmd = ['claude', '-p', '--output-format', 'json', '--tools', '', '--no-session-persistence', '--setting-sources', '',
               '--system-prompt', _system(msgs) or 'You are a precise text-processing function. Follow the instructions exactly and output only what is asked.']
        if model: cmd += ['--model', model]
        env = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}   # force the subscription login
        r = subprocess.run(cmd, input=_prompt(msgs), capture_output=True, text=True, timeout=900, env=env)
        d = json.loads(r.stdout or '{}')
        if r.returncode or d.get('is_error'): raise RuntimeError('claude: ' + (d.get('result') or r.stderr)[:300])
        return _wrap(d.get('result') or '', 0.0)
    if ROUTE == 'codex':
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'out.txt')
            cmd = ['codex', 'exec', '--skip-git-repo-check', '--ephemeral', '--sandbox', 'read-only', '-C', tmp, '-o', out]
            if model: cmd += ['-m', model]
            env = {k: v for k, v in os.environ.items() if k != 'OPENAI_API_KEY'}
            r = subprocess.run(cmd + ['-'], input=(_system(msgs) + '\n\n' if _system(msgs) else '') + _prompt(msgs),
                               capture_output=True, text=True, timeout=900, env=env)
            if r.returncode or not os.path.exists(out): raise RuntimeError('codex: ' + (r.stderr or r.stdout)[-300:])
            return _wrap(open(out).read(), 0.0)
    raise SystemExit(f'LIBRARY_LLM={ROUTE!r} is not one of {", ".join(ROUTES)}')

def chat(payload, tries=4):
    last = None
    for a in range(tries):
        try: return _call(payload)
        except SystemExit: raise
        except Exception as e:
            last = e; time.sleep(min(60, 2 ** a * (5 if SUBSCRIPTION else 1)))   # subscriptions rate-limit harder
    raise last

def workers(default):
    """Parallel calls: subscriptions are CLI processes with rate limits, so keep them low."""
    return int(os.environ.get('LIBRARY_WORKERS') or (2 if SUBSCRIPTION else default))

def ready():
    """(ok, message) for doctor."""
    need = {'openrouter': 'OPENROUTER_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY', 'openai': 'OPENAI_API_KEY'}
    if ROUTE in need: return bool(os.environ.get(need[ROUTE])), need[ROUTE]
    exe = 'claude' if ROUTE == 'claude-code' else 'codex'
    try:
        if ROUTE == 'claude-code':
            r = subprocess.run(['claude', 'auth', 'status'], capture_output=True, text=True, timeout=30)
            return '"loggedIn": true' in r.stdout, 'claude CLI logged in (claude auth login)'
        r = subprocess.run(['codex', 'login', 'status'], capture_output=True, text=True, timeout=30)
        return r.returncode == 0 and 'Logged in' in (r.stdout + r.stderr), 'codex CLI logged in (codex login)'
    except FileNotFoundError:
        return False, f'{exe} CLI installed'

# ---- embeddings ----
EMBED_ROUTE = os.environ.get('LIBRARY_EMBED_PROVIDER', 'openrouter').strip().lower()
EMBED_DEFAULTS = {'openrouter': 'qwen/qwen3-embedding-8b', 'voyage': 'voyage-4-large', 'openai': 'text-embedding-3-large'}
# Vectors are cut to this many dimensions and re-normalised (Matryoshka). Measured: no quality loss at 1024 for
# qwen3-embedding-8b and nemotron; keeps the index 4x smaller. Must be the same for building and searching.
EMBED_DIMS = int(os.environ.get('LIBRARY_EMBED_DIMS') or 1024)
def embed_model(): return os.environ.get('LIBRARY_EMBED_MODEL') or EMBED_DEFAULTS[EMBED_ROUTE]
def embed_key_name(): return {'openrouter': 'OPENROUTER_API_KEY', 'voyage': 'VOYAGE_API_KEY', 'openai': 'OPENAI_API_KEY'}[EMBED_ROUTE]

def embed(texts, input_type='document', tries=5):
    """Returns (vectors, usage dict with 'cost' when the provider reports it)."""
    model = embed_model(); key = os.environ[embed_key_name()]
    if input_type == 'query' and 'qwen3-embedding' in model:     # Qwen3 expects an instruction on queries only
        texts = ['Instruct: Given a question or statement, retrieve the book passage that answers or makes it\nQuery: ' + x for x in texts]
    if EMBED_ROUTE == 'openrouter':
        url = os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/') + '/embeddings'; b = {'model': model, 'input': texts}
    elif EMBED_ROUTE == 'voyage':
        url = 'https://api.voyageai.com/v1/embeddings'; b = {'model': model, 'input': texts, 'input_type': input_type}
    else:
        url = 'https://api.openai.com/v1/embeddings'; b = {'model': model, 'input': texts}
    for a in range(tries):
        try:
            r = _http(url, b, {'Authorization': 'Bearer ' + key}, timeout=180)
            vs = [x['embedding'][:EMBED_DIMS] for x in sorted(r['data'], key=lambda x: x['index'])]
            vs = [[c / n for c in v] for v in vs for n in [sum(c * c for c in v) ** 0.5 or 1.0]]
            return vs, r.get('usage', {})
        except Exception as e:
            err = e; time.sleep(2 ** a)
    raise err
