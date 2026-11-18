/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#include "graphing/common_factor.h"
#include "graphing/interval.h"
#include "graphing/remainder.h"
#include "graphing/transcendental.h"

#include <assert.h>
#include <fenv.h>
#include <float.h>
#include <math.h>
#include <mpfr.h>
#include <stdbool.h>
#include <stdint.h>

#pragma STDC FENV_ACCESS ON

#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE__)
#include <xmmintrin.h>

enum {
    TEST_MXCSR_RMODE_MASK = 0x6000u,
    TEST_MXCSR_RMODE_PLUS_INF = 0x4000u,
    TEST_MXCSR_CONTROL_MASK = 0xffc0u
};
#endif

typedef struct {
    int fenv_round;
#if defined(__aarch64__)
    uint64_t fpcr;
#elif (defined(__i386__) || defined(__x86_64__)) && defined(__SSE__)
    unsigned short x87_control;
    unsigned int mxcsr_control;
#endif
} test_round_control_state;

static test_round_control_state test_round_control_save(void)
{
    test_round_control_state state = { .fenv_round = fegetround() };

#if defined(__aarch64__)
    __asm__ volatile("mrs %0, fpcr" : "=r"(state.fpcr));
#elif (defined(__i386__) || defined(__x86_64__)) && defined(__SSE__)
    __asm__ volatile("fnstcw %0" : "=m"(state.x87_control));
    state.mxcsr_control = _mm_getcsr() & TEST_MXCSR_CONTROL_MASK;
#endif
    return state;
}

static void assert_round_control_equal(
    test_round_control_state expected,
    test_round_control_state actual)
{
    assert(actual.fenv_round == expected.fenv_round);
#if defined(__aarch64__)
    assert(actual.fpcr == expected.fpcr);
#elif (defined(__i386__) || defined(__x86_64__)) && defined(__SSE__)
    assert(actual.x87_control == expected.x87_control);
    assert(actual.mxcsr_control == expected.mxcsr_control);
#endif
}

#define ASSERT_ROUND_CONTROL_PRESERVED(expression) \
    do { \
        test_round_control_state before = test_round_control_save(); \
        (void)(expression); \
        test_round_control_state after = test_round_control_save(); \
        assert_round_control_equal(before, after); \
    } while (false)

static void assert_interval_contains(gi_interval x, double value)
{
    assert(!gi_interval_is_empty(x));
    assert(x.lo <= value);
    assert(value <= x.hi);
}

static void assert_interval_equals(gi_interval x, double lo, double hi)
{
    assert(!gi_interval_is_empty(x));
    assert(x.lo == lo);
    assert(x.hi == hi);
}

static void assert_bool_equals(gi_bool_interval x, bool lo, bool hi)
{
    assert(x.lo == lo);
    assert(x.hi == hi);
}

static void assert_interval_contains_mpfr(
    gi_interval interval,
    mpfr_srcptr expected)
{
    assert(!gi_interval_is_empty(interval));
    assert(mpfr_cmp_d(expected, interval.lo) >= 0);
    assert(mpfr_cmp_d(expected, interval.hi) <= 0);
}

static void assert_interval_contains_exact_power(
    gi_interval interval,
    double value,
    uint32_t exponent)
{
    mpfr_t base;
    mpfr_t expected;

    mpfr_init2(base, 1024);
    mpfr_init2(expected, 1024);
    mpfr_set_d(base, value, MPFR_RNDN);
    mpfr_pow_ui(expected, base, exponent, MPFR_RNDN);

    assert_interval_contains_mpfr(interval, expected);

    mpfr_clear(base);
    mpfr_clear(expected);
}

static void test_construction_and_predicate_boundary_table(void)
{
    gi_interval signed_zero = gi_interval_make(-0.0, 0.0);
    gi_interval negative_infinite = gi_interval_point(-INFINITY);
    gi_interval positive_infinite = gi_interval_point(INFINITY);
    gi_interval empty = gi_interval_empty();
    gi_interval whole = gi_interval_whole();

    assert(signbit(signed_zero.lo));
    assert(!signbit(signed_zero.hi));
    assert_interval_equals(negative_infinite, -INFINITY, -INFINITY);
    assert_interval_equals(positive_infinite, INFINITY, INFINITY);
    assert(gi_interval_is_empty(empty));
    assert(gi_interval_is_empty(gi_interval_make(2.0, 1.0)));
    assert(gi_interval_is_empty(gi_interval_make(NAN, 1.0)));
    assert(gi_interval_is_empty(gi_interval_make(1.0, NAN)));
    assert(gi_interval_is_empty(gi_interval_point(NAN)));
    assert_interval_equals(whole, -INFINITY, INFINITY);
    assert(gi_interval_contains(signed_zero, -0.0));
    assert(gi_interval_contains(signed_zero, 0.0));
    assert(gi_interval_contains(whole, -DBL_MAX));
    assert(gi_interval_contains(whole, DBL_MAX));
    assert(!gi_interval_contains(empty, 0.0));
    assert(!gi_interval_contains(whole, NAN));
}

