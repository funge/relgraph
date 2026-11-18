/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#pragma STDC FENV_ACCESS ON

#include "graphing/common_factor.h"

#include <fenv.h>
#include <gmp.h>
#include <math.h>
#include <mpfr.h>

static gi_interval nonnegative_rational_interval(mpq_srcptr value)
{
    double lo;
    double hi;
    mpfr_t lower;
    mpfr_t upper;

    mpfr_init2(lower, 53U);
    mpfr_init2(upper, 53U);
    mpfr_set_q(lower, value, MPFR_RNDD);
    mpfr_set_q(upper, value, MPFR_RNDU);
    lo = mpfr_get_d(lower, MPFR_RNDD);
    hi = mpfr_get_d(upper, MPFR_RNDU);
    mpfr_clear(lower);
    mpfr_clear(upper);

    if (lo == 0.0) {
        lo = 0.0;
    }
    if (hi == 0.0) {
        hi = 0.0;
    }
    return gi_interval_make(lo, hi);
}

static void set_absolute_numerator(mpz_ptr output, mpq_srcptr value)
{
    mpz_abs(output, mpq_numref(value));
}

gi_interval gi_common_factor_gcd_point(double left, double right)
{
    gi_interval interval;
    mpq_t left_value;
    mpq_t right_value;
    mpq_t result;
    mpz_t left_numerator;
    mpz_t right_numerator;

    if (!isfinite(left) || !isfinite(right)) {
        return gi_interval_empty();
    }

    mpq_inits(left_value, right_value, result, (mpq_ptr)0);
    mpz_inits(left_numerator, right_numerator, (mpz_ptr)0);
    mpq_set_d(left_value, left);
    mpq_set_d(right_value, right);
    set_absolute_numerator(left_numerator, left_value);
    set_absolute_numerator(right_numerator, right_value);
    mpz_gcd(mpq_numref(result), left_numerator, right_numerator);
    mpz_lcm(mpq_denref(result), mpq_denref(left_value), mpq_denref(right_value));
    mpq_canonicalize(result);
    interval = nonnegative_rational_interval(result);
    mpz_clears(left_numerator, right_numerator, (mpz_ptr)0);
    mpq_clears(left_value, right_value, result, (mpq_ptr)0);
    return interval;
}

gi_interval gi_common_factor_lcm_point(double left, double right)
{
    gi_interval interval;
    mpq_t left_value;
    mpq_t right_value;
    mpq_t result;
    mpz_t left_numerator;
    mpz_t right_numerator;

    if (!isfinite(left) || !isfinite(right)) {
        return gi_interval_empty();
    }
    if (left == 0.0 || right == 0.0) {
        return gi_interval_point(0.0);
    }

    mpq_inits(left_value, right_value, result, (mpq_ptr)0);
    mpz_inits(left_numerator, right_numerator, (mpz_ptr)0);
    mpq_set_d(left_value, left);
    mpq_set_d(right_value, right);
    set_absolute_numerator(left_numerator, left_value);
    set_absolute_numerator(right_numerator, right_value);
    mpz_lcm(mpq_numref(result), left_numerator, right_numerator);
    mpz_gcd(mpq_denref(result), mpq_denref(left_value), mpq_denref(right_value));
    mpq_canonicalize(result);
    interval = nonnegative_rational_interval(result);
    mpz_clears(left_numerator, right_numerator, (mpz_ptr)0);
    mpq_clears(left_value, right_value, result, (mpq_ptr)0);
    return interval;
}


double gi_common_factor_gcd_unit_upper(
    gi_interval span, double unit, double current_upper)
{
    fenv_t saved;
    double result = current_upper;
    mpq_t lower, upper, exact_unit, scale, lower_ratio, upper_ratio, bound;
    mpz_t first, last;
    unsigned long denominator;

    if (fegetenv(&saved) != 0) {
        return current_upper;
    }
    if (isnan(current_upper) || current_upper <= 0.0
        || gi_interval_is_empty(span)
        || !isfinite(span.lo) || !isfinite(span.hi)
        || !isfinite(unit) || unit == 0.0) {
        goto restore;
    }

    mpq_inits(lower, upper, exact_unit, scale, lower_ratio, upper_ratio, bound,
        (mpq_ptr)0);
    mpz_inits(first, last, (mpz_ptr)0);
    mpq_set_d(lower, span.lo);
    mpq_set_d(upper, span.hi);
    mpq_set_d(exact_unit, fabs(unit));
    /* Binary64 input dyadics and n<=16 bound these exact integers to <2156
       bits. No floating quotient or data-dependent unbounded search occurs. */
    for (denominator = 1; denominator <= 16; ++denominator) {
        mpq_set_ui(scale, denominator, 1);
        mpq_mul(lower_ratio, lower, scale);
        mpq_div(lower_ratio, lower_ratio, exact_unit);
        mpq_mul(upper_ratio, upper, scale);
        mpq_div(upper_ratio, upper_ratio, exact_unit);
        mpz_cdiv_q(first, mpq_numref(lower_ratio), mpq_denref(lower_ratio));
        mpz_fdiv_q(last, mpq_numref(upper_ratio), mpq_denref(upper_ratio));
        if (mpz_cmp(first, last) <= 0) {
            break;
        }
    }
    /* No hit among 1..16 implies every positive divisor is <=Q/17. */
    mpq_set_ui(scale, denominator, 1);
    mpq_div(bound, exact_unit, scale);
    {
        gi_interval demoted = nonnegative_rational_interval(bound);
        /* A nonpositive/NaN demotion cannot justify a tighter positive upper.
           Returning the caller bound also handles unsupported MPFR ranges. */
        if (demoted.hi > 0.0 && demoted.hi < result) {
            result = demoted.hi;
        }
    }
    mpz_clears(first, last, (mpz_ptr)0);
    mpq_clears(lower, upper, exact_unit, scale, lower_ratio, upper_ratio, bound,
        (mpq_ptr)0);
restore:
    if (fesetenv(&saved) != 0) {
        return current_upper;
    }
    return result;
}
