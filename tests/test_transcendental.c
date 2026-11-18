/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#include "graphing/transcendental.h"

#include <assert.h>
#include <float.h>
#include <fenv.h>
#include <math.h>
#include <mpfr.h>

enum {
    TEST_MPFR_PRECISION = 256
};

static double test_pi(void)
{
    return acos(-1.0);
}

static void assert_contains(gi_interval x, double value)
{
    assert(!gi_interval_is_empty(x));
    assert(x.lo <= value);
    assert(value <= x.hi);
}

static void assert_same_double(double actual, double expected)
{
    assert(actual == expected);
    if (actual == 0.0) {
        assert(signbit(actual) == signbit(expected));
    }
}

static void test_point_sin_cos_match_directed_mpfr(void)
{
    const double pi = test_pi();
    const double values[] = {
        0.0,
        -0.0,
        DBL_TRUE_MIN,
        -DBL_TRUE_MIN,
        1.0,
        -1.0,
        nextafter(pi / 2.0, -INFINITY),
        pi / 2.0,
        nextafter(pi / 2.0, INFINITY),
        pi,
        -pi,
        0x1p40,
        -0x1p40,
        nextafter(0x1p40, -INFINITY),
        nextafter(0x1p40, INFINITY),
        0x1p40 + 1.0,
        -0x1p40 - 1.0,
        0x1p100,
        -0x1p100,
        DBL_MAX,
        -DBL_MAX,
    };
    mpfr_t argument;
    mpfr_t directed;

    mpfr_init2(argument, TEST_MPFR_PRECISION);
    mpfr_init2(directed, TEST_MPFR_PRECISION);
    for (size_t index = 0;
         index < sizeof(values) / sizeof(values[0]);
         ++index) {
        const gi_interval point = gi_interval_point(values[index]);
        mpfr_set_d(argument, values[index], MPFR_RNDN);

        mpfr_sin(directed, argument, MPFR_RNDD);
        const double sin_lo = mpfr_get_d(directed, MPFR_RNDD);
        mpfr_sin(directed, argument, MPFR_RNDU);
        const double sin_hi = mpfr_get_d(directed, MPFR_RNDU);
        const gi_interval sine = gi_trans_sin(point);
        assert_same_double(sine.lo, sin_lo);
        assert_same_double(sine.hi, sin_hi);

        mpfr_cos(directed, argument, MPFR_RNDD);
        const double cos_lo = mpfr_get_d(directed, MPFR_RNDD);
        mpfr_cos(directed, argument, MPFR_RNDU);
        const double cos_hi = mpfr_get_d(directed, MPFR_RNDU);
        const gi_interval cosine = gi_trans_cos(point);
        assert_same_double(cosine.lo, cos_lo);
        assert_same_double(cosine.hi, cos_hi);
    }
    mpfr_clear(argument);
    mpfr_clear(directed);
}

static void test_sin_point_zero(void)
{
    gi_interval result = gi_trans_sin(gi_interval_point(0.0));

    assert(result.lo == 0.0);
    assert(result.hi == 0.0);
}

static void test_sin_point_one(void)
{
    gi_interval result = gi_trans_sin(gi_interval_point(1.0));

    assert_contains(result, sin(1.0));
    assert(result.hi - result.lo <= 0x1p-50);
}

static void test_sin_interval_with_maximum(void)
{
    gi_interval result = gi_trans_sin(gi_interval_make(1.0, 2.0));

    assert(result.hi == 1.0);
    assert(result.lo > 0.8);
}

static void test_sin_interval_with_minimum(void)
{
    gi_interval result = gi_trans_sin(gi_interval_make(-2.0, -1.0));

    assert(result.lo == -1.0);
    assert(result.hi < -0.8);
}

static void test_sin_large_argument_is_conservative(void)
{
    gi_interval result = gi_trans_sin(gi_interval_point(0x1p41));

    mpfr_t argument, lower, upper;
    mpfr_inits2(1024, argument, lower, upper, (mpfr_ptr)0);
    mpfr_set_d(argument, 0x1p41, MPFR_RNDN);
    mpfr_sin(lower, argument, MPFR_RNDD);
    mpfr_sin(upper, argument, MPFR_RNDU);
    assert(mpfr_cmp_d(lower, result.lo) >= 0);
    assert(mpfr_cmp_d(upper, result.hi) <= 0);
    assert(result.hi - result.lo <= 0x1p-50);
    mpfr_clears(argument, lower, upper, (mpfr_ptr)0);
}

