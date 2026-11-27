# division and discrete evaluation

The experimental `relgraph_eval.rational_refinement` and
`relgraph_eval.functions.{division,discrete}` modules provide headless numeric
kernels. They use the caller-owned numeric operations contract; they do not load
a native library, parse source, choose application options or classify cells.
Internal Python records and names are not a stable ABI.

Division preserves denominator exclusions, inherited definedness, branch choices,
section order and chart metadata. Optional rational refinement intersects the
ordinary enclosure; it does not cancel a hole or promote unknown definedness.
The caller must certify the plan's polynomial quotient and remainder for the
original coordinate box, supply outward-rounded coefficient intervals and share
the same operation budget across construction and application. An interval
quotient/remainder representation is not an assertion of interval Q*D equality.
Zero-crossing denominators and exhausted budgets retain the ordinary interval
object. Degree is bounded by eight and the default operation budget is 4096.
Unexpected numeric exceptions propagate. Source admission and source-cache
policy belong to the caller.

Discrete kernels retain factorial's nonnegative integer domain and floor/ceil
scalar discontinuity and choice metadata. Scope-sensitive floor/ceil set dispatch
is deliberately outside this interface: structural scope identity must be supplied
and enforced by the caller's dispatcher. Neither this module nor the division
module owns source spelling, exact literal provenance or cache lifetimes.

These are mechanical transfers of existing project-owned kernels. New tests use
original finite exact fixtures and Fraction arithmetic, without an application
or native loader. They cover quotient/refinement arithmetic, shared budgets,
conservative fallback identity, denominator holes, inherited uncertainty,
factorial domain and discrete site identity. They do not constitute a proof of
all callers' source-plan admission or native outward rounding.
