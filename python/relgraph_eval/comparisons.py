# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Experimental headless comparisons primitives."""

from __future__ import annotations

from .values import _CInterval, _EvalSet
from .operations import _IntervalOps
from .branches import merge_branch_maps as _merge_branch_maps
from .definedness import (
    BoolInterval as _CBoolInterval,
    BOOL_FALSE as _BOOL_FALSE,
    bool_is_true as _bool_is_true,
    bool_or as _bool_or,
)


def _compare_eval_sets(
    left: _EvalSet,
    right: _EvalSet,
    operator: str,
    ops: _IntervalOps,
) -> _CBoolInterval:
    if not left.branches or not right.branches:
        return _BOOL_FALSE

    comparisons = [
        _compare_intervals(left_branch.interval, right_branch.interval, operator, ops)
        for left_branch in left.branches
        for right_branch in right.branches
        if _merge_branch_maps(left_branch.branch_map, right_branch.branch_map)
        is not None
    ]
    possible = any(bool(comparison.hi) for comparison in comparisons)
    definite = (
        bool(comparisons)
        and _bool_is_true(left.defined)
        and _bool_is_true(right.defined)
        and all(bool(comparison.lo) for comparison in comparisons)
    )
    return _CBoolInterval(definite, possible)


def _compare_intervals(
    left: _CInterval,
    right: _CInterval,
    operator: str,
    ops: _IntervalOps,
) -> _CBoolInterval:
    if operator in ("=", "=="):
        return ops.eq(left, right)
    if operator == "!=":
        # Paper section 3: undefined/empty comparisons are false, including
        # not-equal. Negating equality would incorrectly make them true.
        return _bool_or(ops.lt(left, right), ops.gt(left, right))
    if operator == "<":
        return ops.lt(left, right)
    if operator == "<=":
        return ops.le(left, right)
    if operator == ">":
        return ops.gt(left, right)
    if operator == ">=":
        return ops.ge(left, right)
    raise ValueError(f"unsupported relation operator {operator!r}")
