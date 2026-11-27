# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Experimental headless sets primitives."""

from __future__ import annotations

from .values import _EvalResult, _EvalSet
from .operations import _IntervalOps
from .scalars import _interval_cache_key
from .definedness import (
    BoolInterval as _CBoolInterval,
    BOOL_FALSE as _BOOL_FALSE,
    BOOL_MAYBE as _BOOL_MAYBE,
    BOOL_TRUE as _BOOL_TRUE,
    bool_and as _bool_and,
    bool_is_false as _bool_is_false,
    bool_is_true as _bool_is_true,
    interval_nonzero as _interval_nonzero,
)


def _eval_set_from_result(result: _EvalResult, ops: _IntervalOps) -> _EvalSet:
    return _eval_set((result,), result.defined, result.continuous, ops)


def _eval_set(
    branches: tuple[_EvalResult, ...],
    defined: _CBoolInterval,
    continuous: bool,
    ops: _IntervalOps,
    *,
    piecewise_continuous: bool = False,
) -> _EvalSet:
    live_branches = tuple(
        branch for branch in branches if not ops.is_empty(branch.interval)
    )
    if not live_branches:
        return _EvalSet((), _bool_and(defined, _BOOL_FALSE), False)
    limited = _limit_branches(live_branches, ops)
    section_continuity = (
        all(branch.continuous for branch in limited)
        if piecewise_continuous
        else len(live_branches) == 1 and all(branch.continuous for branch in limited)
    )
    return _EvalSet(
        limited,
        defined,
        continuous and section_continuity,
    )


def _limit_branches(
    branches: tuple[_EvalResult, ...], ops: _IntervalOps
) -> tuple[_EvalResult, ...]:
    max_branches = 8
    if len(branches) <= max_branches:
        return branches
    if any(branch.branch_map for branch in branches):
        # Paper §11: identical ranges with identical branch conditions have
        # the same union. Never collapse different maps merely by value.
        unique: dict[tuple[str, str, frozenset[tuple[object, int]]], _EvalResult] = {}
        for branch in branches:
            key = (
                *_interval_cache_key(branch.interval),
                frozenset(branch.branch_map),
            )
            previous = unique.get(key)
            unique[key] = (
                branch
                if previous is None
                else _EvalResult(
                    branch.interval,
                    _CBoolInterval(
                        bool(previous.defined.lo and branch.defined.lo),
                        bool(previous.defined.hi or branch.defined.hi),
                    ),
                    previous.continuous and branch.continuous,
                    branch_map=branch.branch_map,
                )
            )
        branches = tuple(unique.values())
        if len(branches) <= max_branches:
            return branches
    interval = branches[0].interval
    defined = branches[0].defined
    continuous = branches[0].continuous
    connected = True
    for branch in branches[1:]:
        connected = connected and (
            branch.interval.lo <= interval.hi and interval.lo <= branch.interval.hi
        )
        interval = ops.hull(interval, branch.interval)
        defined = _bool_and(defined, branch.defined)
        continuous = continuous and branch.continuous
    fallback = (_EvalResult(interval, defined, continuous),)
    # If each range meets the preceding connected union, there is no gap to
    # preserve. Reuse the ordinary hull instead of sorting and hulling twice.
    if connected:
        return fallback
    # Tupper 2.13–2.13.1: overlapping closed value ranges have the same
    # union after coalescing. Preserve genuine gaps if the components fit.
    # This is only a value cover: no charts, continuity or structural facts
    # survive compaction, even on a component containing just one branch.
    components: list[_EvalResult] = []
    for branch in sorted(branches, key=lambda branch: branch.interval.lo):
        if components and branch.interval.lo <= components[-1].interval.hi:
            previous = components[-1]
            components[-1] = _EvalResult(
                ops.hull(previous.interval, branch.interval),
                _bool_and(previous.defined, branch.defined),
                False,
            )
        else:
            if len(components) == max_branches:
                # Later sorted intervals cannot bridge an earlier gap.
                break
            components.append(_EvalResult(branch.interval, branch.defined, False))
    else:
        if len(components) > 1:
            return tuple(components)
    # A connected union or too many components keeps the original hull policy.
    return fallback


def _branches_nonnegative(
    branches: tuple[_EvalResult, ...], ops: _IntervalOps
) -> _CBoolInterval:
    if not branches:
        return _BOOL_FALSE
    if all(
        not ops.is_empty(branch.interval) and branch.interval.lo >= 0.0
        for branch in branches
    ):
        return _BOOL_TRUE
    if all(
        ops.is_empty(branch.interval) or branch.interval.hi < 0.0 for branch in branches
    ):
        return _BOOL_FALSE
    return _BOOL_MAYBE


def _branches_nonzero(
    branches: tuple[_EvalResult, ...], ops: _IntervalOps
) -> _CBoolInterval:
    if not branches:
        return _BOOL_FALSE
    nonzero = [_interval_nonzero(branch.interval, ops) for branch in branches]
    if all(_bool_is_true(value) for value in nonzero):
        return _BOOL_TRUE
    if all(_bool_is_false(value) for value in nonzero):
        return _BOOL_FALSE
    return _BOOL_MAYBE
