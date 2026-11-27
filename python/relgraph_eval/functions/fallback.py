# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import math

from ..values import _EvalResult
from ..operations import _IntervalOps
from ..numeric import _BOOL_MAYBE, _bool_and, _bool_is_false
from ..numeric import _CBoolInterval


def _fallback_function_result(
    argument_domains: tuple[_CBoolInterval, ...],
    ops: _IntervalOps,
) -> _EvalResult:
    # Tupper §§2.7.4, 2.11–2.12: a universal value cover is valid, but
    # supplies no proof of definedness, continuity, or a parameter chart.
    # Strict composition still excludes a certainly undefined argument.
    defined = _bool_and(_BOOL_MAYBE, *argument_domains)
    interval = ops.empty() if _bool_is_false(defined) else ops.make(-math.inf, math.inf)
    return _EvalResult(interval, defined, False)
