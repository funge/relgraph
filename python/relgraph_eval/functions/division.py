# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Division evaluation with exact denominator domains and section charts."""

from __future__ import annotations

from ..definedness import BoolInterval as _CBoolInterval

from ..branches import merge_branch_maps as _merge_branch_maps
from ..values import _EvalResult, _EvalSet, _ReciprocalAffineCoordinate
from ..operations import _IntervalOps
from ..charts import _chart_for_section, _combine_charts
from ..metadata import (
    _binary_affine,
    _binary_constant,
    _binary_quadratic,
    _make_reciprocal_affine,
)
from ..rational_refinement import _LinearRationalPlan, _refine_linear_rational_interval
from ..sets import _branches_nonzero, _eval_set
from ..numeric import (
    _bool_and,
    _bool_is_true,
    _div_interval_sections,
    _interval_nonzero,
)


def _division_result(
    left: _EvalResult,
    right: _EvalResult,
    defined: _CBoolInterval,
    continuous: bool,
    ops: _IntervalOps,
    *,
    rational_plan: _LinearRationalPlan | None = None,
) -> _EvalResult:
    denom_nonzero = _interval_nonzero(right.interval, ops)
    div_defined = _bool_and(defined, denom_nonzero)
    result_factory = _EvalResult
    interval = ops.div(left.interval, right.interval)
    result_continuous = continuous and _bool_is_true(denom_nonzero)
    if rational_plan is not None:
        interval = _refine_linear_rational_interval(
            rational_plan, right.interval, interval, ops
        )
    return result_factory(interval, div_defined, result_continuous)


def _division_reciprocal_affine(
    left: _EvalResult,
    right: _EvalResult,
) -> _ReciprocalAffineCoordinate | None:
    if left.constant is None or left.constant == 0.0 or right.affine is None:
        return None
    return _make_reciprocal_affine(
        right.affine.axis,
        left.constant,
        right.affine.scale,
        right.affine.offset,
    )


def _division_eval_set(
    left: _EvalSet,
    right: _EvalSet,
    ops: _IntervalOps,
    *,
    expression_source: str | None = None,
    rational_plan: _LinearRationalPlan | None = None,
) -> _EvalSet:
    denom_nonzero = _branches_nonzero(right.branches, ops)
    defined = _bool_and(left.defined, right.defined, denom_nonzero)
    branches: list[_EvalResult] = []
    for left_branch in left.branches:
        for right_branch in right.branches:
            branch_map = _merge_branch_maps(
                left_branch.branch_map, right_branch.branch_map
            )
            if branch_map is None:
                continue
            sections = _div_interval_sections(
                left_branch.interval,
                right_branch.interval,
                ops,
            )
            missing_chart_sections = 0
            for quotient, denominator_defined, denominator_section in sections:
                branch_defined = _bool_and(
                    left_branch.defined,
                    right_branch.defined,
                    denominator_defined,
                )
                denominator_chart = _chart_for_section(
                    right_branch, denominator_section, ops
                )
                chart = _combine_charts(ops, left_branch.chart, denominator_chart)
                missing_chart = (
                    left_branch.chart is not None or right_branch.chart is not None
                ) and chart is None
                missing_chart_sections += int(missing_chart)
                if missing_chart and expression_source is not None:
                    if right_branch.chart is None:
                        reason = "denominator_chart_missing"
                    elif denominator_chart is None:
                        reason = "denominator_section_preimage"
                    else:
                        reason = "combine_chart"
                    ops.record_chart_loss("div", expression_source, reason)
                result_factory = _EvalResult
                interval = quotient.interval
                continuous = (
                    left_branch.continuous
                    and right_branch.continuous
                    and quotient.continuous
                    and _bool_is_true(branch_defined)
                )
                affine = _binary_affine(left_branch, right_branch, "div")
                constant = _binary_constant(left_branch, right_branch, "div")
                reciprocal_affine = _division_reciprocal_affine(
                    left_branch, right_branch
                )
                quadratic = _binary_quadratic(left_branch, right_branch, "div")
                if rational_plan is not None:
                    interval = _refine_linear_rational_interval(
                        rational_plan, denominator_section, interval, ops
                    )
                branches.append(
                    result_factory(
                        interval,
                        branch_defined,
                        continuous,
                        chart,
                        affine=affine,
                        constant=constant,
                        reciprocal_affine=reciprocal_affine,
                        quadratic=quadratic,
                        branch_map=branch_map,
                    )
                )
            ops.record_operator_sections(
                "div",
                len(sections),
                noncontinuous_sections=sum(
                    1 for quotient, _, _ in sections if not quotient.continuous
                ),
                missing_chart_sections=missing_chart_sections,
            )
    return _eval_set(
        tuple(branches), defined, left.continuous and right.continuous, ops
    )
