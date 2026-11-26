# Building and embedding the numeric library

Requirements: a supported direct GCC or Clang C compiler, GNU-compatible Make,
Python 3 for build tracking, GMP and MPFR development headers/libraries. Current
application packaging pins GMP 6.3.0 and MPFR 4.2.2; see third-party notices.

```sh
make all test
bash tools/native-numerical-qualification.sh
```

`all` builds static and shared `libgraphing` libraries; `shared` builds only the
shared product; `test` runs the brand-copy checks and all five native suites. `test-c` runs
only the native suites, including exact-input enclosure and optimality tests. `BUILD_DIR` may select a
separate output directory. `MPFR_PREFIX` and `GMP_PREFIX` select dependency
installations; Homebrew prefixes are detected on macOS when available.

The Makefile rejects unsupported fast-math, opaque compiler/plugin/response-file
and late assertion-disable flags. It appends C11, rounding-safe options,
`-ffp-contract=off`, PIC and `-UNDEBUG`. Do not bypass these checks in embedding
builds. Compiler-discovered dependency files include transitive/system headers.
A configuration record invalidates known products when effective flags, compiler,
GMP/MPFR installation, relevant environment or Makefile content changes.

An embedding Makefile may set `KERNEL_ROOT` and include this Makefile. Set include
paths, dependency prefixes and optional `BENCHMARK_OBJECTS`/`BENCHMARK_LIB` before
including it so configuration tracking observes the full product set. The root
and included Makefiles are hashed. Add consumer-only benchmark rules afterward.
The library itself has no benchmark source dependency. Relative paths are resolved
from the invoking working directory. Use absolute BUILD_DIR for cross-builds.

Explicit `INTERVAL_SOURCE`, `COMMON_FACTOR_SOURCE`, `REMAINDER_SOURCE` and
`TRANSCENDENTAL_SOURCE` overrides support controlled tests; they are tracked build
inputs, not an automatic compatibility or mathematical-correctness guarantee.
Keep altered test sources outside the pinned dependency and qualify the actual
production sources separately.

A downstream repository must pin an immutable library revision, verify its
integrity and preserve the source identity in release evidence. Builds must not
silently fetch a moving branch. Authentication while this repository is private
uses the owner's ordinary Git setup, not committed credentials. Binary packaging
is consumer-owned; no prebuilt binary distribution or new platform guarantee is
implied by this source extraction.


The standalone brand checks resolve their tool/test paths through `KERNEL_ROOT`,
so the documented embedded Makefile invocation does not scan the consumer's
pages or assume its working directory is the library root. This does not add
formalization checks to the numeric target.
