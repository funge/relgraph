# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Cache-free interval covers, sections and numerical composition."""

from __future__ import annotations
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol
from .numeric_api import _NumericOps as _IntervalOps
from .values import _CInterval
from .definedness import BoolInterval as _CBoolInterval
from .scalars import (
    _fraction_lower_float as _fraction_lower_float,
    _fraction_upper_float as _fraction_upper_float,
    _interval_cache_key as _interval_cache_key,
)
from .definedness import (
    bool_and as _bool_and,
    bool_or as _bool_or,
    bool_is_true as _bool_is_true,
    bool_is_false as _bool_is_false,
    interval_nonzero as _interval_nonzero,
    sqrt_domain as _sqrt_domain,
    log2_domain as _log2_domain,
    BOOL_FALSE as _BOOL_FALSE,
    BOOL_TRUE as _BOOL_TRUE,
    BOOL_MAYBE as _BOOL_MAYBE,
)


# Compatibility names used by the operator modules.
__all__ = ["_bool_and", "_bool_or", "_sqrt_domain", "_log2_domain"]


_TRIG_CERTIFIED_ABS_MAX = float.fromhex("0x1p40")


def _real_gcd_fraction(values: tuple[float, ...]) -> Fraction:
    # Point floats are exact rationals for Euclidean common factors.
    fractions = _finite_fractions(values)
    numerator_gcd = 0
    denominator_lcm = 1
    for value in fractions:
        numerator_gcd = math.gcd(numerator_gcd, abs(value.numerator))
        denominator_lcm = math.lcm(denominator_lcm, value.denominator)
    return Fraction(numerator_gcd, denominator_lcm)


def _real_lcm_fraction(values: tuple[float, ...]) -> Fraction:
    fractions = _finite_fractions(values)
    if any(value.numerator == 0 for value in fractions):
        return Fraction(0)

    numerator_lcm = 1
    denominator_gcd = 0
    for value in fractions:
        numerator_lcm = math.lcm(numerator_lcm, abs(value.numerator))
        denominator_gcd = math.gcd(denominator_gcd, value.denominator)
    return Fraction(numerator_lcm, denominator_gcd)


def _finite_fractions(values: tuple[float, ...]) -> tuple[Fraction, ...]:
    if any(not math.isfinite(value) for value in values):
        raise ValueError("gcd and lcm require finite point values")
    return tuple(Fraction(value) for value in values)


def _fraction_to_float(value: Fraction) -> float:
    try:
        return float(value)
    except OverflowError:
        return math.inf


def _fraction_interval(value: Fraction, ops: _IntervalOps) -> _CInterval:
    return ops.make(_fraction_lower_float(value), _fraction_upper_float(value))


@dataclass(frozen=True)
class _IntervalSection:
    interval: _CInterval
    continuous: bool
    boundary: bool = False


@dataclass(frozen=True)
class _IntervalBoundary:
    interval: _CInterval
    continuous: bool


@dataclass(frozen=True)
class _IntervalCover:
    sections: tuple[_IntervalSection, ...]


@dataclass(frozen=True)
class _RemainderIntervalSection:
    output: _IntervalSection
    input_interval: _CInterval
    affine_shift: float | None = None
    quotient: int | None = None


def _interval_cover_split_at_points(
    value: _CInterval,
    points: tuple[float, ...],
    ops: _IntervalOps,
    *,
    max_sections: int,
    fallback_continuous: bool,
) -> _IntervalCover:
    boundaries = tuple(
        _IntervalBoundary(ops.point(float(point)), False)
        for point in points
        if math.isfinite(point)
    )
    return _interval_cover_split_at_boundaries(
        value,
        boundaries,
        ops,
        max_sections=max_sections,
        fallback_continuous=fallback_continuous,
    )


