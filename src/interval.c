/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#pragma STDC FENV_ACCESS ON

#include "graphing/interval.h"

#include <fenv.h>
#include <float.h>
#include <math.h>
#include <mpfr.h>
#include <stdint.h>
#include <string.h>

#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE__)
#include <xmmintrin.h>
#endif

#if defined(__clang__) || defined(__GNUC__)
#define GI_NOINLINE __attribute__((noinline))
#else
#define GI_NOINLINE
#endif

typedef enum {
    GI_ROUND_DOWN,
    GI_ROUND_UP
} gi_round_direction;

typedef double (*gi_binary_op)(double, double);
typedef double (*gi_unary_op)(double);

enum {
    GI_INTERVAL_MPFR_PRECISION = 256
};

#if defined(__aarch64__)

typedef uint64_t gi_round_state;

enum {
    GI_AARCH64_FPCR_RMODE_SHIFT = 22,
    GI_AARCH64_FPCR_RMODE_MASK = 3ull << GI_AARCH64_FPCR_RMODE_SHIFT,
    GI_AARCH64_FPCR_RMODE_PLUS_INF = 1ull << GI_AARCH64_FPCR_RMODE_SHIFT,
    GI_AARCH64_FPCR_RMODE_MINUS_INF = 2ull << GI_AARCH64_FPCR_RMODE_SHIFT
};

static inline gi_round_state gi_round_save(void)
{
    gi_round_state fpcr;
    __asm__ volatile("mrs %0, fpcr" : "=r"(fpcr));
    return fpcr;
}

static inline void gi_round_restore(gi_round_state state)
{
    __asm__ volatile("msr fpcr, %0" : : "r"(state) : "memory");
    __asm__ volatile("isb" : : : "memory");
}

static inline void gi_round_set(gi_round_direction direction)
{
    gi_round_state fpcr = gi_round_save();
    uint64_t rmode = direction == GI_ROUND_DOWN
        ? GI_AARCH64_FPCR_RMODE_MINUS_INF
        : GI_AARCH64_FPCR_RMODE_PLUS_INF;
    fpcr = (fpcr & ~GI_AARCH64_FPCR_RMODE_MASK) | rmode;
    gi_round_restore(fpcr);
}

static GI_NOINLINE double gi_raw_add(double a, double b)
{
    double result;
    __asm__ volatile("fadd %d0, %d1, %d2" : "=w"(result) : "w"(a), "w"(b));
    return result;
}

static GI_NOINLINE double gi_raw_sub(double a, double b)
{
    double result;
    __asm__ volatile("fsub %d0, %d1, %d2" : "=w"(result) : "w"(a), "w"(b));
    return result;
}

static GI_NOINLINE double gi_raw_mul(double a, double b)
{
    double result;
    __asm__ volatile("fmul %d0, %d1, %d2" : "=w"(result) : "w"(a), "w"(b));
    return result;
}

static GI_NOINLINE double gi_raw_div(double a, double b)
{
    double result;
    __asm__ volatile("fdiv %d0, %d1, %d2" : "=w"(result) : "w"(a), "w"(b));
    return result;
}

static GI_NOINLINE double gi_raw_sqrt(double a)
{
    double result;
    __asm__ volatile("fsqrt %d0, %d1" : "=w"(result) : "w"(a));
    return result;
}

#elif (defined(__i386__) || defined(__x86_64__)) && defined(__SSE__)

typedef struct {
    int fenv_round;
    unsigned int mxcsr;
} gi_round_state;

enum {
    GI_X86_MXCSR_RMODE_MASK = 0x6000u,
    GI_X86_MXCSR_RMODE_MINUS_INF = 0x2000u,
    GI_X86_MXCSR_RMODE_PLUS_INF = 0x4000u
};

static inline gi_round_state gi_round_save(void)
{
    return (gi_round_state){
        fegetround(),
        _mm_getcsr()
    };
}

static inline void gi_round_restore(gi_round_state state)
{
    unsigned int mxcsr = _mm_getcsr();
    (void)fesetround(state.fenv_round);
    mxcsr = (mxcsr & ~GI_X86_MXCSR_RMODE_MASK) |
        (state.mxcsr & GI_X86_MXCSR_RMODE_MASK);
    _mm_setcsr(mxcsr);
}

