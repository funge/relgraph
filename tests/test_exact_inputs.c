/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#include "graphing/interval.h"

#include <assert.h>
#include <fenv.h>
#include <gmp.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#pragma STDC FENV_ACCESS ON

/* Independent oracle: decimal exact inputs and raw binary64 field decoding.
   Do not use the production mpz_import/mpq_get_d/mpq_set_d conversion path. */
static void oracle_input(mpq_t q, int64_t n, uint64_t d)
{
    char text[64];
    int length = snprintf(text, sizeof text, "%" PRId64 "/%" PRIu64, n, d);
    assert(length > 0 && (size_t)length < sizeof text && d != 0);
    assert(mpq_set_str(q, text, 10) == 0);
    mpq_canonicalize(q);
}

static void oracle_double(mpq_t q, double x)
{
    uint64_t bits;
    memcpy(&bits, &x, sizeof bits);
    unsigned exponent = (unsigned)((bits >> 52) & UINT64_C(0x7ff));
    uint64_t significand = bits & UINT64_C(0xfffffffffffff);
    assert(exponent != 0x7ff);
    if (exponent != 0) {
        significand |= UINT64_C(1) << 52;
    }
    char text[32];
    snprintf(text, sizeof text, "%" PRIu64, significand);
    assert(mpq_set_str(q, text, 10) == 0);
    int shift = exponent == 0 ? -1074 : (int)exponent - 1075;
    if (shift >= 0) {
        mpz_mul_2exp(mpq_numref(q), mpq_numref(q), (unsigned)shift);
    } else {
        mpz_mul_2exp(mpq_denref(q), mpq_denref(q), (unsigned)-shift);
    }
    if ((bits >> 63) != 0) {
        mpq_neg(q, q);
    }
    mpq_canonicalize(q);
}

static void assert_optimal(gi_interval result, mpq_srcptr lo, mpq_srcptr hi)
{
    mpq_t endpoint;
    mpq_init(endpoint);
    assert(!gi_interval_is_empty(result));
    assert(isfinite(result.lo) && isfinite(result.hi));
    oracle_double(endpoint, result.lo);
    assert(mpq_cmp(endpoint, lo) <= 0);
    oracle_double(endpoint, nextafter(result.lo, INFINITY));
    assert(mpq_cmp(endpoint, lo) > 0);
    oracle_double(endpoint, result.hi);
    assert(mpq_cmp(endpoint, hi) >= 0);
    oracle_double(endpoint, nextafter(result.hi, -INFINITY));
    assert(mpq_cmp(endpoint, hi) < 0);
    mpq_clear(endpoint);
}

static void check_point(int64_t n, uint64_t d)
{
    mpq_t q;
    mpq_init(q);
    oracle_input(q, n, d);
    int mode = fegetround();
    gi_interval result = gi_interval_from_rational64(n, d);
    assert(fegetround() == mode);
    assert_optimal(result, q, q);
    if (n == 0) {
        assert(result.lo == 0.0 && !signbit(result.lo));
        assert(result.hi == 0.0 && !signbit(result.hi));
    }
    if (d == 1) {
        result = gi_interval_from_int64(n);
        assert(fegetround() == mode);
        assert_optimal(result, q, q);
    }
    mpq_clear(q);
}

static void check_bounds(int64_t ln, uint64_t ld, int64_t hn, uint64_t hd)
{
    int mode = fegetround();
    gi_interval result = gi_interval_from_rational64_bounds(ln, ld, hn, hd);
    assert(fegetround() == mode);
    if (ld == 0 || hd == 0) {
        assert(gi_interval_is_empty(result));
        return;
    }
    mpq_t lo, hi;
    mpq_inits(lo, hi, (mpq_ptr)0);
    oracle_input(lo, ln, ld);
    oracle_input(hi, hn, hd);
    if (mpq_cmp(lo, hi) > 0) {
        assert(gi_interval_is_empty(result));
    } else {
        assert_optimal(result, lo, hi);
    }
    if (ld == 1 && hd == 1) {
        result = gi_interval_from_int64_bounds(ln, hn);
        assert(fegetround() == mode);
        if (ln > hn) {
            assert(gi_interval_is_empty(result));
        } else {
            assert_optimal(result, lo, hi);
        }
    }
    mpq_clears(lo, hi, (mpq_ptr)0);
}

