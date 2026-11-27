# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Experimental headless metadata primitives."""

from __future__ import annotations

import math
from fractions import Fraction
from .values import (
    _AffineCoordinate,
    _EvalResult,
    _IntervalAffine,
    _QuadraticCoordinate,
    _ReciprocalAffineCoordinate,
    _CInterval,
)
from .operations import _IntervalOps
from .scalars import _exact_metadata_float


def _make_affine(
    axis: str,
    scale: Fraction | float,
    offset: Fraction | float,
) -> _AffineCoordinate | None:
    exact_scale, exact_offset = (
        _exact_metadata_float(scale),
        _exact_metadata_float(offset),
    )
    if exact_scale is None or exact_offset is None:
        return None
    return _AffineCoordinate(axis, exact_scale, exact_offset)


def _coordinate_affine(axis: str) -> _AffineCoordinate:
    return _AffineCoordinate(axis, 1.0, 0.0)


def _neg_affine(affine: _AffineCoordinate | None) -> _AffineCoordinate | None:
    if affine is None:
        return None
    return _make_affine(affine.axis, -affine.scale, -affine.offset)


def _neg_reciprocal_affine(
    reciprocal: _ReciprocalAffineCoordinate | None,
) -> _ReciprocalAffineCoordinate | None:
    if reciprocal is None:
        return None
    return _make_reciprocal_affine(
        reciprocal.axis,
        -reciprocal.numerator,
        reciprocal.denominator_scale,
        reciprocal.denominator_offset,
    )


def _neg_quadratic(
    quadratic: _QuadraticCoordinate | None,
) -> _QuadraticCoordinate | None:
    if quadratic is None:
        return None
    return _make_quadratic(quadratic.axis, -quadratic.scale, -quadratic.offset)


def _binary_affine(
    left: _EvalResult,
    right: _EvalResult,
    operation: str,
) -> _AffineCoordinate | None:
    left_affine = left.affine
    right_affine = right.affine
    left_constant = Fraction(left.constant) if left.constant is not None else None
    right_constant = Fraction(right.constant) if right.constant is not None else None

    if operation in {"add", "sub"}:
        right_sign = 1 if operation == "add" else -1
        if left_affine is not None and right_affine is not None:
            if left_affine.axis != right_affine.axis:
                return None
            return _make_affine(
                left_affine.axis,
                Fraction(left_affine.scale) + right_sign * Fraction(right_affine.scale),
                Fraction(left_affine.offset)
                + right_sign * Fraction(right_affine.offset),
            )
        if left_affine is not None and right_constant is not None:
            return _make_affine(
                left_affine.axis,
                Fraction(left_affine.scale),
                Fraction(left_affine.offset) + right_sign * right_constant,
            )
        if right_affine is not None and left_constant is not None:
            return _make_affine(
                right_affine.axis,
                right_sign * Fraction(right_affine.scale),
                left_constant + right_sign * Fraction(right_affine.offset),
            )
        return None

    if operation == "mul":
        if left_affine is not None and right_constant is not None:
            return _scale_affine(left_affine, right_constant)
        if right_affine is not None and left_constant is not None:
            return _scale_affine(right_affine, left_constant)
        return None

    if operation == "div":
        if (
            left_affine is not None
            and right_constant is not None
            and right_constant != 0.0
        ):
            return _scale_affine(left_affine, 1 / right_constant)
        return None

    return None


def _binary_quadratic(
    left: _EvalResult,
    right: _EvalResult,
    operation: str,
) -> _QuadraticCoordinate | None:
    left_quadratic = left.quadratic
    right_quadratic = right.quadratic
    left_constant = Fraction(left.constant) if left.constant is not None else None
    right_constant = Fraction(right.constant) if right.constant is not None else None

    if operation in {"add", "sub"}:
        right_sign = 1 if operation == "add" else -1
        if left_quadratic is not None and right_constant is not None:
            return _make_quadratic(
                left_quadratic.axis,
                Fraction(left_quadratic.scale),
                Fraction(left_quadratic.offset) + right_sign * right_constant,
            )
        if right_quadratic is not None and left_constant is not None:
            return _make_quadratic(
                right_quadratic.axis,
                right_sign * Fraction(right_quadratic.scale),
                left_constant + right_sign * Fraction(right_quadratic.offset),
            )
        return None

    if operation == "mul":
        if left_quadratic is not None and right_constant is not None:
            return _scale_quadratic(left_quadratic, right_constant)
        if right_quadratic is not None and left_constant is not None:
            return _scale_quadratic(right_quadratic, left_constant)
        return None

    if operation == "div":
        if (
            left_quadratic is not None
            and right_constant is not None
            and right_constant != 0.0
        ):
            return _scale_quadratic(left_quadratic, 1 / right_constant)
        return None

    return None


