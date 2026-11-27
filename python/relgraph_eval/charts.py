# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Experimental headless charts primitives."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import cast
from .values import (
    _AffineCoordinate,
    _ChartDomain,
    _EvalResult,
    _IntervalAffine,
    _QuadraticCoordinate,
    _ReciprocalAffineCoordinate,
    _CInterval,
)
from .operations import _IntervalOps
from .metadata import _make_affine
from .scalars import _fraction_lower_float, _fraction_upper_float
from .definedness import bool_is_true as _bool_is_true


def _combine_charts(
    ops: _IntervalOps, *charts: _ChartDomain | None
) -> _ChartDomain | None:
    if not charts or any(chart is None for chart in charts):
        return None

    first = charts[0]
    assert first is not None
    x = first.x
    y = first.y
    for chart in charts[1:]:
        assert chart is not None
        x = ops.intersect(x, chart.x)
        y = ops.intersect(y, chart.y)
        if ops.is_empty(x) or ops.is_empty(y):
            return None
    return _ChartDomain(x, y)


def _chart_for_section(
    branch: _EvalResult,
    section: _CInterval,
    ops: _IntervalOps,
) -> _ChartDomain | None:
    if branch.chart is None:
        return None
    if section.lo <= branch.interval.lo and branch.interval.hi <= section.hi:
        return branch.chart
    # Constant intervals cannot invert arbitrary expressions, so only
    # coordinate-derived affine branches can soundly narrow their chart domains.
    if branch.affine is not None:
        return _chart_for_affine_section(branch.chart, branch.affine, section, ops)
    if branch.reciprocal_affine is not None:
        return _chart_for_reciprocal_affine_section(
            branch.chart,
            branch.reciprocal_affine,
            section,
            ops,
        )
    if branch.quadratic is not None:
        return _chart_for_quadratic_section(
            branch.chart, branch.quadratic, section, ops
        )
    if branch.coordinate == "x":
        restricted = ops.intersect(branch.chart.x, section)
        if ops.is_empty(restricted):
            return None
        return _ChartDomain(restricted, branch.chart.y)
    if branch.coordinate == "y":
        restricted = ops.intersect(branch.chart.y, section)
        if ops.is_empty(restricted):
            return None
        return _ChartDomain(branch.chart.x, restricted)
    return None


def _chart_for_quadratic_section(
    chart: _ChartDomain,
    quadratic: _QuadraticCoordinate,
    section: _CInterval,
    ops: _IntervalOps,
) -> _ChartDomain | None:
    if quadratic.scale == 0.0:
        return None

    if ops.is_empty(section):
        return None
    square_section = _affine_inner_preimage(
        quadratic.scale,
        quadratic.offset,
        section,
        ops,
    )
    square_section = ops.intersect(square_section, ops.make(0.0, math.inf))
    if ops.is_empty(square_section):
        return None

    # C sqrt supplies outer bounds. The upper bound of the lower endpoint
    # and lower bound of the upper endpoint form a contained witness interval.
    roots = ops.make(
        ops.sqrt(ops.point(square_section.lo)).hi,
        ops.sqrt(ops.point(square_section.hi)).lo,
    )
    if ops.is_empty(roots):
        return None

    axis_interval = chart.x if quadratic.axis == "x" else chart.y
    if axis_interval.lo > 0.0:
        preimage = roots
    elif axis_interval.hi < 0.0:
        preimage = ops.neg(roots)
    else:
        return None

    restricted = ops.intersect(axis_interval, preimage)
    if ops.is_empty(restricted):
        return None
    if quadratic.axis == "x":
        return _ChartDomain(restricted, chart.y)
    if quadratic.axis == "y":
        return _ChartDomain(chart.x, restricted)
    return None


def _chart_for_reciprocal_affine_section(
    chart: _ChartDomain,
    reciprocal: _ReciprocalAffineCoordinate,
    section: _CInterval,
    ops: _IntervalOps,
) -> _ChartDomain | None:
    if ops.is_empty(section) or section.lo <= 0.0 <= section.hi:
        return None

    lower, upper = (
        (section.hi, section.lo)
        if reciprocal.numerator > 0
        else (section.lo, section.hi)
    )
    numerator = Fraction(reciprocal.numerator)
    lo = (
        0.0 if math.isinf(lower) else _fraction_upper_float(numerator / Fraction(lower))
    )
    hi = (
        0.0 if math.isinf(upper) else _fraction_lower_float(numerator / Fraction(upper))
    )
    # A zero limit from an unbounded section is not an admissible denominator.
    if lo == 0.0:
        lo = math.nextafter(0.0, math.inf)
    if hi == 0.0:
        hi = math.nextafter(0.0, -math.inf)
    denominator_section = ops.make(lo, hi)
    denominator_affine = _make_affine(
        reciprocal.axis,
        reciprocal.denominator_scale,
        reciprocal.denominator_offset,
    )
    if denominator_affine is None:
        return None
    return _chart_for_affine_section(
        chart, denominator_affine, denominator_section, ops
    )


