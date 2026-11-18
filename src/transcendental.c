/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#include "graphing/transcendental.h"

#include <stdint.h>
#include <math.h>
#include <mpfr.h>
#include <stdbool.h>

enum {
    GI_MPFR_PRECISION = 256
};

static const double GI_TRIG_CERTIFIED_ABS_MAX = 0x1p40;
static const uint64_t GI_MAX_EXACT_INTEGER_BASE = UINT64_C(9007199254740992);

static gi_interval gi_trans_full_unit_range(void)
{
    return gi_interval_make(-1.0, 1.0);
}

static gi_interval gi_trans_point_sin_or_cos(double x, bool sine)
{
    double lo;
    double hi;
    mpfr_t argument;
    mpfr_t result;

    mpfr_init2(argument, GI_MPFR_PRECISION);
    mpfr_init2(result, GI_MPFR_PRECISION);
    mpfr_set_d(argument, x, MPFR_RNDN);
    if (sine) {
        mpfr_sin(result, argument, MPFR_RNDD);
        lo = mpfr_get_d(result, MPFR_RNDD);
        mpfr_sin(result, argument, MPFR_RNDU);
        hi = mpfr_get_d(result, MPFR_RNDU);
    } else {
        mpfr_cos(result, argument, MPFR_RNDD);
        lo = mpfr_get_d(result, MPFR_RNDD);
        mpfr_cos(result, argument, MPFR_RNDU);
        hi = mpfr_get_d(result, MPFR_RNDU);
    }
    mpfr_clear(argument);
    mpfr_clear(result);
    return gi_interval_make(lo, hi);
}

static bool gi_trans_requires_fallback_range(gi_interval x)
{
    if (!isfinite(x.lo) || !isfinite(x.hi)) {
        return true;
    }
    return fabs(x.lo) > GI_TRIG_CERTIFIED_ABS_MAX || fabs(x.hi) > GI_TRIG_CERTIFIED_ABS_MAX;
}

static void gi_set_pi_bounds(mpfr_t pi_lo, mpfr_t pi_hi)
{
    mpfr_const_pi(pi_lo, MPFR_RNDD);
    mpfr_const_pi(pi_hi, MPFR_RNDU);
}

static void gi_set_two_pi_bounds(mpfr_t period_lo, mpfr_t period_hi)
{
    mpfr_t pi_lo;
    mpfr_t pi_hi;

    mpfr_init2(pi_lo, GI_MPFR_PRECISION);
    mpfr_init2(pi_hi, GI_MPFR_PRECISION);

    gi_set_pi_bounds(pi_lo, pi_hi);
    mpfr_mul_ui(period_lo, pi_lo, 2, MPFR_RNDD);
    mpfr_mul_ui(period_hi, pi_hi, 2, MPFR_RNDU);

    mpfr_clear(pi_lo);
    mpfr_clear(pi_hi);
}

static void gi_set_half_pi_bounds(mpfr_t phase_lo, mpfr_t phase_hi, int sign)
{
    mpfr_t pi_lo;
    mpfr_t pi_hi;
    mpfr_t half_lo;
    mpfr_t half_hi;

    mpfr_init2(pi_lo, GI_MPFR_PRECISION);
    mpfr_init2(pi_hi, GI_MPFR_PRECISION);
    mpfr_init2(half_lo, GI_MPFR_PRECISION);
    mpfr_init2(half_hi, GI_MPFR_PRECISION);

    mpfr_const_pi(pi_lo, MPFR_RNDD);
    mpfr_const_pi(pi_hi, MPFR_RNDU);
    mpfr_div_ui(half_lo, pi_lo, 2, MPFR_RNDD);
    mpfr_div_ui(half_hi, pi_hi, 2, MPFR_RNDU);

    if (sign > 0) {
        mpfr_set(phase_lo, half_lo, MPFR_RNDD);
        mpfr_set(phase_hi, half_hi, MPFR_RNDU);
    } else {
        mpfr_neg(phase_lo, half_hi, MPFR_RNDD);
        mpfr_neg(phase_hi, half_lo, MPFR_RNDU);
    }

    mpfr_clear(pi_lo);
    mpfr_clear(pi_hi);
    mpfr_clear(half_lo);
    mpfr_clear(half_hi);
}

