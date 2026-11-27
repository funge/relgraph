# expression dispatch

`relgraph_eval.dispatch` supplies experimental scalar and set dispatch for raw
Python expression nodes accepted by the canonical syntax. The entrypoints are
`_eval_expr_uncached` and `_eval_expr_set_uncached`; names and records remain
internal and do not promise a stable Python ABI.

The numeric context implements `DispatchOps`. A `DispatchHost` supplies 19 live
services for recursive evaluation, exact literal and source interpretation,
structural comparison, optional rational/phase recognition and context-sensitive
operator evaluation. The dispatcher does not create a cache, change AST spelling,
copy nodes, create a discrete scope or configure options. Recursive calls return
to the host at the original evaluation points. Caller-owned literal metadata and
scope tokens must survive those calls unchanged. A host must implement the
services reached by its accepted inputs; missing services are not silently
replaced with weaker evaluation.

The dispatch order, operand order, call admission, constructor order and existing
operator algorithms are retained. In particular cancellation preserves inherited
definedness, division retains original exclusions, malformed supported calls fail
before operand or numeric access, and optional source proofs retain ordinary
fallbacks. Callbacks are looked up when used rather than snapshotted at entry.
The host is responsible for the safety of any exact-source certificate and for
context identity, recursion/cache lifetime, cancellation and profiling policy.

This module is not a compiler, formula proof policy, renderer or cell classifier.
Standalone tests use original exact fixtures and directly exercise both public
entrypoints, authored decimal fractions and spelling, poles, error precedence,
recursive cache identity and scope-sensitive choice tokens.
