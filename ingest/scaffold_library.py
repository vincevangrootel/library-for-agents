#!/usr/bin/env python3
"""Create a new ICM-structured book library from template/.
  scaffold_library.py DEST            (DEST must not exist or be empty)
"""
import os, shutil, sys
src = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'template')
dest = sys.argv[1]
if os.path.exists(dest) and os.listdir(dest):
    sys.exit(f'{dest} is not empty')
shutil.copytree(src, dest, dirs_exist_ok=True)
print(f'library scaffolded at {dest}. Next: git init, add your first book with the stages in stages/.')
