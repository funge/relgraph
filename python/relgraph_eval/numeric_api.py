# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Structural numeric contract; discovery, validation and loading are caller-owned."""

from __future__ import annotations
from typing import Callable, Protocol
from .values import _CInterval
from .definedness import BoolInterval as _CBoolInterval


class _ConfiguredLibrary(Protocol):
    """The finite required ABI, after all ctypes signatures are configured."""

    _name: str
    gi_kernel_abi_descriptor: Callable[[], int]
    gi_kernel_numeric_contract_check: Callable[[], int]
    gi_interval_make: Callable[[float, float], _CInterval]
    gi_interval_point: Callable[[float], _CInterval]
    gi_interval_empty: Callable[[], _CInterval]
    gi_interval_is_empty: Callable[[_CInterval], bool]
    gi_interval_contains: Callable[[_CInterval, float], bool]
    gi_interval_pow_nonnegative_integer_exponent: Callable[
        [_CInterval, int], _CInterval
    ]
    gi_trans_pow_positive_integer_base: Callable[[int, _CInterval], _CInterval]
    gi_trans_pi_multiple: Callable[[int, int], _CInterval]
    gi_trans_atan2: Callable[[_CInterval, _CInterval], _CInterval]
    gi_trans_tan_defined: Callable[[_CInterval], _CBoolInterval]
    gi_interval_add: Callable[[_CInterval, _CInterval], _CInterval]
    gi_interval_sub: Callable[[_CInterval, _CInterval], _CInterval]
    gi_interval_mul: Callable[[_CInterval, _CInterval], _CInterval]
    gi_interval_div: Callable[[_CInterval, _CInterval], _CInterval]
    gi_interval_min: Callable[[_CInterval, _CInterval], _CInterval]
    gi_interval_max: Callable[[_CInterval, _CInterval], _CInterval]
    gi_interval_hull: Callable[[_CInterval, _CInterval], _CInterval]
    gi_interval_intersect: Callable[[_CInterval, _CInterval], _CInterval]
    gi_interval_sqrt: Callable[[_CInterval], _CInterval]
    gi_interval_neg: Callable[[_CInterval], _CInterval]
    gi_interval_abs: Callable[[_CInterval], _CInterval]
    gi_interval_floor: Callable[[_CInterval], _CInterval]
    gi_interval_ceil: Callable[[_CInterval], _CInterval]
    gi_interval_factorial: Callable[[_CInterval], _CInterval]
    gi_remainder_mod_point: Callable[[float, float], _CInterval]
    gi_remainder_fmod_point: Callable[[float, float], _CInterval]
    gi_common_factor_gcd_point: Callable[[float, float], _CInterval]
    gi_common_factor_gcd_unit_upper: Callable[[_CInterval, float, float], float]
    gi_common_factor_lcm_point: Callable[[float, float], _CInterval]
    gi_interval_gt: Callable[[_CInterval, _CInterval], _CBoolInterval]
    gi_interval_ge: Callable[[_CInterval, _CInterval], _CBoolInterval]
    gi_interval_lt: Callable[[_CInterval, _CInterval], _CBoolInterval]
    gi_interval_le: Callable[[_CInterval, _CInterval], _CBoolInterval]
    gi_interval_eq: Callable[[_CInterval, _CInterval], _CBoolInterval]
    gi_trans_atan: Callable[[_CInterval], _CInterval]
    gi_trans_log2: Callable[[_CInterval], _CInterval]
    gi_trans_sin: Callable[[_CInterval], _CInterval]
    gi_trans_cos: Callable[[_CInterval], _CInterval]
    gi_trans_tan: Callable[[_CInterval], _CInterval]
    gi_trans_cbrt: Callable[[_CInterval], _CInterval]
    gi_trans_exp: Callable[[_CInterval], _CInterval]
    gi_trans_ln: Callable[[_CInterval], _CInterval]
    gi_trans_log10: Callable[[_CInterval], _CInterval]
    gi_trans_sinh: Callable[[_CInterval], _CInterval]
    gi_trans_cosh: Callable[[_CInterval], _CInterval]
    gi_trans_tanh: Callable[[_CInterval], _CInterval]
    gi_trans_asin: Callable[[_CInterval], _CInterval]
    gi_trans_acos: Callable[[_CInterval], _CInterval]
    gi_trans_asinh: Callable[[_CInterval], _CInterval]
    gi_trans_acosh: Callable[[_CInterval], _CInterval]
    gi_trans_atanh: Callable[[_CInterval], _CInterval]


class _NumericOps(Protocol):
    lib: _ConfiguredLibrary

    def make(self, lo: float, hi: float) -> _CInterval: ...

    def point(self, value: float) -> _CInterval: ...

    def empty(self) -> _CInterval: ...

    def is_empty(self, value: _CInterval) -> bool: ...

    def contains(self, value: _CInterval, point: float) -> bool: ...

    def add(self, x: _CInterval, y: _CInterval) -> _CInterval: ...

    def sub(self, x: _CInterval, y: _CInterval) -> _CInterval: ...

    def mul(self, x: _CInterval, y: _CInterval) -> _CInterval: ...

    def div(self, x: _CInterval, y: _CInterval) -> _CInterval: ...

    def hull(self, x: _CInterval, y: _CInterval) -> _CInterval: ...

    def intersect(self, x: _CInterval, y: _CInterval) -> _CInterval: ...

    def sqrt(self, x: _CInterval) -> _CInterval: ...

    def pow_positive_integer_base(
        self, base: int, exponent: _CInterval
    ) -> _CInterval: ...

    def cbrt(self, x: _CInterval) -> _CInterval: ...

    def ceil(self, x: _CInterval) -> _CInterval: ...

    def floor(self, x: _CInterval) -> _CInterval: ...

    def factorial(self, x: _CInterval) -> _CInterval: ...

    def gcd(self, *values: _CInterval) -> _CInterval: ...

    def lcm(self, *values: _CInterval) -> _CInterval: ...

    def neg(self, x: _CInterval) -> _CInterval: ...

    def abs(self, x: _CInterval) -> _CInterval: ...

    def max(self, x: _CInterval, y: _CInterval) -> _CInterval: ...

    def min(self, x: _CInterval, y: _CInterval) -> _CInterval: ...

    def elementary(self, name: str, x: _CInterval) -> _CInterval: ...

    def atan(self, x: _CInterval) -> _CInterval: ...

    def atan2(self, y: _CInterval, x: _CInterval) -> _CInterval: ...

    def log2(self, x: _CInterval) -> _CInterval: ...

    def cos(self, x: _CInterval) -> _CInterval: ...

    def pi_multiple(self, numerator: int, denominator: int) -> _CInterval: ...

    def mod(self, x: _CInterval, y: _CInterval) -> _CInterval: ...

    def fmod(self, x: _CInterval, y: _CInterval) -> _CInterval: ...

    def sin(self, x: _CInterval) -> _CInterval: ...

    def tan(self, x: _CInterval) -> _CInterval: ...

    def tan_defined(self, x: _CInterval) -> _CBoolInterval: ...

    def gt(self, x: _CInterval, y: _CInterval) -> _CBoolInterval: ...

    def ge(self, x: _CInterval, y: _CInterval) -> _CBoolInterval: ...

    def lt(self, x: _CInterval, y: _CInterval) -> _CBoolInterval: ...

    def le(self, x: _CInterval, y: _CInterval) -> _CBoolInterval: ...

    def eq(self, x: _CInterval, y: _CInterval) -> _CBoolInterval: ...
