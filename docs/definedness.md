# experimental definedness primitives

`relgraph_eval.definedness` owns Boolean intervals and elementary domain tests.
It uses only the standard library and loads no numeric library, parser or app.
The existing experimental relgraph-parser distribution supplies this namespace.

`BoolInterval` retains two ctypes c_bool fields, lo then hi. Valid logical
intervals are false/false, false/true and true/true. BOOL_FALSE, BOOL_MAYBE and
BOOL_TRUE are shared instances: callers must not mutate them. bool_and and
bool_or compute endpoint conjunction/disjunction, including true and false
respectively for empty argument lists. bool_is_true and bool_is_false recognize
certainty; neither turns uncertainty into proof. No validation or normalization
of malformed Boolean intervals is introduced.

interval_nonzero, sqrt_domain and log2_domain take an interval and an object
with is_empty(interval). IntervalBounds and EmptyQuery describe this structural
interface; no numeric backend is selected. Callers supply ordered, non-NaN bounds
or an empty interval recognized by their query. sqrt_domain accepts zero;
log2_domain requires strictly positive values. Domain predicates propagate the
argument's definedness, retain the same object for wholly valid ranges, and use
conservative Boolean conjunction for ranges crossing the domain boundary.
Empty numeric inputs return false. Interval construction, arithmetic, domain
splitting, continuity and proof policy remain the caller's responsibility.

The construction follows Tupper's thesis sections 2.11.4–2.11.5 (conjunctions
and partial functions) and 2.12 (property tracking). This is an ownership move
of original John Funge code under AGPL-3.0-only, not a new mathematical rule or
a proof of the implementation. Bodies and the two-field layout are retained;
only names and structural type annotations change. The Python interface and
serialization are experimental, without a stable ABI promise.

Original tests enumerate finite Boolean assignments and independent domain
membership cases, with empty inputs, signed zero, subnormal endpoints,
unbounded intervals, object identity and ctypes layout controls. Run
`make test-evaluation`; the full `make all test` includes these checks.
