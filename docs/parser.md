# experimental canonical formula parser

`relgraph_parser` is a standard-library-only, headless parsing slice. It does not
load the numeric library. Install with Python 3.14 using `pip install .`, or run
`make test-parser` from a clean checkout. `make test` includes these controls.

```python
from relgraph_parser import parse_formula, normalize_formula
from relgraph_parser.raw import exact_decimal_value

formula = parse_formula("x=1e-20; y>0 or x=9223372036854775809")
value = exact_decimal_value(formula.alternatives[0][0].right)
assert value.numerator == 1 and value.denominator == 10**20
```

The result retains the supplied source and ordered alternatives of ordered raw
relations. Each relation contains `left`, `operator`, and `right`. Expression
nodes are provisional Python `ast` objects. There is **no stable Python AST ABI,
serialization format, or cross-version compatibility promise**. Consumers should
pin a tested revision and keep representation adaptation at their boundary.

Decimals retain their normalized token spelling and exact base-ten fraction,
including values outside binary64 range. `exact_decimal_value` retrieves that
fraction for decimal leaves; `decimal_spelling` retrieves their token spelling.
Integer leaves remain Python integers, including values outside int64. Signs
remain unary nodes. A decimal node's Python `value` may be rounded, zero or
infinity: it is not the numeric contract. Do not evaluate it in place of the exact
annotation. Parsing alone does not convert constants to binary64 intervals.

Canonical normalization preserves established ordering, relation expansion,
operator vocabulary, opaque calls and admission errors. It bounds input and
normalized text at 16,384 characters and alternatives at 256, with additional
work, recursion and intermediate-text limits. Decimal digit/scale allocation is
bounded at 16,384. These are admission controls, not a process-isolation promise.
Malformed input raises `ValueError`; resource rejection remains explicit.

The parser performs no expression simplification, cancellation, domain analysis,
proof, sampling or rendering. Raw division must reach the consumer's domain
analysis even when a later algebraic identity could cancel it. Editor notation,
external-language translators and application data are outside this package.
The underscore-prefixed normalization primitives and lazy raw iterator are
internal integration seams, not supported extension APIs.

## provenance and license

This slice consists of original canonical normalization, literal annotation and
validation code authored for this project, with new original small tests. The
normalizer's function-name inventory is now local data; it imports no numeric
implementation. Only parsing ownership is transferred. No reference corpus,
external implementation, application assets or repository history is included.
The source, tests and documentation are covered by the repository copyright and
`AGPL-3.0-only` license. Python's standard library supplies token-tree construction
and rational arithmetic; no third-party parser code is vendored.

This remains a local review candidate until provenance and the complete diff
are approved for publication. The tests establish syntax and exact-literal
contracts, not numerical evaluation or formal correctness.
