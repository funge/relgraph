# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded GCD/LCM interval-set composition with original metadata."""

from __future__ import annotations

from typing import Callable
from ..numeric import _CInterval

from ..branches import BranchMap as _BranchMap, merge_branch_maps as _merge_branch_maps
from ..charts import _combine_charts
from ..values import _EvalResult, _EvalSet
from ..operations import _IntervalOps
from ..sets import _eval_set
from ..numeric import _bool_and, _interval_is_point


def _common_factor_result(
    name: str,
    arguments: tuple[_EvalResult, ...],
    ops: _IntervalOps,
) -> _EvalResult:
    defined = _bool_and(*(argument.defined for argument in arguments))
    operation = ops.gcd if name == "gcd" else ops.lcm
    value = operation(*(argument.interval for argument in arguments))
    return _EvalResult(
        value,
        defined,
        all(argument.continuous for argument in arguments)
        and all(_interval_is_point(argument.interval, ops) for argument in arguments),
    )


def _common_factor_eval_set(
    arguments: tuple[_EvalSet, ...],
    operation: Callable[[_CInterval, _CInterval], _CInterval],
    ops: _IntervalOps,
) -> _EvalSet:
    def combine(branch_set: tuple[_EvalResult, ...]) -> _EvalResult | None:
        branch_map: _BranchMap = ()
        for branch in branch_set:
            merged = _merge_branch_maps(branch_map, branch.branch_map)
            if merged is None:
                return None
            branch_map = merged
        return _EvalResult(
            operation(*(branch.interval for branch in branch_set)),
            _bool_and(*(branch.defined for branch in branch_set)),
            all(branch.continuous for branch in branch_set)
            and all(_interval_is_point(branch.interval, ops) for branch in branch_set),
            _combine_charts(ops, *(branch.chart for branch in branch_set)),
            branch_map=branch_map,
        )

    if all(len(argument.branches) == 1 for argument in arguments):
        # Keep exact finite point GCD/LCM rational until its final outward
        # conversion. A binary fold could round a nonrepresentable LCM early.
        combined = combine(tuple(argument.branches[0] for argument in arguments))
        return _eval_set(
            () if combined is None else (combined,),
            _bool_and(*(argument.defined for argument in arguments)),
            all(argument.continuous for argument in arguments),
            ops,
        )

    # Real common divisors/multiples compose associatively. Tupper paper §11
    # permits conservative merging between set operations: with each input
    # capped at eight branches, each step creates at most 64 candidates.
    # Intermediate enclosures may widen; never recover charts/continuity lost
    # in compaction, or skip an operand's domain even after reaching zero.
    result = arguments[0]
    for argument in arguments[1:]:
        result = _eval_set(
            tuple(
                combined
                for left in result.branches
                for right in argument.branches
                if (combined := combine((left, right))) is not None
            ),
            _bool_and(result.defined, argument.defined),
            result.continuous and argument.continuous,
            ops,
        )
    return result
