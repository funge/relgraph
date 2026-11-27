# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded numeric rational-plan construction and refinement; no source/cache owner."""

from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
import math
from .operations import _IntervalOps
from .values import _CInterval

_MAX_OPERATIONS = 4096


_MAX_DEGREE = 8


class _Decline(Exception):
    """Exhausted or inapplicable optional proof; ordinary evaluation survives."""


@dataclass
class _OperationBudget:
    remaining: int = _MAX_OPERATIONS

    def use(self) -> None:
        if self.remaining <= 0:
            raise _Decline
        self.remaining -= 1


@dataclass(frozen=True)
class _Polynomial:
    axis: str | None
    coefficients: tuple[_CInterval, ...]


@dataclass(frozen=True)
class _LinearRationalPlan:
    axis: str
    quotient: tuple[_CInterval, ...]
    remainder: _CInterval
    coordinate: _CInterval
    budget: _OperationBudget


def _finite(interval: _CInterval) -> bool:
    return (
        math.isfinite(interval.lo)
        and math.isfinite(interval.hi)
        and interval.lo <= interval.hi
    )


def _binary(
    operation: Callable[[_CInterval, _CInterval], _CInterval],
    left: _CInterval,
    right: _CInterval,
    budget: _OperationBudget,
) -> _CInterval:
    budget.use()
    result = operation(left, right)
    if not _finite(result):
        raise _Decline
    return result


def _point(value: float, ops: _IntervalOps, budget: _OperationBudget) -> _CInterval:
    budget.use()
    return ops.point(value)


def _normalized(axis: str | None, coefficients: list[_CInterval]) -> _Polynomial:
    while len(coefficients) > 1 and coefficients[-1].lo == coefficients[-1].hi == 0:
        coefficients.pop()
    if len(coefficients) > _MAX_DEGREE + 1:
        raise _Decline
    return _Polynomial(axis if len(coefficients) > 1 else None, tuple(coefficients))


def _combine(
    left: _Polynomial,
    right: _Polynomial,
    operation: str,
    ops: _IntervalOps,
    budget: _OperationBudget,
) -> _Polynomial:
    if left.axis is not None and right.axis is not None and left.axis != right.axis:
        raise _Decline
    axis = left.axis or right.axis
    zero = _point(0, ops, budget)
    if operation == "mul":
        degree = len(left.coefficients) + len(right.coefficients) - 2
        if degree > _MAX_DEGREE:
            raise _Decline
        result = [zero] * (degree + 1)
        for i, a in enumerate(left.coefficients):
            for j, b in enumerate(right.coefficients):
                product = _binary(ops.mul, a, b, budget)
                result[i + j] = _binary(ops.add, result[i + j], product, budget)
    else:
        result = []
        for i in range(max(len(left.coefficients), len(right.coefficients))):
            a = left.coefficients[i] if i < len(left.coefficients) else zero
            b = right.coefficients[i] if i < len(right.coefficients) else zero
            result.append(
                _binary(ops.add if operation == "add" else ops.sub, a, b, budget)
            )
    return _normalized(axis, result)


def _refine_linear_rational_interval(
    plan: _LinearRationalPlan,
    denominator_section: _CInterval,
    ordinary: _CInterval,
    ops: _IntervalOps,
) -> _CInterval:
    """Intersect a full-original-box enclosure, preserving ordinary on decline."""
    if not (denominator_section.hi < 0 or denominator_section.lo > 0):
        return ordinary
    try:
        value = plan.quotient[-1]
        for coefficient in reversed(plan.quotient[:-1]):
            value = _binary(ops.mul, value, plan.coordinate, plan.budget)
            value = _binary(ops.add, value, coefficient, plan.budget)
        # A constant quotient is its coefficient, even when normalization
        # demoted the polynomial axis. No axisNone -> whole source quirk.
        plan.budget.use()
        remainder = ops.div(plan.remainder, denominator_section)
        plan.budget.use()
        rewritten = ops.add(value, remainder)
        plan.budget.use()
        refined = ops.intersect(ordinary, rewritten)
        if refined.lo <= refined.hi:
            return refined
    except _Decline:
        pass
    return ordinary
