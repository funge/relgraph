# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Integer and positive-base power evaluation with exact domains and metadata."""

from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction

from .elementary import _sqrt_result, _sqrt_eval_set, _unary_eval_set
from ..numeric import _CBoolInterval, _CInterval

from ..branches import merge_branch_maps as _merge_branch_maps

from ..values import (
    _EvalResult,
    _EvalSet,
    _QuadraticCoordinate,
    _ReciprocalAffineCoordinate,
)
from ..operations import _IntervalOps
from ..charts import _chart_for_section, _combine_charts
from ..metadata import _make_reciprocal_affine, _make_quadratic, _power_constant
from ..sets import _branches_nonzero, _branches_nonnegative, _eval_set
from ..numeric import (
    _BOOL_FALSE,
    _BOOL_MAYBE,
    _BOOL_TRUE,
    _bool_and,
    _bool_is_true,
    _log2_domain,
    _positive_base_pow_interval,
    _positive_constant_base_pow_interval,
    _pow_interval,
    _power_interval_sections,
    _interval_nonzero,
    _rational_root_interval,
    _sqrt_domain,
    _positive_x_power_x_range,
    _negative_x_power_x_magnitude_range,
)


def _integer_power_result(
    left: _EvalResult,
    exponent: int,
    pow_defined: _CBoolInterval,
    pow_continuous: bool,
    ops: _IntervalOps,
) -> _EvalResult:
    value = _pow_interval(left.interval, exponent, ops)
    if exponent < 0:
        base_nonzero = _interval_nonzero(left.interval, ops)
        pow_defined = _bool_and(pow_defined, base_nonzero)
        pow_continuous = pow_continuous and _bool_is_true(base_nonzero)
    return _EvalResult(
        value,
        pow_defined,
        pow_continuous and _bool_is_true(pow_defined),
    )


def _positive_integer_literal_power_result(
    literal_base: int,
    right: _EvalResult,
    ops: _IntervalOps,
) -> _EvalResult:
    return _EvalResult(
        ops.pow_positive_integer_base(literal_base, right.interval),
        right.defined,
        right.continuous and _bool_is_true(right.defined),
    )


def _power_reciprocal_affine(
    branch: _EvalResult,
    exponent: int,
) -> _ReciprocalAffineCoordinate | None:
    if exponent != -1 or branch.affine is None:
        return None
    return _make_reciprocal_affine(
        branch.affine.axis,
        1.0,
        branch.affine.scale,
        branch.affine.offset,
    )


def _power_quadratic(branch: _EvalResult, exponent: int) -> _QuadraticCoordinate | None:
    if exponent == 1:
        return branch.quadratic
    if exponent != 2 or branch.coordinate not in {"x", "y"} or branch.chart is None:
        return None
    axis_interval = branch.chart.x if branch.coordinate == "x" else branch.chart.y
    if axis_interval.lo <= 0.0 <= axis_interval.hi:
        return None
    return _make_quadratic(branch.coordinate, 1.0, 0.0)


def _power_eval_set(value: _EvalSet, exponent: int, ops: _IntervalOps) -> _EvalSet:
    base_nonzero = (
        _BOOL_TRUE if exponent >= 0 else _branches_nonzero(value.branches, ops)
    )
    defined = _bool_and(value.defined, base_nonzero)

    if exponent >= 0:
        branches = tuple(
            _EvalResult(
                _pow_interval(branch.interval, exponent, ops),
                branch.defined,
                branch.continuous,
                branch.chart,
                affine=branch.affine if exponent == 1 else None,
                interval_affine=branch.interval_affine if exponent == 1 else None,
                constant=_power_constant(branch.constant, exponent),
                quadratic=_power_quadratic(branch, exponent),
                branch_map=branch.branch_map,
            )
            for branch in value.branches
        )
    else:
        branches = tuple(
            _EvalResult(
                section.interval,
                branch_defined,
                branch.continuous
                and section.continuous
                and _bool_is_true(branch_defined),
                _chart_for_section(branch, base_section, ops),
                constant=_power_constant(branch.constant, exponent),
                reciprocal_affine=_power_reciprocal_affine(branch, exponent),
                branch_map=branch.branch_map,
            )
            for branch in value.branches
            for section, section_defined, base_section in _power_interval_sections(
                branch.interval,
                exponent,
                ops,
            )
            for branch_defined in (_bool_and(branch.defined, section_defined),)
        )
    return _eval_set(
        branches, defined, value.continuous and _bool_is_true(base_nonzero), ops
    )


