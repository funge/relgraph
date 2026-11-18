# Numeric C library contract

The numeric library supplies certified binary64 interval bounds. It is not a
formula parser, expression evaluator or graph renderer. A numeric enclosure does
not by itself establish continuity, totality, a domain, or an existence proof.
Callers retain those responsibilities and must keep unresolved results honest.

## Interface and representation

Public headers live under `include/graphing/`. Keep the `gi_` C names and public
structure layouts stable within a qualified consumer revision. `gi_interval`
contains two binary64 endpoints; finite point arguments denote their exact
binary64 values. `gi_bool_interval` represents bounded Boolean information.
Headers do not expose GMP or MPFR object types. NaN/empty, infinity, signed-zero,
domain and operation-specific preconditions are documented by the declarations
and tested in the corresponding native suites; do not replace them with epsilon
snapping or ordinary nearest-rounded scalar arithmetic.

`gi_kernel_abi_descriptor` and `gi_kernel_numeric_contract_check` allow an
embedding boundary to reject an incompatible ABI or unsupported arithmetic
context before numerical use. They do not prove every operation correct.

## Arithmetic owners

| Owner | Responsibility |
| --- | --- |
| `interval.c` | Basic arithmetic uses directed binary64 operations with saved/restored rounding state. Factorial and bounded nonnegative integer powers use MPFR 256-bit intermediates and outward conversion. |
| `transcendental.c` | Provided transcendental/phase kernels use explicitly requested MPFR 256-bit values and directed conversion to binary64 bounds. |
| `remainder.c` | Exact finite-binary64 point reduction uses 2304-bit MPFR values to preserve full quotients and operands. Positive remainder demotes outward; truncating remainder preserves its exact representable result and dividend zero sign. |
| `common_factor.c` | GMP rational/integer operations form exact common factors of finite binary64 points and bounded fixed-unit upper refinements; MPFR 53-bit values perform final directed rational conversion. |

Requested object precision is not an internal memory, time or working-precision
ceiling. These operations do not make an entire caller expression arbitrary
precision. The numerical owners do not change MPFR exponent limits or its default
precision/rounding configuration. MPFR sticky exception flags are scratch state,
not a preserved caller interface. Callers must retain MPFR startup exponent limits
for the transcendental kernels, as required by `include/graphing/transcendental.h`.
Hardware rounding-state behavior remains operation-specific as described above
and in the public headers; embeddings must maintain a compatible thread arithmetic
context rather than relying on the bootstrap check to certify later changes.

The external Python renderer from which this library was extracted uses
`FE_TONEAREST` between calls and retains MPFR startup exponent limits throughout
rendering. That is historical context for an external embedding policy, not an
in-repository Python API or an additional implementation supplied by this library.
Its renderer/cache responsibilities are outside this standalone contract.

## Reference grounding

The mathematical foundation is Jeffrey Allen Tupper, *Graphing Equations with
Generalized Interval Arithmetic* (MSc, University of Toronto, 1996), and *Reliable
Two-Dimensional Graphing Methods for Mathematical Formulae with Two Free
Variables* (SIGGRAPH, 2001), linked from the README. Their interval and provided
rounded-function constructions require outward enclosure and faithful domain,
continuity and argument-reduction conditions. The initial extraction changed ownership
and build paths only, preserving the four C owners, public interfaces and native
tests. It introduced no sharper bounds, new domain interpretation or proof
algorithm. Independent tests remain necessary; source fidelity alone does not
establish implementation correctness.

## Validation

Run all four native suites in optimized, debug and address/undefined sanitizer
modes. Retain endpoint/domain/signed-zero, exact-point, enclosure and numeric
context controls. Consumers additionally validate ABI/layout, environment error
handling and their complete rendering/classification behavior. Platform-specific
cross-compilation validates packaging, not execution on that physical device.


## optional fixed-unit GCD refinement

The [fixed-unit upper primitive](gcd-fixed-unit-bound.md) is a subsequent bounded
refinement, separate from the initial extraction. It conditionally preserves an
existing sound upper, retains unsupported cases unchanged and does not certify
definedness or continuity. Consumer dependency and release adoption remain
separate from native qualification.