static void test_cos_point_zero(void)
{
    gi_interval result = gi_trans_cos(gi_interval_point(0.0));

    assert(result.lo == 1.0);
    assert(result.hi == 1.0);
}

static void test_cos_interval_with_minimum(void)
{
    gi_interval result = gi_trans_cos(gi_interval_make(3.0, 4.0));

    assert(result.lo == -1.0);
    assert(result.hi < -0.6);
}

static void test_cbrt_point_239_is_outward_rounded(void)
{
    gi_interval result = gi_trans_cbrt(gi_interval_point(239.0));
    mpfr_t argument;
    mpfr_t root;

    mpfr_init2(argument, 256);
    mpfr_init2(root, 256);
    mpfr_set_ui(argument, 239, MPFR_RNDN);
    mpfr_cbrt(root, argument, MPFR_RNDN);

    assert(result.lo < result.hi);
    assert(mpfr_cmp_d(root, result.lo) >= 0);
    assert(mpfr_cmp_d(root, result.hi) <= 0);

    mpfr_clear(argument);
    mpfr_clear(root);
}

static void test_pi_multiple_brackets_irrational_boundary(void)
{
    gi_interval half_pi = gi_trans_pi_multiple(1, 2);
    gi_interval negative_pi = gi_trans_pi_multiple(-1, 1);
    double pi = test_pi();

    assert_contains(half_pi, pi / 2.0);
    assert(half_pi.lo < half_pi.hi);
    assert_contains(negative_pi, -pi);
    assert(negative_pi.lo < negative_pi.hi);
}

static void test_positive_integer_base_power_is_monotone_and_outward(void)
{
    gi_interval result = gi_trans_pow_positive_integer_base(
        2,
        gi_interval_make(-2.0, 3.0));

    assert(result.lo == 0.25);
    assert(result.hi == 8.0);
}

static void test_positive_integer_base_power_point_brackets_mpfr(void)
{
    gi_interval result = gi_trans_pow_positive_integer_base(
        2,
        gi_interval_point(0.5));
    mpfr_t base;
    mpfr_t exponent;
    mpfr_t exact;

    mpfr_inits2(256, base, exponent, exact, (mpfr_ptr)0);
    mpfr_set_ui(base, 2, MPFR_RNDN);
    mpfr_set_d(exponent, 0.5, MPFR_RNDN);
    mpfr_pow(exact, base, exponent, MPFR_RNDN);

    assert(result.lo < result.hi);
    assert(mpfr_cmp_d(exact, result.lo) >= 0);
    assert(mpfr_cmp_d(exact, result.hi) <= 0);
    mpfr_clears(base, exponent, exact, (mpfr_ptr)0);
}

static void test_positive_integer_base_power_boundaries_are_conservative(void)
{
    double smallest = nextafter(0.0, INFINITY);
    gi_interval one = gi_trans_pow_positive_integer_base(
        1,
        gi_interval_make(-INFINITY, INFINITY));
    gi_interval overflow = gi_trans_pow_positive_integer_base(
        2,
        gi_interval_point(1024.0));
    gi_interval underflow = gi_trans_pow_positive_integer_base(
        2,
        gi_interval_point(-1075.0));
    gi_interval unbounded = gi_trans_pow_positive_integer_base(
        2,
        gi_interval_make(-INFINITY, 3.0));
    gi_interval invalid = gi_trans_pow_positive_integer_base(
        0,
        gi_interval_point(2.0));

    assert(one.lo == 1.0 && one.hi == 1.0);
    assert(overflow.lo == DBL_MAX && overflow.hi == INFINITY);
    assert(underflow.lo == 0.0 && underflow.hi == smallest);
    assert(unbounded.lo == 0.0 && unbounded.hi == INFINITY);
    assert(invalid.lo == -INFINITY && invalid.hi == INFINITY);
    assert(gi_interval_is_empty(gi_trans_pow_positive_integer_base(
        2,
        gi_interval_empty())));
}