def _positive_base_power_result(
    base: _EvalResult,
    exponent: _EvalResult,
    ops: _IntervalOps,
) -> _EvalResult:
    if not ops.is_empty(base.interval) and base.interval.hi <= 0.0:
        raise ValueError("noninteger exponents require a positive constant base")
    domain = _log2_domain(base.interval, base.defined, ops)
    defined = _bool_and(domain, exponent.defined)
    return _EvalResult(
        _positive_base_pow_interval(base.interval, exponent.interval, ops),
        defined,
        base.continuous and exponent.continuous and _bool_is_true(defined),
        _combine_charts(ops, base.chart, exponent.chart),
        constant=(
            _positive_constant_base_pow_constant(base.constant, exponent.constant)
            if base.constant is not None and base.constant > 0.0
            else None
        ),
    )


def _positive_base_power_eval_set(
    base: _EvalSet,
    exponent: _EvalSet,
    ops: _IntervalOps,
) -> _EvalSet:
    branches = tuple(
        replace(_positive_base_power_result(a, b, ops), branch_map=branch_map)
        for a in base.branches
        for b in exponent.branches
        if (branch_map := _merge_branch_maps(a.branch_map, b.branch_map)) is not None
    )
    domain = (
        _BOOL_TRUE if all(b.interval.lo > 0.0 for b in base.branches) else _BOOL_MAYBE
    )
    if not base.branches:
        domain = _BOOL_FALSE
    domain = _bool_and(base.defined, domain)
    defined = _bool_and(domain, exponent.defined)
    return _eval_set(
        branches,
        defined,
        base.continuous and exponent.continuous and _bool_is_true(defined),
        ops,
    )


def _positive_constant_base_power_eval_set(
    base: float,
    exponent: _EvalSet,
    ops: _IntervalOps,
    *,
    exact_base: bool,
) -> _EvalSet:
    branches = tuple(
        _EvalResult(
            _positive_constant_base_pow_interval(base, branch.interval, ops),
            branch.defined,
            branch.continuous,
            branch.chart,
            branch_map=branch.branch_map,
            constant=_positive_constant_base_pow_constant(base, branch.constant)
            if exact_base
            else None,
        )
        for branch in exponent.branches
    )
    return _eval_set(branches, exponent.defined, exponent.continuous, ops)


def _positive_constant_base_pow_constant(
    base: float, exponent: float | None
) -> float | None:
    if exponent is None or not exponent.is_integer():
        return None
    return _power_constant(base, int(exponent))


def _rational_root_result(
    argument: _EvalResult, denominator: int, ops: _IntervalOps
) -> _EvalResult:
    domain = (
        _sqrt_domain(argument.interval, argument.defined, ops)
        if denominator % 2 == 0
        else argument.defined
    )
    return _EvalResult(
        _rational_root_interval(argument.interval, denominator, ops),
        domain,
        argument.continuous and _bool_is_true(domain),
        argument.chart,
    )


def _rational_power_result(
    base: _EvalResult,
    exponent: _EvalResult,
    exact: Fraction,
    ops: _IntervalOps,
) -> _EvalResult:
    defined = _bool_and(base.defined, exponent.defined)
    argument = _EvalResult(
        base.interval,
        defined,
        base.continuous and exponent.continuous and _bool_is_true(defined),
        base.chart,
    )
    root = (
        _sqrt_result(argument, ops)
        if exact.denominator == 2
        else _EvalResult(
            ops.cbrt(argument.interval),
            argument.defined,
            argument.continuous,
            argument.chart,
        )
        if exact.denominator == 3
        else _rational_root_result(argument, exact.denominator, ops)
    )
    return _integer_power_result(
        root, exact.numerator, root.defined, root.continuous, ops
    )