static void gi_mpfr_min_into(mpfr_t target, const mpfr_t candidate)
{
    if (mpfr_less_p(candidate, target)) {
        mpfr_set(target, candidate, MPFR_RNDD);
    }
}

static void gi_mpfr_max_into(mpfr_t target, const mpfr_t candidate)
{
    if (mpfr_greater_p(candidate, target)) {
        mpfr_set(target, candidate, MPFR_RNDU);
    }
}

static bool gi_interval_maybe_contains_phase_bounds(
    gi_interval x,
    const mpfr_t phase_lo,
    const mpfr_t phase_hi,
    const mpfr_t period_lo,
    const mpfr_t period_hi)
{
    bool result;
    mpfr_t arg_lo;
    mpfr_t arg_hi;
    mpfr_t numerator_lo;
    mpfr_t numerator_hi;
    mpfr_t q_lo;
    mpfr_t q_hi;
    mpfr_t candidate;
    mpfr_t ceil_q_lo;
    mpfr_t floor_q_hi;

    mpfr_inits2(
        GI_MPFR_PRECISION,
        arg_lo,
        arg_hi,
        numerator_lo,
        numerator_hi,
        q_lo,
        q_hi,
        candidate,
        ceil_q_lo,
        floor_q_hi,
        (mpfr_ptr)0);

    mpfr_set_d(arg_lo, x.lo, MPFR_RNDN);
    mpfr_set_d(arg_hi, x.hi, MPFR_RNDN);

    mpfr_sub(numerator_lo, arg_lo, phase_hi, MPFR_RNDD);
    mpfr_sub(numerator_hi, arg_hi, phase_lo, MPFR_RNDU);

    mpfr_div(q_lo, numerator_lo, period_lo, MPFR_RNDD);
    mpfr_set(q_hi, q_lo, MPFR_RNDU);

    mpfr_div(candidate, numerator_lo, period_hi, MPFR_RNDD);
    gi_mpfr_min_into(q_lo, candidate);
    mpfr_div(candidate, numerator_hi, period_lo, MPFR_RNDD);
    gi_mpfr_min_into(q_lo, candidate);
    mpfr_div(candidate, numerator_hi, period_hi, MPFR_RNDD);
    gi_mpfr_min_into(q_lo, candidate);

    mpfr_div(candidate, numerator_lo, period_lo, MPFR_RNDU);
    gi_mpfr_max_into(q_hi, candidate);
    mpfr_div(candidate, numerator_lo, period_hi, MPFR_RNDU);
    gi_mpfr_max_into(q_hi, candidate);
    mpfr_div(candidate, numerator_hi, period_lo, MPFR_RNDU);
    gi_mpfr_max_into(q_hi, candidate);
    mpfr_div(candidate, numerator_hi, period_hi, MPFR_RNDU);
    gi_mpfr_max_into(q_hi, candidate);

    mpfr_ceil(ceil_q_lo, q_lo);
    mpfr_floor(floor_q_hi, q_hi);
    result = mpfr_cmp(ceil_q_lo, floor_q_hi) <= 0;

    mpfr_clears(
        arg_lo,
        arg_hi,
        numerator_lo,
        numerator_hi,
        q_lo,
        q_hi,
        candidate,
        ceil_q_lo,
        floor_q_hi,
        (mpfr_ptr)0);

    return result;
}

static bool gi_interval_maybe_contains_sine_phase(gi_interval x, int phase_sign)
{
    bool result;
    mpfr_t phase_lo;
    mpfr_t phase_hi;
    mpfr_t period_lo;
    mpfr_t period_hi;

    mpfr_inits2(GI_MPFR_PRECISION, phase_lo, phase_hi, period_lo, period_hi, (mpfr_ptr)0);
    gi_set_half_pi_bounds(phase_lo, phase_hi, phase_sign);
    gi_set_two_pi_bounds(period_lo, period_hi);

    result = gi_interval_maybe_contains_phase_bounds(x, phase_lo, phase_hi, period_lo, period_hi);

    mpfr_clears(phase_lo, phase_hi, period_lo, period_hi, (mpfr_ptr)0);
    return result;
}

