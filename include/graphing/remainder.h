/* Copyright (c) 2026 John Funge
 * SPDX-License-Identifier: AGPL-3.0-only
 */

#ifndef GRAPHING_REMAINDER_H
#define GRAPHING_REMAINDER_H

#include "graphing/interval.h"

/*
 * A finite binary64 quotient can require just over 2,098 integer bits.  This
 * leaves room for that quotient and both 53-bit operands, so the reduction is
 * exact before its final directed binary64 demotion.
 */
enum {
    GI_REMAINDER_MPFR_PRECISION = 2304
};

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Enclose the positive remainder of two finite binary64 points exactly:
 *
 *     dividend - floor(dividend / |divisor|) * |divisor|
 *
 * A zero divisor or nonfinite operand returns the empty interval.  Exact zero
 * is canonicalized to positive zero.  The wider interval policy and domain /
 * continuity metadata remain evaluator responsibilities.
 */
gi_interval gi_remainder_mod_point(double dividend, double divisor);

/*
 * Return the exact conventional truncating remainder of two finite binary64
 * points:
 *
 *     dividend - trunc(dividend / |divisor|) * |divisor|
 *
 * A zero divisor or nonfinite operand returns the empty interval.  The exact
 * result is representable in binary64 when subnormals are supported; exact
 * zero preserves the dividend's sign.  Wider interval/domain/continuity
 * policy remains an evaluator responsibility.
 */
gi_interval gi_remainder_fmod_point(double dividend, double divisor);

#ifdef __cplusplus
}
#endif

#endif
