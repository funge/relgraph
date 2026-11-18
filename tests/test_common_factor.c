/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#include "graphing/common_factor.h"

#include <assert.h>
#include <float.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <mpfr.h>
#include <math.h>

static void assert_interval(gi_interval value, double lo, double hi)
{
    assert(!gi_interval_is_empty(value));
    assert(value.lo == lo);
    assert(value.hi == hi);
}

static void test_integer_fraction_and_sign_values(void)
{
    assert_interval(gi_common_factor_gcd_point(12.0, 18.0), 6.0, 6.0);
    assert_interval(gi_common_factor_lcm_point(12.0, 18.0), 36.0, 36.0);
    assert_interval(gi_common_factor_gcd_point(1.5, 0.5), 0.5, 0.5);
    assert_interval(gi_common_factor_lcm_point(1.5, 0.5), 1.5, 1.5);
    assert_interval(gi_common_factor_gcd_point(-12.0, 18.0), 6.0, 6.0);
    assert_interval(gi_common_factor_lcm_point(-12.0, 18.0), 36.0, 36.0);
}

static void test_zero_and_subnormal_values(void)
{
    gi_interval gcd_zero = gi_common_factor_gcd_point(-0.0, 18.0);
    gi_interval lcm_zero = gi_common_factor_lcm_point(-0.0, -18.0);

    assert_interval(gcd_zero, 18.0, 18.0);
    assert_interval(lcm_zero, 0.0, 0.0);
    assert(!signbit(lcm_zero.lo));
    assert(!signbit(lcm_zero.hi));
    assert_interval(
        gi_common_factor_gcd_point(DBL_TRUE_MIN, 2.0 * DBL_TRUE_MIN),
        DBL_TRUE_MIN,
        DBL_TRUE_MIN);
    assert_interval(
        gi_common_factor_lcm_point(DBL_TRUE_MIN, 2.0 * DBL_TRUE_MIN),
        2.0 * DBL_TRUE_MIN,
        2.0 * DBL_TRUE_MIN);
}

static void test_outward_nonrepresentable_and_overflow_values(void)
{
    gi_interval nonrepresentable = gi_common_factor_lcm_point(
        9007199254740991.0,
        9007199254740989.0);
    gi_interval overflow = gi_common_factor_lcm_point(
        0x1p1023,
        0x1.8p1023);

    assert_interval(
        nonrepresentable,
        0x1.ffffffffffffcp+105,
        0x1.ffffffffffffdp+105);
    assert_interval(overflow, DBL_MAX, INFINITY);
}

static void test_nonfinite_values_are_empty(void)
{
    assert(gi_interval_is_empty(gi_common_factor_gcd_point(INFINITY, 1.0)));
    assert(gi_interval_is_empty(gi_common_factor_lcm_point(1.0, NAN)));
}

static uint64_t bits(double value)
{
    uint64_t result;
    memcpy(&result, &value, sizeof(result));
    return result;
}

static double from_bits(uint64_t value)
{
    double result;
    memcpy(&result, &value, sizeof(result));
    return result;
}

static void test_fixed_unit_sections_and_outward_bounds(void)
{
    assert(gi_common_factor_gcd_unit_upper(gi_interval_make(1.25, 1.3125),
        1.0, 1.0) == 0.25);
    assert(gi_common_factor_gcd_unit_upper(gi_interval_make(-1.3125, -1.25),
        -1.0, 1.0) == 0.25);
    assert(gi_common_factor_gcd_unit_upper(gi_interval_make(17.0/16.0, 19.0/16.0),
        1.0, 1.0) == 0x1.5555555555556p-3);
    assert(gi_common_factor_gcd_unit_upper(
        gi_interval_make(nextafter(1.25, INFINITY), 1.3125),
        1.0, 1.0) == 0x1.2492492492493p-3);
    assert(gi_common_factor_gcd_unit_upper(
        gi_interval_point(nextafter(0.5, INFINITY)),
        1.0, 1.0) == 0x1.e1e1e1e1e1e1fp-5);
    assert(gi_common_factor_gcd_unit_upper(gi_interval_make(-1.0, 1.0),
        -4.0, 4.0) == 4.0);
    assert(gi_common_factor_gcd_unit_upper(gi_interval_point(2.0),
        1.0, 1.0) == 1.0);
    assert(gi_common_factor_gcd_unit_upper(
        gi_interval_point(nextafter(0.5, INFINITY)), 1.0, 0.05) == 0.05);
    assert(gi_common_factor_gcd_unit_upper(gi_interval_make(1.25, 1.3125),
        1.0, INFINITY) == 0.25);
}

