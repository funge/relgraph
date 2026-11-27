# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Experimental headless arithmetic primitives."""

from __future__ import annotations

from typing import Callable
from .values import _CInterval, _EvalResult, _EvalSet
from .definedness import (
    BoolInterval as _CBoolInterval,
    bool_and as _bool_and,
    bool_is_true as _bool_is_true,
)
from .operations import _IntervalOps
from .branches import merge_branch_maps as _merge_branch_maps
from .charts import _combine_charts
from .metadata import (
    _binary_affine,
    _binary_interval_affine,
    _neg_interval_affine,
    _binary_constant,
    _binary_quadratic,
    _neg_affine,
    _neg_reciprocal_affine,
    _neg_quadratic,
)
from .sets import _eval_set


def _negate_eval_set(operand: _EvalSet, ops: _IntervalOps) -> _EvalSet:
    branches = tuple(
        _EvalResult(
            ops.neg(branch.interval),
            branch.defined,
            branch.continuous,
            branch.chart,
            affine=_neg_affine(branch.affine),
            constant=-branch.constant if branch.constant is not None else None,
            reciprocal_affine=_neg_reciprocal_affine(branch.reciprocal_affine),
            quadratic=_neg_quadratic(branch.quadratic),
            interval_affine=_neg_interval_affine(branch.interval_affine, ops),
            branch_map=branch.branch_map,
        )
        for branch in operand.branches
    )
    return _eval_set(branches, operand.defined, operand.continuous, ops)


def _minmax_result(
    left: _EvalResult,
    right: _EvalResult,
    operation: Callable[[_CInterval, _CInterval], _CInterval],
) -> _EvalResult:
    defined = _bool_and(left.defined, right.defined)
    return _EvalResult(
        operation(left.interval, right.interval),
        defined,
        left.continuous and right.continuous and _bool_is_true(defined),
    )


def _negate_result(operand: _EvalResult, ops: _IntervalOps) -> _EvalResult:
    return _EvalResult(ops.neg(operand.interval), operand.defined, operand.continuous)


def _add_result(
    left: _EvalResult,
    right: _EvalResult,
    defined: _CBoolInterval,
    continuous: bool,
    ops: _IntervalOps,
) -> _EvalResult:
    return _EvalResult(ops.add(left.interval, right.interval), defined, continuous)


def _subtract_result(
    left: _EvalResult,
    right: _EvalResult,
    defined: _CBoolInterval,
    continuous: bool,
    ops: _IntervalOps,
) -> _EvalResult:
    return _EvalResult(ops.sub(left.interval, right.interval), defined, continuous)


def _multiply_result(
    left: _EvalResult,
    right: _EvalResult,
    defined: _CBoolInterval,
    continuous: bool,
    ops: _IntervalOps,
) -> _EvalResult:
    return _EvalResult(ops.mul(left.interval, right.interval), defined, continuous)


def _binary_eval_set(
    left: _EvalSet,
    right: _EvalSet,
    operation: Callable[[_CInterval, _CInterval], _CInterval],
    ops: _IntervalOps,
    *,
    affine_operation: str | None = None,
    operator_name: str | None = None,
    expression_source: str | None = None,
) -> _EvalSet:
    defined = _bool_and(left.defined, right.defined)
    branches: list[_EvalResult] = []
    for left_branch in left.branches:
        for right_branch in right.branches:
            branch_map = _merge_branch_maps(
                left_branch.branch_map, right_branch.branch_map
            )
            if branch_map is None:
                continue
            chart = _combine_charts(ops, left_branch.chart, right_branch.chart)
            missing_chart = (
                left_branch.chart is not None or right_branch.chart is not None
            ) and (chart is None)
            if operator_name is not None:
                ops.record_operator_sections(
                    operator_name,
                    1,
                    missing_chart_sections=int(missing_chart),
                )
            if missing_chart and expression_source is not None:
                ops.record_chart_loss(
                    operator_name or affine_operation or "binary",
                    expression_source,
                    "combine_chart",
                )
            branches.append(
                _EvalResult(
                    operation(left_branch.interval, right_branch.interval),
                    _bool_and(left_branch.defined, right_branch.defined),
                    left_branch.continuous and right_branch.continuous,
                    chart,
                    branch_map=branch_map,
                    affine=_binary_affine(left_branch, right_branch, affine_operation)
                    if affine_operation is not None
                    else None,
                    constant=_binary_constant(
                        left_branch, right_branch, affine_operation
                    )
                    if affine_operation is not None
                    else None,
                    quadratic=_binary_quadratic(
                        left_branch, right_branch, affine_operation
                    )
                    if affine_operation is not None
                    else None,
                    interval_affine=_binary_interval_affine(
                        left_branch, right_branch, affine_operation, ops
                    ),
                )
            )
    return _eval_set(
        tuple(branches),
        defined,
        left.continuous and right.continuous,
        ops,
    )
