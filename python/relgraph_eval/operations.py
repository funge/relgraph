# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Caller-owned evaluation callbacks; no cache, profile, loader or app state."""

from __future__ import annotations
from typing import Protocol
from .numeric_api import _NumericOps
from .numeric import _IntervalCover
from .values import _CInterval, _EvalResult, _EvalSet
from .definedness import BoolInterval as _CBoolInterval


class _IntervalOps(_NumericOps, Protocol):
    def record_operator_sections(
        self,
        name: str,
        section_count: int,
        *,
        noncontinuous_sections: int = 0,
        missing_chart_sections: int = 0,
    ) -> None: ...

    def record_chart_loss(
        self, name: str, expression: str, reason: str, *, sections: int = 1
    ) -> None: ...

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


class _ResultFactory(Protocol):
    def __call__(
        self,
        interval: _CInterval,
        defined: _CBoolInterval,
        continuous: bool,
        *,
        constant: float | None = None,
    ) -> _EvalResult: ...


class _SetFactory(Protocol):
    def __call__(
        self,
        branches: tuple[_EvalResult, ...],
        defined: _CBoolInterval,
        continuous: bool,
        ops: _IntervalOps,
    ) -> _EvalSet: ...
