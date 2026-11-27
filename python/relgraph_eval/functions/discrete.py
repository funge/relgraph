# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Discrete scalar/factorial kernels; scope-sensitive floor/ceil dispatch is caller-owned."""

from __future__ import annotations
from typing import Callable
from ..values import _CInterval
import math
from ..branches import branch_choice as _branch_choice
from ..values import _EvalResult, _EvalSet
from ..operations import _IntervalOps
from ..charts import _chart_for_section
from ..sets import _eval_set
from ..numeric import (
    _integer_function_cover,
    _IntervalSection,
    _factorial_domain,
    _factorial_interval,
    _factorial_interval_hull,
    _interval_is_point,
    _BOOL_FALSE,
    _BOOL_MAYBE,
    _bool_and,
    _bool_is_false,
    _bool_is_true,
)


def _integer_scalar_result(
    operation: Callable[[_CInterval], _CInterval],
    argument: _EvalResult,
    ops: _IntervalOps,
) -> _EvalResult:
    value = operation(argument.interval)
    return _EvalResult(
        value,
        argument.defined,
        argument.continuous and _interval_is_point(value, ops),
    )


def _factorial_result(argument: _EvalResult, ops: _IntervalOps) -> _EvalResult:
    factorial_domain = _factorial_domain(argument.interval, ops)
    value = _factorial_interval_hull(argument.interval, ops)
    defined = _bool_and(argument.defined, factorial_domain)
    return _EvalResult(
        value,
        defined,
        argument.continuous
        and _bool_is_true(defined)
        and _interval_is_point(argument.interval, ops),
        constant=(
            value.lo
            if argument.constant is not None
            and _interval_is_point(value, ops)
            and math.isfinite(value.lo)
            else None
        ),
    )


def _factorial_eval_set(argument: _EvalSet, ops: _IntervalOps) -> _EvalSet:
    """Evaluate canonical factorial on its nonnegative-integer domain.

    GrafEQ defines factorial recursively for non-negative integers. Keep that
    partial domain explicit: only nonnegative-integer sections contribute a
    value. If the bounded integer cover cannot fit, retain a conservative
    hull without chart or continuity metadata.
    """
    branches: list[_EvalResult] = []
    invalid_sections = 0
    section_count = 0
    noncontinuous_sections = 0
    missing_chart_sections = 0
    for branch in argument.branches:
        if branch.constant is not None:
            sections = (_IntervalSection(branch.interval, True),)
        else:
            sections = _integer_function_cover(branch.interval, ops).sections
        section_count += len(sections)
        for section in sections:
            section_domain = _factorial_domain(section.interval, ops)
            if _bool_is_false(section_domain):
                invalid_sections += 1
                continue
            is_exact_input = _bool_is_true(section_domain) and _interval_is_point(
                section.interval, ops
            )
            value = (
                _factorial_interval(section.interval, ops)
                if is_exact_input
                else _factorial_interval_hull(section.interval, ops)
            )
            if ops.is_empty(value):
                invalid_sections += 1
                continue
            chart = (
                _chart_for_section(branch, section.interval, ops)
                if is_exact_input
                else None
            )
            missing_chart_sections += int(branch.chart is not None and chart is None)
            point_value = _interval_is_point(value, ops)
            continuous = (
                branch.continuous and is_exact_input and _bool_is_true(branch.defined)
            )
            if not _bool_is_true(section_domain):
                invalid_sections += 1
            noncontinuous_sections += int(not continuous)
            branches.append(
                _EvalResult(
                    value,
                    _bool_and(branch.defined, section_domain),
                    continuous,
                    chart,
                    branch_map=branch.branch_map,
                    constant=value.lo
                    if point_value and math.isfinite(value.lo)
                    else None,
                )
            )
    ops.record_operator_sections(
        "factorial",
        section_count,
        noncontinuous_sections=noncontinuous_sections,
        missing_chart_sections=missing_chart_sections,
    )
    if not branches:
        defined = _BOOL_FALSE
    elif invalid_sections:
        defined = _bool_and(argument.defined, _BOOL_MAYBE)
    else:
        defined = argument.defined
    return _eval_set(
        tuple(branches),
        defined,
        argument.continuous and not invalid_sections and _bool_is_true(defined),
        ops,
        piecewise_continuous=True,
    )


def _integer_function_result(
    branch: _EvalResult,
    operation: Callable[[_CInterval], _CInterval],
    ops: _IntervalOps,
    *,
    branch_site: object | None = None,
) -> _EvalResult:
    value = operation(branch.interval)
    point_value = _interval_is_point(value, ops)
    return _EvalResult(
        value,
        branch.defined,
        branch.continuous and point_value,
        branch.chart,
        constant=value.lo if point_value and math.isfinite(value.lo) else None,
        branch_map=_branch_choice(
            branch.branch_map,
            branch_site,
            int(value.lo) if point_value and math.isfinite(value.lo) else None,
        ),
    )
