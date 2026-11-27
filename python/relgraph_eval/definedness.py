# SPDX-License-Identifier: AGPL-3.0-only
"""Experimental Boolean intervals and conservative elementary domain predicates."""

from __future__ import annotations

import ctypes
from typing import Protocol


class BoolInterval(ctypes.Structure):
    lo: bool
    hi: bool

    _fields_ = [
        ("lo", ctypes.c_bool),
        ("hi", ctypes.c_bool),
    ]


class IntervalBounds(Protocol):
    @property
    def lo(self) -> float: ...

    @property
    def hi(self) -> float: ...


class EmptyQuery[T](Protocol):
    def is_empty(self, value: T) -> bool: ...


BOOL_FALSE = BoolInterval(False, False)
BOOL_MAYBE = BoolInterval(False, True)
BOOL_TRUE = BoolInterval(True, True)


def bool_and(*values: BoolInterval) -> BoolInterval:
    lo = True
    hi = True
    for value in values:
        lo = lo and bool(value.lo)
        hi = hi and bool(value.hi)
    return BoolInterval(lo, hi)


def bool_or(*values: BoolInterval) -> BoolInterval:
    lo = False
    hi = False
    for value in values:
        lo = lo or bool(value.lo)
        hi = hi or bool(value.hi)
    return BoolInterval(lo, hi)


def bool_is_true(value: BoolInterval) -> bool:
    return bool(value.lo and value.hi)


def bool_is_false(value: BoolInterval) -> bool:
    return not value.lo and not value.hi


def interval_nonzero[T: IntervalBounds](value: T, ops: EmptyQuery[T]) -> BoolInterval:
    if ops.is_empty(value):
        return BOOL_FALSE
    if value.hi < 0.0 or value.lo > 0.0:
        return BOOL_TRUE
    if value.lo == 0.0 and value.hi == 0.0:
        return BOOL_FALSE
    return BOOL_MAYBE


def sqrt_domain[T: IntervalBounds](
    value: T,
    argument_defined: BoolInterval,
    ops: EmptyQuery[T],
) -> BoolInterval:
    if ops.is_empty(value) or value.hi < 0.0:
        return BOOL_FALSE
    if value.lo >= 0.0:
        return argument_defined
    return bool_and(argument_defined, BOOL_MAYBE)


def log2_domain[T: IntervalBounds](
    value: T,
    argument_defined: BoolInterval,
    ops: EmptyQuery[T],
) -> BoolInterval:
    if ops.is_empty(value) or value.hi <= 0.0:
        return BOOL_FALSE
    if value.lo > 0.0:
        return argument_defined
    return bool_and(argument_defined, BOOL_MAYBE)
