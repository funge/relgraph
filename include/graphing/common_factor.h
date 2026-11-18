/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#ifndef GRAPHING_COMMON_FACTOR_H
#define GRAPHING_COMMON_FACTOR_H

#include "graphing/interval.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Treat each finite binary64 operand as an exact reduced rational.  Return
 * the outward binary64 enclosure of the greatest common real divisor.
 * Nonfinite operands return the empty interval; exact zero is positive zero.
 */
gi_interval gi_common_factor_gcd_point(double left, double right);

/*
 * Treat each finite binary64 operand as an exact reduced rational.  Return
 * the outward binary64 enclosure of their least common real multiple.
 * Nonfinite operands return the empty interval; either zero operand returns
 * positive zero.
 */
gi_interval gi_common_factor_lcm_point(double left, double right);

/*
 * Optional upper refinement for gcd(a, unit), a in the finite closed span.
 * Preconditions for a certified result: current_upper is a sound nonnegative
 * upper (or +infinity); unit is an exact finite nonzero binary64 point.
 * Returns min(current_upper, upward bound) from exact divisor sections n<=16.
 * Unsupported/empty inputs or an unavailable arithmetic context return the
 * original bound unchanged. Invalid negative/NaN caller bounds are unchanged,
 * not repaired or certified. Signed-zero fallback bits are retained.
 * No lower bound, definedness or continuity is established. Hardware fenv is
 * preserved on supported platforms; MPFR flags remain scratch state.
 */
double gi_common_factor_gcd_unit_upper(
    gi_interval span, double unit, double current_upper);

#ifdef __cplusplus
}
#endif

#endif