def _interval_cover_split_at_boundaries(
    value: _CInterval,
    boundaries: tuple[_IntervalBoundary, ...],
    ops: _IntervalOps,
    *,
    max_sections: int,
    fallback_continuous: bool,
) -> _IntervalCover:
    # Tupper's exhaustive absence test requires a cover of real points, not
    # only floating-point members. Include the real gaps next to each boundary
    # in its boundary section, overlapping the neighboring closed sections.
    # This keeps the ordinary pieces away from discontinuities without dropping
    # the real values between adjacent floats. Merge expanded boundaries so a
    # continuous boundary cannot absorb a neighboring discontinuity unnoticed.
    if ops.is_empty(value):
        return _IntervalCover(())

    expanded_boundaries = tuple(
        _IntervalBoundary(
            ops.make(
                math.nextafter(boundary.interval.lo, -math.inf),
                math.nextafter(boundary.interval.hi, math.inf),
            ),
            boundary.continuous,
        )
        for boundary in boundaries
        if not ops.is_empty(boundary.interval)
    )
    split_boundaries = _boundaries_overlapping(value, expanded_boundaries, ops)
    if len(split_boundaries) * 2 + 1 > max_sections:
        return _IntervalCover((_IntervalSection(value, fallback_continuous),))

    sections: list[_IntervalSection] = []
    segment_lo = value.lo
    for boundary in split_boundaries:
        segment_hi = boundary.interval.lo
        if segment_lo < segment_hi:
            sections.append(_IntervalSection(ops.make(segment_lo, segment_hi), True))
        sections.append(
            _IntervalSection(
                boundary.interval,
                boundary.continuous,
                boundary=True,
            )
        )
        segment_lo = boundary.interval.hi

    if segment_lo < value.hi or not sections:
        sections.append(_IntervalSection(ops.make(segment_lo, value.hi), True))
    return _IntervalCover(tuple(sections))


def _boundaries_overlapping(
    value: _CInterval,
    boundaries: tuple[_IntervalBoundary, ...],
    ops: _IntervalOps,
) -> tuple[_IntervalSection, ...]:
    clipped = sorted(
        (
            _IntervalSection(intersection, boundary.continuous, boundary=True)
            for boundary in boundaries
            for intersection in (ops.intersect(value, boundary.interval),)
            if not ops.is_empty(intersection)
        ),
        key=lambda boundary: (boundary.interval.lo, boundary.interval.hi),
    )

    merged: list[_IntervalSection] = []
    for boundary in clipped:
        if not merged:
            merged.append(boundary)
            continue
        previous = merged[-1]
        if boundary.interval.lo <= previous.interval.hi:
            merged[-1] = _IntervalSection(
                ops.hull(previous.interval, boundary.interval),
                previous.continuous and boundary.continuous,
                boundary=True,
            )
            continue
        merged.append(boundary)
    return tuple(merged)


def _periodic_interval_cover_uncached(
    value: _CInterval,
    ops: _IntervalOps,
    *,
    phase_numerator: int,
    period_numerator: int,
    denominator: int,
    boundary_continuous: bool,
    max_sections: int,
    fallback_continuous: bool,
) -> _IntervalCover:
    boundaries = _periodic_pi_boundaries(
        value,
        ops,
        phase_numerator=phase_numerator,
        period_numerator=period_numerator,
        denominator=denominator,
        max_boundaries=(max_sections - 1) // 2,
        boundary_continuous=boundary_continuous,
    )
    if boundaries is None:
        return _IntervalCover((_IntervalSection(value, fallback_continuous),))
    return _interval_cover_split_at_boundaries(
        value,
        boundaries,
        ops,
        max_sections=max_sections,
        fallback_continuous=fallback_continuous,
    )


def _periodic_pi_boundaries(
    value: _CInterval,
    ops: _IntervalOps,
    *,
    phase_numerator: int,
    period_numerator: int,
    denominator: int,
    max_boundaries: int,
    boundary_continuous: bool,
) -> tuple[_IntervalBoundary, ...] | None:
    if ops.is_empty(value):
        return ()
    if (
        denominator <= 0
        or period_numerator <= 0
        or not math.isfinite(value.lo)
        or not math.isfinite(value.hi)
        or abs(value.lo) > _TRIG_CERTIFIED_ABS_MAX
        or abs(value.hi) > _TRIG_CERTIFIED_ABS_MAX
    ):
        return None

    # Floats only choose candidate k values here; the actual split points below
    # are MPFR-bracketed intervals and are filtered by interval intersection.
    approximate_period = period_numerator * math.pi / denominator
    approximate_phase = phase_numerator * math.pi / denominator
    first = math.floor((value.lo - approximate_phase) / approximate_period) - 4
    last = math.ceil((value.hi - approximate_phase) / approximate_period) + 4
    if last < first:
        return ()
    if last - first + 1 > max_boundaries + 8:
        return None

    boundaries: list[_IntervalBoundary] = []
    for index in range(first, last + 1):
        numerator = phase_numerator + index * period_numerator
        boundary = ops.pi_multiple(numerator, denominator)
        if ops.is_empty(ops.intersect(value, boundary)):
            continue
        boundaries.append(_IntervalBoundary(boundary, boundary_continuous))
        if len(boundaries) > max_boundaries:
            return None
    return tuple(boundaries)


