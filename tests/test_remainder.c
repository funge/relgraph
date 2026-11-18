/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#include "graphing/remainder.h"

#include <assert.h>
#include <float.h>
#include <math.h>

static void assert_interval(gi_interval value, double lo, double hi)
{
    assert(!gi_interval_is_empty(value));
    assert(value.lo == lo);
    assert(value.hi == hi);
}

static void test_sign_and_divisor_conventions(void)
{
    assert_interval(gi_remainder_mod_point(5.0, 3.0), 2.0, 2.0);
    assert_interval(gi_remainder_mod_point(-5.0, 3.0), 1.0, 1.0);
    assert_interval(gi_remainder_mod_point(5.0, -3.0), 2.0, 2.0);
    assert_interval(gi_remainder_mod_point(-5.0, -3.0), 1.0, 1.0);
}

static void test_exact_multiples_and_signed_zero(void)
{
    gi_interval positive = gi_remainder_mod_point(6.0, 3.0);
    gi_interval negative = gi_remainder_mod_point(-6.0, 3.0);
    gi_interval signed_zero = gi_remainder_mod_point(-0.0, -3.0);

    assert_interval(positive, 0.0, 0.0);
    assert_interval(negative, 0.0, 0.0);
    assert_interval(signed_zero, 0.0, 0.0);
    assert(!signbit(positive.lo) && !signbit(positive.hi));
    assert(!signbit(negative.lo) && !signbit(negative.hi));
    assert(!signbit(signed_zero.lo) && !signbit(signed_zero.hi));
}

static void test_inexact_result_is_outward(void)
{
    const double dividend = -0x1.2233c483f679ep-68;
    const double divisor = 0x1.96ba36d164da6p+40;
    gi_interval result = gi_remainder_mod_point(dividend, divisor);

    assert_interval(
        result,
        0x1.96ba36d164da5p+40,
        0x1.96ba36d164da6p+40);
}

static void test_extreme_binary64_quotient_is_retained_exactly(void)
{
    gi_interval positive = gi_remainder_mod_point(DBL_MAX, DBL_TRUE_MIN);
    gi_interval negative = gi_remainder_mod_point(-DBL_MAX, DBL_TRUE_MIN);

    assert_interval(positive, 0.0, 0.0);
    assert_interval(negative, 0.0, 0.0);
}

static void test_invalid_point_domain_is_empty(void)
{
    assert(gi_interval_is_empty(gi_remainder_mod_point(1.0, 0.0)));
    assert(gi_interval_is_empty(gi_remainder_mod_point(1.0, -0.0)));
    assert(gi_interval_is_empty(gi_remainder_mod_point(INFINITY, 2.0)));
    assert(gi_interval_is_empty(gi_remainder_mod_point(1.0, INFINITY)));
}

static void test_fmod_sign_and_divisor_conventions(void)
{
    assert_interval(gi_remainder_fmod_point(5.0, 3.0), 2.0, 2.0);
    assert_interval(gi_remainder_fmod_point(-5.0, 3.0), -2.0, -2.0);
    assert_interval(gi_remainder_fmod_point(5.0, -3.0), 2.0, 2.0);
    assert_interval(gi_remainder_fmod_point(-5.0, -3.0), -2.0, -2.0);
}

static void test_fmod_exact_signed_zero(void)
{
    gi_interval positive = gi_remainder_fmod_point(6.0, 3.0);
    gi_interval negative = gi_remainder_fmod_point(-6.0, 3.0);
    gi_interval signed_zero = gi_remainder_fmod_point(-0.0, -3.0);

    assert_interval(positive, 0.0, 0.0);
    assert_interval(negative, 0.0, 0.0);
    assert_interval(signed_zero, 0.0, 0.0);
    assert(!signbit(positive.lo) && !signbit(positive.hi));
    assert(signbit(negative.lo) && signbit(negative.hi));
    assert(signbit(signed_zero.lo) && signbit(signed_zero.hi));
}

static void test_fmod_subnormal_and_extreme_quotient(void)
{
    gi_interval subnormal = gi_remainder_fmod_point(
        DBL_TRUE_MIN,
        2.0 * DBL_TRUE_MIN);
    gi_interval negative_subnormal = gi_remainder_fmod_point(
        -DBL_TRUE_MIN,
        2.0 * DBL_TRUE_MIN);
    gi_interval positive = gi_remainder_fmod_point(DBL_MAX, DBL_TRUE_MIN);
    gi_interval negative = gi_remainder_fmod_point(-DBL_MAX, DBL_TRUE_MIN);

    assert_interval(subnormal, DBL_TRUE_MIN, DBL_TRUE_MIN);
    assert_interval(negative_subnormal, -DBL_TRUE_MIN, -DBL_TRUE_MIN);
    assert_interval(positive, 0.0, 0.0);
    assert_interval(negative, 0.0, 0.0);
    assert(signbit(negative.lo) && signbit(negative.hi));
}

static void test_fmod_invalid_point_domain_is_empty(void)
{
    assert(gi_interval_is_empty(gi_remainder_fmod_point(1.0, 0.0)));
    assert(gi_interval_is_empty(gi_remainder_fmod_point(1.0, -0.0)));
    assert(gi_interval_is_empty(gi_remainder_fmod_point(INFINITY, 2.0)));
    assert(gi_interval_is_empty(gi_remainder_fmod_point(1.0, INFINITY)));
}

int main(void)
{
    test_sign_and_divisor_conventions();
    test_exact_multiples_and_signed_zero();
    test_inexact_result_is_outward();
    test_extreme_binary64_quotient_is_retained_exactly();
    test_invalid_point_domain_is_empty();
    test_fmod_sign_and_divisor_conventions();
    test_fmod_exact_signed_zero();
    test_fmod_subnormal_and_extreme_quotient();
    test_fmod_invalid_point_domain_is_empty();
}