def _affine_inner_preimage(
    scale: float,
    offset: float,
    section: _CInterval,
    ops: _IntervalOps,
) -> _CInterval:
    """Invert a nonconstant exact affine map, rounding the interval inward."""
    lower, upper = section.lo, section.hi
    if scale < 0.0:
        lower, upper = upper, lower
    fraction_scale, fraction_offset = Fraction(scale), Fraction(offset)
    lo = (
        cast(float, lower / fraction_scale)
        if math.isinf(lower)
        else _fraction_upper_float((Fraction(lower) - fraction_offset) / fraction_scale)
    )
    hi = (
        cast(float, upper / fraction_scale)
        if math.isinf(upper)
        else _fraction_lower_float((Fraction(upper) - fraction_offset) / fraction_scale)
    )
    return ops.make(lo, hi)


def _chart_for_affine_section(
    chart: _ChartDomain,
    affine: _AffineCoordinate,
    section: _CInterval,
    ops: _IntervalOps,
) -> _ChartDomain | None:
    # Tupper paper 10–11: a continuity chart must lie inside this branch's
    # input region. An outward inverse covers that region but can cross a cut.
    if ops.is_empty(section):
        return None
    if affine.scale == 0.0:
        return chart if section.lo <= affine.offset <= section.hi else None

    preimage = _affine_inner_preimage(affine.scale, affine.offset, section, ops)
    if ops.is_empty(preimage):
        return None
    if affine.axis == "x":
        restricted = ops.intersect(chart.x, preimage)
        if ops.is_empty(restricted):
            return None
        return _ChartDomain(restricted, chart.y)
    if affine.axis == "y":
        restricted = ops.intersect(chart.y, preimage)
        if ops.is_empty(restricted):
            return None
        return _ChartDomain(chart.x, restricted)
    return None


def _chart_for_interval_affine_section(
    branch: _EvalResult, section: _CInterval, ops: _IntervalOps
) -> _ChartDomain | None:
    """Return a contained witness chart, never a complete value/domain cover.

    Every possible offset must map the whole chart into the strict-sign
    section. Tupper 2.11–2.13 and 4.2.6 require keeping this certificate
    separate from ordinary division domains and exhaustive absence covers.
    """
    value = branch.interval_affine
    if (
        branch.chart is None
        or not branch.continuous
        or not _bool_is_true(branch.defined)
        or value is None
        or value.axis not in {"x", "y"}
        or value.scale not in {-1, 1}
        or ops.is_empty(section)
        or math.isnan(section.lo)
        or math.isnan(section.hi)
        or not math.isfinite(value.offset.lo)
        or not math.isfinite(value.offset.hi)
        or value.offset.lo > value.offset.hi
        or not (section.hi < 0.0 or section.lo > 0.0)
    ):
        return None
    preimage = _interval_affine_inner_preimage(value, section, ops)
    parent = branch.chart.x if value.axis == "x" else branch.chart.y
    restricted = ops.intersect(parent, preimage)
    if ops.is_empty(restricted):
        return None
    if value.axis == "x":
        return _ChartDomain(restricted, branch.chart.y)
    return _ChartDomain(branch.chart.x, restricted)


def _interval_affine_inner_preimage(
    value: _IntervalAffine, section: _CInterval, ops: _IntervalOps
) -> _CInterval:
    lower, upper = section.lo, section.hi
    if value.scale == -1:
        lower, upper = -upper, -lower
        offset_lo, offset_hi = -value.offset.hi, -value.offset.lo
    else:
        offset_lo, offset_hi = value.offset.lo, value.offset.hi
    lo = (
        lower
        if math.isinf(lower)
        else _fraction_upper_float(Fraction(lower) - Fraction(offset_lo))
    )
    hi = (
        upper
        if math.isinf(upper)
        else _fraction_lower_float(Fraction(upper) - Fraction(offset_hi))
    )
    return ops.make(lo, hi)