static void test_atan_is_monotone_and_outward_rounded(void)
{
    gi_interval result = gi_trans_atan(gi_interval_make(-4.0, -0.25));
    mpfr_t argument;
    mpfr_t exact;

    mpfr_init2(argument, 256);
    mpfr_init2(exact, 256);
    mpfr_set_d(argument, -4.0, MPFR_RNDN);
    mpfr_atan(exact, argument, MPFR_RNDN);
    assert(mpfr_cmp_d(exact, result.lo) >= 0);
    mpfr_set_d(argument, -0.25, MPFR_RNDN);
    mpfr_atan(exact, argument, MPFR_RNDN);
    assert(mpfr_cmp_d(exact, result.hi) <= 0);
    assert(result.lo < result.hi);

    mpfr_clear(argument);
    mpfr_clear(exact);
}

static void test_atan_zero_is_exact(void)
{
    gi_interval result = gi_trans_atan(gi_interval_point(-0.0));

    assert(result.lo == 0.0);
    assert(result.hi == 0.0);
    assert(!signbit(result.lo));
    assert(!signbit(result.hi));
}

static void test_atan_point_one_retains_outward_bracket(void)
{
    gi_interval result = gi_trans_atan(gi_interval_point(1.0));
    mpfr_t argument;
    mpfr_t exact;

    mpfr_init2(argument, 256);
    mpfr_init2(exact, 256);
    mpfr_set_ui(argument, 1, MPFR_RNDN);
    mpfr_atan(exact, argument, MPFR_RNDN);

    assert(result.lo < result.hi);
    assert(mpfr_cmp_d(exact, result.lo) >= 0);
    assert(mpfr_cmp_d(exact, result.hi) <= 0);

    mpfr_clear(argument);
    mpfr_clear(exact);
}

static void test_log2_is_monotone_and_outward_rounded(void)
{
    gi_interval result = gi_trans_log2(gi_interval_make(0.25, 8.0));

    assert(result.lo == -2.0);
    assert(result.hi == 3.0);
}

static void test_log2_point_three_retains_outward_bracket(void)
{
    gi_interval result = gi_trans_log2(gi_interval_point(3.0));
    mpfr_t argument;
    mpfr_t exact;

    mpfr_inits2(256, argument, exact, (mpfr_ptr)0);
    mpfr_set_ui(argument, 3, MPFR_RNDN);
    mpfr_log2(exact, argument, MPFR_RNDN);

    assert(result.lo < result.hi);
    assert(mpfr_cmp_d(exact, result.lo) >= 0);
    assert(mpfr_cmp_d(exact, result.hi) <= 0);
    mpfr_clears(argument, exact, (mpfr_ptr)0);
}

static void test_log2_domain_boundaries(void)
{
    const double smallest = nextafter(0.0, INFINITY);
    gi_interval crossing = gi_trans_log2(gi_interval_make(-1.0, 8.0));
    gi_interval subnormal = gi_trans_log2(gi_interval_point(smallest));
    gi_interval infinite = gi_trans_log2(gi_interval_point(INFINITY));

    assert(crossing.lo == -INFINITY);
    assert(crossing.hi == 3.0);
    assert(subnormal.lo == -1074.0 && subnormal.hi == -1074.0);
    assert(infinite.lo == INFINITY && infinite.hi == INFINITY);
    assert(gi_interval_is_empty(gi_trans_log2(gi_interval_point(0.0))));
    assert(gi_interval_is_empty(gi_trans_log2(gi_interval_make(-2.0, -1.0))));
    assert(gi_interval_is_empty(gi_trans_log2(gi_interval_empty())));
}

