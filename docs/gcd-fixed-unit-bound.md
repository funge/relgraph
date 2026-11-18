# fixed-unit greatest-common-factor upper refinement

This optional primitive refines an existing sound upper bound. It is not a
standalone GCD evaluator, a domain or continuity certificate, or a renderer proof.
The scalar API keeps GMP/MPFR ownership in `common_factor.c` and exposes no new
numeric representation. The original exact-point APIs remain unchanged.

## source and theorem

Tupper's thesis section 4.9 defines the greatest common real-valued divisor;
the installed GrafEq manual B.3 has the same real-valued convention. For fixed
nonzero q, write Q=abs(q). Every positive common divisor is Q/n for a positive
integer n, at an argument a=Q*k/n. For a closed interval A, a section at n meets
A exactly when ceil(A.lo*n/Q)<=floor(A.hi*n/Q).

Search n=1..16 in ascending order. The first hit attains maximal Q/n. A reduced
ratio with a smaller denominator would have hit earlier, so no coprimality test
is necessary. If all sixteen miss, every positive GCD is at most Q/17. Irrational
ratios contribute zero. A containing zero hits n=1, retaining gcd(0,q)=Q.
This construction sharpens the existing enclosure under its stated fixed-unit
conditions; it does not change the operation's mathematical meaning.

## contract and native bounds

`gi_common_factor_gcd_unit_upper(span, unit, current_upper)` accepts a caller's
sound nonnegative upper bound (including positive infinity). It returns the
smaller of that argument and the upward binary64 demotion of the bound above.
It cannot validate or repair an unsound caller bound. Negative or NaN bounds are
invalid caller inputs and returned unchanged. Zero, including negative zero, is
returned unchanged. Unsupported/empty/nonfinite spans and nonfinite/zero units
return the original argument directly. No epsilon comparisons or nearest-rounded
quotient tests are used.

Finite endpoints and the unit are exact binary64 dyadics. GMP conversion and
signed integer ceil/floor are exact. The loop has sixteen iterations. Endpoint
numerators/denominators use at most 1075 bits; forming endpoint*n/Q uses at most
2155 bits before normalization, below a conservative 4096-bit operation bound.
This is a fixed-size primitive, not an unbounded search or allocation policy.
The no-hit Q/17 result is a proved completed branch, not an unsupported exhaustion
case. Final demotion reuses explicit 53-bit MPFR values and directed rounding.
No MPFR defaults or exponent limits are changed; sticky MPFR flags retain their
existing scratch-state contract. Hardware fenv is saved/restored, including
rounding and exception flags; failure to obtain/restore a supported fenv declines
the refinement. The restoration guarantee assumes successful fenv services;
returning the old numerical bound after a failed `fesetenv` does not assert that
an unsupported platform restored its environment. The returned upper may remain broad under unsupported arithmetic
contexts. No additional precision escalation or new backend is introduced.

## consumer and qualification boundary

An embedding caller must retain its all-point path and existing lower/domain/
continuity metadata. The initial application design is binary fixed-unit only,
intersected with the old upper. No variadic extension or pin update follows from
standalone tests. Native optimized/debug/sanitizer suites, independent exact
rational interval oracle and arithmetic-context tests are required before a
consumer candidate. The application still pins its earlier immutable snapshot;
current main's license/build changes require separate integration disposition.

## local qualification

Product revision `13d7d3a8976fb48bdc3d8fc725f328b51370a7e1` passed the
optimized, debug and ASan/UBSan native matrix on Apple arm64 (Apple Clang 21,
GMP 6.3.0, MPFR 4.2.2). The independent black-box oracle checked 2,410
interval/fallback obligations in each mode, with identical output bits. Tests
include directed conversion, signed endpoints, huge/subnormal units, invalid
inputs, hardware rounding modes/exception flags and MPFR context preservation.
See [the compact receipt](gcd-fixed-unit-bound-qualification.json).

This is standalone native evidence. External consumer bridge observations are
exploratory and do not qualify a changed application pin. Application adoption
requires its own locked-input, domain/protocol, replay and worker checks.