def _factorial_interval(value: _CInterval, ops: _IntervalOps) -> _CInterval:
    return ops.factorial(value)


def _factorial_domain(value: _CInterval, ops: _IntervalOps) -> _CBoolInterval:
    if ops.is_empty(value) or value.hi < 0.0:
        return _BOOL_FALSE
    if value.lo == value.hi and not math.isfinite(value.lo):
        return _BOOL_FALSE
    if (
        _interval_is_point(value, ops)
        and math.isfinite(value.lo)
        and value.lo >= 0.0
        and value.lo.is_integer()
    ):
        return _BOOL_TRUE
    first_integer = math.ceil(max(value.lo, 0.0))
    return _BOOL_MAYBE if first_integer <= value.hi else _BOOL_FALSE


def _factorial_interval_hull(
    value: _CInterval,
    ops: _IntervalOps,
) -> _CInterval:
    if _bool_is_false(_factorial_domain(value, ops)):
        return ops.empty()
    first_integer = math.ceil(max(value.lo, 0.0))
    lower = ops.factorial(ops.point(first_integer))
    if not math.isfinite(value.hi):
        return ops.make(lower.lo, math.inf)
    last_integer = math.floor(value.hi)
    upper = ops.factorial(ops.point(last_integer))
    return ops.make(lower.lo, upper.hi)


def _integer_function_cover(
    value: _CInterval,
    ops: _IntervalOps,
) -> _IntervalCover:
    if ops.is_empty(value):
        return _IntervalCover(())
    if not math.isfinite(value.lo) or not math.isfinite(value.hi):
        return _IntervalCover((_IntervalSection(value, False),))

    first_integer = math.ceil(value.lo)
    last_integer = math.floor(value.hi)
    if last_integer < first_integer:
        return _IntervalCover((_IntervalSection(value, True),))
    if (last_integer - first_integer + 1) * 2 + 1 > 8:
        return _IntervalCover((_IntervalSection(value, False),))

    integers = range(first_integer, last_integer + 1)
    points = tuple(float(integer) for integer in integers)
    if any(
        int(point) != integer for point, integer in zip(points, integers, strict=True)
    ):
        # Binary64 cannot represent every integer beyond 2**53.  Dropping an
        # unrepresentable boundary would leave its floor value out of the
        # section cover and could turn an unknown relation into a false proof.
        return _IntervalCover((_IntervalSection(value, False),))
    return _interval_cover_split_at_points(
        value,
        points,
        ops,
        max_sections=8,
        fallback_continuous=False,
    )


def _mod_interval_section(
    input_interval: _CInterval,
    modulus_interval: _CInterval,
    ops: _IntervalOps,
) -> _RemainderIntervalSection:
    return _remainder_interval_sections(
        input_interval,
        modulus_interval,
        ops,
        operation_name="mod",
    )[0]


def _fmod_interval_section(
    input_interval: _CInterval,
    modulus_interval: _CInterval,
    ops: _IntervalOps,
) -> _RemainderIntervalSection:
    return _remainder_interval_sections(
        input_interval,
        modulus_interval,
        ops,
        operation_name="fmod",
    )[0]