static void test_empty_interval_boundary_table(void)
{
    gi_interval empty = gi_interval_empty();
    gi_interval finite = gi_interval_make(-2.0, 3.0);

    assert(gi_interval_is_empty(gi_interval_add(empty, finite)));
    assert(gi_interval_is_empty(gi_interval_add(finite, empty)));
    assert(gi_interval_is_empty(gi_interval_sub(empty, finite)));
    assert(gi_interval_is_empty(gi_interval_sub(finite, empty)));
    assert(gi_interval_is_empty(gi_interval_mul(empty, finite)));
    assert(gi_interval_is_empty(gi_interval_mul(finite, empty)));
    assert(gi_interval_is_empty(gi_interval_div(empty, finite)));
    assert(gi_interval_is_empty(gi_interval_div(finite, empty)));
    assert(gi_interval_is_empty(gi_interval_min(empty, finite)));
    assert(gi_interval_is_empty(gi_interval_min(finite, empty)));
    assert(gi_interval_is_empty(gi_interval_max(empty, finite)));
    assert(gi_interval_is_empty(gi_interval_max(finite, empty)));
    assert(gi_interval_is_empty(gi_interval_sqrt(empty)));
    assert(gi_interval_is_empty(gi_interval_neg(empty)));
    assert(gi_interval_is_empty(gi_interval_abs(empty)));
    assert(gi_interval_is_empty(gi_interval_floor(empty)));
    assert(gi_interval_is_empty(gi_interval_ceil(empty)));
    assert(gi_interval_is_empty(gi_interval_factorial(empty)));
    assert(gi_interval_is_empty(gi_interval_pow_nonnegative_integer_exponent(empty, 0)));

    assert_interval_equals(gi_interval_hull(empty, finite), -2.0, 3.0);
    assert_interval_equals(gi_interval_hull(finite, empty), -2.0, 3.0);
    assert(gi_interval_is_empty(gi_interval_intersect(empty, finite)));
    assert(gi_interval_is_empty(gi_interval_intersect(finite, empty)));

    assert_bool_equals(gi_interval_gt(empty, finite), false, false);
    assert_bool_equals(gi_interval_ge(finite, empty), false, false);
    assert_bool_equals(gi_interval_lt(empty, finite), false, false);
    assert_bool_equals(gi_interval_le(finite, empty), false, false);
    assert_bool_equals(gi_interval_eq(empty, finite), false, false);
}

static void test_infinite_interval_boundary_table(void)
{
    gi_interval whole = gi_interval_whole();
    gi_interval finite = gi_interval_make(-1.0, 1.0);
    gi_interval positive = gi_interval_make(2.0, 3.0);

    assert_interval_equals(gi_interval_add(whole, finite), -INFINITY, INFINITY);
    assert_interval_equals(gi_interval_sub(whole, finite), -INFINITY, INFINITY);
    assert_interval_equals(gi_interval_mul(positive, whole), -INFINITY, INFINITY);
    assert_interval_equals(gi_interval_div(whole, positive), -INFINITY, INFINITY);
    assert_interval_equals(gi_interval_div(positive, whole), -INFINITY, INFINITY);
    assert_interval_equals(gi_interval_min(whole, finite), -INFINITY, 1.0);
    assert_interval_equals(gi_interval_max(whole, finite), -1.0, INFINITY);
    assert_interval_equals(gi_interval_sqrt(whole), 0.0, INFINITY);
    assert_interval_equals(gi_interval_neg(whole), -INFINITY, INFINITY);
    assert_interval_equals(gi_interval_abs(whole), 0.0, INFINITY);
    assert_interval_equals(gi_interval_floor(whole), -INFINITY, INFINITY);
    assert_interval_equals(gi_interval_ceil(whole), -INFINITY, INFINITY);
    assert(gi_interval_is_empty(gi_interval_factorial(whole)));
    assert_interval_equals(gi_interval_hull(whole, finite), -INFINITY, INFINITY);
    assert_interval_equals(gi_interval_intersect(whole, finite), -1.0, 1.0);
}

static void test_subnormal_and_signed_zero_boundary_table(void)
{
    double smallest = nextafter(0.0, INFINITY);
    gi_interval positive_zero = gi_interval_point(0.0);
    gi_interval negative_zero = gi_interval_point(-0.0);
    gi_interval sum = gi_interval_add(
        gi_interval_point(smallest),
        gi_interval_point(smallest));
    gi_interval difference = gi_interval_sub(
        gi_interval_point(smallest),
        positive_zero);
    gi_interval product = gi_interval_mul(
        gi_interval_point(smallest),
        gi_interval_point(smallest));
    gi_interval quotient = gi_interval_div(
        gi_interval_point(smallest),
        gi_interval_point(2.0));
    gi_interval root = gi_interval_sqrt(gi_interval_point(smallest));

    assert_interval_equals(sum, 2.0 * smallest, 2.0 * smallest);
    assert_interval_equals(difference, smallest, smallest);
    assert_interval_equals(product, 0.0, smallest);
    assert_interval_equals(quotient, 0.0, smallest);
    assert_interval_equals(root, 0x1p-537, 0x1p-537);

    assert_interval_contains(gi_interval_add(positive_zero, negative_zero), 0.0);
    assert_interval_contains(gi_interval_sub(positive_zero, positive_zero), 0.0);
    assert_interval_equals(gi_interval_mul(negative_zero, gi_interval_point(2.0)), 0.0, 0.0);
    assert_interval_equals(gi_interval_div(gi_interval_point(1.0), negative_zero), -INFINITY, INFINITY);
    assert_interval_contains(gi_interval_sqrt(negative_zero), 0.0);
    assert_interval_contains(gi_interval_neg(positive_zero), 0.0);
    assert_interval_equals(gi_interval_abs(negative_zero), 0.0, 0.0);
    assert_interval_equals(gi_interval_floor(negative_zero), 0.0, 0.0);
    assert_interval_equals(
        gi_interval_floor(gi_interval_point(smallest)),
        0.0,
        0.0);
    assert_interval_equals(
        gi_interval_floor(gi_interval_point(-smallest)),
        -1.0,
        -1.0);
    assert_interval_equals(gi_interval_ceil(negative_zero), 0.0, 0.0);
    assert_interval_equals(gi_interval_factorial(negative_zero), 1.0, 1.0);
    gi_interval minimum_zero = gi_interval_min(negative_zero, positive_zero);
    gi_interval maximum_zero = gi_interval_max(negative_zero, positive_zero);
    assert_interval_equals(minimum_zero, 0.0, 0.0);
    assert_interval_equals(maximum_zero, 0.0, 0.0);
    assert(!signbit(minimum_zero.lo));
    assert(!signbit(minimum_zero.hi));
    assert(!signbit(maximum_zero.lo));
    assert(!signbit(maximum_zero.hi));
    assert_interval_equals(
        gi_interval_ceil(gi_interval_point(smallest)),
        1.0,
        1.0);
    assert_interval_equals(
        gi_interval_ceil(gi_interval_point(-smallest)),
        0.0,
        0.0);
    assert_interval_contains(gi_interval_hull(negative_zero, positive_zero), 0.0);
    assert_interval_contains(gi_interval_intersect(negative_zero, positive_zero), 0.0);
    assert_bool_equals(gi_interval_gt(negative_zero, positive_zero), false, false);
    assert_bool_equals(gi_interval_ge(negative_zero, positive_zero), true, true);
    assert_bool_equals(gi_interval_eq(negative_zero, positive_zero), true, true);
}