static void test_fixed_unit_fallback_bits_and_extreme_ratios(void)
{
    const double nan_bound = from_bits(UINT64_C(0x7ff8000000000042));
    const double signaling_bound = from_bits(UINT64_C(0x7ff0000000000042));
    const gi_interval valid = {1.0, 2.0};
    const gi_interval reversed = {2.0, 1.0};
    assert(bits(gi_common_factor_gcd_unit_upper(valid, 1.0, nan_bound))
        == bits(nan_bound));
    assert(bits(gi_common_factor_gcd_unit_upper(valid, 1.0, signaling_bound))
        == bits(signaling_bound));
    assert(bits(gi_common_factor_gcd_unit_upper(valid, 1.0, -0.0)) == bits(-0.0));
    assert(bits(gi_common_factor_gcd_unit_upper(valid, 1.0, -2.0)) == bits(-2.0));
    assert(bits(gi_common_factor_gcd_unit_upper(valid, -0.0, 7.0)) == bits(7.0));
    assert(bits(gi_common_factor_gcd_unit_upper(valid, INFINITY, 7.0)) == bits(7.0));
    assert(bits(gi_common_factor_gcd_unit_upper(valid, NAN, 7.0)) == bits(7.0));
    assert(bits(gi_common_factor_gcd_unit_upper(reversed, 1.0, 7.0)) == bits(7.0));
    assert(bits(gi_common_factor_gcd_unit_upper(gi_interval_empty(), 1.0, 7.0)) == bits(7.0));
    assert(bits(gi_common_factor_gcd_unit_upper(gi_interval_whole(), 1.0, 7.0)) == bits(7.0));
    assert(gi_common_factor_gcd_unit_upper(gi_interval_point(DBL_MAX),
        DBL_TRUE_MIN, DBL_TRUE_MIN) == DBL_TRUE_MIN);
    assert(gi_common_factor_gcd_unit_upper(gi_interval_point(DBL_TRUE_MIN),
        DBL_MAX, DBL_TRUE_MIN) == DBL_TRUE_MIN);
    assert(gi_common_factor_gcd_unit_upper(
        gi_interval_make(DBL_TRUE_MIN, 2.0*DBL_TRUE_MIN),
        DBL_TRUE_MIN, DBL_TRUE_MIN) == DBL_TRUE_MIN);
}

static void test_fixed_unit_preserves_numeric_context(void)
{
    fenv_t saved;
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    mpfr_prec_t precision = mpfr_get_default_prec();
    mpfr_rnd_t rounding = mpfr_get_default_rounding_mode();
    mpfr_exp_t emin = mpfr_get_emin();
    mpfr_exp_t emax = mpfr_get_emax();
    assert(fegetenv(&saved) == 0);
    mpfr_set_default_prec(137);
    mpfr_set_default_rounding_mode(MPFR_RNDZ);
    for (size_t i = 0; i < sizeof(modes)/sizeof(modes[0]); ++i) {
        assert(fesetround(modes[i]) == 0);
        feclearexcept(FE_ALL_EXCEPT);
        feraiseexcept(FE_INVALID | FE_DIVBYZERO);
        int flags = fetestexcept(FE_ALL_EXCEPT);
        assert(gi_common_factor_gcd_unit_upper(
            gi_interval_make(17.0/16.0, 19.0/16.0), 1.0, 1.0)
            == 0x1.5555555555556p-3);
        assert(fegetround() == modes[i]);
        assert(fetestexcept(FE_ALL_EXCEPT) == flags);
        assert(gi_common_factor_gcd_unit_upper(gi_interval_whole(), 0.0, 7.0) == 7.0);
        assert(fegetround() == modes[i]);
        assert(fetestexcept(FE_ALL_EXCEPT) == flags);
        {
            double signaling = from_bits(UINT64_C(0x7ff0000000000042));
            assert(bits(gi_common_factor_gcd_unit_upper(
                gi_interval_make(1.0, 2.0), 1.0, signaling)) == bits(signaling));
            assert(fegetround() == modes[i]);
            assert(fetestexcept(FE_ALL_EXCEPT) == flags);
            feclearexcept(FE_ALL_EXCEPT);
            assert(fetestexcept(FE_ALL_EXCEPT) == 0);
            assert(bits(gi_common_factor_gcd_unit_upper(
                gi_interval_make(1.0, 2.0), 1.0, signaling)) == bits(signaling));
            assert(fegetround() == modes[i]);
            assert(fetestexcept(FE_ALL_EXCEPT) == 0);
        }
        assert(mpfr_get_default_prec() == 137);
        assert(mpfr_get_default_rounding_mode() == MPFR_RNDZ);
        assert(mpfr_get_emin() == emin && mpfr_get_emax() == emax);
    }
    assert(mpfr_set_emax(128) == 0);
    assert(gi_common_factor_gcd_unit_upper(gi_interval_point(DBL_TRUE_MIN),
        DBL_MAX, DBL_MAX) == DBL_MAX);
    assert(mpfr_get_emax() == 128);
    assert(mpfr_set_emax(emax) == 0);
    mpfr_set_default_prec(precision);
    mpfr_set_default_rounding_mode(rounding);
    assert(fesetenv(&saved) == 0);
}

/* Batch black-box hook for the independent exact interval oracle. Ordinary
   invocation still runs every native assertion below. Raw binary64 bits avoid
   decimal parsing or process rounding being mistaken for input identity. */
static int unit_bound_probe(void)
{
    uint64_t lo, hi, unit, upper;
    int fields;
    while ((fields = scanf("%" SCNx64 " %" SCNx64 " %" SCNx64 " %" SCNx64,
            &lo, &hi, &unit, &upper)) == 4) {
        gi_interval span = {from_bits(lo), from_bits(hi)};
        double result = gi_common_factor_gcd_unit_upper(
            span, from_bits(unit), from_bits(upper));
        printf("%016" PRIx64 "\n", bits(result));
    }
    return fields == EOF ? 0 : 2;
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--unit-bound-probe") == 0) {
        return unit_bound_probe();
    }
    assert(argc == 1);
    test_fixed_unit_sections_and_outward_bounds();
    test_fixed_unit_fallback_bits_and_extreme_ratios();
    test_fixed_unit_preserves_numeric_context();
    test_integer_fraction_and_sign_values();
    test_zero_and_subnormal_values();
    test_outward_nonrepresentable_and_overflow_values();
    test_nonfinite_values_are_empty();
}
