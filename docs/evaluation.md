# experimental branch provenance

`relgraph_eval.branches` is a headless, standard-library-only primitive for
correlating shared evaluation choices. This first slice supplies `BranchMap`,
`BRANCH_MAP_MAX_ENTRIES` (16), `merge_branch_maps` and `branch_choice`. It does
not evaluate expressions, classify regions, assign site identities, or decide
definedness, continuity or domain membership.

A map is an immutable tuple of `(opaque_site, integer_choice)` pairs. Callers
supply valid partial functions with unique sites and at most 16 entries. Sites
are compared by object identity, never equality or hashing; the caller owns
stable site tokens and their lifetime. Choices retain arbitrary-size integers.
Tuple order is preserved. This is an experimental in-process interface, not a
serialization or stable ABI contract.

`merge_branch_maps` returns the compatible union, `None` for conflicting shared
choices, or an empty map when the union exceeds the budget. Conflicts are checked
before budget forgetting. An empty map imposes no restrictions; it is not an
empty value set. Empty-input and identity fast paths return the existing operand.
`branch_choice` attaches known provenance, retains the input when site or choice
is unknown, and forgets provenance on conflict. Its empty result never certifies
absence. Consumers must preserve all value components and independently retain
strict domain and definedness information when provenance is forgotten.

The construction follows partial choice maps for shared discontinuities in
Tupper, SIGGRAPH 2001 section 12. The 16-entry bound forgets restrictions rather
than removing values. No numerical operation or proof policy changes here.

This module is currently delivered by the existing experimental
`relgraph-parser` distribution alongside `relgraph_parser`; import namespaces
remain separate and neither loads the other. The distribution is not renamed
or split in this slice. Consumers should pin an exact reviewed commit.

Run `make test-evaluation`; `make test` includes it. Original tests compare
compatible maps against an independent finite-assignment intersection oracle,
plus identity-only sites, exact large choices, ordering, conflicts and budgets.
The implementation is original John Funge code, covered by AGPL-3.0-only like
the repository. No third-party implementation or application fixtures are copied.