static inline void gi_round_set(gi_round_direction direction)
{
    unsigned int rmode = direction == GI_ROUND_DOWN
        ? GI_X86_MXCSR_RMODE_MINUS_INF
        : GI_X86_MXCSR_RMODE_PLUS_INF;
    unsigned int mxcsr = _mm_getcsr();
    (void)fesetround(direction == GI_ROUND_DOWN ? FE_DOWNWARD : FE_UPWARD);
    mxcsr = (mxcsr & ~GI_X86_MXCSR_RMODE_MASK) | rmode;
    _mm_setcsr(mxcsr);
}

static GI_NOINLINE double gi_raw_add(double a, double b)
{
    volatile double av = a;
    volatile double bv = b;
    return av + bv;
}

static GI_NOINLINE double gi_raw_sub(double a, double b)
{
    volatile double av = a;
    volatile double bv = b;
    return av - bv;
}

static GI_NOINLINE double gi_raw_mul(double a, double b)
{
    volatile double av = a;
    volatile double bv = b;
    return av * bv;
}

static GI_NOINLINE double gi_raw_div(double a, double b)
{
    volatile double av = a;
    volatile double bv = b;
    return av / bv;
}

static GI_NOINLINE double gi_raw_sqrt(double a)
{
    volatile double av = a;
    return sqrt(av);
}

#else

typedef int gi_round_state;

static inline gi_round_state gi_round_save(void)
{
    return fegetround();
}

static inline void gi_round_restore(gi_round_state state)
{
    (void)fesetround(state);
}

static inline void gi_round_set(gi_round_direction direction)
{
    (void)fesetround(direction == GI_ROUND_DOWN ? FE_DOWNWARD : FE_UPWARD);
}

static GI_NOINLINE double gi_raw_add(double a, double b)
{
    volatile double av = a;
    volatile double bv = b;
    return av + bv;
}

static GI_NOINLINE double gi_raw_sub(double a, double b)
{
    volatile double av = a;
    volatile double bv = b;
    return av - bv;
}

static GI_NOINLINE double gi_raw_mul(double a, double b)
{
    volatile double av = a;
    volatile double bv = b;
    return av * bv;
}

static GI_NOINLINE double gi_raw_div(double a, double b)
{
    volatile double av = a;
    volatile double bv = b;
    return av / bv;
}

static GI_NOINLINE double gi_raw_sqrt(double a)
{
    volatile double av = a;
    return sqrt(av);
}

#endif

static double gi_rounded_unary(double a, gi_round_direction direction, gi_unary_op op)
{
    gi_round_state old = gi_round_save();
    gi_round_set(direction);
    double result = op(a);
    gi_round_restore(old);
    return result;
}

static double gi_sqrt_down(double a)
{
    return gi_rounded_unary(a, GI_ROUND_DOWN, gi_raw_sqrt);
}

static double gi_sqrt_up(double a)
{
    return gi_rounded_unary(a, GI_ROUND_UP, gi_raw_sqrt);
}

static double gi_min_ignore_nan(double a, double b)
{
    if (isnan(a)) {
        return b;
    }
    if (isnan(b)) {
        return a;
    }
    /* C fmin/fmax do not guarantee an operand-order-independent zero sign.
       Keep the lower/upper endpoint convention explicit (Tupper 3.2.6 hull). */
    if (a == 0.0 && b == 0.0) {
        return signbit(a) || signbit(b) ? -0.0 : 0.0;
    }
    return fmin(a, b);
}

static double gi_max_ignore_nan(double a, double b)
{
    if (isnan(a)) {
        return b;
    }
    if (isnan(b)) {
        return a;
    }
    if (a == 0.0 && b == 0.0) {
        return signbit(a) && signbit(b) ? -0.0 : 0.0;
    }
    return fmax(a, b);
}

static bool gi_interval_is_zero(gi_interval x)
{
    return !gi_interval_is_empty(x) && x.lo == 0.0 && x.hi == 0.0;
}

static bool gi_interval_contains_zero(gi_interval x)
{
    return !gi_interval_is_empty(x) && x.lo <= 0.0 && 0.0 <= x.hi;
}

