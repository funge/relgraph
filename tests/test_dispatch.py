# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Original direct-entrypoint controls with caller-owned exact source services."""

import ast
from fractions import Fraction
import unittest
from test_rational_discrete import Ops
from test_value_algebra import bounds, truth
from relgraph_eval import dispatch, numeric
from relgraph_parser import parse_formula
from relgraph_parser.raw import _EXACT_DECIMAL_NUMERATOR_ATTR as NUM
from relgraph_parser.raw import _EXACT_DECIMAL_DENOMINATOR_ATTR as DEN
from relgraph_parser.raw import _EXACT_DECIMAL_SPELLING_ATTR as SPELLING


class Context(Ops):
    chart_loss_enabled = False

    def __init__(self):
        super().__init__()
        self.scope = object()
        self.sites = {}

    def expression_dependency(self, node):
        return (
            "x"
            if any(isinstance(n, ast.Name) and n.id == "x" for n in ast.walk(node))
            else "constant"
        )

    def branch_site(self, node, *, x, y):
        return self.sites.setdefault((self.scope, id(node)), object())

    def floor(self, value):
        raise AssertionError("scope host should receive this operation")


class Host:
    def __init__(self):
        self.calls, self.literals = [], []

    def _eval_expr(self, node, x, y, ops, *, cache=None):
        self.calls.append((node, cache))
        return dispatch._eval_expr_uncached(node, x, y, ops, cache=cache, host=self)

    def _eval_expr_set(self, node, x, y, ops):
        return dispatch._eval_expr_set_uncached(node, x, y, ops, host=self)

    def _constant_literal_interval(self, node, ops):
        exact = (
            Fraction(getattr(node, NUM), getattr(node, DEN))
            if hasattr(node, NUM)
            else Fraction(node.value)
        )
        self.literals.append((node, exact, getattr(node, SPELLING, None)))
        value = numeric._fraction_interval(exact, ops)
        return value, value.lo if value.lo == value.hi else None

    def _ast_equivalent(self, left, right):
        return ast.dump(left) == ast.dump(right)

    def _linear_rational_plan(self, *args):
        return None

    def _inverse_sinc_phase(self, node):
        return None

    def _expr_source(self, node):
        return ast.unparse(node)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.host, self.ops = Host(), Context()
        self.x, self.y = self.ops.point(2), self.ops.point(4)

    def test_both_dispatchers_execute_arithmetic(self):
        node = ast.parse("(x+2)/y", mode="eval").body
        a = self.host._eval_expr(node, self.x, self.y, self.ops)
        b = self.host._eval_expr_set(node, self.x, self.y, self.ops)
        self.assertEqual(bounds(a.interval), (1, 1))
        self.assertEqual(bounds(b.branches[0].interval), (1, 1))
        self.assertEqual(truth(a.defined), (True, True))
        self.assertEqual(truth(b.defined), (True, True))

    def test_exact_literal_node_spelling_and_fraction(self):
        for spelling in ("1e-20", "9223372036854775809"):
            node = parse_formula(spelling + "=0").alternatives[0][0].left
            value = self.host._eval_expr(node, self.x, self.y, self.ops)
            record = self.host.literals[-1]
            self.assertIs(record[0], node)
            self.assertEqual(record[1], Fraction(spelling))
            if isinstance(node.value, float):
                self.assertEqual(record[2], spelling)
            self.assertLessEqual(Fraction(value.interval.lo), Fraction(spelling))
            self.assertGreaterEqual(Fraction(value.interval.hi), Fraction(spelling))

    def test_cancellation_preserves_poles_and_uncertainty(self):
        node = ast.parse("x/y-x/y", mode="eval").body
        for evaluator in (self.host._eval_expr, self.host._eval_expr_set):
            result = evaluator(node, self.x, self.ops.point(0), self.ops)
            self.assertEqual(truth(result.defined), (False, False))
        result = self.host._eval_expr(node, self.x, self.ops.make(-1, 1), self.ops)
        self.assertEqual(truth(result.defined), (False, True))
        self.assertEqual(bounds(result.interval), (0, 0))

    def test_recursion_retains_cache_and_node_identity(self):
        node = ast.parse("+x", mode="eval").body
        cache = {}
        result = dispatch._eval_expr_uncached(
            node, self.x, self.y, self.ops, cache=cache, host=self.host
        )
        self.assertIs(self.host.calls[0][0], node.operand)
        self.assertIs(self.host.calls[0][1], cache)
        self.assertIs(result.interval, self.x)
        self.assertEqual(cache, {})

    def test_discrete_site_and_scope_are_host_owned(self):
        node = ast.parse("floor(x)", mode="eval").body
        seen, marker = [], object()

        def scoped(argument, operation, ops, *, operator_name, branch_site):
            seen.append((ops, operator_name, branch_site))
            return marker

        self.host._integer_function_eval_set = scoped
        for _ in range(2):
            self.assertIs(
                self.host._eval_expr_set(node, self.x, self.y, self.ops), marker
            )
        self.assertIs(seen[0][0], self.ops)
        self.assertEqual(seen[0][1], "floor")
        self.assertIs(seen[0][2], seen[1][2])
        self.ops.scope = object()
        self.host._eval_expr_set(node, self.x, self.y, self.ops)
        self.assertIsNot(seen[0][2], seen[2][2])

    def test_invalid_calls_precede_operand_and_numeric_access(self):
        for source in ("sin(1,2)", "sin(x=1)", "sin(*x)", "mod(1)"):
            node = ast.parse(source, mode="eval").body
            for fn in (dispatch._eval_expr_uncached, dispatch._eval_expr_set_uncached):
                with self.assertRaises(ValueError):
                    fn(
                        node,
                        self.x,
                        self.y,
                        object(),
                        host=object(),
                        **(
                            {"cache": None}
                            if fn is dispatch._eval_expr_uncached
                            else {}
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