static void test_directed_addition(void)
{
    gi_interval x = gi_interval_point(1.0);
    gi_interval half_ulp = gi_interval_point(0x1p-53);
    gi_interval sum = gi_interval_add(x, half_ulp);

    assert(sum.lo == 1.0);
    assert(sum.hi == nextafter(1.0, INFINITY));
}

static void test_directed_subtraction(void)
{
    gi_interval x = gi_interval_point(1.0);
    gi_interval quarter_ulp = gi_interval_point(0x1p-54);
    gi_interval diff = gi_interval_sub(x, quarter_ulp);

    assert(diff.lo == nextafter(1.0, -INFINITY));
    assert(diff.hi == 1.0);
}

static void test_division_contains_decimal(void)
{
    gi_interval tenth = gi_interval_div(gi_interval_point(1.0), gi_interval_point(10.0));

    assert_interval_contains(tenth, 0.1);
    assert(tenth.lo < tenth.hi);
}

static void test_division_through_zero_is_whole(void)
{
    gi_interval x = gi_interval_make(2.0, 3.0);
    gi_interval y = gi_interval_make(-1.0, 1.0);
    gi_interval result = gi_interval_div(x, y);

    assert(result.lo == -INFINITY);
    assert(result.hi == INFINITY);
}

static void test_multiplication_with_zero_and_infinity(void)
{
    gi_interval zero = gi_interval_point(0.0);
    gi_interval whole = gi_interval_whole();
    gi_interval product = gi_interval_mul(zero, whole);

    assert(product.lo == 0.0);
    assert(product.hi == 0.0);
}

static void test_square_root_bounds(void)
{
    gi_interval root_two = gi_interval_sqrt(gi_interval_point(2.0));

    assert_interval_contains(root_two, sqrt(2.0));
    assert(root_two.lo < root_two.hi);
}

static void test_arithmetic_contains_mpfr_point_oracles(void)
{
    double value = nextafter(1.0, INFINITY);
    mpfr_t left;
    mpfr_t right;
    mpfr_t expected;

    mpfr_inits2(1024, left, right, expected, (mpfr_ptr)0);

    mpfr_set_d(left, 1.0, MPFR_RNDN);
    mpfr_set_d(right, 0x1p-53, MPFR_RNDN);
    mpfr_add(expected, left, right, MPFR_RNDN);
    assert_interval_contains_mpfr(
        gi_interval_add(gi_interval_point(1.0), gi_interval_point(0x1p-53)),
        expected);

    mpfr_set_d(right, 0x1p-54, MPFR_RNDN);
    mpfr_sub(expected, left, right, MPFR_RNDN);
    assert_interval_contains_mpfr(
        gi_interval_sub(gi_interval_point(1.0), gi_interval_point(0x1p-54)),
        expected);

    mpfr_set_d(left, value, MPFR_RNDN);
    mpfr_mul(expected, left, left, MPFR_RNDN);
    gi_interval product = gi_interval_mul(
        gi_interval_point(value),
        gi_interval_point(value));
    assert_interval_contains_mpfr(product, expected);
    assert(product.lo < product.hi);

    mpfr_set_ui(left, 1, MPFR_RNDN);
    mpfr_set_ui(right, 10, MPFR_RNDN);
    mpfr_div(expected, left, right, MPFR_RNDN);
    gi_interval quotient = gi_interval_div(
        gi_interval_point(1.0),
        gi_interval_point(10.0));
    assert_interval_contains_mpfr(quotient, expected);
    assert(quotient.lo < quotient.hi);

    mpfr_set_ui(left, 2, MPFR_RNDN);
    mpfr_sqrt(expected, left, MPFR_RNDN);
    gi_interval root = gi_interval_sqrt(gi_interval_point(2.0));
    assert_interval_contains_mpfr(root, expected);
    assert(root.lo < root.hi);

    mpfr_clears(left, right, expected, (mpfr_ptr)0);
}

static void test_absolute_value_extension(void)
{
    gi_interval negative = gi_interval_abs(gi_interval_make(-5.0, -2.0));
    gi_interval positive = gi_interval_abs(gi_interval_make(2.0, 5.0));
    gi_interval crossing = gi_interval_abs(gi_interval_make(-5.0, 3.0));
    gi_interval whole = gi_interval_abs(gi_interval_whole());
    gi_interval negative_zero = gi_interval_abs(gi_interval_point(-0.0));

    assert(negative.lo == 2.0 && negative.hi == 5.0);
    assert(positive.lo == 2.0 && positive.hi == 5.0);
    assert(crossing.lo == 0.0 && crossing.hi == 5.0);
    assert(whole.lo == 0.0 && whole.hi == INFINITY);
    assert(negative_zero.lo == 0.0 && !signbit(negative_zero.lo));
    assert(negative_zero.hi == 0.0 && !signbit(negative_zero.hi));
    const double zeros[] = {-0.0, 0.0};
    for (size_t i = 0; i < 2; ++i) {
        for (size_t j = 0; j < 2; ++j) {
            gi_interval zero = gi_interval_abs(gi_interval_make(zeros[i], zeros[j]));
            assert(zero.lo == 0.0 && !signbit(zero.lo));
            assert(zero.hi == 0.0 && !signbit(zero.hi));
        }
    }
    assert(gi_interval_is_empty(gi_interval_abs(gi_interval_empty())));
}

