<!-- Copyright (c) 2026 John Funge -->
<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# experimental numeric evaluation primitives

The `relgraph_eval` package now includes cache-free interval covers and general
operator composition. This is an experimental implementation interface, not a
complete expression evaluator or a stable Python extension/AST ABI.

## owners and caller contract

`numeric_api` describes the configured C ABI and structural numeric operations.
`numeric` owns interval section/boundary/cover records, exact rational endpoint
conversion, periodic and nonzero-domain covers, integer/discrete/remainder/power
sections, rational roots and self-power magnitude bounds. `operations` extends
the numeric protocol with diagnostic and periodic-cover callbacks plus result
and set factory signatures.

`functions` contains seven operator families: elementary, powers, periodic,
remainders, common factors, atan2 and conservative fallback. Their operands are
already evaluated scalar/branch-set records. They do not parse or dispatch ASTs.
Existing value metadata, shared-choice compatibility and branch grouping remain
unchanged. The discrete policy dispatcher, source-aware division and sinc
certification are outside this interface.

The caller must locate and validate a compatible native library and configure
all ctypes signatures before supplying `lib`. Numeric methods must return
certified outward binary64 enclosures with the established empty/domain rules.
Some composition routines call the configured C functions directly. Protocols
check shapes only; they neither load a library nor certify a backend. There is
no automatic approximate fallback. Importing these modules requires only the
standard library and other modules in this package.

Periodic-cover caching, diagnostic storage, interruption ownership, source
bindings and application options belong to the caller. A periodic-cover callback
must preserve the cache-free function's sections and metadata. Diagnostic
callbacks may be no-ops, but their invocation order and exceptions are retained.
Result factories retain positional/keyword calls and object identity; they are
not interchangeable with arbitrary serialization or reconstruction.

## domain and uncertainty rules

Cover sections include real gaps between adjacent binary64 endpoints. At a pole,
closed one-sided enclosures can contain the excluded endpoint while partial
and discontinuous metadata prevents treating it as a defined witness. Exceeding
a section budget conservatively returns the existing unsplit cover. Branch cuts,
zero denominators, invalid elementary domains and inherited argument domains
retain their current behavior. Unknown functions produce a universal value cover
with uncertain definedness; certainly undefined arguments remain excluded.

No proof search, cell classification, cache/profile policy, renderer behavior,
source simplification or native pin change is part of this transfer. Values and
charts have the obligations and limits described in [value algebra](value-algebra.md).
In particular, absent witnesses do not prove absence and lost provenance does
not allow regrouping expressions.

## provenance and checks

The numerical bodies are mechanically transferred project-owned code by John
Funge, licensed AGPL-3.0-only. No algorithm or numerical policy is changed, and
no formal verification is claimed. New tests are original redistributable
fixtures, independent of any application or private corpus.

Run `make all test` with supported Python, or:

```sh
PYTHONPATH=python python3 -m unittest discover -s tests -p test_numeric_evaluation.py
```

The intentionally restricted exact fixture backend checks rational endpoints,
power enclosures, real covers, pole tails, domains, shared choices, callback
identity/errors and import isolation. It is not a production numeric backend.
Native/application integration and distribution qualification remain required
for each consumer adoption.