static void test_point_atan2_matches_directed_mpfr(void)
{
    const double values[] = {
        -INFINITY, -DBL_MAX, -0x1p500, -0x1.0000000000001p0, -1.0,
        -0x1.fffffffffffffp-1, -0x1p-500, -DBL_MIN, -DBL_TRUE_MIN, -0.0,
        0.0, DBL_TRUE_MIN, DBL_MIN, 0x1p-500, 0x1.fffffffffffffp-1,
        1.0, 0x1.0000000000001p0, 0x1p500, DBL_MAX, INFINITY
    };
    mpfr_t x;
    mpfr_t y;
    mpfr_t directed;
    mpfr_inits2(TEST_MPFR_PRECISION, x, y, directed, (mpfr_ptr)0);
    for (size_t xi = 0; xi < sizeof(values) / sizeof(values[0]); ++xi) {
        for (size_t yi = 0; yi < sizeof(values) / sizeof(values[0]); ++yi) {
            const double xv = values[xi];
            const double yv = values[yi];
            const gi_interval actual = gi_trans_atan2(
                gi_interval_point(yv), gi_interval_point(xv));
            if (xv == 0.0 && yv == 0.0) {
                assert(gi_interval_is_empty(actual));
                continue;
            }
            mpfr_set_d(x, xv, MPFR_RNDN);
            mpfr_set_d(y, yv, MPFR_RNDN);
            /* Tupper 3.2.22 includes +pi on the negative axis, for either
             * signed zero. All other points retain directed MPFR evaluation. */
            if (xv < 0.0 && yv == 0.0) {
                mpfr_const_pi(directed, MPFR_RNDD);
            } else {
                mpfr_atan2(directed, y, x, MPFR_RNDD);
            }
            double expected_lo = mpfr_get_d(directed, MPFR_RNDD);
            if (xv < 0.0 && yv == 0.0) {
                mpfr_const_pi(directed, MPFR_RNDU);
            } else {
                mpfr_atan2(directed, y, x, MPFR_RNDU);
            }
            double expected_hi = mpfr_get_d(directed, MPFR_RNDU);
            if (expected_lo == 0.0) {
                expected_lo = 0.0;
            }
            if (expected_hi == 0.0) {
                expected_hi = 0.0;
            }
            assert_same_double(actual.lo, expected_lo);
            assert_same_double(actual.hi, expected_hi);
        }
    }
    /* Opposite signed-zero endpoints still describe one geometric point. */
    const gi_interval mixed = gi_trans_atan2(
        gi_interval_make(-0.0, 0.0), gi_interval_point(-1.0));
    const gi_interval negative_axis = gi_trans_atan2(
        gi_interval_point(0.0), gi_interval_point(-1.0));
    assert_same_double(mixed.lo, negative_axis.lo);
    assert_same_double(mixed.hi, negative_axis.hi);
    mpfr_clears(x, y, directed, (mpfr_ptr)0);
}

static void test_atan2_axes_and_argument_order(void)
{
    gi_interval first_quadrant = gi_trans_atan2(
        gi_interval_point(2.0),
        gi_interval_point(1.0));
    gi_interval second_quadrant = gi_trans_atan2(
        gi_interval_point(2.0),
        gi_interval_point(-1.0));
    gi_interval negative_axis = gi_trans_atan2(
        gi_interval_point(-0.0),
        gi_interval_point(-1.0));

    assert_contains(first_quadrant, atan2(2.0, 1.0));
    assert_contains(second_quadrant, atan2(2.0, -1.0));
    assert(first_quadrant.hi < second_quadrant.lo);
    assert_contains(negative_axis, test_pi());
    assert(negative_axis.lo > 0.0);
}

static void test_atan2_origin_is_empty(void)
{
    gi_interval result = gi_trans_atan2(
        gi_interval_point(0.0),
        gi_interval_point(0.0));

    assert(gi_interval_is_empty(result));
}

static void test_atan2_partial_origin_keeps_live_range(void)
{
    gi_interval result = gi_trans_atan2(
        gi_interval_make(0.0, 1.0),
        gi_interval_make(0.0, 1.0));

    assert_contains(result, 0.0);
    assert_contains(result, test_pi() / 2.0);
    assert(result.lo == 0.0);
}

static void test_atan2_branch_cut_uses_full_turn(void)
{
    gi_interval result = gi_trans_atan2(
        gi_interval_make(-1.0, 0.0),
        gi_interval_make(-2.0, -1.0));

    assert(result.lo < -test_pi());
    assert(result.hi > test_pi());
}

static void test_tan_regular_branch_is_bounded(void)
{
    gi_interval result = gi_trans_tan(gi_interval_make(3.0, 3.2));
    gi_bool_interval defined = gi_trans_tan_defined(gi_interval_make(3.0, 3.2));

    assert_contains(result, tan(3.0));
    assert_contains(result, tan(3.2));
    assert(result.lo > -0.2);
    assert(result.hi < 0.1);
    assert(defined.lo);
    assert(defined.hi);
}