gi_interval gi_interval_make(double lo, double hi)
{
    if (isnan(lo) || isnan(hi) || lo > hi) {
        return gi_interval_empty();
    }
    return (gi_interval){lo, hi};
}

gi_interval gi_interval_point(double value)
{
    return gi_interval_make(value, value);
}

gi_interval gi_interval_empty(void)
{
    return (gi_interval){NAN, NAN};
}

gi_interval gi_interval_whole(void)
{
    return (gi_interval){-INFINITY, INFINITY};
}

bool gi_interval_is_empty(gi_interval x)
{
    return isnan(x.lo) || isnan(x.hi) || x.lo > x.hi;
}

bool gi_interval_contains(gi_interval x, double value)
{
    return !gi_interval_is_empty(x) && x.lo <= value && value <= x.hi;
}

/* Evaluate a lower/upper pair with one saved caller state. Each raw
   operation still runs under its required directed rounding mode. */
static gi_interval gi_binary_bounds(double lo_a, double lo_b,
                                   double hi_a, double hi_b, gi_binary_op op)
{
    gi_round_state old = gi_round_save();
    gi_round_set(GI_ROUND_DOWN);
    double lo = op(lo_a, lo_b);
    gi_round_set(GI_ROUND_UP);
    double hi = op(hi_a, hi_b);
    gi_round_restore(old);
    return gi_interval_make(lo, hi);
}

gi_interval gi_interval_add(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_interval_empty();
    }
    return gi_binary_bounds(x.lo, y.lo, x.hi, y.hi, gi_raw_add);
}

gi_interval gi_interval_sub(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_interval_empty();
    }
    return gi_binary_bounds(x.lo, y.hi, x.hi, y.lo, gi_raw_sub);
}

gi_interval gi_interval_mul(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_interval_empty();
    }
    if (gi_interval_is_zero(x) || gi_interval_is_zero(y)) {
        return gi_interval_point(0.0);
    }

    /* Tupper 3.2.25: sign sections determine the extremal corners.
       Internal zero boundaries add no extremum. Zero endpoints retain the
       all-corner path to preserve signed-zero ties; nonfinite endpoints retain
       its corner/NaN policy. */
    if (isfinite(x.lo) && isfinite(x.hi) && isfinite(y.lo) && isfinite(y.hi)
        && x.lo != 0.0 && x.hi != 0.0 && y.lo != 0.0 && y.hi != 0.0) {
        double lo_a, lo_b, hi_a, hi_b;
        if (x.lo >= 0.0) {
            if (y.lo >= 0.0) {
                lo_a = x.lo;
                lo_b = y.lo;
                hi_a = x.hi;
                hi_b = y.hi;
            } else if (y.hi <= 0.0) {
                lo_a = x.hi;
                lo_b = y.lo;
                hi_a = x.lo;
                hi_b = y.hi;
            } else {
                lo_a = x.hi;
                lo_b = y.lo;
                hi_a = x.hi;
                hi_b = y.hi;
            }
        } else if (x.hi <= 0.0) {
            if (y.lo >= 0.0) {
                lo_a = x.lo;
                lo_b = y.hi;
                hi_a = x.hi;
                hi_b = y.lo;
            } else if (y.hi <= 0.0) {
                lo_a = x.hi;
                lo_b = y.hi;
                hi_a = x.lo;
                hi_b = y.lo;
            } else {
                lo_a = x.lo;
                lo_b = y.hi;
                hi_a = x.lo;
                hi_b = y.lo;
            }
        } else {
            if (y.lo >= 0.0) {
                lo_a = x.lo;
                lo_b = y.hi;
                hi_a = x.hi;
                hi_b = y.hi;
            } else if (y.hi <= 0.0) {
                lo_a = x.hi;
                lo_b = y.lo;
                hi_a = x.lo;
                hi_b = y.lo;
            } else {
                gi_round_state old = gi_round_save();
                gi_round_set(GI_ROUND_DOWN);
                double lo = fmin(gi_raw_mul(x.lo, y.hi), gi_raw_mul(x.hi, y.lo));
                gi_round_set(GI_ROUND_UP);
                double hi = fmax(gi_raw_mul(x.lo, y.lo), gi_raw_mul(x.hi, y.hi));
                gi_round_restore(old);
                return gi_interval_make(lo, hi);
            }
        }
        return gi_binary_bounds(lo_a, lo_b, hi_a, hi_b, gi_raw_mul);
    }

    gi_round_state old = gi_round_save();
    gi_round_set(GI_ROUND_DOWN);
    double lows[] = {
        gi_raw_mul(x.lo, y.lo),
        gi_raw_mul(x.lo, y.hi),
        gi_raw_mul(x.hi, y.lo),
        gi_raw_mul(x.hi, y.hi)
    };
    gi_round_set(GI_ROUND_UP);
    double highs[] = {
        gi_raw_mul(x.lo, y.lo),
        gi_raw_mul(x.lo, y.hi),
        gi_raw_mul(x.hi, y.lo),
        gi_raw_mul(x.hi, y.hi)
    };
    gi_round_restore(old);

    double lo = lows[0];
    double hi = highs[0];
    for (int i = 1; i < 4; ++i) {
        lo = gi_min_ignore_nan(lo, lows[i]);
        hi = gi_max_ignore_nan(hi, highs[i]);
    }
    if (isnan(lo) || isnan(hi)) {
        return gi_interval_whole();
    }
    return gi_interval_make(lo, hi);
}