def _rational_power_eval_set(
    base: _EvalSet,
    exponent: _EvalSet,
    exact: Fraction,
    ops: _IntervalOps,
) -> _EvalSet:
    defined = _bool_and(base.defined, exponent.defined)
    # Nonlinear roots invalidate coordinate/inverse and exact-constant metadata.
    # Whole original charts remain usable; narrowed reciprocal root sections
    # cannot invert the original coordinate without a separate proof.
    argument = _eval_set(
        tuple(
            _EvalResult(
                branch.interval,
                _bool_and(branch.defined, exponent.defined),
                branch.continuous
                and exponent.continuous
                and _bool_is_true(exponent.defined),
                branch.chart,
            )
            for branch in base.branches
        ),
        defined,
        base.continuous and exponent.continuous and _bool_is_true(defined),
        ops,
    )
    if exact.denominator == 2:
        root = _sqrt_eval_set(argument, ops)
    elif exact.denominator == 3:
        root = _unary_eval_set(argument, ops.cbrt, ops)
    else:
        root_domain = (
            _bool_and(argument.defined, _branches_nonnegative(argument.branches, ops))
            if exact.denominator % 2 == 0
            else argument.defined
        )
        rooted = []
        for branch in argument.branches:
            result = _rational_root_result(branch, exact.denominator, ops)
            if not result.defined.hi:
                ops.record_operator_sections("rational_root", 0)
                continue
            ops.record_operator_sections(
                "rational_root",
                1,
                noncontinuous_sections=int(not result.continuous),
            )
            rooted.append(result)
        root = _eval_set(
            tuple(rooted),
            root_domain,
            argument.continuous and _bool_is_true(root_domain),
            ops,
        )
    return _power_eval_set(root, exact.numerator, ops)


def _zero_base_power_result(
    left: _EvalResult, right: _EvalResult, ops: _IntervalOps
) -> _EvalResult:
    """Cover numeric-zero powers without filling the discontinuous image."""
    if (
        ops.is_empty(left.interval)
        or ops.is_empty(right.interval)
        or not left.defined.hi
        or not right.defined.hi
        or right.interval.hi < 0.0
    ):
        return _EvalResult(ops.empty(), _BOOL_FALSE, False)
    domain = _BOOL_TRUE if right.interval.lo >= 0.0 else _BOOL_MAYBE
    defined = _bool_and(_bool_and(left.defined, right.defined), domain)
    has_zero = right.interval.hi > 0.0
    has_one = right.interval.lo <= 0.0 <= right.interval.hi
    value = ops.make(0.0 if has_zero else 1.0, 1.0 if has_one else 0.0)
    whole_mode = (
        right.interval.lo > 0.0 or right.interval.lo == right.interval.hi == 0.0
    )
    certified = whole_mode and _bool_is_true(defined)
    return _EvalResult(
        value,
        defined,
        certified and left.continuous and right.continuous,
        right.chart if certified else None,
        constant=value.lo if certified else None,
    )


def _zero_base_power_eval_set(
    left: _EvalSet, right: _EvalSet, ops: _IntervalOps
) -> _EvalSet:
    """Keep zero and one as separate sections, with original domain flags."""
    if (
        not left.branches
        or not right.branches
        or not left.defined.hi
        or not right.defined.hi
    ):
        return _eval_set((), _BOOL_FALSE, False, ops)
    defined = _bool_and(
        _bool_and(left.defined, right.defined),
        _branches_nonnegative(right.branches, ops),
    )
    outputs: list[_EvalResult] = []
    for branch in right.branches:
        if (
            ops.is_empty(branch.interval)
            or not branch.defined.hi
            or branch.interval.hi < 0.0
        ):
            continue
        domain = _BOOL_TRUE if branch.interval.lo >= 0.0 else _BOOL_MAYBE
        branch_defined = _bool_and(
            _bool_and(_bool_and(left.defined, right.defined), branch.defined), domain
        )
        whole_mode = (
            branch.interval.lo > 0.0 or branch.interval.lo == branch.interval.hi == 0.0
        )
        certified = whole_mode and _bool_is_true(branch_defined)
        values = []
        if branch.interval.hi > 0.0:
            values.append(0.0)
        if branch.interval.lo <= 0.0 <= branch.interval.hi:
            values.append(1.0)
        for value in values:
            outputs.append(
                _EvalResult(
                    ops.point(value),
                    branch_defined,
                    certified and left.continuous and branch.continuous,
                    branch.chart if certified else None,
                    constant=value if certified else None,
                )
            )
    ops.record_operator_sections(
        "zero_base_power",
        len(outputs),
        noncontinuous_sections=sum(not branch.continuous for branch in outputs),
        missing_chart_sections=sum(branch.chart is None for branch in outputs),
    )
    whole_mode = all(branch.interval.lo > 0.0 for branch in right.branches) or all(
        branch.interval.lo == branch.interval.hi == 0.0 for branch in right.branches
    )
    return _eval_set(
        tuple(outputs),
        defined,
        whole_mode and _bool_is_true(defined) and left.continuous and right.continuous,
        ops,
    )


