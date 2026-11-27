# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Original exact controls for caller-owned headless numeric evaluation."""

from fractions import Fraction
import math
from pathlib import Path
import subprocess
import sys
import unittest

from test_value_algebra import ExactFixtureOps, bounds, branch, truth
from relgraph_eval import numeric, sets
from relgraph_eval.definedness import BOOL_FALSE, BOOL_MAYBE, BOOL_TRUE
from relgraph_eval.functions import (
    atan2,
    common_factor,
    elementary,
    fallback,
    periodic,
    powers,
    remainders,
)
from relgraph_eval.values import _EvalResult, _EvalSet


class FixtureOps(ExactFixtureOps):
    """Finite exact fixtures, deliberately not a general numeric implementation."""

    def empty(self):
        return self.make(math.inf, -math.inf)

    def contains(self, value, point):
        return value.lo <= point <= value.hi

    def gcd(self, *values):
        assert all(v.lo == v.hi and v.lo.is_integer() for v in values)
        return self.point(math.gcd(*(int(v.lo) for v in values)))

    def mod(self, left, right):
        assert left.lo == left.hi and right.lo == right.hi
        if right.lo == 0:
            return self.empty()
        a, b = Fraction(left.lo), abs(Fraction(right.lo))
        return self.point(self.exact(a - (a // b) * b))

    def fmod(self, left, right):
        assert left.lo == left.hi and right.lo == right.hi
        if right.lo == 0:
            return self.empty()
        a, b = Fraction(left.lo), Fraction(right.lo)
        return self.point(self.exact(a - int(a / b) * b))

    def mul(self, left, right):
        return super().mul(left, right)


class NumericEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.ops = FixtureOps()

    def test_fraction_conversion_is_least_enclosing(self):
        for exact in (
            Fraction(1, 3),
            Fraction(-2, 7),
            Fraction(2**60 + 1),
            Fraction(1, 2**1075),
        ):
            value = numeric._fraction_interval(exact, self.ops)
            self.assertLessEqual(Fraction(value.lo), exact)
            self.assertGreaterEqual(Fraction(value.hi), exact)
            self.assertGreater(Fraction(math.nextafter(value.lo, math.inf)), exact)
            self.assertLess(Fraction(math.nextafter(value.hi, -math.inf)), exact)

    def test_common_factors_use_exact_binary64_rationals(self):
        self.assertEqual(numeric._real_gcd_fraction((0.75, 1.25)), Fraction(1, 4))
        self.assertEqual(numeric._real_lcm_fraction((0.75, 1.25)), Fraction(15, 4))
        self.assertEqual(numeric._real_lcm_fraction((0.0, -1.25)), 0)
        with self.assertRaises(ValueError):
            numeric._real_gcd_fraction((math.inf,))

    def test_real_cover_includes_adjacent_float_gap_and_budget_fallback(self):
        value = self.ops.make(-1, 1)
        cover = numeric._interval_cover_split_at_points(
            value, (0.0,), self.ops, max_sections=3, fallback_continuous=False
        )
        self.assertEqual(len(cover.sections), 3)
        self.assertFalse(cover.sections[1].continuous)
        self.assertTrue(cover.sections[1].boundary)
        tiny = Fraction(math.ulp(0.0)) / 2
        for exact in (-tiny, Fraction(0), tiny):
            self.assertTrue(
                any(
                    Fraction(s.interval.lo) <= exact <= Fraction(s.interval.hi)
                    for s in cover.sections
                )
            )
        fallback_cover = numeric._interval_cover_split_at_points(
            value, (0.0,), self.ops, max_sections=2, fallback_continuous=False
        )
        self.assertEqual(len(fallback_cover.sections), 1)
        self.assertIs(fallback_cover.sections[0].interval, value)
        self.assertFalse(fallback_cover.sections[0].continuous)
        self.assertEqual(
            numeric._interval_cover_split_at_points(
                self.ops.empty(), (), self.ops, max_sections=3, fallback_continuous=True
            ).sections,
            (),
        )

    def test_pole_tails_are_partial_and_keep_both_signs(self):
        sections = numeric._nonzero_domain_sections(self.ops.make(-1, 1), self.ops)
        tails = [(s, d) for s, d in sections if s.boundary]
        self.assertEqual(len(tails), 2)
        self.assertEqual([truth(d) for _, d in tails], [(False, True)] * 2)
        self.assertTrue(all(not s.continuous for s, _ in tails))
        self.assertEqual(tails[0][0].interval.hi, 0)
        self.assertEqual(tails[1][0].interval.lo, 0)
        self.assertEqual(
            numeric._nonzero_domain_sections(self.ops.point(0), self.ops), ()
        )

    def test_integer_power_encloses_independent_exact_grid(self):
        for lo, hi in ((-3, -1), (-2, 3), (0, 4)):
            for exponent in (1, 2, 3, 4):
                result = numeric._pow_interval(
                    self.ops.make(lo, hi), exponent, self.ops
                )
                for i in range(lo * 4, hi * 4 + 1):
                    exact = Fraction(i, 4) ** exponent
                    self.assertLessEqual(Fraction(result.lo), exact)
                    self.assertGreaterEqual(Fraction(result.hi), exact)

    def test_power_set_keeps_shared_choice(self):
        value = branch(-2, 2, branch_map=((4, 1),))
        result = powers._power_eval_set(
            _EvalSet((value,), BOOL_TRUE, True), 2, self.ops
        )
        self.assertTrue(result.branches)
        self.assertTrue(all(v.branch_map == ((4, 1),) for v in result.branches))
        self.assertEqual(bounds(result.branches[0].interval), (0, 4))

    def test_elementary_sqrt_exact_and_undefined(self):
        result = elementary._sqrt_result(branch(1, 4), self.ops)
        self.assertEqual(bounds(result.interval), (1, 2))
        self.assertEqual(truth(result.defined), (True, True))

        class NoNumeric(FixtureOps):
            def elementary(self, name, value):
                raise AssertionError("undefined input must not call numeric backend")

        result = elementary._elementary_unary_result("ln", branch(-2, -1), NoNumeric())
        self.assertEqual(truth(result.defined), (False, False))
        self.assertTrue(self.ops.is_empty(result.interval))

    def test_remainder_signs_and_zero_domain(self):
        for a in (-7, 7):
            for b in (-3, 3):
                for name in ("mod", "fmod"):
                    result = remainders._remainder_result(
                        name, branch(a), branch(b), self.ops
                    )
                    expected = (
                        Fraction(a) % abs(b)
                        if name == "mod"
                        else Fraction(a) - int(Fraction(a, b)) * b
                    )
                    self.assertEqual(bounds(result.interval), (expected, expected))
                    self.assertFalse(result.continuous)
        result = remainders._remainder_result("mod", branch(1), branch(0), self.ops)
        self.assertEqual(truth(result.defined), (False, False))

    def test_common_factor_conflicting_choices_do_not_evaluate(self):
        left = _EvalSet((branch(6, branch_map=((1, 0),)),), BOOL_TRUE, True)
        right = _EvalSet((branch(9, branch_map=((1, 1),)),), BOOL_TRUE, True)

        def forbidden(*args):
            raise AssertionError("incompatible choices")

        result = common_factor._common_factor_eval_set(
            (left, right), forbidden, self.ops
        )
        self.assertEqual(result.branches, ())
        result = common_factor._common_factor_result(
            "gcd", (branch(6), branch(9)), self.ops
        )
        self.assertEqual(bounds(result.interval), (3, 3))

    def test_atan2_origin_and_branch_cut(self):
        for y, x, expected in (
            (self.ops.point(0), self.ops.point(0), (False, False)),
            (self.ops.make(-1, 1), self.ops.make(-1, 1), (False, True)),
            (self.ops.point(1), self.ops.point(0), (True, True)),
        ):
            self.assertEqual(
                truth(numeric._atan2_interval_domain(y, x, self.ops)), expected
            )
        self.assertTrue(
            numeric._atan2_crosses_branch_cut(
                self.ops.make(-1, 0), self.ops.make(-2, -1)
            )
        )
        self.assertFalse(
            numeric._atan2_crosses_branch_cut(
                self.ops.make(0, 1), self.ops.make(-2, -1)
            )
        )
        result = atan2._atan2_eval_set(
            _EvalSet((branch(0),), BOOL_TRUE, True),
            _EvalSet((branch(0),), BOOL_TRUE, True),
            self.ops,
        )
        self.assertEqual(result.branches, ())

    def test_periodic_factories_preserve_identity_order_and_exceptions(self):
        arg = branch(0, branch_map=((2, 0),))
        value = self.ops.point(0)
        calls = []

        def factory(*args, **kwargs):
            calls.append((args, kwargs))
            return _EvalResult(*args, **kwargs)

        result = periodic._periodic_scalar_constant_result(factory, value, arg, -0.0)
        self.assertIs(calls[0][0][0], value)
        self.assertIs(calls[0][0][1], arg.defined)
        self.assertEqual(math.copysign(1, result.constant), -1)
        failure = RuntimeError("callback failed")

        def broken(*args, **kwargs):
            raise failure

        with self.assertRaises(RuntimeError) as raised:
            periodic._periodic_scalar_result(broken, value, arg)
        self.assertIs(raised.exception, failure)
        result = periodic._periodic_constant_eval_set(
            sets._eval_set, _EvalSet((arg,), BOOL_TRUE, True), self.ops, 0
        )
        self.assertEqual(result.branches[0].branch_map, ((2, 0),))

    def test_unknown_fallback_never_becomes_defined(self):
        for inputs, expected in (
            ((), (False, True)),
            ((BOOL_TRUE,), (False, True)),
            ((BOOL_MAYBE,), (False, True)),
            ((BOOL_FALSE,), (False, False)),
        ):
            result = fallback._fallback_function_result(inputs, self.ops)
            self.assertEqual(truth(result.defined), expected)
            self.assertFalse(result.continuous)
            self.assertIsNone(result.chart)
            self.assertEqual(self.ops.is_empty(result.interval), not expected[1])

    def test_import_has_no_application_or_native_loading(self):
        source = """
import ctypes, importlib, sys
ctypes.CDLL = lambda *a, **k: (_ for _ in ()).throw(AssertionError('native load'))
for name in ('numeric', 'numeric_api', 'operations', 'functions.elementary', 'functions.powers', 'functions.periodic', 'functions.remainders', 'functions.common_factor', 'functions.atan2', 'functions.fallback'):
    importlib.import_module('relgraph_eval.' + name)
assert not any(n == 'graphing' or n.startswith('graphing.') for n in sys.modules)
"""
        result = subprocess.run(
            [sys.executable, "-c", source],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
