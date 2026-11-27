# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Periodic sin/cos/tan set evaluation with preserved domain and chart metadata."""

from __future__ import annotations

from typing import Callable
from ..numeric import _CInterval
from ..operations import _ResultFactory, _SetFactory

from ..values import _EvalResult, _EvalSet
from ..operations import _IntervalOps
from ..charts import _chart_for_section
from ..sets import _eval_set
from ..numeric import (
    _tan_interval_sections,
    _BOOL_FALSE,
    _BOOL_TRUE,
    _BOOL_MAYBE,
    _bool_and,
    _bool_is_false,
    _bool_is_true,
)
from ..numeric import _CBoolInterval


def _periodic_scalar_result(
    result_factory: Callable[[_CInterval, _CBoolInterval, bool], _EvalResult],
    value: _CInterval,
    argument: _EvalResult,
) -> _EvalResult:
    return result_factory(value, argument.defined, argument.continuous)


def _periodic_scalar_constant_result(
    result_factory: _ResultFactory,
    value: _CInterval,
    argument: _EvalResult,
    constant: float,
) -> _EvalResult:
    return result_factory(
        value, argument.defined, argument.continuous, constant=constant
    )


def _tan_result(argument: _EvalResult, ops: _IntervalOps) -> _EvalResult:
    tangent_domain = _bool_and(argument.defined, ops.tan_defined(argument.interval))
    return _EvalResult(
        ops.tan(argument.interval),
        tangent_domain,
        argument.continuous and _bool_is_true(tangent_domain),
    )


def _periodic_constant_eval_set(
    set_factory: _SetFactory,
    argument: _EvalSet,
    ops: _IntervalOps,
    constant: float,
) -> _EvalSet:
    return set_factory(
        tuple(
            _EvalResult(
                ops.point(constant),
                branch.defined,
                branch.continuous,
                branch.chart,
                branch_map=branch.branch_map,
                constant=constant,
            )
            for branch in argument.branches
        ),
        argument.defined,
        argument.continuous,
        ops,
    )


def _periodic_unary_eval_set(
    argument: _EvalSet,
    operation: Callable[[_CInterval], _CInterval],
    ops: _IntervalOps,
    *,
    operator_name: str,
    expression_source: str | None = None,
    phase_numerator: int,
    period_numerator: int,
    denominator: int,
) -> _EvalSet:
    branches: list[_EvalResult] = []
    for branch in argument.branches:
        if branch.affine is not None and operator_name in {"sin", "cos"}:
            # Extrema alone make sin/cos monotone, but a monotone section can
            # still cross zero. A later division then splits the output at
            # zero and cannot recover which half of the affine input chart it
            # belongs to. On affine phases, split at every pi/2 instead: these
            # are exactly the alternating extrema and roots, so nonzero
            # quotient sections retain their already-narrowed chart domains.
            cover = ops.periodic_interval_cover(
                branch.interval,
                phase_numerator=0,
                period_numerator=1,
                denominator=2,
                boundary_continuous=True,
                max_sections=8,
                fallback_continuous=True,
            )
        else:
            cover = ops.periodic_interval_cover(
                branch.interval,
                phase_numerator=phase_numerator,
                period_numerator=period_numerator,
                denominator=denominator,
                boundary_continuous=True,
                max_sections=8,
                fallback_continuous=True,
            )
        missing_chart_sections = 0
        for section in cover.sections:
            chart = _chart_for_section(branch, section.interval, ops)
            missing_chart = branch.chart is not None and chart is None
            missing_chart_sections += int(missing_chart)
            if missing_chart and expression_source is not None:
                ops.record_chart_loss(
                    operator_name,
                    expression_source,
                    "periodic_section_preimage",
                )
            branches.append(
                _EvalResult(
                    operation(section.interval),
                    branch.defined,
                    branch.continuous and section.continuous,
                    chart,
                    branch_map=branch.branch_map,
                )
            )
        ops.record_operator_sections(
            operator_name,
            len(cover.sections),
            noncontinuous_sections=sum(
                1 for section in cover.sections if not section.continuous
            ),
            missing_chart_sections=missing_chart_sections,
        )
    return _eval_set(
        tuple(branches),
        argument.defined,
        argument.continuous,
        ops,
        piecewise_continuous=True,
    )


def _tan_eval_set(argument: _EvalSet, ops: _IntervalOps) -> _EvalSet:
    branches: list[_EvalResult] = []
    branch_domains: list[_CBoolInterval] = []
    for branch in argument.branches:
        branch_domain = _bool_and(branch.defined, ops.tan_defined(branch.interval))
        branch_domains.append(branch_domain)
        sections = _tan_interval_sections(branch.interval, ops)
        missing_chart_sections = 0
        for section, input_section in sections:
            section_domain = _bool_and(branch.defined, ops.tan_defined(input_section))
            chart = _chart_for_section(branch, input_section, ops)
            missing_chart_sections += int(branch.chart is not None and chart is None)
            branches.append(
                _EvalResult(
                    section.interval,
                    section_domain,
                    branch.continuous
                    and section.continuous
                    and _bool_is_true(section_domain),
                    chart,
                    branch_map=branch.branch_map,
                )
            )
        ops.record_operator_sections(
            "tan",
            len(sections),
            noncontinuous_sections=sum(
                1 for section, _ in sections if not section.continuous
            ),
            missing_chart_sections=missing_chart_sections,
        )

    if not branch_domains:
        tangent_domain = _BOOL_FALSE
    elif all(_bool_is_true(domain) for domain in branch_domains):
        tangent_domain = _BOOL_TRUE
    elif all(_bool_is_false(domain) for domain in branch_domains):
        tangent_domain = _BOOL_FALSE
    else:
        tangent_domain = _BOOL_MAYBE
    domain = _bool_and(argument.defined, tangent_domain)
    return _eval_set(
        tuple(branches), domain, argument.continuous and _bool_is_true(domain), ops
    )