static void test_tan_interval_crossing_pole_is_unbounded(void)
{
    gi_interval result = gi_trans_tan(gi_interval_make(1.56, 1.58));
    gi_bool_interval defined = gi_trans_tan_defined(gi_interval_make(1.56, 1.58));

    assert(result.lo == -INFINITY);
    assert(result.hi == INFINITY);
    assert(!defined.lo);
    assert(defined.hi);
}

static void test_elementary_unary_directed_bounds(void)
{
    struct unary_case {
        gi_interval (*bound)(gi_interval);
        int (*oracle)(mpfr_ptr, mpfr_srcptr, mpfr_rnd_t);
        double lower;
        double upper;
        bool open;
    };
    const struct unary_case cases[] = {
        {gi_trans_exp, mpfr_exp, -INFINITY, INFINITY, false},
        {gi_trans_ln, mpfr_log, 0, INFINITY, true},
        {gi_trans_log10, mpfr_log10, 0, INFINITY, true},
        {gi_trans_sinh, mpfr_sinh, -INFINITY, INFINITY, false},
        {gi_trans_cosh, mpfr_cosh, -INFINITY, INFINITY, false},
        {gi_trans_tanh, mpfr_tanh, -INFINITY, INFINITY, false},
        {gi_trans_asin, mpfr_asin, -1, 1, false},
        {gi_trans_acos, mpfr_acos, -1, 1, false},
        {gi_trans_asinh, mpfr_asinh, -INFINITY, INFINITY, false},
        {gi_trans_acosh, mpfr_acosh, 1, INFINITY, false},
        {gi_trans_atanh, mpfr_atanh, -1, 1, true},
    };
    const double points[] = {-DBL_MAX, -1000, -2, -1, nextafter(-1, 0),
        -0.5, -DBL_TRUE_MIN, 0, DBL_TRUE_MIN, 0.25, 0.5, nextafter(1, 0),
        1, nextafter(1, INFINITY), 2, 1000, DBL_MAX};
    mpfr_t input;
    mpfr_t lower;
    mpfr_t upper;
    mpfr_inits2(512, input, lower, upper, (mpfr_ptr)0);
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        const struct unary_case c = cases[i];
        assert(gi_interval_is_empty(c.bound(gi_interval_empty())));
        for (size_t j = 0; j < sizeof points / sizeof points[0]; ++j) {
            const double x = points[j];
            gi_interval result = c.bound(gi_interval_point(x));
            if (x < c.lower || x > c.upper || (c.open && (x == c.lower || x == c.upper))) {
                assert(gi_interval_is_empty(result));
                continue;
            }
            mpfr_set_d(input, x, MPFR_RNDN);
            c.oracle(lower, input, MPFR_RNDD);
            c.oracle(upper, input, MPFR_RNDU);
            assert(!gi_interval_is_empty(result));
            assert(mpfr_cmp_d(lower, result.lo) >= 0);
            assert(mpfr_cmp_d(upper, result.hi) <= 0);
        }
    }
    mpfr_clears(input, lower, upper, (mpfr_ptr)0);
    gi_interval result = gi_trans_cosh(gi_interval_make(-2, 1));
    assert(result.lo == 1);
    assert(result.hi >= cosh(2));
    result = gi_trans_acos(gi_interval_make(-2, 2));
    assert(result.lo == 0 && result.hi >= test_pi());
    result = gi_trans_atanh(gi_interval_make(-2, 2));
    assert(result.lo == -INFINITY && result.hi == INFINITY);
    result = gi_trans_exp(gi_interval_point(1000));
    assert(result.lo == DBL_MAX && result.hi == INFINITY);
    result = gi_trans_exp(gi_interval_point(-1000));
    assert(result.lo == 0 && result.hi == DBL_TRUE_MIN);
}


/* Extracted from the native cache suite: no C++ evaluator/cache is an oracle.
 * Use four times the kernel precision and exact full-width integer inputs. */