static bool gi_interval_maybe_contains_cosine_phase(gi_interval x, int phase_sign)
{
    bool result;
    mpfr_t phase_lo;
    mpfr_t phase_hi;
    mpfr_t period_lo;
    mpfr_t period_hi;

    mpfr_inits2(GI_MPFR_PRECISION, phase_lo, phase_hi, period_lo, period_hi, (mpfr_ptr)0);
    if (phase_sign > 0) {
        mpfr_set_ui(phase_lo, 0, MPFR_RNDD);
        mpfr_set_ui(phase_hi, 0, MPFR_RNDU);
    } else {
        gi_set_pi_bounds(phase_lo, phase_hi);
    }
    gi_set_two_pi_bounds(period_lo, period_hi);

    result = gi_interval_maybe_contains_phase_bounds(x, phase_lo, phase_hi, period_lo, period_hi);

    mpfr_clears(phase_lo, phase_hi, period_lo, period_hi, (mpfr_ptr)0);
    return result;
}

static bool gi_interval_maybe_contains_tangent_pole(gi_interval x)
{
    bool result;
    mpfr_t phase_lo;
    mpfr_t phase_hi;
    mpfr_t period_lo;
    mpfr_t period_hi;

    mpfr_inits2(GI_MPFR_PRECISION, phase_lo, phase_hi, period_lo, period_hi, (mpfr_ptr)0);
    gi_set_half_pi_bounds(phase_lo, phase_hi, 1);
    gi_set_pi_bounds(period_lo, period_hi);

    result = gi_interval_maybe_contains_phase_bounds(x, phase_lo, phase_hi, period_lo, period_hi);

    mpfr_clears(phase_lo, phase_hi, period_lo, period_hi, (mpfr_ptr)0);
    return result;
}

gi_interval gi_trans_pi_multiple(intmax_t numerator, intmax_t denominator)
{
    double lo;
    double hi;
    mpfr_t pi_lo;
    mpfr_t pi_hi;
    mpfr_t factor;
    mpfr_t divisor;
    mpfr_t value_lo;
    mpfr_t value_hi;

    if (denominator <= 0) {
        return gi_interval_empty();
    }

    mpfr_inits2(
        GI_MPFR_PRECISION,
        pi_lo,
        pi_hi,
        factor,
        divisor,
        value_lo,
        value_hi,
        (mpfr_ptr)0);
    gi_set_pi_bounds(pi_lo, pi_hi);
    mpfr_set_sj(factor, numerator, MPFR_RNDN);
    mpfr_set_sj(divisor, denominator, MPFR_RNDN);

    if (numerator < 0) {
        mpfr_mul(value_lo, pi_hi, factor, MPFR_RNDD);
        mpfr_mul(value_hi, pi_lo, factor, MPFR_RNDU);
    } else {
        mpfr_mul(value_lo, pi_lo, factor, MPFR_RNDD);
        mpfr_mul(value_hi, pi_hi, factor, MPFR_RNDU);
    }
    mpfr_div(value_lo, value_lo, divisor, MPFR_RNDD);
    mpfr_div(value_hi, value_hi, divisor, MPFR_RNDU);

    lo = mpfr_get_d(value_lo, MPFR_RNDD);
    hi = mpfr_get_d(value_hi, MPFR_RNDU);

    mpfr_clears(pi_lo, pi_hi, factor, divisor, value_lo, value_hi, (mpfr_ptr)0);
    return gi_interval_make(lo, hi);
}

