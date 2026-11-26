# exact integer and rational inputs

The four constructors in `graphing/interval.h` accept exact values before any
binary64 rounding:

| function | input meaning |
| --- | --- |
| `gi_interval_from_int64(n)` | exact signed 64-bit integer point |
| `gi_interval_from_int64_bounds(lo, hi)` | closed interval with exact signed integer bounds |
| `gi_interval_from_rational64(n, d)` | exact rational point `n/d` |
| `gi_interval_from_rational64_bounds(ln, ld, hn, hd)` | closed interval `[ln/ld, hn/hd]` |

Numerators are `int64_t`; denominators are `uint64_t` and must be positive.
Unreduced fractions are accepted. The sign belongs in the numerator; negative
signed denominators must be normalized by the caller before entering this API,
not cast to unsigned. Zero denominators and reversed **exact** bounds return
`gi_interval_empty()`. A returned empty interval is invalid input, not a valid
numeric point. This interface supplies no separate error code. Equal exact
bounds are allowed, including differently written fractions such as `2/6` and
`1/3`. Exact zero returns two positive zero endpoints; integer/rational inputs
have no negative-zero distinction.

For valid input `[a,b]`, the result is `[down(a), up(b)]`: the greatest binary64
value at most `a` and the least binary64 value at least `b`. Thus it is the least
closed binary64 enclosure, not merely a sound overestimate. Exact dyadics that
fit binary64 remain points. For example:

```c
gi_interval a = gi_interval_from_int64(INT64_C(9007199254740993));
/* a = [9007199254740992, 9007199254740994] */
gi_interval b = gi_interval_from_rational64(-3, 8);
/* b = [-0.375, -0.375] */
gi_interval c = gi_interval_from_rational64_bounds(-1, 3, 1, 10);
/* c encloses the exact closed interval [-1/3, 1/10]. */
```

`gi_interval_point(double)` and `gi_interval_make(double,double)` retain their
existing meaning: the doubles already supplied by the caller. Passing an integer
through a double cast, or dividing two nearest-rounded doubles before using
those constructors, can lose the original exact value. These new constructors
do not take that route.

## conversion and range argument

The implementation imports the fixed-width integer words into GMP rationals,
without assuming that C `long` has 64 bits and without signed negation of
`INT64_MIN`. It validates ordering with exact rational comparison; even reversed
bounds that would round to the same double are rejected.

GMP's [`mpq_get_d`](https://gmplib.org/manual/Converting-Rationals) specifies
truncation toward zero. The implementation compares that double's exact rational
value with the input and uses `nextafter` once only when the requested outward
endpoint differs. For a positive inexact value truncation is already the lower
neighbor; for a negative one it is the upper neighbor. The other endpoint is
adjacent. Exact values require no step. This gives both enclosure and endpoint
optimality without first constructing a nearest-rounded pair. GMP rational
comparison and import simplify exact ordering and signed-width portability; no
additional dependency or public GMP/MPFR object is introduced.

Every nonzero supported input satisfies
`1/(2^64-1) <= |n/d| <= 2^63`. In particular it is greater than `2^-64`, and its
outward endpoints are finite normal binary64 values. Overflow, nonzero
subnormal results, underflow to zero, and GMP's documented out-of-range
conversion behavior are unreachable in this format. The maximum signed
numerator is `2^63-1`; `INT64_MIN` supplies the negative magnitude `2^63`.
The extreme denominator and numerator cases are tested. Extending the input
format would require a new range argument and new overflow/subnormal tests.

Results are independent of the caller's four standard rounding modes, which
are not changed. These constructors do not use MPFR and therefore do not depend
on its precision, exponent limits, rounding default or flags. No new guarantee
about hardware exception flags is made. Existing supported compiler/binary64
requirements continue to apply. GMP allocations follow the dependency's normal
allocation-failure behavior; this API adds no recoverable allocation status.

## provenance, specification and validation

This is a new implementation for the public numeric library. It uses the
outward scalar rounding interpretation described in the
[numeric contract](numeric-contract.md), rather than a parser or app adapter.
The mathematical target is GIA's pinned
[`DiscreteDemotion.lean`](https://github.com/funge/gia/blob/2ecbb161bd136fd2ad51c432c0e70dc62b668ed1/DiscreteDemotion.lean)
and its [specification](https://github.com/funge/gia/blob/2ecbb161bd136fd2ad51c432c0e70dc62b668ed1/DISCRETE_DEMOTION.md):
`down_greatest`, `up_least`, and `least` describe extremal endpoints and least
outward hulls, including the finite binary64 value family. The related
[`EndpointOptimality.lean` specification](https://github.com/funge/gia/blob/2ecbb161bd136fd2ad51c432c0e70dc62b668ed1/ENDPOINT_OPTIMALITY.md)
characterizes when sound decoded endpoints equal that least hull; its
`interval_exact_iff` specializes to ordered closed ideal intervals. These are
mathematical results, **not a proof of this C implementation**, GMP, the compiler, native
bit transport or `nextafter`. No Lean build or runtime dependency is added.

`tests/test_exact_inputs.c` builds an independent exact oracle from decimal
integer strings and raw binary64 sign/exponent/significand decoding. It does not
use the implementation's `mpz_import`, `mpq_get_d` or `mpq_set_d` path. GMP exact
arithmetic remains a shared trusted dependency. For each valid endpoint it checks
outward order and proves that its inward adjacent double would exclude the exact
bound. The suite covers integer ties above `2^53`, binade transitions, signed
extremes, fractions of both signs, exact dyadics, zero, unreduced equal bounds,
invalid denominators and exact reversed bounds, plus deterministic full-width
samples in all four standard rounding modes. Run it through `make test-c` or the
usual `make all test`; it participates in native qualification modes.

## follow-ons and non-goals

Decimal strings, arbitrary-size integers/rationals and an optional MPFR adapter
are follow-ons. They need explicit input syntax, lifetime/error contracts, and
range/overflow/subnormal behavior; they must not silently narrow through this
fixed-width format. This change does not add a parser, graphing/app integration,
consumer dependency update, general expression evaluator, new arithmetic
operations or formal C verification. No performance guarantee is claimed.