gi_interval gi_interval_div(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_interval_empty();
    }
    if (gi_interval_contains_zero(y)) {
        return gi_interval_whole();
    }

    gi_interval reciprocal = gi_binary_bounds(1.0, y.hi, 1.0, y.lo, gi_raw_div);
    return gi_interval_mul(x, reciprocal);
}

gi_interval gi_interval_min(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_interval_empty();
    }

    double lo = fmin(x.lo, y.lo);
    double hi = fmin(x.hi, y.hi);
    if (lo == 0.0) {
        lo = 0.0;
    }
    if (hi == 0.0) {
        hi = 0.0;
    }
    return gi_interval_make(lo, hi);
}

gi_interval gi_interval_max(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_interval_empty();
    }

    double lo = fmax(x.lo, y.lo);
    double hi = fmax(x.hi, y.hi);
    if (lo == 0.0) {
        lo = 0.0;
    }
    if (hi == 0.0) {
        hi = 0.0;
    }
    return gi_interval_make(lo, hi);
}

gi_interval gi_interval_sqrt(gi_interval x)
{
    if (gi_interval_is_empty(x) || x.hi < 0.0) {
        return gi_interval_empty();
    }

    double lo = x.lo <= 0.0 ? 0.0 : gi_sqrt_down(x.lo);
    double hi = gi_sqrt_up(x.hi);
    return gi_interval_make(lo, hi);
}

gi_interval gi_interval_neg(gi_interval x)
{
    if (gi_interval_is_empty(x)) {
        return gi_interval_empty();
    }
    return gi_interval_make(-x.hi, -x.lo);
}

gi_interval gi_interval_abs(gi_interval x)
{
    /* Tupper 3.2.10–3.2.14: reflect/select monotone endpoints, with a
     * known minimum of zero when the input contains zero. These operations
     * are exact; fabs also gives every zero magnitude a positive sign. */
    if (gi_interval_is_empty(x)) {
        return gi_interval_empty();
    }
    if (x.hi <= 0.0) {
        return gi_interval_make(fabs(x.hi), fabs(x.lo));
    }
    if (x.lo >= 0.0) {
        return gi_interval_make(fabs(x.lo), x.hi);
    }
    return gi_interval_make(0.0, fmax(-x.lo, x.hi));
}

gi_interval gi_interval_floor(gi_interval x)
{
    if (gi_interval_is_empty(x)) {
        return gi_interval_empty();
    }

    double lo = floor(x.lo);
    double hi = floor(x.hi);
    if (lo == 0.0) {
        lo = 0.0;
    }
    if (hi == 0.0) {
        hi = 0.0;
    }
    return gi_interval_make(lo, hi);
}

gi_interval gi_interval_ceil(gi_interval x)
{
    if (gi_interval_is_empty(x)) {
        return gi_interval_empty();
    }

    double lo = ceil(x.lo);
    double hi = ceil(x.hi);
    if (lo == 0.0) {
        lo = 0.0;
    }
    if (hi == 0.0) {
        hi = 0.0;
    }
    return gi_interval_make(lo, hi);
}

