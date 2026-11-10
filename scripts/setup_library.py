#!/usr/bin/env python3
"""Create a new library folder from the template.

  setup_library.py DEST [--books DIR] [--no-git]

DEST must not exist or be empty. --books copies every .epub found in DIR into DEST/inbox/.
By default runs `git init` in DEST (the library is meant to be a private Git repo); --no-git skips it. Writes DEST/.library.env with the paths the tools use.
"""
import argparse, glob, os, shutil, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument('dest'); ap.add_argument('--books'); ap.add_argument('--no-git', action='store_true')
a = ap.parse_args()
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dest = os.path.abspath(os.path.expanduser(a.dest))
if os.path.exists(dest) and os.listdir(dest):
    sys.exit(f'{dest} is not empty; choose a new or empty folder')
shutil.copytree(os.path.join(repo, 'template'), dest, dirs_exist_ok=True)
os.makedirs(os.path.join(dest, 'inbox'), exist_ok=True)
os.makedirs(os.path.join(dest, 'index'), exist_ok=True)
n = 0
if a.books:
    for f in sorted(glob.glob(os.path.join(os.path.expanduser(a.books), '*.epub'))):
        shutil.copy2(f, os.path.join(dest, 'inbox')); n += 1
with open(os.path.join(dest, '.library.env'), 'w') as f:
    f.write(f'export LIBRARY_ROOT="{dest}"\nexport LIBRARY_INDEX="{dest}/index"\nexport LIBRARY_TOOLS="{repo}"\n# export OPENROUTER_API_KEY=...   (set in your shell, never commit it)\n# export LIBRARY_PUBLISH_REMOTE=myremote:library   (optional file storage)\n')
with open(os.path.join(dest, '.gitignore'), 'w') as f:
    f.write('.library.env\n.env\n__pycache__/\n')
if not a.no_git:
    subprocess.run(['git', 'init', '-q', '-b', 'main', dest], check=True)
print(f'library created at {dest}\n  EPUBs copied to inbox/: {n}\n  git repository: {"no" if a.no_git else "yes (keep it private)"}\n  next: cd {dest} && . .library.env   (then see SETUP.md step 4)')