gi_interval gi_trans_pow_positive_integer_base(
    uint64_t base,
    gi_interval exponent)
{
    double lo;
    double hi;
    mpfr_t base_value;
    mpfr_t exponent_lo;
    mpfr_t exponent_hi;
    mpfr_t value_lo;
    mpfr_t value_hi;

    if (gi_interval_is_empty(exponent)) {
        return gi_interval_empty();
    }
    if (base == 0 || base > GI_MAX_EXACT_INTEGER_BASE) {
        return gi_interval_whole();
    }
    if (base == 1) {
        return gi_interval_point(1.0);
    }
    if (!isfinite(exponent.lo) || !isfinite(exponent.hi)) {
        return gi_interval_make(0.0, INFINITY);
    }

    mpfr_inits2(
        GI_MPFR_PRECISION,
        base_value,
        exponent_lo,
        exponent_hi,
        value_lo,
        value_hi,
        (mpfr_ptr)0);
    /* Every admitted base is exactly representable as binary64. */
    mpfr_set_d(base_value, (double)base, MPFR_RNDN);
    mpfr_set_d(exponent_lo, exponent.lo, MPFR_RNDN);
    mpfr_set_d(exponent_hi, exponent.hi, MPFR_RNDN);
    mpfr_pow(value_lo, base_value, exponent_lo, MPFR_RNDD);
    mpfr_pow(value_hi, base_value, exponent_hi, MPFR_RNDU);
    lo = mpfr_get_d(value_lo, MPFR_RNDD);
    hi = mpfr_get_d(value_hi, MPFR_RNDU);
    mpfr_clears(
        base_value,
        exponent_lo,
        exponent_hi,
        value_lo,
        value_hi,
        (mpfr_ptr)0);
    return gi_interval_make(lo, hi);
}

gi_interval gi_trans_cbrt(gi_interval x)
{
    double lo;
    double hi;
    mpfr_t arg_lo;
    mpfr_t arg_hi;
    mpfr_t root_lo;
    mpfr_t root_hi;

    if (gi_interval_is_empty(x)) {
        return gi_interval_empty();
    }

    mpfr_inits2(GI_MPFR_PRECISION, arg_lo, arg_hi, root_lo, root_hi, (mpfr_ptr)0);
    mpfr_set_d(arg_lo, x.lo, MPFR_RNDN);
    mpfr_set_d(arg_hi, x.hi, MPFR_RNDN);
    mpfr_cbrt(root_lo, arg_lo, MPFR_RNDD);
    mpfr_cbrt(root_hi, arg_hi, MPFR_RNDU);

    lo = mpfr_get_d(root_lo, MPFR_RNDD);
    hi = mpfr_get_d(root_hi, MPFR_RNDU);

    mpfr_clears(arg_lo, arg_hi, root_lo, root_hi, (mpfr_ptr)0);
    return gi_interval_make(lo, hi);
}

/* Tupper §§3.2.10–3.2.14: outward endpoint bounds on monotone sections.
 * Callers intersect the value domain; evaluator metadata retains partial domains.
 */
static gi_interval gi_trans_monotone(
    gi_interval x,
    int (*operation)(mpfr_ptr, mpfr_srcptr, mpfr_rnd_t),
    bool decreasing)
{
    mpfr_t input;
    mpfr_t output;
    double lo;
    double hi;
    if (gi_interval_is_empty(x)) return gi_interval_empty();
    mpfr_inits2(GI_MPFR_PRECISION, input, output, (mpfr_ptr)0);
    mpfr_set_d(input, decreasing ? x.hi : x.lo, MPFR_RNDN);
    operation(output, input, MPFR_RNDD);
    lo = mpfr_get_d(output, MPFR_RNDD);
    mpfr_set_d(input, decreasing ? x.lo : x.hi, MPFR_RNDN);
    operation(output, input, MPFR_RNDU);
    hi = mpfr_get_d(output, MPFR_RNDU);
    mpfr_clears(input, output, (mpfr_ptr)0);
    return gi_interval_make(lo == 0.0 ? 0.0 : lo, hi == 0.0 ? 0.0 : hi);
}

gi_interval gi_trans_exp(gi_interval x)
{
    return gi_trans_monotone(x, mpfr_exp, false);
}

gi_interval gi_trans_ln(gi_interval x)
{
    if (gi_interval_is_empty(x) || x.hi <= 0.0) return gi_interval_empty();
    x.lo = fmax(x.lo, 0.0);
    return gi_trans_monotone(x, mpfr_log, false);
}

gi_interval gi_trans_log10(gi_interval x)
{
    if (gi_interval_is_empty(x) || x.hi <= 0.0) return gi_interval_empty();
    x.lo = fmax(x.lo, 0.0);
    return gi_trans_monotone(x, mpfr_log10, false);
}