static void test_floor_extension(void)
{
    gi_interval positive = gi_interval_floor(gi_interval_make(0.25, 3.75));
    gi_interval negative = gi_interval_floor(gi_interval_make(-3.75, -0.25));
    gi_interval crossing = gi_interval_floor(gi_interval_make(-1.25, 1.25));
    gi_interval integer = gi_interval_floor(gi_interval_point(2.0));
    gi_interval largest_exact = gi_interval_floor(gi_interval_point(0x1p53));
    gi_interval negative_zero = gi_interval_floor(gi_interval_point(-0.0));

    assert_interval_equals(positive, 0.0, 3.0);
    assert_interval_equals(negative, -4.0, -1.0);
    assert_interval_equals(crossing, -2.0, 1.0);
    assert_interval_equals(integer, 2.0, 2.0);
    assert_interval_equals(largest_exact, 0x1p53, 0x1p53);
    assert_interval_equals(negative_zero, 0.0, 0.0);
    assert(!signbit(negative_zero.lo));
    assert(!signbit(negative_zero.hi));
}

static void test_ceil_extension(void)
{
    gi_interval positive = gi_interval_ceil(gi_interval_make(0.25, 3.75));
    gi_interval negative = gi_interval_ceil(gi_interval_make(-3.75, -0.25));
    gi_interval crossing = gi_interval_ceil(gi_interval_make(-1.25, 1.25));
    gi_interval integer = gi_interval_ceil(gi_interval_point(2.0));
    gi_interval largest_exact = gi_interval_ceil(gi_interval_point(0x1p53));
    gi_interval negative_zero = gi_interval_ceil(gi_interval_point(-0.0));

    assert_interval_equals(positive, 1.0, 4.0);
    assert_interval_equals(negative, -3.0, 0.0);
    assert_interval_equals(crossing, -1.0, 2.0);
    assert_interval_equals(integer, 2.0, 2.0);
    assert_interval_equals(largest_exact, 0x1p53, 0x1p53);
    assert_interval_equals(negative_zero, 0.0, 0.0);
    assert(!signbit(negative_zero.lo));
    assert(!signbit(negative_zero.hi));
}

static void test_factorial_point_extension(void)
{
    mpfr_t exact;
    mpfr_init2(exact, 2048);

    assert_interval_equals(gi_interval_factorial(gi_interval_point(0.0)), 1.0, 1.0);
    assert_interval_equals(gi_interval_factorial(gi_interval_point(1.0)), 1.0, 1.0);
    assert_interval_equals(gi_interval_factorial(gi_interval_point(5.0)), 120.0, 120.0);

    gi_interval nonrepresentable = gi_interval_factorial(gi_interval_point(23.0));
    mpfr_fac_ui(exact, 23U, MPFR_RNDN);
    assert_interval_contains_mpfr(nonrepresentable, exact);
    assert(nonrepresentable.lo < nonrepresentable.hi);

    gi_interval largest_finite = gi_interval_factorial(
        gi_interval_point(GI_INTERVAL_MAX_FINITE_FACTORIAL_INPUT));
    mpfr_fac_ui(exact, GI_INTERVAL_MAX_FINITE_FACTORIAL_INPUT, MPFR_RNDN);
    assert_interval_contains_mpfr(largest_finite, exact);
    assert(isfinite(largest_finite.lo));
    assert(isfinite(largest_finite.hi));

    gi_interval overflow = gi_interval_factorial(
        gi_interval_point(GI_INTERVAL_MAX_FINITE_FACTORIAL_INPUT + 1));
    mpfr_fac_ui(exact, GI_INTERVAL_MAX_FINITE_FACTORIAL_INPUT + 1U, MPFR_RNDN);
    assert_interval_contains_mpfr(overflow, exact);
    assert(overflow.lo == DBL_MAX);
    assert(overflow.hi == INFINITY);
    assert_interval_equals(
        gi_interval_factorial(gi_interval_point(1000.0)),
        DBL_MAX,
        INFINITY);

    assert(gi_interval_is_empty(gi_interval_factorial(gi_interval_point(-1.0))));
    assert(gi_interval_is_empty(gi_interval_factorial(gi_interval_point(2.5))));
    assert(gi_interval_is_empty(gi_interval_factorial(gi_interval_make(2.0, 3.0))));
    assert(gi_interval_is_empty(gi_interval_factorial(gi_interval_point(INFINITY))));

    mpfr_clear(exact);
}

static void test_min_max_extensions(void)
{
    gi_interval left = gi_interval_make(-3.0, 2.0);
    gi_interval right = gi_interval_make(-1.0, 5.0);
    gi_interval disjoint_left = gi_interval_make(-5.0, -4.0);
    gi_interval disjoint_right = gi_interval_make(7.0, 8.0);

    assert_interval_equals(gi_interval_min(left, right), -3.0, 2.0);
    assert_interval_equals(gi_interval_max(left, right), -1.0, 5.0);
    assert_interval_equals(
        gi_interval_min(disjoint_left, disjoint_right),
        -5.0,
        -4.0);
    assert_interval_equals(
        gi_interval_max(disjoint_left, disjoint_right),
        7.0,
        8.0);
    assert_interval_equals(gi_interval_min(left, left), -3.0, 2.0);
    assert_interval_equals(gi_interval_max(right, right), -1.0, 5.0);
    assert_interval_equals(
        gi_interval_min(
            gi_interval_point(nextafter(0.0, INFINITY)),
            gi_interval_point(0.0)),
        0.0,
        0.0);
    assert_interval_equals(
        gi_interval_max(
            gi_interval_point(-nextafter(0.0, INFINITY)),
            gi_interval_point(0.0)),
        0.0,
        0.0);
}

