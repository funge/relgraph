# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Original exact controls for source-independent division/discrete kernels."""

from fractions import Fraction
import math
import operator
from pathlib import Path
import subprocess
import sys
import unittest

from test_numeric_evaluation import FixtureOps
from test_value_algebra import bounds, branch, truth
from relgraph_eval import rational_refinement as r
from relgraph_eval.definedness import BOOL_MAYBE, BOOL_TRUE
from relgraph_eval.functions import discrete, division
from relgraph_eval.values import _EvalSet


class Ops(FixtureOps):
    def div(self, left, right):
        if right.lo <= 0 <= right.hi:
            return self.make(-math.inf, math.inf)
        return self.arithmetic(left, right, operator.truediv)

    def factorial(self, value):
        assert value.lo == value.hi and value.lo >= 0 and value.lo.is_integer()
        return self.point(math.factorial(int(value.lo)))


class RationalDiscreteTests(unittest.TestCase):
    def setUp(self):
        self.ops = Ops()

    def plan(self, budget=20, quotient=(1, 2)):
        return r._LinearRationalPlan(
            "x",
            tuple(self.ops.point(v) for v in quotient),
            self.ops.point(1),
            self.ops.point(3),
            r._OperationBudget(budget),
        )

    def test_exact_refinement_and_shared_budget(self):
        plan = self.plan()
        ordinary = self.ops.make(0, 10)
        result = r._refine_linear_rational_interval(
            plan, self.ops.point(4), ordinary, self.ops
        )
        expected = Fraction(1) + 2 * Fraction(3) + Fraction(1, 4)
        self.assertEqual(bounds(result), (expected, expected))
        self.assertEqual(plan.budget.remaining, 15)
        r._refine_linear_rational_interval(plan, self.ops.point(-4), ordinary, self.ops)
        self.assertEqual(plan.budget.remaining, 10)
        constant = self.plan(3, (2,))
        self.assertEqual(
            bounds(
                r._refine_linear_rational_interval(
                    constant, self.ops.point(4), ordinary, self.ops
                )
            ),
            (2.25, 2.25),
        )
        self.assertEqual(constant.budget.remaining, 0)

    def test_poles_exhaustion_and_empty_intersection_preserve_identity(self):
        ordinary = self.ops.make(0, 10)
        for denominator in (
            self.ops.point(0),
            self.ops.make(-1, 1),
            self.ops.make(0, 2),
        ):
            plan = self.plan()
            self.assertIs(
                r._refine_linear_rational_interval(
                    plan, denominator, ordinary, self.ops
                ),
                ordinary,
            )
            self.assertEqual(plan.budget.remaining, 20)
        for budget in range(5):
            self.assertIs(
                r._refine_linear_rational_interval(
                    self.plan(budget), self.ops.point(4), ordinary, self.ops
                ),
                ordinary,
            )
        empty = self.ops.make(-2, -1)
        self.assertIs(
            r._refine_linear_rational_interval(
                self.plan(), self.ops.point(4), empty, self.ops
            ),
            empty,
        )

    def test_budget_finite_and_exception_contract(self):
        budget = r._OperationBudget(1)
        with self.assertRaises(r._Decline):
            r._binary(
                lambda a, b: self.ops.make(-math.inf, math.inf),
                self.ops.point(1),
                self.ops.point(2),
                budget,
            )
        self.assertEqual(budget.remaining, 0)
        with self.assertRaises(r._Decline):
            budget.use()

        def fail(a, b):
            raise LookupError("numeric failure")

        with self.assertRaisesRegex(LookupError, "numeric failure"):
            r._binary(fail, self.ops.point(1), self.ops.point(2), r._OperationBudget())

    def test_polynomial_exact_convolution_axis_and_degree_limits(self):
        a = r._Polynomial("x", tuple(self.ops.point(x) for x in (1, 2)))
        b = r._Polynomial("x", tuple(self.ops.point(x) for x in (-1, 3)))
        product = r._combine(a, b, "mul", self.ops, r._OperationBudget())
        self.assertEqual(
            tuple(bounds(c) for c in product.coefficients), ((-1, -1), (1, 1), (6, 6))
        )
        for x in (Fraction(-2), Fraction(0), Fraction(3, 2)):
            self.assertEqual(
                sum(Fraction(c.lo) * x**i for i, c in enumerate(product.coefficients)),
                (1 + 2 * x) * (-1 + 3 * x),
            )
        self.assertIsNone(
            r._normalized("x", [self.ops.point(2), self.ops.point(0)]).axis
        )
        with self.assertRaises(r._Decline):
            r._combine(
                a,
                r._Polynomial("y", b.coefficients),
                "add",
                self.ops,
                r._OperationBudget(),
            )
        with self.assertRaises(r._Decline):
            r._normalized("x", [self.ops.point(1)] * 10)

    def test_division_retains_denominator_exclusion_and_inherited_unknown(self):
        for numerator, denominator in ((3, 4), (-3, 4), (3, -4)):
            result = division._division_result(
                branch(numerator), branch(denominator), BOOL_TRUE, True, self.ops
            )
            exact = Fraction(numerator, denominator)
            self.assertEqual(bounds(result.interval), (exact, exact))
            self.assertEqual(truth(result.defined), (True, True))
        result = division._division_result(
            branch(0), branch(-1, 1), BOOL_TRUE, True, self.ops
        )
        self.assertEqual(truth(result.defined), (False, True))
        self.assertFalse(result.continuous)
        result = division._division_result(
            branch(3), branch(4), BOOL_MAYBE, True, self.ops
        )
        self.assertEqual(truth(result.defined), (False, True))

    def test_set_choice_conflict_precedes_numeric_work(self):
        site = object()
        left = _EvalSet((branch(3, branch_map=((site, 1),)),), BOOL_TRUE, True)
        right = _EvalSet((branch(4, branch_map=((site, 2),)),), BOOL_TRUE, True)
        result = division._division_eval_set(left, right, self.ops)
        self.assertEqual(result.branches, ())
        self.assertFalse(self.ops.events)
        right = _EvalSet((branch(4, branch_map=((site, 1),)),), BOOL_TRUE, True)
        result = division._division_eval_set(left, right, self.ops)
        self.assertEqual(len(result.branches), 1)
        self.assertEqual(bounds(result.branches[0].interval), (0.75, 0.75))
        self.assertEqual(result.branches[0].branch_map, ((site, 1),))

    def test_import_has_no_application_or_native_load(self):
        code = """
import ctypes, sys
sys.path.insert(0, sys.argv[1])
def fail(*a, **k):
    raise AssertionError('unexpected native load')
ctypes.CDLL = fail
before = set(sys.modules)
from relgraph_eval import rational_refinement
from relgraph_eval.functions import discrete, division
assert all(n.partition('.')[0] in sys.stdlib_module_names | {'relgraph_eval'} for n in set(sys.modules) - before)
"""
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                code,
                str(Path(__file__).resolve().parents[1] / "python"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_discrete_scalar_domain_and_choice_identity(self):
        for value, expected in ((5, 120), (0, 1)):
            result = discrete._factorial_result(branch(value, constant=value), self.ops)
            self.assertEqual(bounds(result.interval), (expected, expected))
            self.assertTrue(result.continuous)
        for value in (-1, 0.5):
            result = discrete._factorial_result(branch(value), self.ops)
            self.assertEqual(truth(result.defined), (False, False))
            self.assertFalse(result.continuous)
        site = object()
        result = discrete._integer_function_result(
            branch(1.25, 1.75),
            lambda v: self.ops.make(math.floor(v.lo), math.floor(v.hi)),
            self.ops,
            branch_site=site,
        )
        self.assertEqual(bounds(result.interval), (1, 1))
        self.assertEqual(result.branch_map, ((site, 1),))
        self.assertTrue(result.continuous)


if __name__ == "__main__":
    unittest.main()