gi_interval gi_trans_sinh(gi_interval x)
{
    return gi_trans_monotone(x, mpfr_sinh, false);
}

gi_interval gi_trans_cosh(gi_interval x)
{
    x = gi_interval_abs(x);
    return gi_trans_monotone(x, mpfr_cosh, false);
}

gi_interval gi_trans_tanh(gi_interval x)
{
    return gi_trans_monotone(x, mpfr_tanh, false);
}

gi_interval gi_trans_asin(gi_interval x)
{
    x = gi_interval_intersect(x, gi_interval_make(-1.0, 1.0));
    return gi_trans_monotone(x, mpfr_asin, false);
}

gi_interval gi_trans_acos(gi_interval x)
{
    x = gi_interval_intersect(x, gi_interval_make(-1.0, 1.0));
    return gi_trans_monotone(x, mpfr_acos, true);
}

gi_interval gi_trans_asinh(gi_interval x)
{
    return gi_trans_monotone(x, mpfr_asinh, false);
}

gi_interval gi_trans_acosh(gi_interval x)
{
    x = gi_interval_intersect(x, gi_interval_make(1.0, INFINITY));
    return gi_trans_monotone(x, mpfr_acosh, false);
}

gi_interval gi_trans_atanh(gi_interval x)
{
    if (gi_interval_is_empty(x) || x.hi <= -1.0 || x.lo >= 1.0) return gi_interval_empty();
    x = gi_interval_intersect(x, gi_interval_make(-1.0, 1.0));
    return gi_trans_monotone(x, mpfr_atanh, false);
}

gi_interval gi_trans_atan(gi_interval x)
{
    double lo;
    double hi;
    mpfr_t arg_lo;
    mpfr_t arg_hi;
    mpfr_t atan_lo;
    mpfr_t atan_hi;

    if (gi_interval_is_empty(x)) {
        return gi_interval_empty();
    }

    mpfr_inits2(GI_MPFR_PRECISION, arg_lo, arg_hi, atan_lo, atan_hi, (mpfr_ptr)0);
    mpfr_set_d(arg_lo, x.lo, MPFR_RNDN);
    mpfr_set_d(arg_hi, x.hi, MPFR_RNDN);
    mpfr_atan(atan_lo, arg_lo, MPFR_RNDD);
    mpfr_atan(atan_hi, arg_hi, MPFR_RNDU);

    lo = mpfr_get_d(atan_lo, MPFR_RNDD);
    hi = mpfr_get_d(atan_hi, MPFR_RNDU);
    if (lo == 0.0) {
        lo = 0.0;
    }
    if (hi == 0.0) {
        hi = 0.0;
    }

    mpfr_clears(arg_lo, arg_hi, atan_lo, atan_hi, (mpfr_ptr)0);
    return gi_interval_make(lo, hi);
}

gi_interval gi_trans_log2(gi_interval x)
{
    double lo;
    double hi;
    mpfr_t arg_lo;
    mpfr_t arg_hi;
    mpfr_t log_lo;
    mpfr_t log_hi;

    if (gi_interval_is_empty(x) || x.hi <= 0.0) {
        return gi_interval_empty();
    }

    mpfr_inits2(GI_MPFR_PRECISION, arg_lo, arg_hi, log_lo, log_hi, (mpfr_ptr)0);
    mpfr_set_d(arg_hi, x.hi, MPFR_RNDN);
    mpfr_log2(log_hi, arg_hi, MPFR_RNDU);
    hi = mpfr_get_d(log_hi, MPFR_RNDU);

    if (x.lo <= 0.0) {
        lo = -INFINITY;
    } else {
        mpfr_set_d(arg_lo, x.lo, MPFR_RNDN);
        mpfr_log2(log_lo, arg_lo, MPFR_RNDD);
        lo = mpfr_get_d(log_lo, MPFR_RNDD);
    }
    if (lo == 0.0) {
        lo = 0.0;
    }
    if (hi == 0.0) {
        hi = 0.0;
    }

    mpfr_clears(arg_lo, arg_hi, log_lo, log_hi, (mpfr_ptr)0);
    return gi_interval_make(lo, hi);
}

