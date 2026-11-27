# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Polar-angle interval-set evaluation with preserved domains and cut covers."""

from __future__ import annotations

import math

from ..branches import merge_branch_maps as _merge_branch_maps
from ..values import _EvalResult, _EvalSet
from ..operations import _IntervalOps
from ..charts import _combine_charts
from ..sets import _eval_set
from ..numeric import (
    _BOOL_FALSE,
    _BOOL_MAYBE,
    _BOOL_TRUE,
    _atan2_crosses_branch_cut,
    _atan2_interval_domain,
    _bool_and,
    _bool_is_false,
    _bool_is_true,
    _interval_is_point,
)
from ..numeric import _CBoolInterval


def _atan2_result(
    y_result: _EvalResult,
    x_result: _EvalResult,
    ops: _IntervalOps,
) -> _EvalResult:
    domain = _atan2_interval_domain(
        y_result.interval,
        x_result.interval,
        ops,
    )
    defined = _bool_and(y_result.defined, x_result.defined, domain)
    value = ops.atan2(y_result.interval, x_result.interval)
    point_value = _interval_is_point(value, ops)
    return _EvalResult(
        value,
        defined,
        y_result.continuous
        and x_result.continuous
        and _bool_is_true(domain)
        and not _atan2_crosses_branch_cut(
            y_result.interval,
            x_result.interval,
        ),
        constant=(
            value.lo
            if y_result.constant is not None
            and x_result.constant is not None
            and point_value
            and math.isfinite(value.lo)
            else None
        ),
    )


def _atan2_eval_set(
    y_result: _EvalSet,
    x_result: _EvalSet,
    ops: _IntervalOps,
) -> _EvalSet:
    domain_values: list[_CBoolInterval] = []
    branches: list[_EvalResult] = []
    for y_branch in y_result.branches:
        for x_branch in x_result.branches:
            branch_map = _merge_branch_maps(y_branch.branch_map, x_branch.branch_map)
            if branch_map is None:
                continue
            domain = _atan2_interval_domain(
                y_branch.interval,
                x_branch.interval,
                ops,
            )
            domain_values.append(domain)
            if _bool_is_false(domain):
                continue
            branch_defined = _bool_and(
                y_branch.defined,
                x_branch.defined,
                domain,
            )
            y, x = y_branch.interval, x_branch.interval
            if (
                x.hi <= 0.0
                and _atan2_crosses_branch_cut(y, x)
                and math.isfinite(x.lo)
                and math.isfinite(y.lo)
                and math.isfinite(y.hi)
            ):
                # Tupper 3.2.22–3.2.24: retain both one-sided value ranges.
                # -pi is a limit; the included negative axis has value +pi.
                # These are not input charts: neither range is continuous
                # over the operand box, and an included origin stays partial.
                pi = ops.pi_multiple(1, 1)
                negative_end = ops.atan2(ops.point(y.lo), ops.point(x.hi))
                positive_end = (
                    pi
                    if x.hi == y.hi == 0.0
                    else ops.atan2(ops.point(y.hi), ops.point(x.hi))
                )
                branches.extend(
                    (
                        _EvalResult(
                            ops.make(-pi.hi, negative_end.hi),
                            branch_defined,
                            False,
                            branch_map=branch_map,
                        ),
                        _EvalResult(
                            ops.make(positive_end.lo, pi.hi),
                            branch_defined,
                            False,
                            branch_map=branch_map,
                        ),
                    )
                )
                ops.record_operator_sections(
                    "atan2",
                    2,
                    noncontinuous_sections=2,
                    missing_chart_sections=(
                        2
                        if y_branch.chart is not None or x_branch.chart is not None
                        else 0
                    ),
                )
                continue
            value = ops.atan2(y, x)
            continuous = (
                y_branch.continuous
                and x_branch.continuous
                and _bool_is_true(branch_defined)
                and not _atan2_crosses_branch_cut(
                    y_branch.interval,
                    x_branch.interval,
                )
            )
            chart = _combine_charts(ops, y_branch.chart, x_branch.chart)
            point_value = _interval_is_point(value, ops)
            branches.append(
                _EvalResult(
                    value,
                    branch_defined,
                    continuous,
                    chart,
                    branch_map=branch_map,
                    constant=(
                        value.lo
                        if y_branch.constant is not None
                        and x_branch.constant is not None
                        and point_value
                        and math.isfinite(value.lo)
                        else None
                    ),
                )
            )
            ops.record_operator_sections(
                "atan2",
                1,
                noncontinuous_sections=int(not continuous),
                missing_chart_sections=int(
                    (y_branch.chart is not None or x_branch.chart is not None)
                    and chart is None
                ),
            )
    if domain_values and all(_bool_is_true(value) for value in domain_values):
        domain = _BOOL_TRUE
    elif domain_values and all(_bool_is_false(value) for value in domain_values):
        domain = _BOOL_FALSE
    else:
        domain = _BOOL_MAYBE
    defined = _bool_and(y_result.defined, x_result.defined, domain)
    return _eval_set(
        tuple(branches),
        defined,
        y_result.continuous and x_result.continuous and _bool_is_true(defined),
        ops,
    )
