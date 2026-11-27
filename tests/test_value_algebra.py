# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Original finite/exact controls, independent of any application or native loader."""

import ctypes
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import math
import operator
from pathlib import Path
import subprocess
import sys
import unittest

from relgraph_eval import arithmetic, charts, comparisons, metadata, scalars, sets
from relgraph_eval.definedness import BOOL_FALSE, BOOL_MAYBE, BOOL_TRUE, BoolInterval
from relgraph_eval.values import (
    _AffineCoordinate,
    _CInterval,
    _ChartDomain,
    _EvalResult,
    _EvalSet,
    _IntervalAffine,
    _QuadraticCoordinate,
    _ReciprocalAffineCoordinate,
)


def bounds(value):
    return value.lo, value.hi


def truth(value):
    return bool(value.lo), bool(value.hi)


def branch(lo, hi=None, **kwargs):
    return _EvalResult(
        _CInterval(lo, lo if hi is None else hi), BOOL_TRUE, True, **kwargs
    )


class ExactFixtureOps:
    """Only exact dyadic arithmetic and perfect roots; never a production backend.

    Fraction checks reject accidental rounded fixture arithmetic. Comparisons
    exhaust a half-unit grid, which includes every endpoint in these fixtures.
    """

    def __init__(self):
        self.events = []

    def make(self, lo, hi):
        return _CInterval(lo, hi)

    def point(self, value):
        return self.make(value, value)

    def is_empty(self, value):
        return math.isnan(value.lo) or math.isnan(value.hi) or value.lo > value.hi

    def intersect(self, x, y):
        return self.make(max(x.lo, y.lo), min(x.hi, y.hi))

    def hull(self, x, y):
        return self.make(min(x.lo, y.lo), max(x.hi, y.hi))

    def neg(self, x):
        return self.make(-x.hi, -x.lo)

    def exact(self, value):
        result = float(value)
        assert Fraction(result) == value, "fixture must be exactly representable"
        return result

    def arithmetic(self, x, y, op):
        values = [op(Fraction(a), Fraction(b)) for a in bounds(x) for b in bounds(y)]
        return self.make(self.exact(min(values)), self.exact(max(values)))

    def add(self, x, y):
        return self.arithmetic(x, y, operator.add)

    def sub(self, x, y):
        return self.arithmetic(x, y, operator.sub)

    def mul(self, x, y):
        return self.arithmetic(x, y, operator.mul)

    def sqrt(self, x):
        a, b = math.sqrt(x.lo), math.sqrt(x.hi)
        assert Fraction(a) ** 2 == Fraction(x.lo)
        assert Fraction(b) ** 2 == Fraction(x.hi)
        return self.make(a, b)

    def compare(self, x, y, op):
        if self.is_empty(x) or self.is_empty(y):
            return BOOL_FALSE
        pairs = [
            op(Fraction(a, 2), Fraction(b, 2))
            for a in range(int(x.lo * 2), int(x.hi * 2) + 1)
            for b in range(int(y.lo * 2), int(y.hi * 2) + 1)
        ]
        return BoolInterval(all(pairs), any(pairs))

    def eq(self, x, y):
        return self.compare(x, y, operator.eq)

    def lt(self, x, y):
        return self.compare(x, y, operator.lt)

    def le(self, x, y):
        return self.compare(x, y, operator.le)

    def gt(self, x, y):
        return self.compare(x, y, operator.gt)

    def ge(self, x, y):
        return self.compare(x, y, operator.ge)

    def record_operator_sections(self, name, count, **kwargs):
        self.events.append(("sections", name, count, kwargs))

    def record_chart_loss(self, name, expression, reason, **kwargs):
        self.events.append(("loss", name, expression, reason, kwargs))


