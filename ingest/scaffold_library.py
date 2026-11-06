#!/usr/bin/env python3
"""Kept for compatibility. Use scripts/setup_library.py instead."""
import os, subprocess, sys
sys.exit(subprocess.call([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'setup_library.py'), *sys.argv[1:]]))
