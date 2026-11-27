# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Experimental interval ABI and immutable evaluation records; no loader."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from .branches import BranchMap as _BranchMap
from .definedness import BoolInterval as _CBoolInterval


class _CInterval(ctypes.Structure):
    lo: float
    hi: float

    _fields_ = [
        ("lo", ctypes.c_double),
        ("hi", ctypes.c_double),
    ]


@dataclass(frozen=True)
class _ChartDomain:
    x: _CInterval
    y: _CInterval


@dataclass(frozen=True)
class _AffineCoordinate:
    axis: str
    scale: float
    offset: float


@dataclass(frozen=True)
class _IntervalAffine:
    """Enclose an expression as an exact integer slope plus interval offset.

    This is witness-only metadata, separate from exact affine identities.
    """

    axis: str | None
    scale: int
    offset: _CInterval


@dataclass(frozen=True)
class _ReciprocalAffineCoordinate:
    axis: str
    numerator: float
    denominator_scale: float
    denominator_offset: float


@dataclass(frozen=True)
class _QuadraticCoordinate:
    axis: str
    scale: float
    offset: float


@dataclass(frozen=True)
class _EvalResult:
    interval: _CInterval
    defined: _CBoolInterval
    continuous: bool
    chart: _ChartDomain | None = None
    coordinate: str | None = None
    affine: _AffineCoordinate | None = None
    constant: float | None = None
    reciprocal_affine: _ReciprocalAffineCoordinate | None = None
    quadratic: _QuadraticCoordinate | None = None
    interval_affine: _IntervalAffine | None = None
    branch_map: _BranchMap = ()


@dataclass(frozen=True)
class _EvalSet:
    branches: tuple[_EvalResult, ...]
    defined: _CBoolInterval
    continuous: bool
