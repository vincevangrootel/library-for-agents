"""Which book sections are reference material rather than body text.

Back-of-book indexes, notes, bibliographies, copyright pages, acknowledgements and similar sections
are left out of the search index: they match queries on keywords and citations, then crowd out the
passage that actually makes the point. Two signals:
  1. the section title (Index, Notes, Bibliography, Copyright, ...; EN + NL), and
  2. the content: at least 5 paragraphs, 70%+ of them citation-like (years, journals, URLs, page refs).
The manifest 'kind' (front/back) is not used: it is unreliable (real introductions are tagged 'front').
"""
import re

TITLE = re.compile(
    r'^(index(\s+of\s+\w+)?|register|(end)?notes|notes?\s+(and|&)\s+\w+|noten|bronnen|bronvermelding|sources|references|'
    r'bibliograph\w*|literatuur\w*|further reading|copyright(\s+page)?|colofon|acknowledg\w*|dankwoord|dankbetuiging|'
    r'about the (author|authors|book|publisher)|over de auteurs?|praise(\s+for\b.*)?|also by\b.*|follow penguin.*|promo\b.*|'
    r'what.s next on your reading list.*|contents|table of contents|inhoud(sopgave)?|epigraph|dedication|opdracht|'
    r'cover|title page|titelpagina)\s*[.:]?\s*$', re.I)
CITE = re.compile(r'(\b(1[89]|20)\d\d\)?[.,;:]|journal of|ibid\.?|op\. cit|\bpp?\.\s?\d|https?://|doi\.org|retrieved)', re.I)

def is_reference(title, paragraphs):
    """title: section title from the manifest; paragraphs: list of paragraph texts in that section."""
    if TITLE.match((title or '').strip()):
        return True
    n = len(paragraphs)
    return n >= 5 and sum(1 for p in paragraphs if CITE.search(p)) / n >= 0.7