class ValueAlgebraTests(unittest.TestCase):
    def setUp(self):
        self.ops = ExactFixtureOps()

    def test_layout_frozen_records_and_signed_zero_key(self):
        self.assertEqual(ctypes.sizeof(_CInterval), 2 * ctypes.sizeof(ctypes.c_double))
        self.assertEqual(_CInterval.hi.offset, ctypes.sizeof(ctypes.c_double))
        value = branch(-0.0, 0.0)
        self.assertEqual(value.branch_map, ())
        self.assertIsNone(value.chart)
        with self.assertRaises(FrozenInstanceError):
            value.constant = 1
        self.assertEqual(
            scalars._interval_cache_key(value.interval), ("-0x0.0p+0", "0x0.0p+0")
        )

    def test_directed_endpoints_exact_enclosure_and_optimality(self):
        values = [
            Fraction(0),
            Fraction(1, 3),
            Fraction(7, 8),
            Fraction(2**53 + 1),
            Fraction(1, 2**1075),
            Fraction(3, 2**1075),
            Fraction(2**1100),
        ]
        for value in values + [-x for x in values]:
            with self.subTest(value=str(value)):
                lo = scalars._fraction_lower_float(value)
                hi = scalars._fraction_upper_float(value)
                if math.isfinite(lo):
                    self.assertLessEqual(Fraction(lo), value)
                else:
                    self.assertEqual(lo, -math.inf)
                if math.isfinite(hi):
                    self.assertGreaterEqual(Fraction(hi), value)
                else:
                    self.assertEqual(hi, math.inf)
                successor = math.nextafter(lo, math.inf)
                predecessor = math.nextafter(hi, -math.inf)
                if math.isfinite(successor):
                    self.assertGreater(Fraction(successor), value)
                if math.isfinite(predecessor):
                    self.assertLess(Fraction(predecessor), value)

    def test_exact_metadata_admission_and_budgets(self):
        self.assertIsNone(metadata._make_affine("x", Fraction(1, 3), 0))
        self.assertEqual(
            metadata._make_affine("y", Fraction(3, 8), 2),
            _AffineCoordinate("y", 0.375, 2),
        )
        self.assertIsNone(scalars._exact_metadata_float(Fraction(2**53 + 1)))
        self.assertIsNone(scalars._exact_metadata_float(Fraction(2**1100)))
        self.assertIsNone(
            metadata._binary_constant(
                branch(1, constant=1), branch(3, constant=3), "div"
            )
        )
        self.assertEqual(metadata._power_constant(2, 32), 2**32)
        self.assertIsNone(metadata._power_constant(2, 33))
        self.assertIsNone(metadata._power_constant(0, -1))
        self.assertIsNotNone(
            metadata._make_interval_affine("x", 2**4095, _CInterval(0, 1))
        )
        self.assertIsNone(
            metadata._make_interval_affine("x", 2**4096, _CInterval(0, 1))
        )
        self.assertIsNone(metadata._make_interval_affine(None, 1, _CInterval(0, 1)))

    def test_compaction_union_and_metadata_forgetting(self):
        original = tuple(branch(k, k + 1, constant=float(k)) for k in range(8))
        self.assertIs(sets._limit_branches(original, self.ops), original)
        components = tuple(
            branch(k, k + 1, constant=float(k)) for k in (0, 1, 2, 6, 7, 8, 12, 13, 14)
        )
        result = sets._limit_branches(components, self.ops)
        self.assertEqual(
            [bounds(x.interval) for x in result], [(0, 3), (6, 9), (12, 15)]
        )
        for quarter in range(-4, 65):
            point = Fraction(quarter, 4)
            self.assertEqual(
                any(x.interval.lo <= point <= x.interval.hi for x in components),
                any(x.interval.lo <= point <= x.interval.hi for x in result),
            )
        self.assertTrue(
            all(
                x.constant is None and x.chart is None and not x.continuous
                for x in result
            )
        )
        disjoint = tuple(branch(k * 2) for k in range(9))
        self.assertEqual(
            [bounds(x.interval) for x in sets._limit_branches(disjoint, self.ops)],
            [(0, 16)],
        )
        mapped = tuple(
            branch(1, branch_map=(("choice", 0),), constant=1) for _ in range(9)
        )
        merged = sets._limit_branches(mapped, self.ops)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].branch_map, (("choice", 0),))
        self.assertIsNone(merged[0].constant)

    def test_empty_and_piecewise_continuity(self):
        empty = sets._eval_set((branch(2, 1),), BOOL_TRUE, True, self.ops)
        self.assertEqual(empty.branches, ())
        self.assertEqual(truth(empty.defined), (False, False))
        self.assertFalse(empty.continuous)
        parts = (branch(0), branch(1))
        self.assertFalse(sets._eval_set(parts, BOOL_TRUE, True, self.ops).continuous)
        self.assertTrue(
            sets._eval_set(
                parts, BOOL_TRUE, True, self.ops, piecewise_continuous=True
            ).continuous
        )

    def test_strict_relations_against_finite_oracle(self):
        relations = {
            "=": operator.eq,
            "==": operator.eq,
            "!=": operator.ne,
            "<": operator.lt,
            "<=": operator.le,
            ">": operator.gt,
            ">=": operator.ge,
        }
        for left in (-1, 0, 1):
            for right in (-1, 0, 1):
                for symbol, op in relations.items():
                    expected = op(left, right)
                    self.assertEqual(
                        truth(
                            comparisons._compare_intervals(
                                _CInterval(left, left),
                                _CInterval(right, right),
                                symbol,
                                self.ops,
                            )
                        ),
                        (expected, expected),
                    )
        for symbol in relations:
            self.assertEqual(
                truth(
                    comparisons._compare_intervals(
                        _CInterval(1, 0), _CInterval(0, 0), symbol, self.ops
                    )
                ),
                (False, False),
            )
        self.assertEqual(
            truth(
                comparisons._compare_intervals(
                    _CInterval(0, 1), _CInterval(0, 1), "!=", self.ops
                )
            ),
            (False, True),
        )
        with self.assertRaises(ValueError):
            comparisons._compare_intervals(
                _CInterval(), _CInterval(), "unknown", self.ops
            )

    def test_shared_choices_and_aggregate_definedness(self):
        left = _EvalSet(
            (branch(1, branch_map=(("c", 0),)), branch(3, branch_map=(("c", 1),))),
            BOOL_TRUE,
            True,
        )
        right = _EvalSet(
            (branch(1, branch_map=(("c", 0),)), branch(3, branch_map=(("c", 1),))),
            BOOL_TRUE,
            True,
        )
        self.assertEqual(
            truth(comparisons._compare_eval_sets(left, right, "=", self.ops)),
            (True, True),
        )
        self.assertEqual(
            truth(
                comparisons._compare_eval_sets(
                    replace(left, defined=BOOL_MAYBE), right, "=", self.ops
                )
            ),
            (False, True),
        )
        result = arithmetic._binary_eval_set(
            left, right, self.ops.add, self.ops, affine_operation="add"
        )
        self.assertEqual(
            [bounds(x.interval) for x in result.branches], [(2, 2), (6, 6)]
        )
        self.assertEqual(
            [x.branch_map for x in result.branches], [(("c", 0),), (("c", 1),)]
        )
        incompatible = replace(right, branches=(branch(1, branch_map=(("c", 2),)),))
        self.assertEqual(
            truth(comparisons._compare_eval_sets(left, incompatible, "=", self.ops)),
            (False, False),
        )

    def test_eager_callbacks_order_and_exceptions(self):
        chart = _ChartDomain(_CInterval(0, 1), _CInterval(0, 1))
        left = _EvalSet(
            (branch(1, chart=chart), branch(2, chart=chart)), BOOL_TRUE, True
        )
        right = _EvalSet((branch(3), branch(4)), BOOL_TRUE, True)

        def observed(x, y):
            self.ops.events.append(("add", x.lo, y.lo))
            return self.ops.add(x, y)

        value = arithmetic._binary_eval_set(
            left,
            right,
            observed,
            self.ops,
            operator_name="add",
            expression_source="a+b",
        )
        self.assertEqual([x.interval.lo for x in value.branches], [4, 5, 5, 6])
        self.assertEqual(
            [e[0] for e in self.ops.events], ["sections", "loss", "add"] * 4
        )
        self.assertEqual(
            [e for e in self.ops.events if e[0] == "add"],
            [("add", 1, 3), ("add", 1, 4), ("add", 2, 3), ("add", 2, 4)],
        )
        failure = RuntimeError("backend control")

        def failing(x, y):
            raise failure

        with self.assertRaises(RuntimeError) as raised:
            arithmetic._binary_eval_set(left, right, failing, self.ops)
        self.assertIs(raised.exception, failure)

    def test_arithmetic_and_negation_exact_oracle(self):
        for operation, scalar in (
            (self.ops.add, operator.add),
            (self.ops.sub, operator.sub),
            (self.ops.mul, operator.mul),
        ):
            left, right = branch(-2, 1), branch(3, 4)
            result = arithmetic._binary_eval_set(
                _EvalSet((left,), BOOL_TRUE, True),
                _EvalSet((right,), BOOL_TRUE, True),
                operation,
                self.ops,
            )
            exact = [scalar(Fraction(a), Fraction(b)) for a in (-2, 1) for b in (3, 4)]
            self.assertEqual(
                bounds(result.branches[0].interval), (min(exact), max(exact))
            )
        value = branch(
            2,
            3,
            affine=_AffineCoordinate("x", 1, 2),
            constant=2,
            branch_map=(("a", 0),),
        )
        result = arithmetic._negate_eval_set(
            _EvalSet((value,), BOOL_TRUE, True), self.ops
        ).branches[0]
        self.assertEqual(bounds(result.interval), (-3, -2))
        self.assertEqual(result.affine, _AffineCoordinate("x", -1, -2))
        self.assertEqual((result.constant, result.branch_map), (-2, value.branch_map))

    def test_affine_contained_preimages_and_unavailable_chart(self):
        chart = _ChartDomain(_CInterval(-10, 10), _CInterval(-10, 10))
        for scale in (3.0, -3.0):
            result = charts._chart_for_affine_section(
                chart, _AffineCoordinate("x", scale, 1), _CInterval(2, 3), self.ops
            )
            self.assertIsNotNone(result)
            for endpoint in bounds(result.x):
                exact = Fraction(scale) * Fraction(endpoint) + 1
                self.assertLessEqual(Fraction(2), exact)
                self.assertLessEqual(exact, Fraction(3))
        self.assertIsNone(
            charts._chart_for_section(
                branch(-10, 10, chart=chart), _CInterval(1, 2), self.ops
            )
        )
        self.assertIsNone(charts._combine_charts(self.ops, chart, None))

    def test_quadratic_and_reciprocal_charts_preserve_holes(self):
        for lo, hi, expected in ((1, 5, (2, 3)), (-5, -1, (-3, -2))):
            chart = _ChartDomain(_CInterval(lo, hi), _CInterval(0, 0))
            result = charts._chart_for_quadratic_section(
                chart, _QuadraticCoordinate("x", 1, 0), _CInterval(4, 9), self.ops
            )
            self.assertEqual(bounds(result.x), expected)
        crossing = _ChartDomain(_CInterval(-5, 5), _CInterval(0, 0))
        self.assertIsNone(
            charts._chart_for_quadratic_section(
                crossing, _QuadraticCoordinate("x", 1, 0), _CInterval(4, 9), self.ops
            )
        )
        reciprocal = _ReciprocalAffineCoordinate("x", 1, 1, 0)
        self.assertIsNone(
            charts._chart_for_reciprocal_affine_section(
                crossing, reciprocal, _CInterval(-1, 1), self.ops
            )
        )
        result = charts._chart_for_reciprocal_affine_section(
            crossing, reciprocal, _CInterval(1, math.inf), self.ops
        )
        self.assertGreater(result.x.lo, 0)
        self.assertEqual(result.x.hi, 1)

    def test_interval_affine_is_contained_witness_only(self):
        chart = _ChartDomain(_CInterval(-10, 10), _CInterval(0, 0))
        value = branch(
            -10,
            12,
            chart=chart,
            interval_affine=_IntervalAffine("x", 1, _CInterval(1, 2)),
        )
        result = charts._chart_for_interval_affine_section(
            value, _CInterval(3, 5), self.ops
        )
        self.assertEqual(bounds(result.x), (2, 3))
        for x in bounds(result.x):
            for offset in (1, 2):
                self.assertTrue(3 <= Fraction(x) + offset <= 5)
        self.assertIsNone(
            charts._chart_for_interval_affine_section(
                replace(value, defined=BOOL_MAYBE), _CInterval(3, 5), self.ops
            )
        )
        self.assertIsNone(
            charts._chart_for_interval_affine_section(
                value, _CInterval(-1, 1), self.ops
            )
        )

    def test_import_has_no_parser_application_or_native_loader(self):
        code = """
import ctypes, sys
from unittest.mock import patch
with patch.object(ctypes, 'CDLL', side_effect=AssertionError('no native load')):
    from relgraph_eval import arithmetic, charts, comparisons, metadata, sets
assert not any(name.startswith(('graphing', 'relgraph_parser')) for name in sys.modules)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
