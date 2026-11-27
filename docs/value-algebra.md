<!-- Copyright (c) 2026 John Funge -->
<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# experimental headless value algebra

The `relgraph_eval` package includes shared value algebra below expression
execution and proof policy. These are experimental Python implementation
interfaces, including their underscore-prefixed names; no stable Python AST,
record, serialization or extension ABI is promised.

## scope and dependency direction

- `values`: the two-double ctypes interval layout and frozen result, branch-set,
  chart and exact/witness metadata records.
- `scalars`: exact metadata admission, directed rational endpoints and signed-zero
  aware interval keys.
- `metadata`: affine, quadratic, reciprocal-affine, constant and interval-affine
  metadata algebra.
- `charts`: intersections and contained preimage witnesses for supported metadata.
- `sets`: branch construction, domain predicates and bounded value compaction.
- `arithmetic`: shared scalar/set operations with branch compatibility and ordered
  diagnostic callbacks.
- `comparisons`: strict interval and compatible-branch comparisons.
- `operations`: the structural protocol supplied by the numerical caller.

Imports require only the standard library and the existing branch/definedness
modules. They do not load a native library, parser, application or renderer.
The records use the same interval layout as the C interface, but this package
does not locate or bind that interface. The caller supplies a backend; there is
no fallback numerical implementation.

## caller obligations and preserved limits

Backend operations must supply outward enclosures, consistent empty-interval
handling, strict comparisons and a certified square root. The protocol describes
method shapes, not a runtime proof of those properties. Diagnostic methods must
be provided (they may be no-ops); their call order and propagated exceptions are
part of the current implementation. Inputs must carry sound metadata and chart
certificates. Frozen dataclasses do not make their ctypes interval payloads
immutable: callers must not mutate values retained by an evaluation.

Exact affine/quadratic/constant annotations are admitted only when exactly
representable as finite binary64. Optional power metadata is bounded to exponent
magnitude 32; interval-affine slopes are bounded to 4096 bits. Losing metadata is
a conservative fallback. Interval-affine metadata is a witness aid, not an exact
identity or an exhaustive domain cover.

At most eight value components survive compaction; a larger union falls back to
a hull. Compaction can forget source charts, structural metadata and branch
provenance. It does not justify regrouping operations: provenance forgetting is
not the same as a conflicting merge (`None`). Retain the caller's existing
operation grouping, branch order and definedness/continuity rules.

Charts returned for restricted sections are contained witnesses. They can be
absent even when an expression has valid points. An absent chart is not proof of
absence. Strict comparisons on empty values, including not-equal, are false;
uncertain definedness prevents a definite set relation. No cell classification,
proof search, source-domain simplification or rendering policy is implemented
here. In particular, arithmetic identities do not authorize filling domain holes.

## provenance and validation

These implementation bodies and record layouts are a mechanical transfer of
project-owned code by John Funge under AGPL-3.0-only. The numeric algorithms,
branch limits, admission rules and conservative fallbacks are unchanged. This is
not a new mathematical algorithm or a claim of formal verification. Tests in
`tests/test_value_algebra.py` are original, redistributable controls; no external
corpus or application fixture data is included.

Run `make all test` with the supported Python version, or run the headless controls
alone with:

```sh
PYTHONPATH=python python3 -m unittest discover -s tests -p test_value_algebra.py
```
 The fixture backend accepts only exact
arithmetic used by its tests; it is not an interval library for general use.
Fraction and adjacent-float checks cover endpoint optimality, including overflow
and subnormal values. Other controls cover finite relations, union preservation,
shared choices, partial definedness, chart holes, contained witnesses, callback
order, metadata budgets, layout and import isolation. Application/backend
qualification is also required before a consumer adopts a new immutable pin.