static void gi_atan2_include_point(
    double y,
    double x,
    mpfr_t range_lo,
    mpfr_t range_hi,
    bool *has_value)
{
    mpfr_t x_value;
    mpfr_t y_value;
    mpfr_t point_lo;
    mpfr_t point_hi;

    if (x == 0.0 && y == 0.0) {
        return;
    }

    mpfr_inits2(
        GI_MPFR_PRECISION,
        x_value,
        y_value,
        point_lo,
        point_hi,
        (mpfr_ptr)0);
    if (x < 0.0 && y == 0.0) {
        gi_set_pi_bounds(point_lo, point_hi);
    } else {
        mpfr_set_d(x_value, x, MPFR_RNDN);
        mpfr_set_d(y_value, y, MPFR_RNDN);
        const int inexact = mpfr_atan2(point_lo, y_value, x_value, MPFR_RNDD);
        /* MPFR's ternary result distinguishes an exact value from a lower
         * rounded neighbour. At the same precision its successor is exactly
         * the upward-rounded bound; exact results must not be widened. */
        mpfr_set(point_hi, point_lo, MPFR_RNDN);
        if (inexact < 0) {
            mpfr_nextabove(point_hi);
        }
    }

    if (!*has_value) {
        mpfr_set(range_lo, point_lo, MPFR_RNDD);
        mpfr_set(range_hi, point_hi, MPFR_RNDU);
        *has_value = true;
    } else {
        gi_mpfr_min_into(range_lo, point_lo);
        gi_mpfr_max_into(range_hi, point_hi);
    }
    mpfr_clears(x_value, y_value, point_lo, point_hi, (mpfr_ptr)0);
}

gi_interval gi_trans_atan2(gi_interval y, gi_interval x)
{
    bool has_value = false;
    double lo;
    double hi;
    mpfr_t range_lo;
    mpfr_t range_hi;

    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_interval_empty();
    }
    if (x.lo == 0.0 && x.hi == 0.0
        && y.lo == 0.0 && y.hi == 0.0) {
        return gi_interval_empty();
    }
    if (x.lo < 0.0 && y.lo < 0.0 && y.hi >= 0.0) {
        gi_interval negative_pi = gi_trans_pi_multiple(-1, 1);
        gi_interval positive_pi = gi_trans_pi_multiple(1, 1);
        return gi_interval_make(negative_pi.lo, positive_pi.hi);
    }

    mpfr_init2(range_lo, GI_MPFR_PRECISION);
    mpfr_init2(range_hi, GI_MPFR_PRECISION);
    gi_atan2_include_point(y.lo, x.lo, range_lo, range_hi, &has_value);
    /* A singleton rectangle has one corner. The origin and branch-cut
     * checks above, and the helper's +pi negative-axis convention, still apply. */
    if (x.lo != x.hi || y.lo != y.hi) {
        gi_atan2_include_point(y.hi, x.lo, range_lo, range_hi, &has_value);
        gi_atan2_include_point(y.lo, x.hi, range_lo, range_hi, &has_value);
        gi_atan2_include_point(y.hi, x.hi, range_lo, range_hi, &has_value);
        if (x.lo <= 0.0 && 0.0 <= x.hi) {
            gi_atan2_include_point(y.lo, 0.0, range_lo, range_hi, &has_value);
            gi_atan2_include_point(y.hi, 0.0, range_lo, range_hi, &has_value);
        }
        if (y.lo <= 0.0 && 0.0 <= y.hi) {
            gi_atan2_include_point(0.0, x.lo, range_lo, range_hi, &has_value);
            gi_atan2_include_point(0.0, x.hi, range_lo, range_hi, &has_value);
        }
    }

    if (!has_value) {
        mpfr_clear(range_lo);
        mpfr_clear(range_hi);
        return gi_interval_empty();
    }
    lo = mpfr_get_d(range_lo, MPFR_RNDD);
    hi = mpfr_get_d(range_hi, MPFR_RNDU);
    if (lo == 0.0) {
        lo = 0.0;
    }
    if (hi == 0.0) {
        hi = 0.0;
    }
    mpfr_clear(range_lo);
    mpfr_clear(range_hi);
    return gi_interval_make(lo, hi);
}