static void test_integer_power_extension_shapes(void)
{
    gi_interval odd_negative = gi_interval_pow_nonnegative_integer_exponent(
        gi_interval_make(-3.0, -2.0),
        3);
    gi_interval odd_crossing = gi_interval_pow_nonnegative_integer_exponent(
        gi_interval_make(-2.0, 3.0),
        3);
    gi_interval even_negative = gi_interval_pow_nonnegative_integer_exponent(
        gi_interval_make(-3.0, -2.0),
        2);
    gi_interval even_positive = gi_interval_pow_nonnegative_integer_exponent(
        gi_interval_make(2.0, 3.0),
        2);
    gi_interval even_crossing = gi_interval_pow_nonnegative_integer_exponent(
        gi_interval_make(-2.0, 3.0),
        2);
    gi_interval even_whole = gi_interval_pow_nonnegative_integer_exponent(gi_interval_whole(), 2);
    gi_interval odd_whole = gi_interval_pow_nonnegative_integer_exponent(gi_interval_whole(), 3);

    assert(odd_negative.lo == -27.0 && odd_negative.hi == -8.0);
    assert(odd_crossing.lo == -8.0 && odd_crossing.hi == 27.0);
    assert(even_negative.lo == 4.0 && even_negative.hi == 9.0);
    assert(even_positive.lo == 4.0 && even_positive.hi == 9.0);
    assert(even_crossing.lo == 0.0 && even_crossing.hi == 9.0);
    assert(even_whole.lo == 0.0 && even_whole.hi == INFINITY);
    assert(odd_whole.lo == -INFINITY && odd_whole.hi == INFINITY);
}

static void test_integer_power_zero_empty_and_capacity_contract(void)
{
    gi_interval source = gi_interval_make(-2.0, 3.0);
    gi_interval identity = gi_interval_pow_nonnegative_integer_exponent(source, 1);
    gi_interval zeroth = gi_interval_pow_nonnegative_integer_exponent(source, 0);
    gi_interval unsupported = gi_interval_pow_nonnegative_integer_exponent(
        source,
        GI_INTERVAL_MAX_INTEGER_POWER + 1);

    assert(identity.lo == source.lo && identity.hi == source.hi);
    assert(zeroth.lo == 1.0 && zeroth.hi == 1.0);
    assert(unsupported.lo == -INFINITY && unsupported.hi == INFINITY);
    assert(gi_interval_is_empty(
        gi_interval_pow_nonnegative_integer_exponent(
            gi_interval_empty(),
            0)));
}

static void test_integer_power_signed_zero_overflow_and_underflow(void)
{
    double smallest = nextafter(0.0, INFINITY);
    gi_interval negative_zero_odd = gi_interval_pow_nonnegative_integer_exponent(
        gi_interval_point(-0.0),
        3);
    gi_interval negative_zero_even = gi_interval_pow_nonnegative_integer_exponent(
        gi_interval_point(-0.0),
        2);
    gi_interval overflow = gi_interval_pow_nonnegative_integer_exponent(
        gi_interval_point(DBL_MAX),
        2);
    gi_interval underflow = gi_interval_pow_nonnegative_integer_exponent(
        gi_interval_point(smallest),
        2);

    assert(negative_zero_odd.lo == 0.0 && signbit(negative_zero_odd.lo));
    assert(negative_zero_odd.hi == 0.0 && signbit(negative_zero_odd.hi));
    assert(negative_zero_even.lo == 0.0 && !signbit(negative_zero_even.lo));
    assert(negative_zero_even.hi == 0.0 && !signbit(negative_zero_even.hi));
    assert(overflow.lo == DBL_MAX && overflow.hi == INFINITY);
    assert(underflow.lo == 0.0 && underflow.hi == smallest);
}

static void test_integer_power_contains_mpfr_point_oracle(void)
{
    const double values[] = {
        -INFINITY,
        -DBL_MAX,
        -1.1,
        -1.0,
        -nextafter(0.0, INFINITY),
        -0.0,
        0.0,
        nextafter(0.0, INFINITY),
        0.1,
        1.0,
        1.1,
        DBL_MAX,
        INFINITY
    };

    size_t value_count = sizeof(values) / sizeof(values[0]);
    for (uint32_t exponent = 0;
         exponent <= GI_INTERVAL_MAX_INTEGER_POWER;
         ++exponent) {
        for (size_t index = 0; index < value_count; ++index) {
            gi_interval result = gi_interval_pow_nonnegative_integer_exponent(
                gi_interval_point(values[index]),
                exponent);
            assert_interval_contains_exact_power(result, values[index], exponent);
        }
    }
}

static void test_integer_power_contains_mpfr_interval_samples(void)
{
    typedef struct {
        gi_interval input;
        double samples[5];
    } power_case;

    const power_case cases[] = {
        { {-1.1, -0.1}, {-1.1, -0.9, -0.5, -0.2, -0.1} },
        { {-1.1, 0.1}, {-1.1, -0.9, -0.5, 0.0, 0.1} },
        { {-0.1, 1.1}, {-0.1, 0.0, 0.2, 0.9, 1.1} },
        { {0.1, 1.1}, {0.1, 0.2, 0.5, 0.9, 1.1} },
        { {-DBL_MAX, DBL_MAX}, {-DBL_MAX, -1.0, 0.0, 1.0, DBL_MAX} }
    };

    size_t case_count = sizeof(cases) / sizeof(cases[0]);
    for (uint32_t exponent = 0;
         exponent <= GI_INTERVAL_MAX_INTEGER_POWER;
         ++exponent) {
        for (size_t case_index = 0; case_index < case_count; ++case_index) {
            gi_interval result = gi_interval_pow_nonnegative_integer_exponent(
                cases[case_index].input,
                exponent);
            for (size_t sample_index = 0; sample_index < 5; ++sample_index) {
                assert_interval_contains_exact_power(
                    result,
                    cases[case_index].samples[sample_index],
                    exponent);
            }
        }
    }
}

