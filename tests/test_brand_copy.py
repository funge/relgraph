# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only

"""Negative controls for owned prose and case-sensitive exclusions."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'brand_copy', Path(__file__).resolve().parents[1] / 'tools/check-brand-copy.py')
brand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brand)


class BrandCopyTests(unittest.TestCase):
    def test_rejects_title_sentence_and_link_copy(self):
        self.assertEqual(brand.violations('# Support\nClear this. [Help](https://EXAMPLE/xY)'),
                         ['Clear', 'Help', 'Support'])

    def test_names_are_exact_not_case_insensitive(self):
        self.assertEqual(brand.violations('GitHub and iOS; Github and IOS'), ['Github', 'IOS'])
        self.assertEqual(brand.violations('HTTP and HTTPS'), [])
        self.assertEqual(brand.violations('HTTPish HTTPSExtra'), ['HTTPSExtra', 'HTTPish'])
        self.assertEqual(brand.violations('Codex and Dot'), [])
        self.assertEqual(brand.violations('CodexExtra Dotty'),
                         ['CodexExtra', 'Dotty'])
        self.assertEqual(brand.violations('John Funge'), [])
        self.assertEqual(brand.violations('Jeffrey Tupper'), [])
        self.assertEqual(brand.violations('Jeffrey TupperExtra'), ['Jeffrey', 'TupperExtra'])
        self.assertEqual(brand.violations("Tupper's work"), [])
        self.assertEqual(brand.violations('TupperExtra'), ['TupperExtra'])
        self.assertEqual(brand.violations('John FungeExtra'), ['FungeExtra', 'John'])
        self.assertEqual(brand.violations('GNU Affero General Public License'), [])
        self.assertEqual(brand.violations('GNU Affero General Public LicenseExtra'),
                         ['Affero', 'GNU', 'General', 'LicenseExtra', 'Public'])

    def test_gia_research_name_is_exact(self):
        self.assertEqual(brand.violations(
            '[GIA](https://github.com/funge/gia); relgraph does not depend on GIA.'), [])
        self.assertEqual(brand.violations('Gia GIAExtra'), ['GIAExtra', 'Gia'])

    def test_readme_technical_names_are_exact(self):
        names = ('AGPL', 'GMP', 'Lean', 'MPFR', 'TestFlight', 'UI')
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(brand.violations(name), [])
                # Neither a capitalized suffix nor a prefix is exempted.
                for other in (name + 'Extra', 'Extra' + name):
                    self.assertEqual(brand.violations(other), [other])
        for other in ('Agpl', 'Gmp', 'LEAN', 'Mpfr', 'Testflight', 'Ui'):
            with self.subTest(unapproved=other):
                self.assertEqual(brand.violations(other), [other])
        self.assertEqual(brand.violations(
            'AGPL, GMP, Lean, MPFR, TestFlight and UI; Unexpected Copy.'),
            ['Copy', 'Unexpected'])

    def test_preserves_code_and_destinations(self):
        self.assertEqual(brand.violations('`X + Y` [formula](https://example/X)\n```c\nX_API\n```'), [])

    def test_accessibility_copy_is_checked(self):
        self.assertEqual(brand.violations('<img src="X.png" alt="Graph"><a aria-label="Open">help</a>'),
                         ['Graph', 'Open'])

    def test_exact_draft_marker_does_not_hide_other_brackets(self):
        self.assertEqual(brand.violations('[CONFIRM DATE] [Unexpected Copy]'), ['Copy', 'Unexpected'])

    def test_bibliography_is_preserved(self):
        self.assertEqual(brand.violations(brand.TITLES[0]), [])
        self.assertEqual(brand.violations('Graphing is Easy'), ['Easy', 'Graphing'])

    def test_lowercase_passes(self):
        self.assertEqual(brand.violations('## privacy and help\nrestore your unfinished graph.'), [])


if __name__ == '__main__':
    unittest.main()