static void check_pi_multiple_independent(intmax_t n, intmax_t d)
{
    const gi_interval result = gi_trans_pi_multiple(n, d);
    if (d <= 0) {
        assert(gi_interval_is_empty(result));
        return;
    }
    mpfr_t pi, factor, divisor, lower, upper;
    mpfr_inits2(1024, pi, factor, divisor, lower, upper, (mpfr_ptr)0);
    mpfr_set_sj(factor, n, MPFR_RNDN);
    mpfr_set_sj(divisor, d, MPFR_RNDN);
    mpfr_const_pi(pi, n < 0 ? MPFR_RNDU : MPFR_RNDD);
    mpfr_mul(lower, pi, factor, MPFR_RNDD);
    mpfr_div(lower, lower, divisor, MPFR_RNDD);
    mpfr_const_pi(pi, n < 0 ? MPFR_RNDD : MPFR_RNDU);
    mpfr_mul(upper, pi, factor, MPFR_RNDU);
    mpfr_div(upper, upper, divisor, MPFR_RNDU);
    assert(!gi_interval_is_empty(result));
    assert(mpfr_cmp_d(lower, result.lo) >= 0);
    assert(mpfr_cmp_d(upper, result.hi) <= 0);
    mpfr_clears(pi, factor, divisor, lower, upper, (mpfr_ptr)0);
}

static void check_trig_independent(gi_interval input)
{
    const gi_interval results[] = {gi_trans_sin(input), gi_trans_cos(input)};
    mpfr_t argument, value;
    mpfr_inits2(1024, argument, value, (mpfr_ptr)0);
    const double samples[] = {input.lo, input.lo / 2 + input.hi / 2, input.hi};
    for (size_t op = 0; op < 2; ++op) {
        assert(!gi_interval_is_empty(results[op]));
        for (size_t j = 0; j < 3; ++j) {
            if (samples[j] < input.lo || samples[j] > input.hi) continue;
            mpfr_set_d(argument, samples[j], MPFR_RNDN);
            const mpfr_rnd_t directions[] = {MPFR_RNDD, MPFR_RNDU};
            for (size_t k = 0; k < 2; ++k) {
                if (op == 0) mpfr_sin(value, argument, directions[k]);
                else mpfr_cos(value, argument, directions[k]);
                assert(mpfr_cmp_d(value, results[op].lo) >= 0);
                assert(mpfr_cmp_d(value, results[op].hi) <= 0);
            }
        }
    }
    mpfr_clears(argument, value, (mpfr_ptr)0);
}

