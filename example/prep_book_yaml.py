#!/usr/bin/env python3
"""Resolve the one 'review' document (the title page) and set content_type in the example book.yaml. Usage: prep_book_yaml.py BOOKDIR"""
import sys, yaml
f = sys.argv[1] + '/book.yaml'; y = yaml.safe_load(open(f))
for d in y['documents']:
    if d['kind'] == 'review':
        d.update(kind='exclude', reason='title page'); d.pop('id', None)
y['content_type'] = 'nonfiction'  # required by the gate: nonfiction or fiction
yaml.safe_dump(y, open(f, 'w'), sort_keys=False, allow_unicode=True, width=100)
