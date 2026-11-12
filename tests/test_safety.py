"""Offline safety checks: no network, no API keys, no real books."""
import os, sys, tempfile, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'ingest'))
from epubtools import Epub, safe_ext

def bad_epub(name, data=b'x', **kw):
    p = os.path.join(tempfile.mkdtemp(), 'bad.epub')
    with zipfile.ZipFile(p, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('META-INF/container.xml', '<container/>')
        z.writestr(name, data)
    return p

def refused(p):
    try: Epub(p)
    except ValueError: return True
    except Exception: return False
    return False

def test_path_traversal_refused():
    assert refused(bad_epub('../../etc/evil.html'))
    assert refused(bad_epub('/abs/evil.html'))

def test_zip_bomb_refused():
    assert refused(bad_epub('OEBPS/bomb.html', b'0' * 50_000_000))

def test_figure_extension_is_sanitised():
    assert safe_ext('img/a.PNG') == '.png'
    assert safe_ext('img/a.png/../../x') == '.bin'
    assert safe_ext('img/a.p/ng') == '.bin'
    assert safe_ext('img/noext') == '.bin'

def test_example_epub_still_opens():
    e = Epub(os.path.join(HERE, '..', 'example', 'field-guide-to-keeping-notes.epub'))
    assert e.spine

if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'): f(); print('ok', k)