def _self_power_domain(value: _CInterval, ops: _IntervalOps) -> _CBoolInterval:
    if ops.is_empty(value):
        return _BOOL_FALSE
    if value.lo >= 0.0:
        return _BOOL_TRUE
    if value.lo == value.hi and math.isfinite(value.lo) and value.lo.is_integer():
        return _BOOL_TRUE
    return _BOOL_MAYBE


def _self_power_sections(
    left: _EvalResult, right: _EvalResult, ops: _IntervalOps
) -> tuple[_EvalResult, ...]:
    """Enclose t^t; negative sign closures never certify attainment."""
    if (
        ops.is_empty(left.interval)
        or ops.is_empty(right.interval)
        or not left.defined.hi
        or not right.defined.hi
    ):
        return ()
    value = left.interval
    domain = _self_power_domain(value, ops)
    defined = _bool_and(_bool_and(left.defined, right.defined), domain)
    continuous = (
        value.lo > 0.0
        and left.continuous
        and right.continuous
        and _bool_is_true(defined)
    )
    outputs: list[_EvalResult] = []
    if value.hi >= 0.0:
        positive = _positive_x_power_x_range(max(0.0, value.lo), value.hi, ops)
        if positive is not None:
            outputs.append(_EvalResult(positive, defined, continuous))
    if value.lo < 0.0:
        magnitude = _negative_x_power_x_magnitude_range(
            max(0.0, -value.hi), -value.lo, ops
        )
        if magnitude is not None:
            singleton = (
                value.lo == value.hi
                and math.isfinite(value.lo)
                and value.lo.is_integer()
            )
            if not singleton or int(value.lo) % 2 == 0:
                outputs.append(_EvalResult(magnitude, defined, False))
            if not singleton or int(value.lo) % 2 != 0:
                outputs.append(_EvalResult(ops.neg(magnitude), defined, False))
    return tuple(outputs)


def _self_power_result(
    left: _EvalResult, right: _EvalResult, ops: _IntervalOps
) -> _EvalResult:
    sections = _self_power_sections(left, right, ops)
    if not sections:
        return _EvalResult(ops.empty(), _BOOL_FALSE, False)
    interval = sections[0].interval
    for section in sections[1:]:
        interval = ops.hull(interval, section.interval)
    return _EvalResult(
        interval, sections[0].defined, all(section.continuous for section in sections)
    )


def _self_power_eval_set(
    left: _EvalSet, right: _EvalSet, ops: _IntervalOps
) -> _EvalSet:
    if (
        not left.branches
        or not right.branches
        or not left.defined.hi
        or not right.defined.hi
    ):
        return _eval_set((), _BOOL_FALSE, False, ops)
    defined = _bool_and(left.defined, right.defined)
    domain = _BOOL_TRUE
    for branch in left.branches:
        domain = _bool_and(domain, _self_power_domain(branch.interval, ops))
    defined = _bool_and(defined, domain)
    outputs = tuple(
        section
        for a in left.branches
        for b in right.branches
        for section in _self_power_sections(a, b, ops)
    )
    return _eval_set(
        outputs,
        defined,
        left.continuous and right.continuous and _bool_is_true(defined),
        ops,
    )