def _make_reciprocal_affine(
    axis: str,
    numerator: float,
    denominator_scale: float,
    denominator_offset: float,
) -> _ReciprocalAffineCoordinate | None:
    if (
        numerator == 0.0
        or not math.isfinite(numerator)
        or not math.isfinite(denominator_scale)
        or not math.isfinite(denominator_offset)
    ):
        return None
    return _ReciprocalAffineCoordinate(
        axis,
        numerator,
        denominator_scale,
        denominator_offset,
    )


def _scale_affine(
    affine: _AffineCoordinate,
    factor: Fraction | float,
) -> _AffineCoordinate | None:
    return _make_affine(
        affine.axis,
        Fraction(affine.scale) * Fraction(factor),
        Fraction(affine.offset) * Fraction(factor),
    )


def _make_quadratic(
    axis: str,
    scale: Fraction | float,
    offset: Fraction | float,
) -> _QuadraticCoordinate | None:
    exact_scale, exact_offset = (
        _exact_metadata_float(scale),
        _exact_metadata_float(offset),
    )
    if exact_scale is None or exact_offset is None or exact_scale == 0.0:
        return None
    return _QuadraticCoordinate(axis, exact_scale, exact_offset)


def _scale_quadratic(
    quadratic: _QuadraticCoordinate,
    factor: Fraction | float,
) -> _QuadraticCoordinate | None:
    return _make_quadratic(
        quadratic.axis,
        Fraction(quadratic.scale) * Fraction(factor),
        Fraction(quadratic.offset) * Fraction(factor),
    )


def _binary_constant(
    left: _EvalResult,
    right: _EvalResult,
    operation: str,
) -> float | None:
    if left.constant is None or right.constant is None:
        return None
    a, b = Fraction(left.constant), Fraction(right.constant)
    if operation == "add":
        value = a + b
    elif operation == "sub":
        value = a - b
    elif operation == "mul":
        value = a * b
    elif operation == "div" and b != 0:
        value = a / b
    elif operation == "min":
        value = min(a, b)
    elif operation == "max":
        value = max(a, b)
    else:
        return None
    return _exact_metadata_float(value)


def _power_constant(value: float | None, exponent: int) -> float | None:
    # Match the bounded exact point-power path; do not allocate huge rationals
    # merely to retain optional metadata for an arbitrary exponent.
    if value is None or abs(exponent) > 32:
        return None
    try:
        return _exact_metadata_float(Fraction(value) ** exponent)
    except ZeroDivisionError:
        return None


_INTERVAL_AFFINE_MAX_SLOPE_BITS = 4096


def _make_interval_affine(
    axis: str | None, scale: int, offset: _CInterval
) -> _IntervalAffine | None:
    if (
        axis not in {None, "x", "y"}
        or (scale != 0 and axis is None)
        or scale.bit_length() > _INTERVAL_AFFINE_MAX_SLOPE_BITS
        or not math.isfinite(offset.lo)
        or not math.isfinite(offset.hi)
        or offset.lo > offset.hi
    ):
        return None
    return _IntervalAffine(axis if scale else None, scale, offset)


def _neg_interval_affine(
    value: _IntervalAffine | None, ops: _IntervalOps
) -> _IntervalAffine | None:
    if value is None:
        return None
    return _make_interval_affine(value.axis, -value.scale, ops.neg(value.offset))


def _binary_interval_affine(
    left: _EvalResult,
    right: _EvalResult,
    operation: str | None,
    ops: _IntervalOps,
) -> _IntervalAffine | None:
    if operation not in {"add", "sub"}:
        return None
    a, b = left.interval_affine, right.interval_affine
    if a is None or b is None:
        return None
    if a.axis is not None and b.axis is not None and a.axis != b.axis:
        return None
    scale = a.scale + b.scale if operation == "add" else a.scale - b.scale
    if scale.bit_length() > _INTERVAL_AFFINE_MAX_SLOPE_BITS:
        return None
    offset = (
        ops.add(a.offset, b.offset)
        if operation == "add"
        else ops.sub(a.offset, b.offset)
    )
    return _make_interval_affine(a.axis or b.axis, scale, offset)
