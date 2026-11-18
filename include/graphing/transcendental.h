/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#ifndef GRAPHING_TRANSCENDENTAL_H
#define GRAPHING_TRANSCENDENTAL_H

#include "graphing/interval.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Numeric context: MPFR exponent limits must retain their startup defaults.
 * These kernels use explicit precision and directed rounding, independently of
 * MPFR default precision/rounding. They do not change exponent limits or the
 * caller's hardware rounding mode. MPFR sticky flags are not preserved.
 * See docs/numeric-contract.md for the standalone library contract. */
gi_interval gi_trans_pi_multiple(intmax_t numerator, intmax_t denominator);
gi_interval gi_trans_pow_positive_integer_base(
    uint64_t base,
    gi_interval exponent);
gi_interval gi_trans_cbrt(gi_interval x);
gi_interval gi_trans_atan(gi_interval x);
gi_interval gi_trans_exp(gi_interval x);
gi_interval gi_trans_ln(gi_interval x);
gi_interval gi_trans_log10(gi_interval x);
gi_interval gi_trans_sinh(gi_interval x);
gi_interval gi_trans_cosh(gi_interval x);
gi_interval gi_trans_tanh(gi_interval x);
gi_interval gi_trans_asin(gi_interval x);
gi_interval gi_trans_acos(gi_interval x);
gi_interval gi_trans_asinh(gi_interval x);
gi_interval gi_trans_acosh(gi_interval x);
gi_interval gi_trans_atanh(gi_interval x);

gi_interval gi_trans_atan2(gi_interval y, gi_interval x);
gi_interval gi_trans_log2(gi_interval x);
gi_interval gi_trans_sin(gi_interval x);
gi_interval gi_trans_cos(gi_interval x);
gi_interval gi_trans_tan(gi_interval x);
gi_bool_interval gi_trans_tan_defined(gi_interval x);

#ifdef __cplusplus
}
#endif

#endif