static void test_integer_power_retains_outward_rounding(void)
{
    double value = nextafter(1.0, INFINITY);
    gi_interval square = gi_interval_pow_nonnegative_integer_exponent(gi_interval_point(value), 2);

    assert(square.lo < square.hi);
    assert_interval_contains_exact_power(square, value, 2);
}

static void test_comparison_boundary_table(void)
{
    gi_interval high = gi_interval_make(3.0, 4.0);
    gi_interval middle = gi_interval_make(1.0, 3.0);
    gi_interval low = gi_interval_make(-1.0, 1.0);
    gi_interval point = gi_interval_point(3.0);

    assert_bool_equals(gi_interval_gt(high, low), true, true);
    assert_bool_equals(gi_interval_gt(high, middle), false, true);
    assert_bool_equals(gi_interval_gt(low, high), false, false);
    assert_bool_equals(gi_interval_ge(high, middle), true, true);
    assert_bool_equals(gi_interval_ge(middle, high), false, true);
    assert_bool_equals(gi_interval_ge(low, high), false, false);
    assert_bool_equals(gi_interval_lt(low, high), true, true);
    assert_bool_equals(gi_interval_lt(middle, high), false, true);
    assert_bool_equals(gi_interval_lt(high, low), false, false);
    assert_bool_equals(gi_interval_le(middle, high), true, true);
    assert_bool_equals(gi_interval_le(high, middle), false, true);
    assert_bool_equals(gi_interval_le(high, low), false, false);
    assert_bool_equals(gi_interval_eq(point, point), true, true);
    assert_bool_equals(gi_interval_eq(high, middle), false, true);
    assert_bool_equals(gi_interval_eq(high, low), false, false);
}

static void test_boolean_truth_tables(void)
{
    const gi_bool_interval values[] = {
        {false, false},
        {false, true},
        {true, true}
    };
    const gi_bool_interval expected_not[] = {
        {true, true},
        {false, true},
        {false, false}
    };
    const gi_bool_interval expected_and[][3] = {
        {{false, false}, {false, false}, {false, false}},
        {{false, false}, {false, true}, {false, true}},
        {{false, false}, {false, true}, {true, true}}
    };
    const gi_bool_interval expected_or[][3] = {
        {{false, false}, {false, true}, {true, true}},
        {{false, true}, {false, true}, {true, true}},
        {{true, true}, {true, true}, {true, true}}
    };

    assert_bool_equals(gi_bool_make(false, false), false, false);
    assert_bool_equals(gi_bool_make(false, true), false, true);
    assert_bool_equals(gi_bool_make(true, false), false, true);
    assert_bool_equals(gi_bool_make(true, true), true, true);

    for (size_t left = 0; left < 3; ++left) {
        assert_bool_equals(
            gi_bool_not(values[left]),
            expected_not[left].lo,
            expected_not[left].hi);
        for (size_t right = 0; right < 3; ++right) {
            assert_bool_equals(
                gi_bool_and(values[left], values[right]),
                expected_and[left][right].lo,
                expected_and[left][right].hi);
            assert_bool_equals(
                gi_bool_or(values[left], values[right]),
                expected_or[left][right].lo,
                expected_or[left][right].hi);
        }
    }

    gi_bool_interval definitely = gi_interval_gt(
        gi_interval_make(3.0, 4.0),
        gi_interval_make(1.0, 2.0));
    gi_bool_interval maybe = gi_interval_gt(
        gi_interval_make(1.0, 4.0),
        gi_interval_make(2.0, 3.0));
    gi_bool_interval never = gi_interval_gt(
        gi_interval_make(0.0, 1.0),
        gi_interval_make(2.0, 3.0));

    assert_bool_equals(definitely, true, true);
    assert_bool_equals(maybe, false, true);
    assert_bool_equals(never, false, false);
}

static void assert_every_primitive_preserves_round_control(void)
{
    gi_interval x = gi_interval_make(-2.0, 3.0);
    gi_interval positive = gi_interval_make(1.0, 2.0);
    gi_interval y = gi_interval_make(4.0, 5.0);
    gi_bool_interval maybe = gi_bool_make(false, true);
    gi_bool_interval definitely = gi_bool_make(true, true);

    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_make(-1.0, 1.0));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_point(1.0));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_empty());
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_whole());
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_is_empty(x));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_contains(x, 0.0));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_add(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_sub(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_mul(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_div(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_min(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_max(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_sqrt(positive));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_neg(x));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_abs(x));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_floor(x));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_ceil(x));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_factorial(gi_interval_point(23.0)));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_pow_nonnegative_integer_exponent(x, 16));
    ASSERT_ROUND_CONTROL_PRESERVED(
        gi_trans_pow_positive_integer_base(2, x));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_trans_log2(positive));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_remainder_mod_point(-5.0, 3.0));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_remainder_fmod_point(-5.0, 3.0));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_common_factor_gcd_point(-12.0, 18.0));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_common_factor_lcm_point(-12.0, 18.0));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_hull(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_intersect(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_gt(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_ge(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_lt(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_le(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_eq(x, y));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_bool_make(false, true));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_bool_not(maybe));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_bool_and(maybe, definitely));
    ASSERT_ROUND_CONTROL_PRESERVED(gi_bool_or(maybe, definitely));
}

static void test_round_control_is_restored_for_every_primitive(void)
{
    int original = fegetround();
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};

    for (size_t index = 0; index < sizeof(modes) / sizeof(modes[0]); ++index) {
        assert(fesetround(modes[index]) == 0);
        assert_every_primitive_preserves_round_control();
    }
    assert(fesetround(original) == 0);
}

static void test_sse_rounding_mode_is_restored(void)
{
#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE__)
    unsigned int original = _mm_getcsr();
    unsigned int upward = (original & ~TEST_MXCSR_RMODE_MASK) | TEST_MXCSR_RMODE_PLUS_INF;
    _mm_setcsr(upward);

    assert_every_primitive_preserves_round_control();
    assert((_mm_getcsr() & TEST_MXCSR_RMODE_MASK)
        == TEST_MXCSR_RMODE_PLUS_INF);
    _mm_setcsr(original);
#endif
}