gi_interval gi_trans_sin(gi_interval x)
{
    bool contains_max;
    bool contains_min;
    double lo;
    double hi;
    mpfr_t arg_lo;
    mpfr_t arg_hi;
    mpfr_t sin_lo_down;
    mpfr_t sin_hi_down;
    mpfr_t sin_lo_up;
    mpfr_t sin_hi_up;
    mpfr_t width;
    mpfr_t period_lo;
    mpfr_t period_hi;

    if (gi_interval_is_empty(x)) {
        return gi_interval_empty();
    }
    /* Every finite singleton is imported exactly by the directed point path.
     * For nonsingletons the existing outward width check may saturate safely.
     * Reaching phase checks implies width < 2*pi: binary64 spacing bounds the
     * endpoints even across the 2^55 binade (whose predecessor gap is 4).
     * No magnitude cutoff is needed here; tangent retains its own policy. */
    if (!isfinite(x.lo) || !isfinite(x.hi)) {
        return gi_trans_full_unit_range();
    }
    if (x.lo == x.hi) {
        return gi_trans_point_sin_or_cos(x.lo, true);
    }

    mpfr_inits2(
        GI_MPFR_PRECISION,
        arg_lo,
        arg_hi,
        sin_lo_down,
        sin_hi_down,
        sin_lo_up,
        sin_hi_up,
        width,
        period_lo,
        period_hi,
        (mpfr_ptr)0);

    mpfr_set_d(arg_lo, x.lo, MPFR_RNDN);
    mpfr_set_d(arg_hi, x.hi, MPFR_RNDN);
    gi_set_two_pi_bounds(period_lo, period_hi);
    mpfr_sub(width, arg_hi, arg_lo, MPFR_RNDU);

    if (mpfr_cmp(width, period_lo) >= 0) {
        mpfr_clears(
            arg_lo,
            arg_hi,
            sin_lo_down,
            sin_hi_down,
            sin_lo_up,
            sin_hi_up,
            width,
            period_lo,
            period_hi,
            (mpfr_ptr)0);
        return gi_trans_full_unit_range();
    }

    mpfr_sin(sin_lo_down, arg_lo, MPFR_RNDD);
    mpfr_sin(sin_hi_down, arg_hi, MPFR_RNDD);
    mpfr_sin(sin_lo_up, arg_lo, MPFR_RNDU);
    mpfr_sin(sin_hi_up, arg_hi, MPFR_RNDU);

    gi_mpfr_min_into(sin_lo_down, sin_hi_down);
    gi_mpfr_max_into(sin_lo_up, sin_hi_up);

    contains_max = gi_interval_maybe_contains_sine_phase(x, 1);
    contains_min = gi_interval_maybe_contains_sine_phase(x, -1);

    lo = contains_min ? -1.0 : mpfr_get_d(sin_lo_down, MPFR_RNDD);
    hi = contains_max ? 1.0 : mpfr_get_d(sin_lo_up, MPFR_RNDU);

    mpfr_clears(
        arg_lo,
        arg_hi,
        sin_lo_down,
        sin_hi_down,
        sin_lo_up,
        sin_hi_up,
        width,
        period_lo,
        period_hi,
        (mpfr_ptr)0);

    return gi_interval_make(lo, hi);
}

