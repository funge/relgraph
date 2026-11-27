# SPDX-License-Identifier: AGPL-3.0-only
"""Original finite-set and boundary controls for definedness primitives."""

import ctypes
import itertools
import math
import subprocess
import sys
import unittest
from dataclasses import dataclass

from relgraph_eval import definedness as d


@dataclass
class Bounds:
    lo: float
    hi: float


class Queries:
    def is_empty(self, value):
        return value.lo > value.hi


def pair(value):
    return bool(value.lo), bool(value.hi)


def possibilities(value):
    return tuple(v for v in (False, True) if value.lo <= v <= value.hi)


class DefinednessTests(unittest.TestCase):
    def test_boolean_finite_set_oracle(self):
        states = (d.BOOL_FALSE, d.BOOL_MAYBE, d.BOOL_TRUE)
        for length in range(5):
            for args in itertools.product(states, repeat=length):
                assignments = list(itertools.product(*(possibilities(v) for v in args)))
                for operation, oracle in ((d.bool_and, all), (d.bool_or, any)):
                    values = [oracle(a) for a in assignments]
                    self.assertEqual(pair(operation(*args)), (min(values), max(values)))
        for state in states:
            self.assertEqual(d.bool_is_true(state), possibilities(state) == (True,))
            self.assertEqual(d.bool_is_false(state), possibilities(state) == (False,))

    def test_domain_finite_set_oracle(self):
        # Integer endpoints plus the midpoint witness distinguish all zero cuts.
        ops = Queries()
        for lo in range(-3, 4):
            for hi in range(lo, 4):
                points = [lo + n / 2 for n in range(2 * (hi - lo) + 1)]
                interval = Bounds(lo, hi)
                nonzero = [x != 0 for x in points]
                self.assertEqual(
                    pair(d.interval_nonzero(interval, ops)),
                    (min(nonzero), max(nonzero)),
                )
                for argument in (d.BOOL_FALSE, d.BOOL_MAYBE, d.BOOL_TRUE):
                    for function, predicate in (
                        (d.sqrt_domain, lambda x: x >= 0),
                        (d.log2_domain, lambda x: x > 0),
                    ):
                        values = [
                            a and predicate(x)
                            for a in possibilities(argument)
                            for x in points
                        ]
                        self.assertEqual(
                            pair(function(interval, argument, ops)),
                            (min(values), max(values)),
                        )

    def test_empty_signed_zero_subnormal_and_infinite(self):
        ops = Queries()
        tiny = math.ulp(0.0)
        for lo, hi, nz, sqrt, log in (
            (1.0, -1.0, (False, False), (False, False), (False, False)),
            (-0.0, 0.0, (False, False), (True, True), (False, False)),
            (tiny, tiny, (True, True), (True, True), (True, True)),
            (-tiny, -tiny, (True, True), (False, False), (False, False)),
            (-tiny, tiny, (False, True), (False, True), (False, True)),
            (-math.inf, math.inf, (False, True), (False, True), (False, True)),
            (0.0, math.inf, (False, True), (True, True), (False, True)),
        ):
            value = Bounds(lo, hi)
            self.assertEqual(pair(d.interval_nonzero(value, ops)), nz)
            self.assertEqual(pair(d.sqrt_domain(value, d.BOOL_TRUE, ops)), sqrt)
            self.assertEqual(pair(d.log2_domain(value, d.BOOL_TRUE, ops)), log)

    def test_identity_layout_and_no_numeric_loader(self):
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from unittest.mock import patch; guard = patch('ctypes.CDLL', side_effect=AssertionError('numeric loader invoked')); guard.start(); import relgraph_eval.definedness; assert not any(n == 'relgraph_parser' or n.startswith('relgraph_parser.') for n in sys.modules)",
            ],
            check=True,
        )
        ops = Queries()
        self.assertIs(d.sqrt_domain(Bounds(0, 1), d.BOOL_MAYBE, ops), d.BOOL_MAYBE)
        self.assertIs(d.log2_domain(Bounds(1, 2), d.BOOL_MAYBE, ops), d.BOOL_MAYBE)
        self.assertIs(d.interval_nonzero(Bounds(0, 0), ops), d.BOOL_FALSE)

        class Layout(ctypes.Structure):
            _fields_ = [("lo", ctypes.c_bool), ("hi", ctypes.c_bool)]

        self.assertEqual(ctypes.sizeof(d.BoolInterval), ctypes.sizeof(Layout))
        self.assertEqual(ctypes.alignment(d.BoolInterval), ctypes.alignment(Layout))
        self.assertEqual(d.BoolInterval.hi.offset, Layout.hi.offset)
        for lo, hi in itertools.product((False, True), repeat=2):
            self.assertEqual(bytes(d.BoolInterval(lo, hi)), bytes(Layout(lo, hi)))


if __name__ == "__main__":
    unittest.main()