gi_interval gi_interval_factorial(gi_interval x)
{
    double lo;
    double hi;
    mpfr_t lower;
    mpfr_t upper;

    if (gi_interval_is_empty(x) || x.lo != x.hi || !isfinite(x.lo)
        || x.lo < 0.0 || trunc(x.lo) != x.lo) {
        return gi_interval_empty();
    }
    if (x.lo > GI_INTERVAL_MAX_FINITE_FACTORIAL_INPUT) {
        return gi_interval_make(DBL_MAX, INFINITY);
    }

    mpfr_inits2(GI_INTERVAL_MPFR_PRECISION, lower, upper, (mpfr_ptr)0);
    mpfr_fac_ui(lower, (unsigned long)x.lo, MPFR_RNDD);
    mpfr_fac_ui(upper, (unsigned long)x.lo, MPFR_RNDU);
    lo = mpfr_get_d(lower, MPFR_RNDD);
    hi = mpfr_get_d(upper, MPFR_RNDU);
    mpfr_clears(lower, upper, (mpfr_ptr)0);
    return gi_interval_make(lo, hi);
}

static gi_interval gi_interval_pow_point(double value, uint32_t exponent)
{
    double lo;
    double hi;
    mpfr_t argument;
    mpfr_t lower;
    mpfr_t upper;

    mpfr_inits2(
        GI_INTERVAL_MPFR_PRECISION,
        argument,
        lower,
        upper,
        (mpfr_ptr)0);
    mpfr_set_d(argument, fabs(value), MPFR_RNDN);
    mpfr_pow_ui(lower, argument, exponent, MPFR_RNDD);
    mpfr_pow_ui(upper, argument, exponent, MPFR_RNDU);
    lo = mpfr_get_d(lower, MPFR_RNDD);
    hi = mpfr_get_d(upper, MPFR_RNDU);
    mpfr_clears(argument, lower, upper, (mpfr_ptr)0);
    if (signbit(value) && (exponent & 1u) != 0) {
        return gi_interval_make(-hi, -lo);
    }
    return gi_interval_make(lo, hi);
}

gi_interval gi_interval_pow_nonnegative_integer_exponent(gi_interval x, uint32_t exponent)
{
    if (gi_interval_is_empty(x)) {
        return gi_interval_empty();
    }
    if (exponent > GI_INTERVAL_MAX_INTEGER_POWER) {
        return gi_interval_whole();
    }
    if (exponent == 0) {
        return gi_interval_point(1.0);
    }
    if (exponent == 1) {
        return x;
    }

    if ((exponent & 1u) != 0) {
        gi_interval lo = gi_interval_pow_point(x.lo, exponent);
        gi_interval hi = gi_interval_pow_point(x.hi, exponent);
        return gi_interval_make(lo.lo, hi.hi);
    }

    if (x.hi <= 0.0) {
        gi_interval lo = gi_interval_pow_point(x.hi, exponent);
        gi_interval hi = gi_interval_pow_point(x.lo, exponent);
        return gi_interval_make(lo.lo, hi.hi);
    }
    if (x.lo >= 0.0) {
        gi_interval lo = gi_interval_pow_point(x.lo, exponent);
        gi_interval hi = gi_interval_pow_point(x.hi, exponent);
        return gi_interval_make(lo.lo, hi.hi);
    }

    gi_interval left = gi_interval_pow_point(x.lo, exponent);
    gi_interval right = gi_interval_pow_point(x.hi, exponent);
    return gi_interval_make(0.0, fmax(left.hi, right.hi));
}

gi_interval gi_interval_hull(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x)) {
        return y;
    }
    if (gi_interval_is_empty(y)) {
        return x;
    }
    return gi_interval_make(
        gi_min_ignore_nan(x.lo, y.lo), gi_max_ignore_nan(x.hi, y.hi));
}

gi_interval gi_interval_intersect(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_interval_empty();
    }
    return gi_interval_make(fmax(x.lo, y.lo), fmin(x.hi, y.hi));
}

gi_bool_interval gi_interval_gt(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_bool_make(false, false);
    }
    return gi_bool_make(x.lo > y.hi, x.hi > y.lo);
}