/* Independent all-corner MPFR oracle: the implementation may select fewer
   products, but its endpoints must equal the directed rectangular extrema. */
static void test_multiplication_sign_sections_against_mpfr(void)
{
    const double endpoints[] = {
        -DBL_MAX, -3.0, -1.0, -DBL_MIN, -DBL_TRUE_MIN, -0.0,
        0.0, DBL_TRUE_MIN, DBL_MIN, 1.0, 3.0, DBL_MAX
    };
    const size_t count = sizeof(endpoints) / sizeof(endpoints[0]);
    mpfr_t a, b, value, lower, upper;
    mpfr_inits2(256, a, b, value, lower, upper, (mpfr_ptr)0);
    for (size_t xl = 0; xl < count; ++xl) {
        for (size_t xh = xl; xh < count; ++xh) {
            for (size_t yl = 0; yl < count; ++yl) {
                for (size_t yh = yl; yh < count; ++yh) {
                    const double x[] = {endpoints[xl], endpoints[xh]};
                    const double y[] = {endpoints[yl], endpoints[yh]};
                    mpfr_set_inf(lower, 1);
                    mpfr_set_inf(upper, -1);
                    for (size_t i = 0; i < 2; ++i) {
                        for (size_t j = 0; j < 2; ++j) {
                            mpfr_set_d(a, x[i], MPFR_RNDN);
                            mpfr_set_d(b, y[j], MPFR_RNDN);
                            /* Products of binary64 significands fit exactly. */
                            mpfr_mul(value, a, b, MPFR_RNDN);
                            mpfr_min(lower, lower, value, MPFR_RNDN);
                            mpfr_max(upper, upper, value, MPFR_RNDN);
                        }
                    }
                    gi_interval actual = gi_interval_mul(
                        gi_interval_make(x[0], x[1]), gi_interval_make(y[0], y[1]));
                    assert_interval_equals(actual,
                        mpfr_get_d(lower, MPFR_RNDD), mpfr_get_d(upper, MPFR_RNDU));
                }
            }
        }
    }
    mpfr_clears(a, b, value, lower, upper, (mpfr_ptr)0);
}

/* Keep the all-corner tie convention: both signs of zero are attainable,
   and the lower bound selected by the existing traversal is negative zero. */
static void test_multiplication_zero_endpoint_ties(void)
{
    gi_interval negative_to_zero = gi_interval_make(-1.0, 0.0);
    gi_interval result = gi_interval_mul(negative_to_zero, negative_to_zero);
    assert_interval_equals(result, 0.0, 1.0);
    assert(signbit(result.lo));
    result = gi_interval_mul(gi_interval_point(0.0), negative_to_zero);
    assert_interval_equals(result, 0.0, 0.0);
    assert(!signbit(result.lo) && !signbit(result.hi));
}

static void assert_zero_interval_signs(gi_interval value, bool lo_negative, bool hi_negative)
{
    assert_interval_equals(value, 0.0, 0.0);
    assert(!!signbit(value.lo) == lo_negative);
    assert(!!signbit(value.hi) == hi_negative);
}

static void test_zero_endpoint_selection_is_order_independent(void)
{
    fenv_t original;
    assert(fegetenv(&original) == 0);
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    const gi_interval zeros[] = {{0.0, 0.0}, {-0.0, -0.0}, {-0.0, 0.0}, {0.0, -0.0}};
    for (size_t mode = 0; mode < sizeof(modes) / sizeof(modes[0]); ++mode) {
        assert(fesetround(modes[mode]) == 0);
        test_round_control_state control = test_round_control_save();
        for (size_t i = 0; i < 4; ++i) {
            gi_interval a = zeros[i];
            assert_zero_interval_signs(gi_interval_hull(a, gi_interval_empty()),
                !!signbit(a.lo), !!signbit(a.hi));
            assert_zero_interval_signs(gi_interval_hull(gi_interval_empty(), a),
                !!signbit(a.lo), !!signbit(a.hi));
            for (size_t j = 0; j < 4; ++j) {
                gi_interval b = zeros[j];
                bool lower_negative = signbit(a.lo) || signbit(b.lo);
                bool upper_negative = signbit(a.hi) && signbit(b.hi);
                assert_zero_interval_signs(gi_interval_hull(a, b),
                    lower_negative, upper_negative);
                assert_round_control_equal(control, test_round_control_save());
                /* The table includes both orders and idempotent same-sign cases. */
                for (size_t k = 0; k < 4; ++k) {
                    gi_interval c = zeros[k];
                    bool lo = lower_negative || signbit(c.lo);
                    bool hi = upper_negative && signbit(c.hi);
                    assert_zero_interval_signs(
                        gi_interval_hull(gi_interval_hull(a, b), c), lo, hi);
                    assert_zero_interval_signs(
                        gi_interval_hull(a, gi_interval_hull(b, c)), lo, hi);
                    assert_round_control_equal(control, test_round_control_save());
                }
                /* Existing public normalization and singleton shortcut stay +0. */
                assert_zero_interval_signs(gi_interval_min(a, b), false, false);
                assert_zero_interval_signs(gi_interval_max(a, b), false, false);
                assert_zero_interval_signs(gi_interval_mul(a, b), false, false);
                gi_interval product = gi_interval_mul(
                    gi_interval_make(-1.0, a.hi), gi_interval_make(-1.0, b.hi));
                assert_interval_equals(product, 0.0, 1.0);
                assert(!!signbit(product.lo) == (!signbit(a.hi) || !signbit(b.hi)));
                assert_round_control_equal(control, test_round_control_save());
            }
        }
        /* All-corner NaNs are still ignored rather than replacing finite extrema. */
        gi_interval positive = gi_interval_mul(
            gi_interval_make(0.0, 1.0), gi_interval_point(INFINITY));
        assert_interval_equals(positive, INFINITY, INFINITY);
        gi_interval negative = gi_interval_mul(
            gi_interval_make(0.0, 1.0), gi_interval_make(-INFINITY, -1.0));
        assert_interval_equals(negative, -INFINITY, 0.0);
        assert(signbit(negative.hi));
        assert_round_control_equal(control, test_round_control_save());
    }
    assert(fesetenv(&original) == 0);
}

