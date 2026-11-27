# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Original direct cell-test controls; no compiler or renderer policy required."""

from dataclasses import FrozenInstanceError
import unittest
from test_dispatch import Context, Host
from relgraph_eval import cells
from relgraph_eval.definedness import BOOL_FALSE, BOOL_MAYBE, BOOL_TRUE
from relgraph_parser import parse_formula


class FormulaHost(Host):
    def __init__(self):
        super().__init__()
        self.relations = []

    def _refine_constant_set_relation(self, relation, left, right, truth):
        self.relations.append((relation, left, right))
        return truth


class CellTests(unittest.TestCase):
    def test_direct_truth_domain_and_witness_matrix(self):
        for truth, expected in (
            (BOOL_FALSE, cells.BoxClassificationState.ABSENT),
            (BOOL_MAYBE, cells.BoxClassificationState.UNDECIDED),
            (BOOL_TRUE, cells.BoxClassificationState.PRESENT),
        ):
            self.assertIs(cells.interval_cell_state(truth), expected)
            self.assertIs(
                cells.interval_cell_state(truth, valid=False),
                cells.BoxClassificationState.UNDECIDED,
            )
            without_witness = (
                cells.BoxClassificationState.ABSENT
                if truth is BOOL_FALSE
                else cells.BoxClassificationState.UNDECIDED
            )
            self.assertIs(
                cells.interval_cell_state(truth, has_witness=False), without_witness
            )
        self.assertIs(
            cells.interval_cell_state(None), cells.BoxClassificationState.UNDECIDED
        )
        self.assertIs(
            cells.interval_cell_state(object(), valid=False),
            cells.BoxClassificationState.UNDECIDED,
        )

    def test_ordered_conjunction_alternatives_and_capacity_inventory(self):
        source = parse_formula("x=0; y=0 or x>0")
        ops, host = Context(), FormulaHost()
        result = cells.evaluate_formula(
            source.alternatives, ops.point(1), ops.point(0), ops, host=host
        )
        ordered = [r for a in source.alternatives for r in a]
        self.assertEqual([id(r[0]) for r in host.relations], [id(r) for r in ordered])
        self.assertEqual(result.counts, cells.EvaluationCounts(3, 6, 6))
        self.assertEqual(result.required_branch_capacity, 6)
        self.assertEqual(
            [(a.relation_offset, a.relation_count) for a in result.alternatives],
            [(0, 2), (2, 1)],
        )
        self.assertIs(
            cells.interval_cell_state(result.truth),
            cells.BoxClassificationState.PRESENT,
        )
        with self.assertRaises(FrozenInstanceError):
            result.required_branch_capacity = 0

    def test_pole_open_boundary_and_crossing_remain_distinct(self):
        for source, x, expected in (
            ("x/x=1", (0, 0), "absent"),
            ("x>0", (0, 0), "absent"),
            ("x>=0", (0, 0), "present"),
            ("x=0", (-1, 1), "undecided"),
        ):
            ops = Context()
            result = cells.evaluate_formula(
                parse_formula(source).alternatives,
                ops.make(*x),
                ops.point(0),
                ops,
                host=FormulaHost(),
            )
            self.assertEqual(cells.interval_cell_state(result.truth).value, expected)

    def test_no_short_circuit_hides_later_host_error(self):
        source = parse_formula("x=0 or y=0")
        ops, host = Context(), FormulaHost()

        def refine(relation, left, right, truth):
            if relation is source.alternatives[1][0]:
                raise LookupError("later relation")
            return truth

        host._refine_constant_set_relation = refine
        with self.assertRaisesRegex(LookupError, "later relation"):
            cells.evaluate_formula(
                source.alternatives, ops.point(0), ops.point(0), ops, host=host
            )


if __name__ == "__main__":
    unittest.main()
