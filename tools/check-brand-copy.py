#!/usr/bin/env python3
# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only

"""Check owned public-home Markdown, never rewrite content or scan C/source code."""

from html.parser import HTMLParser
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('README.md', 'PRIVACY.md', 'SUPPORT.md')
# Exact names, not broad capitalization patterns. Keep rationales reviewable.
NAMES = {
    'AGPL': 'license abbreviation in the public licensing statement',
    'GMP': 'numeric dependency project name',
    'Lean': 'proof assistant name in the related research description',
    'MPFR': 'numeric dependency project name',
    'TestFlight': 'official distribution service name',
    'UI': 'explicitly retained abbreviation in the public repository scope description',
    'GIA': 'proper name of the related Generalized Interval Arithmetic research project',
    'HTTP': 'web protocol in the attribution address explanation',
    'HTTPS': 'secure web protocol in the attribution address explanation',
    'Codex': 'coding agent named in the project motivation',
    'Dot': 'user-chosen proper name of the coding agent in project attribution',
    'GrafEq': 'credited product spelling in the public-home source',
    'Pedagoguery Software': 'publisher name',
    'Windows': 'operating system product',
    'Classic Macintosh': 'historical platform name',
    'GitHub': 'service name',
    'App Store': 'store name',
    'iPhone': 'device product',
    'iOS': 'operating system product',
    'GNU Affero General Public License': 'exact name of the project license',
    'John Funge': 'copyright holder attribution retained from the original license',
    'C': 'programming language name',
    'Jeffrey Allen Tupper': 'research author',
    'Jeffrey Tupper': 'research author as credited in the thesis bibliography',
    'Tupper': 'research author surname in the GrafEq introduction',
    'Jeff Tupper': 'research author',
    'University of Toronto': 'institution',
    'SIGGRAPH': 'conference name',
    'MSc': 'degree designation in exact bibliographic attribution',
}
# Bibliographic titles preserve source attribution rather than product styling.
TITLES = (
    'Graphing Equations with Generalized Interval Arithmetic',
    'Reliable Two-Dimensional Graphing Methods for Mathematical Formulae with Two Free Variables',
)
# Draft editorial markers, exact and finite; not published product copy.
DRAFT_MARKERS = (
    '[CONFIRM DATE]', '[CONFIRM PUBLISHER NAME]', '[PUBLISHER NAME]',
    '[CONFIRM HOST]',
    '[CONFIRM final release logging and any device/OS diagnostic-sharing implications before publication.]',
    '[CONFIRM how support information is used, retained and deleted, and how to request deletion.]',
    '[DECIDE a safe route for requests that cannot be made publicly.]',
)


class VisibleHTML(HTMLParser):
    """Include accessibility copy, exclude markup and machine attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        self.parts.extend(value for key, value in attrs
                          if key in ('alt', 'title', 'aria-label') and value)


def visible_markdown(source):
    """Extract the small Markdown subset used by these three explicit pages."""
    lines = []
    fence = None
    for line in source.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            marker = match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is None:
            lines.append(line)
    source = '\n'.join(lines)
    source = re.sub(r'(`+).*?\1', '', source, flags=re.DOTALL)
    # Link text is owned visible copy; destinations retain exact case.
    source = re.sub(r'(!?\[[^\]\n]*\])\([^\s)]*\)', r'\1', source)
    parser = VisibleHTML()
    parser.feed(source)
    return ' '.join(' '.join(parser.parts).split())


def violations(source):
    visible = visible_markdown(source)
    for literal in (*DRAFT_MARKERS, *TITLES, *sorted(NAMES, key=len, reverse=True)):
        visible = re.sub(r'(?<!\w)' + re.escape(literal) + r'(?!\w)', '', visible)
    return sorted(set(word for word in re.findall(r'[^\W\d_]+', visible)
                      if any(character.isupper() for character in word)))


def main():
    failed = False
    for name in PAGES:
        words = violations((ROOT / name).read_text())
        if words:
            failed = True
            print(f'{name}: unexpected capitals: {", ".join(words)}')
    if not failed:
        print('brand copy: README, privacy and support passed')
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