static void test_binary_paths_preserve_round_control(void)
{
    const gi_interval values[] = {
        {-3.0, -1.0}, {1.0, 3.0}, {-2.0, 3.0}, {-3.0, 0.0},
        {0.0, 3.0}, {-0.0, 0.0}, {-INFINITY, -1.0}, {1.0, INFINITY},
        {-INFINITY, INFINITY}, {-DBL_TRUE_MIN, DBL_TRUE_MIN},
        {DBL_MAX, DBL_MAX}, {NAN, NAN}
    };
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    const size_t count = sizeof(values) / sizeof(values[0]);
    int original = fegetround();
    for (size_t mode = 0; mode < sizeof(modes) / sizeof(modes[0]); ++mode) {
        assert(fesetround(modes[mode]) == 0);
        for (size_t i = 0; i < count; ++i) {
            for (size_t j = 0; j < count; ++j) {
                ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_add(values[i], values[j]));
                ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_sub(values[i], values[j]));
                ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_mul(values[i], values[j]));
                ASSERT_ROUND_CONTROL_PRESERVED(gi_interval_div(values[i], values[j]));
            }
        }
    }
    assert(fesetround(original) == 0);
}

static void test_set_operations(void)
{
    gi_interval a = gi_interval_make(-1.0, 2.0);
    gi_interval b = gi_interval_make(1.5, 4.0);
    gi_interval intersection = gi_interval_intersect(a, b);
    gi_interval hull = gi_interval_hull(a, b);

    assert(intersection.lo == 1.5);
    assert(intersection.hi == 2.0);
    assert(hull.lo == -1.0);
    assert(hull.hi == 4.0);
    assert(gi_interval_is_empty(gi_interval_intersect(a, gi_interval_make(3.0, 4.0))));
}

static void test_kernel_admission_preserves_full_environment(void)
{
    uint64_t expected = (UINT64_C(0x47) << 56) | (UINT64_C(1) << 48)
        | ((uint64_t)sizeof(gi_interval) << 40)
        | ((uint64_t)_Alignof(gi_interval) << 32)
        | ((uint64_t)offsetof(gi_interval, hi) << 24)
        | ((uint64_t)sizeof(gi_bool_interval) << 16)
        | ((uint64_t)_Alignof(gi_bool_interval) << 8)
        | (uint64_t)offsetof(gi_bool_interval, hi);
    assert(gi_kernel_abi_descriptor() == expected);
    fenv_t original;
    assert(fegetenv(&original) == 0);
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    for (size_t i = 0; i < sizeof(modes) / sizeof(modes[0]); ++i) {
        assert(fesetround(modes[i]) == 0);
        assert(feclearexcept(FE_ALL_EXCEPT) == 0);
        assert(feraiseexcept(FE_INVALID | FE_INEXACT) == 0);
        test_round_control_state control = test_round_control_save();
        int exceptions = fetestexcept(FE_ALL_EXCEPT);
        assert(gi_kernel_numeric_contract_check() == 1);
        assert_round_control_equal(control, test_round_control_save());
        assert(fetestexcept(FE_ALL_EXCEPT) == exceptions);
    }
#if defined(__aarch64__)
    uint64_t fpcr;
    __asm__ volatile("mrs %0, fpcr" : "=r"(fpcr));
    uint64_t flushing = fpcr | (UINT64_C(1) << 24);
    __asm__ volatile("msr fpcr, %0" : : "r"(flushing));
#elif (defined(__i386__) || defined(__x86_64__)) && defined(__SSE__)
    unsigned int mxcsr = _mm_getcsr();
    _mm_setcsr(mxcsr | 0x8040u); /* FTZ and DAZ */
#endif
#if defined(__aarch64__) || ((defined(__i386__) || defined(__x86_64__)) && defined(__SSE__))
    test_round_control_state flushing_control = test_round_control_save();
    int flushing_exceptions = fetestexcept(FE_ALL_EXCEPT);
    assert(gi_kernel_numeric_contract_check() == 0);
    assert_round_control_equal(flushing_control, test_round_control_save());
    assert(fetestexcept(FE_ALL_EXCEPT) == flushing_exceptions);
#endif
    assert(fesetenv(&original) == 0);
}

int main(void)
{
    test_kernel_admission_preserves_full_environment();
    test_construction_and_predicate_boundary_table();
    test_empty_interval_boundary_table();
    test_infinite_interval_boundary_table();
    test_subnormal_and_signed_zero_boundary_table();
    test_directed_addition();
    test_directed_subtraction();
    test_division_contains_decimal();
    test_division_through_zero_is_whole();
    test_multiplication_with_zero_and_infinity();
    test_square_root_bounds();
    test_arithmetic_contains_mpfr_point_oracles();
    test_absolute_value_extension();
    test_floor_extension();
    test_ceil_extension();
    test_factorial_point_extension();
    test_min_max_extensions();
    test_integer_power_extension_shapes();
    test_integer_power_zero_empty_and_capacity_contract();
    test_integer_power_signed_zero_overflow_and_underflow();
    test_integer_power_contains_mpfr_point_oracle();
    test_integer_power_contains_mpfr_interval_samples();
    test_integer_power_retains_outward_rounding();
    test_comparison_boundary_table();
    test_boolean_truth_tables();
    test_round_control_is_restored_for_every_primitive();
    test_sse_rounding_mode_is_restored();
    test_multiplication_sign_sections_against_mpfr();
    test_multiplication_zero_endpoint_ties();
    test_zero_endpoint_selection_is_order_independent();
    test_binary_paths_preserve_round_control();
    test_set_operations();
}
