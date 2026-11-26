# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Original small controls for the provisional canonical parser."""

import ast
from fractions import Fraction
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

from relgraph_parser import normalize_formula, parse_formula
from relgraph_parser import raw, syntax


class ParserTests(unittest.TestCase):
    def test_exact_decimal_before_binary64_rounding(self):
        for spelling, expected in (
            ("1e-20", Fraction(1, 10**20)),
            ("0.1000", Fraction(1, 10)),
            ("9.223372036854775809e18", Fraction(9223372036854775809)),
            ("1e-400", Fraction(1, 10**400)),
            ("1e400", Fraction(10**400)),
        ):
            with self.subTest(spelling=spelling):
                value = parse_formula("x=" + spelling).alternatives[0][0].right
                self.assertEqual(raw.exact_decimal_value(value), expected)
                self.assertEqual(raw.decimal_spelling(value), spelling)

    def test_unbounded_integer_and_authored_source(self):
        source = " x = -9223372036854775809 "
        formula = parse_formula(source)
        self.assertEqual(formula.source, source)
        value = formula.alternatives[0][0].right
        self.assertIsInstance(value.op, ast.USub)
        self.assertEqual(value.operand.value, 9223372036854775809)

    def test_ordered_alternatives_and_constraints(self):
        formula = parse_formula("x=2; y<3 or x=4; y>5")
        self.assertEqual(
            [[r.operator for r in a] for a in formula.alternatives],
            [["=", "<"], ["=", ">"]],
        )
        self.assertEqual(
            [[r.right.value for r in a] for a in formula.alternatives], [[2, 3], [4, 5]]
        )
        expanded = parse_formula("x={2,4};y={3,5}")
        self.assertEqual(
            [[r.right.value for r in a] for a in expanded.alternatives],
            [[2, 3], [2, 5], [4, 3], [4, 5]],
        )

    def test_no_simplification_or_domain_cancellation(self):
        formula = parse_formula("x/x=1; 0*(1/y)=0")
        self.assertIsInstance(formula.alternatives[0][0].left.op, ast.Div)
        self.assertIsInstance(formula.alternatives[0][1].left.op, ast.Mult)
        self.assertEqual(
            sum(
                isinstance(n, ast.Div)
                for r in formula.alternatives[0]
                for n in ast.walk(r.left)
            ),
            2,
        )

    def test_supported_and_opaque_calls(self):
        for name in syntax._SUPPORTED_FUNCTIONS:
            arity = (
                syntax._VARIADIC_FUNCTION_MIN_ARITIES.get(name, 0)
                or syntax._FUNCTION_ARITIES[name][0]
            )
            node = (
                parse_formula(name + "(" + ",".join(["x"] * arity) + ")=y")
                .alternatives[0][0]
                .left
            )
            self.assertEqual(node.func.id, name)
        self.assertEqual(parse_formula("f(x,y)=0").alternatives[0][0].left.func.id, "f")

    def test_normalization_and_precedence(self):
        self.assertEqual(normalize_formula("−x^2≤π"), "-(x^2) <= pi")
        node = parse_formula("-x^2=0").alternatives[0][0].left
        self.assertIsInstance(node, ast.UnaryOp)
        self.assertIsInstance(node.operand.op, ast.Pow)
        self.assertEqual(
            normalize_formula(normalize_formula("x=±2")), "x = 2 or x = -(2)"
        )

    def test_malformed_and_noncanonical_input(self):
        for source in (
            "",
            "x=",
            "x=2 or",
            "2x=1",
            "sin x=0",
            "sin(x,y)=0",
            "x=True",
            "x=1_000",
            'x="a"',
            "x=sin(y=2)",
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse_formula(source)

    def test_resource_failures(self):
        for source, message in (
            ("x=" + "1" * 16384, "input characters"),
            (" or ".join(["x=0"] * 257), "alternatives"),
            ("x=1e999999999", "digit/scale budget"),
            ("x=1e-16385", "digit/scale budget"),
        ):
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                parse_formula(source)
        with (
            patch.object(syntax, "_MAX_NORMALIZATION_ENTRIES", 1),
            self.assertRaisesRegex(ValueError, "work limit"),
        ):
            parse_formula("x=1")

    def test_headless_dependency_boundary(self):
        for module in (raw, syntax):
            tree = ast.parse(Path(module.__file__).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 0:
                    self.assertIn(node.module.split(".")[0], sys.stdlib_module_names)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name.split(".")[0], sys.stdlib_module_names)
        self.assertNotIn("ctypes", sys.modules)
        self.assertNotIn("flet", sys.modules)


if __name__ == "__main__":
    unittest.main()
