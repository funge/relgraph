# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Exact scalar admission and directed endpoint conversion."""

from __future__ import annotations

import math
import sys
from fractions import Fraction
from typing import Protocol, cast
from .values import _CInterval


class _HexFloat(Protocol):
    """Native c_double fields and serialized interval records support hex()."""

    def hex(self) -> str: ...


def _fraction_lower_float(value: Fraction) -> float:
    try:
        rounded = float(value)
    except OverflowError:
        return -math.inf if value < 0 else sys.float_info.max
    if math.isinf(rounded):
        return -math.inf if rounded < 0.0 else sys.float_info.max
    if Fraction(rounded) > value:
        return math.nextafter(rounded, -math.inf)
    return rounded


def _fraction_upper_float(value: Fraction) -> float:
    try:
        rounded = float(value)
    except OverflowError:
        return -sys.float_info.max if value < 0 else math.inf
    if math.isinf(rounded):
        return -sys.float_info.max if rounded < 0.0 else math.inf
    if Fraction(rounded) < value:
        return math.nextafter(rounded, math.inf)
    return rounded


def _interval_cache_key(value: _CInterval) -> tuple[str, str]:
    return cast(_HexFloat, value.lo).hex(), cast(_HexFloat, value.hi).hex()


def _exact_metadata_float(value: Fraction | float) -> float | None:
    # Tupper 2.7 / paper 11: structural annotations claim exact identities.
    # A finite rounded approximation is not an exact constant or coefficient.
    try:
        rounded = float(value)
    except OverflowError:
        return None
    if not math.isfinite(rounded) or Fraction(rounded) != value:
        return None
    return rounded
