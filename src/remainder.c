/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#include "graphing/remainder.h"

#include <math.h>
#include <mpfr.h>

gi_interval gi_remainder_mod_point(double dividend, double divisor)
{
    double lo;
    double hi;
    mpfr_t dividend_value;
    mpfr_t modulus;
    mpfr_t quotient;
    mpfr_t product;
    mpfr_t remainder;

    if (!isfinite(dividend) || !isfinite(divisor) || divisor == 0.0) {
        return gi_interval_empty();
    }

    mpfr_inits2(
        GI_REMAINDER_MPFR_PRECISION,
        dividend_value,
        modulus,
        quotient,
        product,
        remainder,
        (mpfr_ptr)0);
    mpfr_set_d(dividend_value, dividend, MPFR_RNDN);
    mpfr_set_d(modulus, divisor, MPFR_RNDN);
    mpfr_abs(modulus, modulus, MPFR_RNDN);

    mpfr_div(quotient, dividend_value, modulus, MPFR_RNDD);
    mpfr_floor(quotient, quotient);
    mpfr_mul(product, quotient, modulus, MPFR_RNDN);
    mpfr_sub(remainder, dividend_value, product, MPFR_RNDN);

    lo = mpfr_get_d(remainder, MPFR_RNDD);
    hi = mpfr_get_d(remainder, MPFR_RNDU);
    if (lo == 0.0) {
        lo = 0.0;
    }
    if (hi == 0.0) {
        hi = 0.0;
    }

    mpfr_clears(
        dividend_value,
        modulus,
        quotient,
        product,
        remainder,
        (mpfr_ptr)0);
    return gi_interval_make(lo, hi);
}

gi_interval gi_remainder_fmod_point(double dividend, double divisor)
{
    double value;
    mpfr_t dividend_value;
    mpfr_t modulus;
    mpfr_t remainder;

    if (!isfinite(dividend) || !isfinite(divisor) || divisor == 0.0) {
        return gi_interval_empty();
    }

    mpfr_inits2(
        GI_REMAINDER_MPFR_PRECISION,
        dividend_value,
        modulus,
        remainder,
        (mpfr_ptr)0);
    mpfr_set_d(dividend_value, dividend, MPFR_RNDN);
    mpfr_set_d(modulus, divisor, MPFR_RNDN);
    mpfr_abs(modulus, modulus, MPFR_RNDN);
    mpfr_fmod(remainder, dividend_value, modulus, MPFR_RNDN);
    value = mpfr_get_d(remainder, MPFR_RNDN);
    if (value == 0.0) {
        value = copysign(0.0, dividend);
    }

    mpfr_clears(dividend_value, modulus, remainder, (mpfr_ptr)0);
    return gi_interval_point(value);
}