gi_interval gi_trans_cos(gi_interval x)
{
    bool contains_max;
    bool contains_min;
    double lo;
    double hi;
    mpfr_t arg_lo;
    mpfr_t arg_hi;
    mpfr_t cos_lo_down;
    mpfr_t cos_hi_down;
    mpfr_t cos_lo_up;
    mpfr_t cos_hi_up;
    mpfr_t width;
    mpfr_t period_lo;
    mpfr_t period_hi;

    if (gi_interval_is_empty(x)) {
        return gi_interval_empty();
    }
    /* Every finite singleton is imported exactly by the directed point path.
     * For nonsingletons the existing outward width check may saturate safely.
     * Reaching phase checks implies width < 2*pi: binary64 spacing bounds the
     * endpoints even across the 2^55 binade (whose predecessor gap is 4).
     * No magnitude cutoff is needed here; tangent retains its own policy. */
    if (!isfinite(x.lo) || !isfinite(x.hi)) {
        return gi_trans_full_unit_range();
    }
    if (x.lo == x.hi) {
        return gi_trans_point_sin_or_cos(x.lo, false);
    }

    mpfr_inits2(
        GI_MPFR_PRECISION,
        arg_lo,
        arg_hi,
        cos_lo_down,
        cos_hi_down,
        cos_lo_up,
        cos_hi_up,
        width,
        period_lo,
        period_hi,
        (mpfr_ptr)0);

    mpfr_set_d(arg_lo, x.lo, MPFR_RNDN);
    mpfr_set_d(arg_hi, x.hi, MPFR_RNDN);
    gi_set_two_pi_bounds(period_lo, period_hi);
    mpfr_sub(width, arg_hi, arg_lo, MPFR_RNDU);

    if (mpfr_cmp(width, period_lo) >= 0) {
        mpfr_clears(
            arg_lo,
            arg_hi,
            cos_lo_down,
            cos_hi_down,
            cos_lo_up,
            cos_hi_up,
            width,
            period_lo,
            period_hi,
            (mpfr_ptr)0);
        return gi_trans_full_unit_range();
    }

    mpfr_cos(cos_lo_down, arg_lo, MPFR_RNDD);
    mpfr_cos(cos_hi_down, arg_hi, MPFR_RNDD);
    mpfr_cos(cos_lo_up, arg_lo, MPFR_RNDU);
    mpfr_cos(cos_hi_up, arg_hi, MPFR_RNDU);

    gi_mpfr_min_into(cos_lo_down, cos_hi_down);
    gi_mpfr_max_into(cos_lo_up, cos_hi_up);

    contains_max = gi_interval_maybe_contains_cosine_phase(x, 1);
    contains_min = gi_interval_maybe_contains_cosine_phase(x, -1);

    lo = contains_min ? -1.0 : mpfr_get_d(cos_lo_down, MPFR_RNDD);
    hi = contains_max ? 1.0 : mpfr_get_d(cos_lo_up, MPFR_RNDU);

    mpfr_clears(
        arg_lo,
        arg_hi,
        cos_lo_down,
        cos_hi_down,
        cos_lo_up,
        cos_hi_up,
        width,
        period_lo,
        period_hi,
        (mpfr_ptr)0);

    return gi_interval_make(lo, hi);
}

gi_interval gi_trans_tan(gi_interval x)
{
    double lo;
    double hi;
    mpfr_t arg_lo;
    mpfr_t arg_hi;
    mpfr_t tan_lo;
    mpfr_t tan_hi;

    if (gi_interval_is_empty(x)) {
        return gi_interval_empty();
    }
    if (gi_trans_requires_fallback_range(x) || gi_interval_maybe_contains_tangent_pole(x)) {
        return gi_interval_whole();
    }

    mpfr_inits2(GI_MPFR_PRECISION, arg_lo, arg_hi, tan_lo, tan_hi, (mpfr_ptr)0);

    mpfr_set_d(arg_lo, x.lo, MPFR_RNDN);
    mpfr_set_d(arg_hi, x.hi, MPFR_RNDN);
    mpfr_tan(tan_lo, arg_lo, MPFR_RNDD);
    mpfr_tan(tan_hi, arg_hi, MPFR_RNDU);

    lo = mpfr_get_d(tan_lo, MPFR_RNDD);
    hi = mpfr_get_d(tan_hi, MPFR_RNDU);

    mpfr_clears(arg_lo, arg_hi, tan_lo, tan_hi, (mpfr_ptr)0);
    return gi_interval_make(lo, hi);
}

gi_bool_interval gi_trans_tan_defined(gi_interval x)
{
    if (gi_interval_is_empty(x)) {
        return gi_bool_make(false, false);
    }
    if (gi_trans_requires_fallback_range(x) || gi_interval_maybe_contains_tangent_pole(x)) {
        return gi_bool_make(false, true);
    }
    return gi_bool_make(true, true);
}
