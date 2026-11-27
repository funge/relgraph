# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Positive and truncating remainder set policies with conditional value covers."""

from __future__ import annotations

import math
from fractions import Fraction

from ..branches import (
    branch_choice as _branch_choice,
    merge_branch_maps as _merge_branch_maps,
)
from ..values import _AffineCoordinate, _EvalResult, _EvalSet
from ..operations import _IntervalOps
from ..charts import _combine_charts
from ..metadata import _make_affine
from ..sets import _eval_set, _branches_nonzero
from ..numeric import (
    _RemainderIntervalSection,
    _remainder_interval_sections,
    _interval_nonzero,
    _interval_is_point,
    _BOOL_MAYBE,
    _bool_and,
    _bool_is_false,
    _bool_is_true,
)


def _remainder_result(
    name: str,
    left: _EvalResult,
    right: _EvalResult,
    ops: _IntervalOps,
) -> _EvalResult:
    modulus_nonzero = _interval_nonzero(right.interval, ops)
    defined = _bool_and(left.defined, right.defined, modulus_nonzero)
    operation = ops.mod if name == "mod" else ops.fmod
    return _EvalResult(
        operation(left.interval, right.interval),
        defined,
        False,
    )


def _mod_eval_set(
    left: _EvalSet,
    right: _EvalSet,
    ops: _IntervalOps,
    *,
    branch_site: object | None = None,
) -> _EvalSet:
    return _remainder_eval_set(
        left, right, ops, operation_name="mod", branch_site=branch_site
    )


def _fmod_eval_set(left: _EvalSet, right: _EvalSet, ops: _IntervalOps) -> _EvalSet:
    return _remainder_eval_set(left, right, ops, operation_name="fmod")


def _remainder_eval_set(
    left: _EvalSet,
    right: _EvalSet,
    ops: _IntervalOps,
    *,
    operation_name: str,
    branch_site: object | None = None,
) -> _EvalSet:
    modulus_nonzero = _branches_nonzero(right.branches, ops)
    defined = _bool_and(left.defined, right.defined, modulus_nonzero)
    split_mod_ranges = (
        operation_name == "mod"
        and len(left.branches) == len(right.branches) == 1
        and _bool_is_true(defined)
    )
    branches: list[_EvalResult] = []
    for left_branch in left.branches:
        for right_branch in right.branches:
            branch_map = _merge_branch_maps(
                left_branch.branch_map, right_branch.branch_map
            )
            if branch_map is None:
                continue
            domain = _interval_nonzero(right_branch.interval, ops)
            if _bool_is_false(domain):
                continue
            branch_defined = _bool_and(
                left_branch.defined,
                right_branch.defined,
                domain,
            )
            sections = _remainder_interval_sections(
                left_branch.interval,
                right_branch.interval,
                ops,
                operation_name=operation_name,
                split_mod_ranges=split_mod_ranges,
            )
            if len(sections) > 1:
                # These are conditional value ranges, not input charts. The
                # union covers the original domain; neither piece alone does.
                branches.extend(
                    _EvalResult(
                        section.output.interval,
                        _BOOL_MAYBE,
                        False,
                        branch_map=_branch_choice(
                            branch_map, branch_site, section.quotient
                        ),
                    )
                    for section in sections
                )
                ops.record_operator_sections(
                    operation_name,
                    len(sections),
                    noncontinuous_sections=len(sections),
                    missing_chart_sections=(
                        len(sections)
                        if left_branch.chart is not None
                        or right_branch.chart is not None
                        else 0
                    ),
                )
                continue
            section = sections[0]
            chart = _combine_charts(ops, left_branch.chart, right_branch.chart)
            continuous = (
                left_branch.continuous
                and right_branch.continuous
                and section.output.continuous
                and _bool_is_true(branch_defined)
            )
            point_value = _interval_is_point(section.output.interval, ops)
            branches.append(
                _EvalResult(
                    section.output.interval,
                    branch_defined,
                    continuous,
                    chart,
                    affine=_remainder_affine(left_branch, section),
                    branch_map=_branch_choice(
                        branch_map, branch_site, section.quotient
                    ),
                    constant=(
                        section.output.interval.lo
                        if left_branch.constant is not None
                        and right_branch.constant is not None
                        and point_value
                        and math.isfinite(section.output.interval.lo)
                        else None
                    ),
                )
            )
            ops.record_operator_sections(
                operation_name,
                1,
                noncontinuous_sections=int(not continuous),
                missing_chart_sections=int(
                    (left_branch.chart is not None or right_branch.chart is not None)
                    and chart is None
                ),
            )
    return _eval_set(
        tuple(branches),
        defined,
        left.continuous and right.continuous and _bool_is_true(defined),
        ops,
        piecewise_continuous=True,
    )


def _remainder_affine(
    branch: _EvalResult,
    section: _RemainderIntervalSection,
) -> _AffineCoordinate | None:
    if branch.affine is None or section.affine_shift is None:
        return None
    return _make_affine(
        branch.affine.axis,
        branch.affine.scale,
        Fraction(branch.affine.offset) - Fraction(section.affine_shift),
    )
