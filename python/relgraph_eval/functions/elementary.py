# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Elementary unary evaluation with preserved domains and metadata."""

from __future__ import annotations

from typing import Callable
from ..numeric import _CInterval

import math

from ..values import _EvalResult, _EvalSet
from ..operations import _IntervalOps
from ..sets import _branches_nonnegative, _eval_set
from ..numeric import (
    _BOOL_FALSE,
    _BOOL_MAYBE,
    _BOOL_TRUE,
    _bool_and,
    _bool_is_false,
    _bool_is_true,
    _interval_is_point,
    _log2_domain,
    _sqrt_domain,
)
from ..numeric import _CBoolInterval


def _elementary_unary_eval_set(
    name: str,
    argument: _EvalSet,
    ops: _IntervalOps,
) -> _EvalSet:
    branches = tuple(
        _elementary_unary_result(name, branch, ops) for branch in argument.branches
    )
    domains = tuple(branch.defined for branch in branches)
    domain = (
        _BOOL_FALSE
        if not domains or all(_bool_is_false(d) for d in domains)
        else _BOOL_TRUE
        if all(_bool_is_true(d) for d in domains)
        else _BOOL_MAYBE
    )
    defined = _bool_and(argument.defined, domain)
    return _eval_set(
        branches, defined, argument.continuous and _bool_is_true(defined), ops
    )


def _elementary_scalar_result(
    result_factory: Callable[[_CInterval, _CBoolInterval, bool], _EvalResult],
    value: _CInterval,
    argument: _EvalResult,
) -> _EvalResult:
    return result_factory(value, argument.defined, argument.continuous)


def _atan_result(argument: _EvalResult, ops: _IntervalOps) -> _EvalResult:
    value = ops.atan(argument.interval)
    point_value = _interval_is_point(value, ops)
    return _EvalResult(
        value,
        argument.defined,
        argument.continuous,
        constant=(
            value.lo
            if argument.constant is not None and point_value and math.isfinite(value.lo)
            else None
        ),
    )


def _log2_result(argument: _EvalResult, ops: _IntervalOps) -> _EvalResult:
    log2_domain = _log2_domain(argument.interval, argument.defined, ops)
    value = ops.log2(argument.interval)
    return _EvalResult(
        value,
        log2_domain,
        argument.continuous and _bool_is_true(log2_domain),
        constant=(
            value.lo
            if argument.constant is not None
            and _interval_is_point(value, ops)
            and math.isfinite(value.lo)
            else None
        ),
    )


def _sqrt_result(argument: _EvalResult, ops: _IntervalOps) -> _EvalResult:
    sqrt_domain = _sqrt_domain(argument.interval, argument.defined, ops)
    return _EvalResult(
        ops.sqrt(argument.interval),
        sqrt_domain,
        argument.continuous and _bool_is_true(sqrt_domain),
    )


def _unary_eval_set(
    argument: _EvalSet, operation: Callable[[_CInterval], _CInterval], ops: _IntervalOps
) -> _EvalSet:
    branches = tuple(
        _EvalResult(
            operation(branch.interval),
            branch.defined,
            branch.continuous,
            branch.chart,
            branch_map=branch.branch_map,
        )
        for branch in argument.branches
    )
    return _eval_set(branches, argument.defined, argument.continuous, ops)


def _atan_eval_set(argument: _EvalSet, ops: _IntervalOps) -> _EvalSet:
    branches = []
    for branch in argument.branches:
        value = ops.atan(branch.interval)
        point_value = _interval_is_point(value, ops)
        branches.append(
            _EvalResult(
                value,
                branch.defined,
                branch.continuous,
                branch.chart,
                branch_map=branch.branch_map,
                constant=(
                    value.lo
                    if branch.constant is not None
                    and point_value
                    and math.isfinite(value.lo)
                    else None
                ),
            )
        )
    return _eval_set(tuple(branches), argument.defined, argument.continuous, ops)


def _sqrt_eval_set(argument: _EvalSet, ops: _IntervalOps) -> _EvalSet:
    domain = _bool_and(argument.defined, _branches_nonnegative(argument.branches, ops))
    branches: list[_EvalResult] = []
    for branch in argument.branches:
        branch_domain = _sqrt_domain(branch.interval, branch.defined, ops)
        if _bool_is_false(branch_domain):
            ops.record_operator_sections("sqrt", 0)
            continue
        continuous = branch.continuous and _bool_is_true(branch_domain)
        ops.record_operator_sections(
            "sqrt",
            1,
            noncontinuous_sections=int(not continuous),
        )
        branches.append(
            _EvalResult(
                ops.sqrt(branch.interval),
                branch_domain,
                continuous,
                branch.chart,
                branch_map=branch.branch_map,
            )
        )
    return _eval_set(
        tuple(branches), domain, argument.continuous and _bool_is_true(domain), ops
    )


def _log2_eval_set(argument: _EvalSet, ops: _IntervalOps) -> _EvalSet:
    branch_domains: list[_CBoolInterval] = []
    branches: list[_EvalResult] = []
    for branch in argument.branches:
        branch_domain = _log2_domain(branch.interval, branch.defined, ops)
        branch_domains.append(branch_domain)
        if _bool_is_false(branch_domain):
            ops.record_operator_sections("log2", 0)
            continue
        value = ops.log2(branch.interval)
        continuous = branch.continuous and _bool_is_true(branch_domain)
        ops.record_operator_sections(
            "log2",
            1,
            noncontinuous_sections=int(not continuous),
        )
        branches.append(
            _EvalResult(
                value,
                branch_domain,
                continuous,
                branch.chart,
                branch_map=branch.branch_map,
                constant=(
                    value.lo
                    if branch.constant is not None
                    and _interval_is_point(value, ops)
                    and math.isfinite(value.lo)
                    else None
                ),
            )
        )

    if not branch_domains or all(_bool_is_false(domain) for domain in branch_domains):
        log2_domain = _BOOL_FALSE
    elif all(_bool_is_true(domain) for domain in branch_domains):
        log2_domain = _BOOL_TRUE
    else:
        log2_domain = _BOOL_MAYBE
    domain = _bool_and(argument.defined, log2_domain)
    return _eval_set(
        tuple(branches),
        domain,
        argument.continuous and _bool_is_true(domain),
        ops,
    )


def _elementary_unary_result(
    name: str, argument: _EvalResult, ops: _IntervalOps
) -> _EvalResult:
    value = argument.interval
    domain = argument.defined
    if ops.is_empty(value):
        domain = _BOOL_FALSE
    elif name in {"ln", "log10"}:
        domain = _log2_domain(value, domain, ops)
    elif name in {"asin", "acos"}:
        if value.hi < -1.0 or value.lo > 1.0:
            domain = _BOOL_FALSE
        elif value.lo < -1.0 or value.hi > 1.0:
            domain = _bool_and(domain, _BOOL_MAYBE)
    elif name == "acosh":
        if value.hi < 1.0:
            domain = _BOOL_FALSE
        elif value.lo < 1.0:
            domain = _bool_and(domain, _BOOL_MAYBE)
    elif name == "atanh":
        if value.hi <= -1.0 or value.lo >= 1.0:
            domain = _BOOL_FALSE
        elif value.lo <= -1.0 or value.hi >= 1.0:
            domain = _bool_and(domain, _BOOL_MAYBE)
    if _bool_is_false(domain):
        return _EvalResult(ops.empty(), domain, False)
    return _EvalResult(
        ops.elementary(name, value),
        domain,
        argument.continuous and _bool_is_true(domain),
        argument.chart,
        branch_map=argument.branch_map,
    )
