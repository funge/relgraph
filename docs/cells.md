# ordered evaluation and the direct cell test

`relgraph_eval.cells.evaluate_formula` evaluates ordered alternatives of ordered
relations using caller-owned source nodes and a `DispatchOps` context. The
`FormulaHost` supplies recursive set evaluation and optional constant-relation
refinement. Every relation is visited in its original order, including after an
earlier false conjunction or true alternative. No numerical operation, source
lookup, refinement callback or exception is hidden by a new short circuit.

The frozen `FormulaFold` reports truth, per-relation and per-alternative records,
offsets and the total branch capacity required. Records are observational
snapshots, not reusable proof certificates or replacements for the evaluator's
branch-choice and domain metadata. Input validation, compiler admission and
capacity-error policy remain caller-owned. In particular an adapter must not
classify an invalid or capacity-exhausted result as known truth.

`interval_cell_state` implements the direct interval test: false over the whole
outer box proves absence; true proves presence only with a nonempty contained
witness. Unknown or invalid input stays undecided. The caller must supply the
truth for the outer box and the correct witness flag. False over only a contained
sub-box cannot establish absence over the outer box. This preserves the direct
test described by Tupper's interval pixel constructions; it does not add a proof
family or change domain semantics.

A caller can retain additional ordered existence proofs after an undecided direct
test. Such proofs, witness selection, sampling, stopping rules and diagnostics
are outside this module. Direct evaluation and a proof-enabled classifier can
legitimately return different states for the same box. A crossing equality is a
simple example: interval truth can be undecided even when a separate existence
proof succeeds.

All records and entrypoints are experimental Python interfaces without a stable
AST/record ABI promise. Original standalone controls cover ordering and counts,
late exceptions, poles, open boundaries, unknown truth, invalid results and
witness admission. No application, private fixture corpus or renderer is needed
for those tests.
