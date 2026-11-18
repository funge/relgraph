/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#ifndef GRAPHING_INTERVAL_H
#define GRAPHING_INTERVAL_H

#include <float.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ != 0)
#error "graphing requires finite/domain-preserving rounding-safe compilation"
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    double lo;
    double hi;
} gi_interval;

typedef struct {
    bool lo;
    bool hi;
} gi_bool_interval;

#ifdef __cplusplus
#define GI_LAYOUT_ASSERT(condition, message) static_assert(condition, message)
#else
#define GI_LAYOUT_ASSERT(condition, message) _Static_assert(condition, message)
#endif
GI_LAYOUT_ASSERT(FLT_RADIX == 2 && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024
    && DBL_MIN_EXP == -1021 && sizeof(double) == 8, "graphing requires binary64");
GI_LAYOUT_ASSERT(offsetof(gi_interval, lo) == 0 && offsetof(gi_bool_interval, lo) == 0,
    "graphing ABI requires first-field offset zero");
GI_LAYOUT_ASSERT(sizeof(gi_interval) <= UINT8_MAX && sizeof(gi_bool_interval) <= UINT8_MAX
    && offsetof(gi_interval, hi) <= UINT8_MAX && offsetof(gi_bool_interval, hi) <= UINT8_MAX,
    "graphing ABI descriptor fields must fit one byte");
#undef GI_LAYOUT_ASSERT

/* Versioned scalar bootstrap, queried before foreign struct-return calls. */
uint64_t gi_kernel_abi_descriptor(void);
/* A few loading-thread checks; preserves the full caller fenv on every exit.
   This does not certify future thread/environment changes or every primitive. */
uint32_t gi_kernel_numeric_contract_check(void);

enum {
    GI_INTERVAL_MAX_INTEGER_POWER = 16,
    GI_INTERVAL_MAX_FINITE_FACTORIAL_INPUT = 170
};

gi_interval gi_interval_make(double lo, double hi);
gi_interval gi_interval_point(double value);
gi_interval gi_interval_empty(void);
gi_interval gi_interval_whole(void);

bool gi_interval_is_empty(gi_interval x);
bool gi_interval_contains(gi_interval x, double value);

gi_interval gi_interval_add(gi_interval x, gi_interval y);
gi_interval gi_interval_sub(gi_interval x, gi_interval y);
gi_interval gi_interval_mul(gi_interval x, gi_interval y);
gi_interval gi_interval_div(gi_interval x, gi_interval y);
gi_interval gi_interval_min(gi_interval x, gi_interval y);
gi_interval gi_interval_max(gi_interval x, gi_interval y);
gi_interval gi_interval_sqrt(gi_interval x);
gi_interval gi_interval_neg(gi_interval x);
gi_interval gi_interval_abs(gi_interval x);
gi_interval gi_interval_floor(gi_interval x);
gi_interval gi_interval_ceil(gi_interval x);

/*
 * Enclose n! for an exact nonnegative-integer point n. Other inputs return
 * the empty interval. Results above binary64's finite range retain the sound
 * one-sided enclosure [DBL_MAX, +infinity].
 */
gi_interval gi_interval_factorial(gi_interval x);

/*
 * Enclose x^exponent for exponents through GI_INTERVAL_MAX_INTEGER_POWER.
 * A nonempty interval raised to zero is [1, 1]. Out-of-contract exponents
 * return the universal interval so an unvalidated caller cannot strengthen a
 * result accidentally.
 */
gi_interval gi_interval_pow_nonnegative_integer_exponent(gi_interval x, uint32_t exponent);

gi_interval gi_interval_hull(gi_interval x, gi_interval y);
gi_interval gi_interval_intersect(gi_interval x, gi_interval y);

gi_bool_interval gi_interval_gt(gi_interval x, gi_interval y);
gi_bool_interval gi_interval_ge(gi_interval x, gi_interval y);
gi_bool_interval gi_interval_lt(gi_interval x, gi_interval y);
gi_bool_interval gi_interval_le(gi_interval x, gi_interval y);
gi_bool_interval gi_interval_eq(gi_interval x, gi_interval y);

gi_bool_interval gi_bool_make(bool lo, bool hi);
gi_bool_interval gi_bool_not(gi_bool_interval x);
gi_bool_interval gi_bool_and(gi_bool_interval x, gi_bool_interval y);
gi_bool_interval gi_bool_or(gi_bool_interval x, gi_bool_interval y);

#ifdef __cplusplus
}
#endif

#endif