static uint64_t random_word(uint64_t *state)
{
    /* Defined unsigned wrap; deterministic across supported platforms. */
    *state = *state * UINT64_C(6364136223846793005) + UINT64_C(1442695040888963407);
    return *state;
}

static int64_t random_integer(uint64_t *state)
{
    uint64_t word = random_word(state);
    int64_t magnitude = (int64_t)(word >> 1);
    return word & 1 ? -magnitude - 1 : magnitude;
}

static void cases(void)
{
    const int64_t integers[] = {
        INT64_MIN, INT64_MIN + 1, INT64_MIN + 1023, INT64_MIN + 1024,
        -9007199254740995LL, -9007199254740993LL, -9007199254740992LL,
        -1, 0, 1, 9007199254740991LL, 9007199254740992LL,
        9007199254740993LL, 9007199254740994LL, 9007199254740995LL,
        INT64_MAX - 1024, INT64_MAX - 1, INT64_MAX
    };
    const uint64_t denominators[] = {
        1, 2, 3, 7, 10, 16, UINT64_C(1) << 32,
        UINT64_C(1) << 63, UINT64_MAX - 1, UINT64_MAX
    };
    for (size_t i = 0; i < sizeof integers / sizeof integers[0]; ++i) {
        for (size_t j = 0; j < sizeof denominators / sizeof denominators[0]; ++j) {
            check_point(integers[i], denominators[j]);
        }
    }
    /* Adjacent integer ties on both sides of multiple binade boundaries. */
    for (unsigned bit = 53; bit <= 62; ++bit) {
        int64_t power = INT64_C(1) << bit;
        for (int offset = -5; offset <= 5; ++offset) {
            check_point(power + offset, 1);
            check_point(-power + offset, 1);
        }
    }
    /* Exactly representable dyadics must not be widened. */
    gi_interval dyadic = gi_interval_from_rational64(-3, 8);
    assert(dyadic.lo == -0.375 && dyadic.hi == -0.375);
    gi_interval tie = gi_interval_from_int64(INT64_C(9007199254740993));
    assert(tie.lo == 0x1p53 && tie.hi == 0x1.0000000000001p53);
    gi_interval negative_tie = gi_interval_from_int64(-INT64_C(9007199254740993));
    assert(negative_tie.lo == -tie.hi && negative_tie.hi == -tie.lo);
    assert(gi_interval_is_empty(gi_interval_from_rational64(0, 0)));
    assert(gi_interval_is_empty(gi_interval_from_rational64(INT64_MIN, 0)));
    check_bounds(1, 0, 2, 1);
    check_bounds(1, 1, 2, 0);
    check_bounds(0, 0, 0, 0);
    check_bounds(INT64_MIN, 1, INT64_MAX, 1);
    check_bounds(INT64_MAX, 1, INT64_MIN, 1);
    check_bounds(-1, 3, 1, 10);
    check_bounds(-1, 3, -1, 10);
    check_bounds(2, 6, 1, 3); /* Equal but unreduced. */
    check_bounds(0, UINT64_MAX, 0, 1);
    check_bounds(9007199254740993LL, 1, 9007199254740992LL, 1);
    /* Reversed inputs whose binary64 enclosures overlap. */
    check_bounds(INT64_MAX, UINT64_MAX - 1, INT64_MAX, UINT64_MAX);
    check_bounds(INT64_MAX, UINT64_MAX, INT64_MAX, UINT64_MAX - 1);

    uint64_t state = UINT64_C(0xb164c0ffee);
    for (unsigned i = 0; i < 3000; ++i) {
        int64_t n = random_integer(&state);
        uint64_t d = random_word(&state) | 1;
        int64_t hn = random_integer(&state);
        uint64_t hd = random_word(&state) | 1;
        check_point(n, d);
        check_point(n, 1);
        check_bounds(n, d, hn, hd);
        check_bounds(hn, hd, n, d);
        check_bounds(n, 1, hn, 1);
    }
}

int main(void)
{
    fenv_t saved;
    assert(fegetenv(&saved) == 0);
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    for (size_t i = 0; i < sizeof modes / sizeof modes[0]; ++i) {
        assert(fesetround(modes[i]) == 0);
        cases();
        assert(fegetround() == modes[i]);
    }
    assert(fesetenv(&saved) == 0);
    puts("exact inputs: enclosure and endpoint optimality passed in four rounding modes");
    return 0;
}