static void test_independent_periodic_oracles_and_numeric_context(void)
{
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    const mpfr_prec_t precisions[] = {32, 512};
    const int saved_round = fegetround();
    const mpfr_prec_t saved_precision = mpfr_get_default_prec();
    const mpfr_exp_t saved_emin = mpfr_get_emin(), saved_emax = mpfr_get_emax();
    const intmax_t numerators[] = {INTMAX_MIN, INTMAX_MIN + 1,
        -INT64_C(9007199254740993), -3, -1, 0, 1, 2, 3,
        INT64_C(9007199254740992), INT64_C(9007199254740993), INTMAX_MAX};
    const intmax_t denominators[] = {INTMAX_MIN, -1, 0, 1, 2, 3, INTMAX_MAX};
    /* Construct these before changing hardware rounding. */
    const double half_pi = test_pi() / 2;
    const gi_interval inputs[] = {
        {0.0, 0.0}, {-0.0, -0.0}, {-0.0, 0.0},
        {-DBL_TRUE_MIN, DBL_TRUE_MIN}, {1, nextafter(1, INFINITY)},
        {nextafter(half_pi, -INFINITY), nextafter(half_pi, INFINITY)},
        {1, 2}, {-2, -1}, {3, 4}, {-4, -3}, {-10, 10},
        {0x1p40, 0x1p40}, {-0x1p40, -0x1p40}, {0x1p60, 0x1p60},
        {0x1p40 + 1, nextafter(0x1p40 + 1, INFINITY)},
        {-nextafter(0x1p40 + 1, INFINITY), -0x1p40 - 1},
        {nextafter(0x1p55, -INFINITY), 0x1p55},
        {-0x1p55, -nextafter(0x1p55, -INFINITY)},
        {0x1p55, nextafter(0x1p55, INFINITY)},
        {-nextafter(0x1p55, INFINITY), -0x1p55},
        {0x1p100, 0x1p100}, {-0x1p100, -0x1p100},
        {DBL_MAX, DBL_MAX}, {-DBL_MAX, -DBL_MAX},
        {nextafter(DBL_MAX, -INFINITY), DBL_MAX},
    };
    for (size_t m = 0; m < sizeof modes / sizeof modes[0]; ++m) {
        assert(fesetround(modes[m]) == 0);
        for (size_t p = 0; p < sizeof precisions / sizeof precisions[0]; ++p) {
            mpfr_set_default_prec(precisions[p]);
            for (size_t n = 0; n < sizeof numerators / sizeof numerators[0]; ++n)
                for (size_t d = 0; d < sizeof denominators / sizeof denominators[0]; ++d)
                    check_pi_multiple_independent(numerators[n], denominators[d]);
            for (size_t i = 0; i < sizeof inputs / sizeof inputs[0]; ++i)
                check_trig_independent(inputs[i]);
            /* Finite samples alone do not check the interior extrema. */
            assert(gi_trans_sin(gi_interval_make(1, 2)).hi == 1);
            assert(gi_trans_sin(gi_interval_make(-2, -1)).lo == -1);
            assert(gi_trans_cos(gi_interval_make(3, 4)).lo == -1);
            assert(gi_trans_cos(gi_interval_make(-1, 1)).hi == 1);
            const gi_interval wide[] = {
                {0x1p55, nextafter(0x1p55, INFINITY)},
                {-nextafter(0x1p55, INFINITY), -0x1p55},
                {0x1p100, nextafter(0x1p100, INFINITY)},
                {nextafter(DBL_MAX, -INFINITY), DBL_MAX},
                {-10, 10},
            };
            for (size_t w = 0; w < sizeof wide / sizeof wide[0]; ++w) {
                const gi_interval sine_wide = gi_trans_sin(wide[w]);
                const gi_interval cosine_wide = gi_trans_cos(wide[w]);
                assert(sine_wide.lo == -1 && sine_wide.hi == 1);
                assert(cosine_wide.lo == -1 && cosine_wide.hi == 1);
            }
            const gi_interval whole = gi_interval_make(-INFINITY, INFINITY);
            const gi_interval sine = gi_trans_sin(whole), cosine = gi_trans_cos(whole);
            assert(sine.lo == -1 && sine.hi == 1);
            assert(cosine.lo == -1 && cosine.hi == 1);
            assert(gi_interval_is_empty(gi_trans_sin(gi_interval_empty())));
            assert(gi_interval_is_empty(gi_trans_cos(gi_interval_empty())));
            assert(fegetround() == modes[m]);
            assert(mpfr_get_default_prec() == precisions[p]);
            assert(mpfr_get_emin() == saved_emin && mpfr_get_emax() == saved_emax);
        }
    }
    mpfr_set_default_prec(saved_precision);
    assert(fesetround(saved_round) == 0);
}

int main(void)
{
    test_independent_periodic_oracles_and_numeric_context();
    test_elementary_unary_directed_bounds();
    test_point_sin_cos_match_directed_mpfr();
    test_sin_point_zero();
    test_sin_point_one();
    test_sin_interval_with_maximum();
    test_sin_interval_with_minimum();
    test_sin_large_argument_is_conservative();
    test_cos_point_zero();
    test_cos_interval_with_minimum();
    test_cbrt_point_239_is_outward_rounded();
    test_pi_multiple_brackets_irrational_boundary();
    test_positive_integer_base_power_is_monotone_and_outward();
    test_positive_integer_base_power_point_brackets_mpfr();
    test_positive_integer_base_power_boundaries_are_conservative();
    test_atan_is_monotone_and_outward_rounded();
    test_atan_zero_is_exact();
    test_atan_point_one_retains_outward_bracket();
    test_log2_is_monotone_and_outward_rounded();
    test_log2_point_three_retains_outward_bracket();
    test_log2_domain_boundaries();
    test_point_atan2_matches_directed_mpfr();
    test_atan2_axes_and_argument_order();
    test_atan2_origin_is_empty();
    test_atan2_partial_origin_keeps_live_range();
    test_atan2_branch_cut_uses_full_turn();
    test_tan_regular_branch_is_bounded();
    test_tan_interval_crossing_pole_is_unbounded();
}
