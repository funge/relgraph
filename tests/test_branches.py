# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Original finite-assignment oracle for partial choice maps."""

from itertools import product
import unittest

from relgraph_eval.branches import (
    BRANCH_MAP_MAX_ENTRIES,
    branch_choice,
    merge_branch_maps,
)


class BranchTests(unittest.TestCase):
    def test_union_matches_independent_assignment_intersection(self):
        sites = [object() for _ in range(3)]
        assignments = list(product((-1, 2), repeat=3))
        maps = [
            tuple((sites[i], c) for i, c in enumerate(row) if c is not None)
            for row in product((None, -1, 2), repeat=3)
        ]

        def admitted(mapping):
            return {
                a
                for a in assignments
                if all(
                    a[next(i for i, s in enumerate(sites) if s is site)] == choice
                    for site, choice in mapping
                )
            }

        for left, right in product(maps, repeat=2):
            expected = admitted(left) & admitted(right)
            result = merge_branch_maps(left, right)
            self.assertEqual(set() if result is None else admitted(result), expected)

    def test_identity_not_equality_or_hashing(self):
        class Site:
            __hash__ = None

            def __eq__(self, other):
                raise AssertionError("site equality must not be called")

        a, b = Site(), Site()
        result = merge_branch_maps(((a, 3),), ((b, 4),))
        self.assertIs(result[0][0], a)
        self.assertIs(result[1][0], b)
        self.assertIsNone(merge_branch_maps(((a, 3),), ((a, 4),)))

    def test_order_identity_and_exact_choices(self):
        a, b = object(), object()
        large = 10**100 + 1
        left = ((a, large),)
        self.assertIs(merge_branch_maps(left, ()), left)
        self.assertIs(merge_branch_maps((), left), left)
        self.assertIs(merge_branch_maps(left, left), left)
        self.assertIs(merge_branch_maps(left, ((a, large),)), left)
        self.assertEqual(merge_branch_maps(left, ((b, -large),)), left + ((b, -large),))
        self.assertIsNone(merge_branch_maps(left, ((a, large + 1),)))

    def test_budget_forgetting_and_conflict_priority(self):
        sites = [object() for _ in range(BRANCH_MAP_MAX_ENTRIES + 1)]
        left = tuple((s, 7) for s in sites[:-1])
        self.assertEqual(merge_branch_maps(left, ((sites[-1], 8),)), ())
        self.assertIsNone(merge_branch_maps(left, ((sites[-1], 8), (sites[0], 9))))
        self.assertEqual(len(merge_branch_maps(left[:-1], ((sites[-1], 8),))), 16)

    def test_attachment_forgets_conflict_without_rejecting_values(self):
        site = object()
        inherited = ((site, 5),)
        self.assertIs(branch_choice(inherited, None, 6), inherited)
        self.assertIs(branch_choice(inherited, site, None), inherited)
        self.assertEqual(branch_choice(inherited, site, 5), inherited)
        self.assertEqual(branch_choice(inherited, site, 6), ())


if __name__ == "__main__":
    unittest.main()