gi_bool_interval gi_interval_ge(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_bool_make(false, false);
    }
    return gi_bool_make(x.lo >= y.hi, x.hi >= y.lo);
}

gi_bool_interval gi_interval_lt(gi_interval x, gi_interval y)
{
    return gi_interval_gt(y, x);
}

gi_bool_interval gi_interval_le(gi_interval x, gi_interval y)
{
    return gi_interval_ge(y, x);
}

gi_bool_interval gi_interval_eq(gi_interval x, gi_interval y)
{
    if (gi_interval_is_empty(x) || gi_interval_is_empty(y)) {
        return gi_bool_make(false, false);
    }
    bool possibly_equal = fmax(x.lo, y.lo) <= fmin(x.hi, y.hi);
    bool definitely_equal = x.lo == x.hi && y.lo == y.hi && x.lo == y.lo;
    return gi_bool_make(definitely_equal, possibly_equal);
}

gi_bool_interval gi_bool_make(bool lo, bool hi)
{
    return (gi_bool_interval){lo && hi, lo || hi};
}

gi_bool_interval gi_bool_not(gi_bool_interval x)
{
    return gi_bool_make(!x.hi, !x.lo);
}

gi_bool_interval gi_bool_and(gi_bool_interval x, gi_bool_interval y)
{
    return gi_bool_make(x.lo && y.lo, x.hi && y.hi);
}

gi_bool_interval gi_bool_or(gi_bool_interval x, gi_bool_interval y)
{
    return gi_bool_make(x.lo || y.lo, x.hi || y.hi);
}

uint64_t gi_kernel_abi_descriptor(void)
{
    _Static_assert(_Alignof(gi_interval) <= UINT8_MAX
        && _Alignof(gi_bool_interval) <= UINT8_MAX,
        "graphing ABI alignments must fit one byte");
    return (UINT64_C(0x47) << 56) | (UINT64_C(1) << 48)
        | ((uint64_t)sizeof(gi_interval) << 40)
        | ((uint64_t)_Alignof(gi_interval) << 32)
        | ((uint64_t)offsetof(gi_interval, hi) << 24)
        | ((uint64_t)sizeof(gi_bool_interval) << 16)
        | ((uint64_t)_Alignof(gi_bool_interval) << 8)
        | (uint64_t)offsetof(gi_bool_interval, hi);
}

uint32_t gi_kernel_numeric_contract_check(void)
{
    fenv_t saved;
    fenv_t held;
    if (fegetenv(&saved) != 0) {
        return 0;
    }
    if (feholdexcept(&held) != 0) {
        (void)fesetenv(&saved);
        return 0;
    }
    gi_interval outward = gi_interval_add(
        gi_interval_point(1.0), gi_interval_point(0x1p-53));
    gi_interval tiny = gi_interval_add(
        gi_interval_point(0.0), gi_interval_point(DBL_TRUE_MIN));
    gi_interval negative_zero = gi_interval_point(-0.0);
    gi_interval negative = gi_interval_neg(gi_interval_point(0.0));
    gi_interval invalid = gi_interval_make(NAN, 1.0);
    gi_interval zero_divisor = gi_interval_div(
        gi_interval_point(1.0), gi_interval_point(0.0));
    uint64_t tiny_lo, tiny_hi;
    memcpy(&tiny_lo, &tiny.lo, sizeof(tiny_lo));
    memcpy(&tiny_hi, &tiny.hi, sizeof(tiny_hi));
    bool valid = outward.lo == 1.0 && outward.hi == 0x1.0000000000001p0
        && tiny_lo == UINT64_C(1) && tiny_hi == UINT64_C(1)
        && signbit(negative_zero.lo) && signbit(negative_zero.hi)
        && signbit(negative.lo) && signbit(negative.hi)
        && gi_interval_is_empty(invalid)
        && gi_interval_is_empty(gi_interval_empty())
        && gi_interval_is_empty(gi_interval_sqrt(gi_interval_point(-1.0)))
        && zero_divisor.lo == -INFINITY && zero_divisor.hi == INFINITY;
    if (fesetenv(&saved) != 0) {
        return 0;
    }
    return valid ? 1u : 0u;
}
