#!/usr/bin/env python3
"""Generate a small synthetic non-fiction EPUB (original text, public domain / CC0) for trying the pipeline.
Usage: make_example_epub.py OUT.epub"""
import sys, zipfile

TITLE, AUTHOR = "A Field Guide to Keeping Notes", "Alex Example"
CHAPTERS = [
 ("Why Notes Fail", [
  "Most note collections fail because the writer treats them as storage. A note that is only stored is never read again, so it has no effect on later decisions.",
  "A useful note answers a question the writer expects to ask later. Writing the question down next to the note makes it far easier to find when the moment arrives.",
  "Long notes tend to be abandoned. Short notes with one idea each are more likely to be reused, because the reader can judge their relevance in a few seconds.",
  "Copying a passage word for word feels productive but teaches little. Restating the idea in your own words forces you to find out whether you understood it.",
  "Notes that are never reviewed decay in value. A weekly review of five minutes keeps the collection connected to current work.",
  "The most common mistake is collecting without a purpose. Before saving anything, decide which project or question it could help with.",
 ]),
 ("Structure Without Rigidity", [
  "A folder tree forces every note into one place, but ideas usually belong to several topics at once. Links between notes solve this without duplicating anything.",
  "Tags are cheap to add and cheap to ignore. They work best when the vocabulary is small and agreed in advance, because synonyms split a topic into pieces nobody finds.",
  "An index note for each active project gives a single starting point. Without it, the reader must remember which keywords were used months ago.",
  "Over-engineered systems collapse under their own maintenance cost. If updating the structure takes longer than writing the note, the structure will be dropped.",
  "Dates on notes help when the order of events matters, such as in decisions or experiments. For timeless ideas the date adds clutter and can be left out.",
  "A naming rule that states the main claim in the title lets the reader scan a list and understand it without opening every item.",
 ]),
 ("Retrieval and Reuse", [
  "Search is only as good as the words in the note. Writing in plain language, and including the terms you would type when looking for it, improves recall.",
  "Reuse is the real test of a note. After a month, count how many notes were actually opened for work; this number says more than the size of the collection.",
  "Quoting a source with a precise location lets you verify a claim later. A note that says only 'a book argued this' cannot be checked and should be treated as a rumour.",
  "When two notes disagree, keep both and record the conflict. Deleting the less convenient one hides information that may matter later.",
  "Summaries written after a delay are better than summaries written at once. Time removes the details that felt important but were not.",
  "Sharing notes with a colleague exposes unclear wording quickly. If a reader needs explanation, the note should be rewritten until it does not.",
 ]),
 ("A Minimal Routine", [
  "A small routine beats an ambitious one that is abandoned. Capture during the day, process once, and review weekly; nothing else is required.",
  "During capture, accept rough wording. The purpose of that step is speed, and polishing at that point interrupts the work the note comes from.",
  "During processing, each rough item is either turned into a clear note, merged into an existing one, or discarded. Leaving items undecided turns the inbox into a pile.",
  "During review, scan recent notes for ones that should be linked and for questions that were never answered. These two checks keep the collection useful.",
  "Measure the routine by what it produces, such as decisions made faster or fewer repeated searches, not by the count of notes created.",
  "Revisit the routine every few months and remove any step that no longer earns its time. A system should shrink as the habit grows.",
 ]),
]

def xhtml(title, body):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en"><head><title>%s</title></head><body>\n%s\n</body></html>' % (title, body))

def build(out):
    files = {}
    ids = []
    for n, (t, ps) in enumerate(CHAPTERS, 1):
        t = '%d. %s' % (n, t)
        body = '<h1 class="cht">%s</h1>\n' % t + '\n'.join('<p class="body">%s</p>' % p for p in ps)
        files['ch%02d.xhtml' % n] = xhtml(t, body)
        ids.append('ch%02d' % n)
    files['title.xhtml'] = xhtml(TITLE, '<h1 class="title">%s</h1><p class="author">%s</p>' % (TITLE, AUTHOR))
    nav = ''.join('<li><a href="ch%02d.xhtml">%d. %s</a></li>' % (n, n, t) for n, (t, _) in enumerate(CHAPTERS, 1))
    files['nav.xhtml'] = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head><body><nav epub:type="toc"><ol>%s</ol></nav></body></html>' % nav)
    manifest = '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>' + ''.join('<item id="%s" href="%s.xhtml" media-type="application/xhtml+xml"/>' % (i, i) for i in ids)
    spine = '<itemref idref="title"/>' + ''.join('<itemref idref="%s"/>' % i for i in ids)
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bid">urn:uuid:00000000-0000-4000-8000-000000000001</dc:identifier><dc:title>%s</dc:title><dc:creator>%s</dc:creator><dc:language>en</dc:language><meta property="dcterms:modified">2026-01-01T00:00:00Z</meta></metadata><manifest>%s</manifest><spine>%s</spine></package>' % (TITLE, AUTHOR, manifest, spine))
    container = '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
    with zipfile.ZipFile(out, 'w') as z:
        z.writestr(zipfile.ZipInfo('mimetype', (2026, 1, 1, 0, 0, 0)), 'application/epub+zip', zipfile.ZIP_STORED)
        z.writestr(zipfile.ZipInfo('META-INF/container.xml', (2026, 1, 1, 0, 0, 0)), container, zipfile.ZIP_DEFLATED)
        z.writestr(zipfile.ZipInfo('OEBPS/content.opf', (2026, 1, 1, 0, 0, 0)), opf, zipfile.ZIP_DEFLATED)
        for k, v in files.items():
            z.writestr(zipfile.ZipInfo('OEBPS/' + k, (2026, 1, 1, 0, 0, 0)), v, zipfile.ZIP_DEFLATED)

if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'field-guide-to-keeping-notes.epub')
