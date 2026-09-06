#!/usr/bin/env python3
"""Check CSS theme hooks in the shipped HTML and its generated UI templates.

Run without arguments to audit, or --inventory to print every hook and source
location as JSON. This reads source; use a browser to check composed markup,
browser-inserted nodes, and newly exercised application states as well.
"""
from __future__ import annotations

import argparse
import bisect
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FILES = ('index.html', 'assets/construction-planner.js', 'assets/icon-sprites-v2.js')
TAGS = ('body main div section article aside header footer nav form fieldset '
        'details summary dialog table thead tbody tfoot tr th td ul ol li dl dt dd '
        'figure figcaption span iframe frame frameset canvas').split()
TAG = re.compile(r'<(' + '|'.join(TAGS) + r')\b', re.I)
NAME = re.compile(r'\sdata-ui=(?:"([a-z][a-z0-9-]*)"|\x27([a-z][a-z0-9-]*)\x27|([a-z][a-z0-9-]*)(?=[\s>"\x27`]))')
CREATED = re.compile(r'(\w+)\s*=\s*document\.createElement\(["\x27](' + '|'.join(TAGS) + r')["\x27]\)')


def mask_comments_and_data(source: str) -> str:
    """Preserve offsets while excluding comments and embedded JSON.

    Parse HTML before scanning JavaScript: literal HTML comment delimiters in
    JS strings are renderer data, not comments that span later functions.
    """
    blanks, scripts = [], []
    offsets = [0] + [m.end() for m in re.finditer('\n', source)]

    class Parser(HTMLParser):
        script = None

        def position(self):
            line, col = self.getpos()
            return offsets[line - 1] + col

        def handle_comment(self, data):
            blanks.append((self.position(), self.position() + len(data) + 7))

        def handle_starttag(self, tag, attrs):
            if tag == 'script':
                self.script = (self.position() + len(self.get_starttag_text()),
                               dict(attrs).get('type') == 'application/json')

        def handle_endtag(self, tag):
            if tag == 'script' and self.script:
                start, is_json = self.script
                (blanks if is_json else scripts).append((start, self.position()))
                self.script = None

    if source.lstrip().lower().startswith('<!doctype'):
        Parser(convert_charrefs=False).feed(source)
    else:
        scripts.append((0, len(source)))
    for start, end in scripts:
        i, quote = start, None
        while i < end:
            c = source[i]
            if quote:
                if c == '\\':
                    i += 2
                    continue
                if c == quote:
                    quote = None
            elif c in '"\x27`':
                quote = c
            elif source.startswith('//', i):
                stop = source.find('\n', i, end)
                stop = end if stop < 0 else stop
                blanks.append((i, stop))
                i = stop
                continue
            elif source.startswith('/*', i):
                stop = source.find('*/', i + 2, end)
                stop = end if stop < 0 else stop + 2
                blanks.append((i, stop))
                i = stop
                continue
            i += 1
    chars = list(source)
    for start, end in blanks:
        for i in range(start, end):
            if chars[i] not in '\r\n':
                chars[i] = ' '
    return ''.join(chars)


def audit(source: str):
    masked = mask_comments_and_data(source)
    newlines = [m.start() for m in re.finditer('\n', source)]
    hooks, missing = [], []
    for match in TAG.finditer(masked):
        line = bisect.bisect_left(newlines, match.start()) + 1
        # Hooks belong immediately after the opening tag, before dynamic attrs.
        name = NAME.match(masked, match.end())
        if name:
            hooks.append({'name': next(v for v in name.groups() if v), 'tag': match[1], 'line': line})
        else:
            missing.append({'line': line, 'tag': match[1], 'kind': 'markup'})
    for match in CREATED.finditer(masked):
        line = bisect.bisect_left(newlines, match.start()) + 1
        name = re.search(re.escape(match[1]) + r'\.dataset\.ui\s*=\s*["\x27]([a-z][a-z0-9-]*)["\x27]', masked[match.end():match.end() + 300])
        if name:
            hooks.append({'name': name[1], 'tag': match[2], 'line': line})
        else:
            missing.append({'line': line, 'tag': match[2], 'kind': 'createElement'})
    return hooks, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        # Deliberately missing names must fail, including late renderers after
        # strings containing HTML comment delimiters (a real source pattern).
        broken = '<!doctype html><div></div><script>const x="<!--";const h=\'<span></span>\';const node=document.createElement("div");</script>'
        assert len(audit(broken)[1]) == 3
        fixed = broken.replace('<div>', '<div data-ui=panel>').replace('<span>', '<span data-ui=label>').replace(');</script>', ');node.dataset.ui="frame";</script>')
        assert not audit(fixed)[1]
        assert len(audit(fixed)[0]) == 3
        assert audit('<!doctype html><!-- <div> --><script type="application/json">{"markup":"<div>"}</script>') == ([], [])
        print('UI naming audit self-test passed: missing markup and created nodes detected.')
        return 0
    report, inventory = [], []
    for filename in FILES:
        hooks, missing = audit((ROOT / filename).read_text(encoding='utf-8'))
        inventory.extend(dict(file=filename, **hook) for hook in hooks)
        report.append({'file': filename, 'definitions': len(hooks), 'missing': missing})
    if args.inventory:
        print(json.dumps(inventory, indent=2))
    else:
        print(json.dumps({'files': report, 'definitions': len(inventory),
                          'uniqueNames': len(Counter(h['name'] for h in inventory))}, indent=2))
    return int(any(row['missing'] for row in report))


if __name__ == '__main__':
    raise SystemExit(main())