def _remainder_interval_sections(
    input_interval: _CInterval,
    modulus_interval: _CInterval,
    ops: _IntervalOps,
    *,
    operation_name: str,
    split_mod_ranges: bool = False,
) -> tuple[_RemainderIntervalSection, ...]:
    if ops.is_empty(input_interval) or ops.is_empty(modulus_interval):
        return (
            _RemainderIntervalSection(
                _IntervalSection(ops.empty(), False),
                input_interval,
            ),
        )
    if not all(
        math.isfinite(value)
        for value in (
            input_interval.lo,
            input_interval.hi,
            modulus_interval.lo,
            modulus_interval.hi,
        )
    ):
        modulus_hi = max(abs(modulus_interval.lo), abs(modulus_interval.hi))
        return (
            _RemainderIntervalSection(
                _IntervalSection(
                    _remainder_fallback_interval(
                        input_interval,
                        modulus_hi,
                        ops,
                        operation_name=operation_name,
                    ),
                    False,
                ),
                input_interval,
            ),
        )

    modulus_zero_possible = modulus_interval.lo <= 0.0 <= modulus_interval.hi
    modulus_hi = max(abs(modulus_interval.lo), abs(modulus_interval.hi))
    if modulus_hi == 0:
        return (
            _RemainderIntervalSection(
                _IntervalSection(ops.empty(), False),
                input_interval,
            ),
        )
    if input_interval.lo == input_interval.hi == 0.0:
        zero = (
            math.copysign(0.0, input_interval.lo) if operation_name == "fmod" else 0.0
        )
        return (
            _RemainderIntervalSection(
                _IntervalSection(ops.point(zero), not modulus_zero_possible),
                input_interval,
                0.0 if not modulus_zero_possible else None,
                0 if not modulus_zero_possible else None,
            ),
        )

    if modulus_zero_possible:
        modulus_lo = 0.0
    elif modulus_interval.hi < 0.0:
        modulus_lo = abs(modulus_interval.hi)
    else:
        modulus_lo = abs(modulus_interval.lo)

    if modulus_lo > 0:
        # Binary64 endpoints are dyadic rationals. With one exact denominator
        # D, a=A/D and m=M/D give a/m=A/M and a-q*m=(A-q*M)/D. Plan the same
        # four-corner quotient band with integers, then demote outward below.
        # The exact integer calculation changes
        # the representation only, including for subnormal/extreme endpoints.
        ratios = tuple(
            value.as_integer_ratio()
            for value in (
                input_interval.lo,
                input_interval.hi,
                modulus_lo,
                modulus_hi,
            )
        )
        denominator = max(part[1] for part in ratios)
        scaled = tuple(
            numerator * (denominator // divisor) for numerator, divisor in ratios
        )
        dividend_values = scaled[:2]
        modulus_values = scaled[2:]
        scaled_modulus_hi = modulus_values[1]
        quotients = tuple(
            _remainder_quotient(dividend, modulus, operation_name)
            for dividend in dividend_values
            for modulus in modulus_values
        )
        quotient = quotients[0]
        if all(candidate == quotient for candidate in quotients):
            if (
                input_interval.lo == input_interval.hi
                and modulus_interval.lo == modulus_interval.hi
            ):
                point_operation = (
                    ops.lib.gi_remainder_mod_point
                    if operation_name == "mod"
                    else ops.lib.gi_remainder_fmod_point
                )
                interval = point_operation(input_interval.lo, modulus_interval.lo)
            else:
                remainder_values = tuple(
                    dividend - quotient * modulus
                    for dividend in dividend_values
                    for modulus in modulus_values
                )
                remainder_lo = min(remainder_values)
                remainder_hi = max(remainder_values)
                if operation_name == "mod":
                    remainder_lo = max(0, remainder_lo)
                    remainder_hi = min(scaled_modulus_hi, remainder_hi)
                elif input_interval.lo >= 0.0:
                    remainder_lo = max(0, remainder_lo)
                    remainder_hi = min(scaled_modulus_hi, remainder_hi)
                elif input_interval.hi <= 0.0:
                    remainder_lo = max(-scaled_modulus_hi, remainder_lo)
                    remainder_hi = min(0, remainder_hi)
                else:
                    remainder_lo = max(-scaled_modulus_hi, remainder_lo)
                    remainder_hi = min(scaled_modulus_hi, remainder_hi)
                lo = _fraction_lower_float(Fraction(remainder_lo, denominator))
                hi = _fraction_upper_float(Fraction(remainder_hi, denominator))
                if (
                    operation_name == "fmod"
                    and remainder_lo == 0
                    and input_interval.lo >= 0.0
                ):
                    lo = 0.0
                if (
                    operation_name == "fmod"
                    and remainder_hi == 0
                    and input_interval.hi <= 0.0
                ):
                    hi = -0.0
                interval = ops.make(
                    lo,
                    hi,
                )
            shift: float | None = None
            if modulus_interval.lo == modulus_interval.hi:
                exact_shift = quotient * abs(Fraction(modulus_interval.lo))
                candidate = _fraction_to_float(exact_shift)
                if math.isfinite(candidate) and Fraction(candidate) == exact_shift:
                    shift = candidate
            return (
                _RemainderIntervalSection(
                    _IntervalSection(interval, True),
                    input_interval,
                    shift,
                    quotient,
                ),
            )

        if split_mod_ranges and operation_name == "mod":
            first, last = min(quotients), max(quotients)
            if last - first == 1:
                # mod(a,m)=a-q*|m|, q=floor(a/|m|).
                # Tupper 2.13/3.2.6: cover both quotient cases outward.
                # Closed [0,m_hi] bounds retain wrap limits; these value
                # covers never imply a continuous or trimmed input section.
                sections = []
                for quotient in (first, last):
                    values = tuple(
                        dividend - quotient * modulus
                        for dividend in dividend_values
                        for modulus in modulus_values
                    )
                    lo = max(0, min(values))
                    hi = min(scaled_modulus_hi, max(values))
                    interval = ops.make(
                        _fraction_lower_float(Fraction(lo, denominator)),
                        _fraction_upper_float(Fraction(hi, denominator)),
                    )
                    sections.append(
                        _RemainderIntervalSection(
                            _IntervalSection(interval, False),
                            input_interval,
                            quotient=quotient,
                        )
                    )
                return tuple(sections)

    return (
        _RemainderIntervalSection(
            _IntervalSection(
                _remainder_fallback_interval(
                    input_interval,
                    modulus_hi,
                    ops,
                    operation_name=operation_name,
                ),
                False,
            ),
            input_interval,
        ),
    )


def _remainder_quotient(dividend: int, modulus: int, operation_name: str) -> int:
    if operation_name == "mod" or dividend >= 0:
        return dividend // modulus
    return -((-dividend) // modulus)


def _remainder_fallback_interval(
    input_interval: _CInterval,
    modulus_hi: float,
    ops: _IntervalOps,
    *,
    operation_name: str,
) -> _CInterval:
    if operation_name == "mod":
        return ops.make(0.0, modulus_hi)
    if input_interval.lo >= 0.0:
        return ops.make(0.0, modulus_hi)
    if input_interval.hi <= 0.0:
        return ops.make(-modulus_hi, -0.0)
    return ops.make(-modulus_hi, modulus_hi)


def _atan2_interval_domain(
    y: _CInterval,
    x: _CInterval,
    ops: _IntervalOps,
) -> _CBoolInterval:
    if ops.is_empty(x) or ops.is_empty(y):
        return _BOOL_FALSE
    origin_possible = x.lo <= 0.0 <= x.hi and y.lo <= 0.0 <= y.hi
    if not origin_possible:
        return _BOOL_TRUE
    if x.lo == x.hi == 0.0 and y.lo == y.hi == 0.0:
        return _BOOL_FALSE
    return _BOOL_MAYBE


def _atan2_crosses_branch_cut(
    y: _CInterval,
    x: _CInterval,
) -> bool:
    return x.lo < 0.0 and y.lo < 0.0 <= y.hi


def _power_interval_sections(
    value: _CInterval,
    exponent: int,
    ops: _IntervalOps,
) -> tuple[tuple[_IntervalSection, _CBoolInterval, _CInterval], ...]:
    if ops.is_empty(value):
        return ()
    if exponent >= 0:
        return (
            (
                _IntervalSection(_pow_interval(value, exponent, ops), True),
                _BOOL_TRUE,
                value,
            ),
        )

    branches: list[tuple[_IntervalSection, _CBoolInterval, _CInterval]] = []
    for section, section_defined in _nonzero_domain_sections(value, ops):
        branches.append(
            (
                _IntervalSection(
                    _pow_interval(section.interval, exponent, ops),
                    section.continuous and _bool_is_true(section_defined),
                ),
                section_defined,
                section.interval,
            )
        )
    return tuple(branches)


class _TangentOps(Protocol):
    def periodic_interval_cover(
        self,
        value: _CInterval,
        *,
        phase_numerator: int,
        period_numerator: int,
        denominator: int,
        boundary_continuous: bool,
        max_sections: int,
        fallback_continuous: bool,
    ) -> _IntervalCover: ...
    def tan(self, value: _CInterval, /) -> _CInterval: ...
    def tan_defined(self, value: _CInterval, /) -> _CBoolInterval: ...
    def is_empty(self, value: _CInterval, /) -> bool: ...
    def point(self, value: float, /) -> _CInterval: ...
    def make(self, lo: float, hi: float, /) -> _CInterval: ...


def _tan_interval_sections(
    value: _CInterval,
    ops: _TangentOps,
) -> tuple[tuple[_IntervalSection, _CInterval], ...]:
    cover = ops.periodic_interval_cover(
        value,
        phase_numerator=1,
        period_numerator=2,
        denominator=2,
        boundary_continuous=False,
        max_sections=8,
        fallback_continuous=False,
    )

    sections: list[tuple[_IntervalSection, _CInterval]] = []
    for section in cover.sections:
        if section.continuous or not section.boundary:
            sections.append(
                (
                    _IntervalSection(
                        ops.tan(section.interval),
                        section.continuous,
                    ),
                    section.interval,
                )
            )
            continue
        sections.extend(
            (pole_section, section.interval)
            for pole_section in _tan_pole_boundary_sections(section.interval, ops)
        )
    return tuple(sections)


def _tan_pole_boundary_sections(
    value: _CInterval, ops: _TangentOps
) -> tuple[_IntervalSection, ...]:
    if ops.is_empty(value):
        return ()
    domain = ops.tan_defined(value)
    if _bool_is_true(domain):
        return (_IntervalSection(ops.tan(value), True),)

    left = ops.tan(ops.point(value.lo))
    right = ops.tan(ops.point(value.hi))
    if (
        not ops.is_empty(left)
        and not ops.is_empty(right)
        and math.isfinite(left.lo)
        and math.isfinite(right.hi)
        and left.lo > 0.0
        and right.hi < 0.0
    ):
        return (
            _IntervalSection(ops.make(left.lo, math.inf), False),
            _IntervalSection(ops.make(-math.inf, right.hi), False),
        )
    return (_IntervalSection(ops.tan(value), False),)


def _div_interval_sections(
    numerator: _CInterval,
    denominator: _CInterval,
    ops: _IntervalOps,
) -> tuple[tuple[_IntervalSection, _CBoolInterval, _CInterval], ...]:
    if ops.is_empty(numerator) or ops.is_empty(denominator):
        return ()

    branches: list[tuple[_IntervalSection, _CBoolInterval, _CInterval]] = []
    for section, section_defined in _nonzero_domain_sections(denominator, ops):
        if section.interval.lo == 0.0 or section.interval.hi == 0.0:
            # Tupper 3.2.22/3.2.27: divide on a nonzero sign section by
            # multiplying its reciprocal enclosure. The included zero is only
            # a closed endpoint for the limit, not a defined argument.
            quotient = ops.mul(numerator, _pow_interval(section.interval, -1, ops))
        else:
            quotient = ops.div(numerator, section.interval)
        branches.append(
            (
                _IntervalSection(
                    quotient,
                    section.continuous and _bool_is_true(section_defined),
                ),
                section_defined,
                section.interval,
            )
        )
    return tuple(branches)


def _nonzero_domain_sections(
    value: _CInterval,
    ops: _IntervalOps,
) -> tuple[tuple[_IntervalSection, _CBoolInterval], ...]:
    if ops.is_empty(value):
        return ()
    if value.hi < 0.0 or value.lo > 0.0:
        return ((_IntervalSection(value, True), _BOOL_TRUE),)
    if value.lo == 0.0 and value.hi == 0.0:
        return ()

    cover = _interval_cover_split_at_points(
        value,
        (0.0,),
        ops,
        max_sections=3,
        fallback_continuous=False,
    )

    sections: list[tuple[_IntervalSection, _CBoolInterval]] = []
    for section in cover.sections:
        if section.boundary:
            # Zero is excluded, but nonzero reals arbitrarily close to it are
            # not. Closed one-sided enclosures retain those tails; MAYBE and
            # noncontinuous metadata prevent using the included zero as a
            # defined witness. Keeping the sides separate preserves reciprocal
            # sign gaps instead of enclosing a two-sided pole by the whole line.
            if section.interval.lo < 0.0:
                sections.append(
                    (
                        _IntervalSection(
                            ops.make(section.interval.lo, 0.0), False, boundary=True
                        ),
                        _BOOL_MAYBE,
                    )
                )
            if section.interval.hi > 0.0:
                sections.append(
                    (
                        _IntervalSection(
                            ops.make(0.0, section.interval.hi), False, boundary=True
                        ),
                        _BOOL_MAYBE,
                    )
                )
            continue
        section_defined = _interval_nonzero(section.interval, ops)
        if _bool_is_false(section_defined):
            continue
        sections.append((section, section_defined))
    return tuple(sections)


def _pow_interval(value: _CInterval, exponent: int, ops: _IntervalOps) -> _CInterval:
    if ops.is_empty(value):
        return ops.empty()
    if exponent == 0:
        return ops.point(1.0)
    if value.lo == value.hi:
        return _pow_point_interval(value.lo, exponent, ops)
    if abs(exponent) > 32:
        raise ValueError("integer exponents larger than 32 are not supported yet")
    if exponent < 0:
        if value.lo <= 0.0 <= value.hi:
            if exponent % 2:
                # One-sided closures enclose the nonzero domain right up to
                # zero. Domain/continuity metadata is owned by the caller.
                if value.hi == 0.0:
                    return ops.make(
                        -math.inf, _pow_point_interval(value.lo, exponent, ops).hi
                    )
                if value.lo == 0.0:
                    return ops.make(
                        _pow_point_interval(value.hi, exponent, ops).lo, math.inf
                    )
                return ops.make(-math.inf, math.inf)
            far_endpoint = value.lo if abs(value.lo) >= abs(value.hi) else value.hi
            lower = _pow_point_interval(far_endpoint, exponent, ops).lo
            return ops.make(lower, math.inf)
        if exponent % 2:
            lo = _pow_point_interval(value.hi, exponent, ops).lo
            hi = _pow_point_interval(value.lo, exponent, ops).hi
            return ops.make(lo, hi)
        if value.hi < 0.0:
            lo = _pow_point_interval(value.lo, exponent, ops).lo
            hi = _pow_point_interval(value.hi, exponent, ops).hi
            return ops.make(lo, hi)
        lo = _pow_point_interval(value.hi, exponent, ops).lo
        hi = _pow_point_interval(value.lo, exponent, ops).hi
        return ops.make(lo, hi)
    if exponent % 2:
        lo = _pow_point_interval(value.lo, exponent, ops).lo
        hi = _pow_point_interval(value.hi, exponent, ops).hi
        return ops.make(lo, hi)
    if value.hi < 0.0:
        lo = _pow_point_interval(value.hi, exponent, ops).lo
        hi = _pow_point_interval(value.lo, exponent, ops).hi
        return ops.make(lo, hi)
    if value.lo > 0.0:
        lo = _pow_point_interval(value.lo, exponent, ops).lo
        hi = _pow_point_interval(value.hi, exponent, ops).hi
        return ops.make(lo, hi)

    left = _pow_point_interval(value.lo, exponent, ops)
    right = _pow_point_interval(value.hi, exponent, ops)
    return ops.make(0.0, max(left.hi, right.hi))


def _positive_base_pow_interval(
    base: _CInterval,
    exponent: _CInterval,
    ops: _IntervalOps,
) -> _CInterval:
    if ops.is_empty(base) or ops.is_empty(exponent):
        return ops.empty()
    if base.hi <= 0.0:
        return ops.empty()
    if base.lo <= 0.0:
        # Positive-base interpretation only; metadata records partial domain.
        return ops.make(0.0, math.inf)
    if base.lo == base.hi and base.lo.is_integer() and base.lo <= 2**53:
        return ops.pow_positive_integer_base(int(base.lo), exponent)
    if not math.isfinite(exponent.lo) or not math.isfinite(exponent.hi):
        return ops.make(0.0, math.inf)
    # Tupper 3.2.22: a^b = exp(b ln(a)) for a > 0. All stages are
    # outward C/MPFR intervals, including overflow and subnormal conversion.
    return ops.elementary("exp", ops.mul(exponent, ops.elementary("ln", base)))


def _rational_root_interval(
    value: _CInterval, denominator: int, ops: _IntervalOps
) -> _CInterval:
    """Directed real qth-root cover for the bounded new denominator family."""
    if not 4 <= denominator <= 16:
        raise ValueError("new rational roots require denominator 4 through 16")
    if ops.is_empty(value):
        return ops.empty()
    if denominator % 2 == 0 and value.hi < 0.0:
        return ops.empty()
    exponent = _fraction_interval(Fraction(1, denominator), ops)

    def positive(lo: float, hi: float) -> _CInterval:
        # Root is total at zero: the logarithmic helper is used only at
        # strictly positive endpoints, never to infer root definedness.
        if hi == 0.0:
            return ops.point(0.0)
        if lo == 0.0:
            upper = (
                math.inf
                if hi == math.inf
                else _positive_base_pow_interval(ops.point(hi), exponent, ops).hi
            )
            return ops.make(0.0, upper)
        if hi == math.inf:
            lower = (
                math.inf
                if lo == math.inf
                else _positive_base_pow_interval(ops.point(lo), exponent, ops).lo
            )
            return ops.make(lower, math.inf)
        return _positive_base_pow_interval(ops.make(lo, hi), exponent, ops)

    if denominator % 2 == 0:
        return positive(max(0.0, value.lo), value.hi)
    if value.hi <= 0.0:
        return ops.neg(positive(-value.hi, -value.lo))
    if value.lo >= 0.0:
        return positive(value.lo, value.hi)
    negative = positive(0.0, -value.lo)
    nonnegative = positive(0.0, value.hi)
    return ops.make(-negative.hi, nonnegative.hi)


def _positive_constant_base_pow_interval(
    base: float,
    exponent: _CInterval,
    ops: _IntervalOps,
) -> _CInterval:
    if not math.isfinite(base) or base <= 0.0:
        raise ValueError("positive constant base power requires a finite positive base")
    return _positive_base_pow_interval(ops.point(base), exponent, ops)


def _pow_point_interval(value: float, exponent: int, ops: _IntervalOps) -> _CInterval:
    if math.isfinite(value) and abs(exponent) <= 32:
        try:
            return _fraction_interval(Fraction(value) ** exponent, ops)
        except ZeroDivisionError:
            return ops.empty()
    if value == 0.0 and exponent < 0:
        return ops.empty()
    # Exact integer exponentiation by squaring has logarithmic work and keeps
    # C outward bounds; ordinary libm pow plus one ULP is not a certificate.
    result = ops.point(1.0)
    factor = ops.point(abs(value))
    remaining = abs(exponent)
    while remaining:
        if remaining & 1:
            result = ops.mul(result, factor)
        remaining >>= 1
        if remaining:
            factor = ops.mul(factor, factor)
    if exponent < 0:
        result = ops.div(ops.point(1.0), result)
    if value < 0.0 and exponent % 2:
        result = ops.neg(result)
    return result


def _interval_is_point(value: _CInterval, ops: _IntervalOps) -> bool:
    return not ops.is_empty(value) and value.lo == value.hi


def _interval_abs_upper(value: _CInterval) -> float:
    return max(abs(value.lo), abs(value.hi))


def _intervals_disjoint(x: _CInterval, y: _CInterval, ops: _IntervalOps) -> bool:
    return ops.is_empty(x) or ops.is_empty(y) or x.hi < y.lo or y.hi < x.lo


def _x_power_x_magnitude_point(
    value: float,
    sign: int,
    ops: _IntervalOps,
) -> _CInterval:
    """Enclose a^(sign*a); a=0 supplies only the one-sided range limit."""
    if value == 0.0:
        return ops.point(1.0)
    if not math.isfinite(value):
        return ops.make(0.0, math.inf)
    return _positive_constant_base_pow_interval(value, ops.point(sign * value), ops)


def _x_power_x_magnitude_range(
    lo: float,
    hi: float,
    sign: int,
    ops: _IntervalOps,
) -> _CInterval:
    # Tupper 3.2.22 and paper 14 require enclosing every evaluation stage.
    # The two monotone sections meet at a=exp(-1). Include its extremum
    # whenever the input intersects the outward enclosure of that site.
    candidates = [
        _x_power_x_magnitude_point(lo, sign, ops),
        _x_power_x_magnitude_point(hi, sign, ops),
    ]
    turning = ops.elementary("exp", ops.point(-1.0))
    if lo <= turning.hi and turning.lo <= hi:
        exponent = ops.neg(turning) if sign > 0 else turning
        candidates.append(ops.elementary("exp", exponent))
    return ops.make(
        min(value.lo for value in candidates), max(value.hi for value in candidates)
    )


def _positive_x_power_x_range(
    lo: float, hi: float, ops: _IntervalOps
) -> _CInterval | None:
    if hi < 0.0 or lo > hi:
        return None
    return _x_power_x_magnitude_range(max(0.0, lo), hi, 1, ops)


def _negative_x_power_x_magnitude_range(
    a_lo: float,
    a_hi: float,
    ops: _IntervalOps,
) -> _CInterval | None:
    if a_hi <= 0.0 or a_lo > a_hi:
        return None
    return _x_power_x_magnitude_range(max(0.0, a_lo), a_hi, -1, ops)
