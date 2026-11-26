# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only

"""Canonical formula syntax and shared text parsing primitives.

No renderer, interval kernel, catalogue or external-dialect imports belong here.
The reference importer supplies its own expression parser and relation spellings
through the internal normalization primitives; normalize_formula is canonical.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class _FormulaSyntax:
    normalize_expression: Callable[[str], str]
    relation_operators: tuple[str, ...]


_LITERAL_LOCAL_CONSTANT_DEFINITION = re.compile(
    r"^(?P<name>[A-Za-z]) = (?P<literal>-?(?:0|[1-9][0-9]*))$"
)
_LOCAL_DEFINITION_LEFT = re.compile(r"^(?P<name>[A-Za-z]) = ")
_LOCAL_CONSTANT_RESERVED_NAMES = frozenset({"e", "x", "y"})
_EXACT_BINARY64_INTEGER_LIMIT = 2**53


_MAX_FORMULA_INPUT_CHARACTERS = 16_384
_MAX_FORMULA_ALTERNATIVES = 256
_MAX_NORMALIZED_FORMULA_CHARACTERS = 16_384
_MAX_INTERMEDIATE_JOIN_CHARACTERS = 65_536
_MAX_NORMALIZATION_DEPTH = 32
_MAX_NORMALIZATION_ENTRIES = 4_096
_MAX_NORMALIZATION_TEXT = 1_048_576


@dataclass
class _NormalizationBudget:
    entries: int = 0
    characters: int = 0
    relation_depth: int = 0

    def check(self, count: int, characters: int) -> None:
        if count > _MAX_FORMULA_ALTERNATIVES:
            raise ValueError(
                f"formula exceeds {_MAX_FORMULA_ALTERNATIVES} alternatives"
            )
        if characters > _MAX_INTERMEDIATE_JOIN_CHARACTERS:
            raise ValueError("formula exceeds intermediate normalization text limit")

    def reserve(self, count: int, characters: int) -> None:
        self.check(count, characters)
        if self.entries + count > _MAX_NORMALIZATION_ENTRIES:
            raise ValueError("formula exceeds normalization expansion work limit")
        if self.characters + characters > _MAX_NORMALIZATION_TEXT:
            raise ValueError("formula exceeds cumulative normalization text limit")
        self.entries += count
        self.characters += characters


def _append_normalized(
    values: list[str], parts: tuple[str, ...], budget: _NormalizationBudget
) -> None:
    length = sum(map(len, parts))
    budget.check(len(values) + 1, sum(map(len, values)) + length + 4 * len(values))
    budget.reserve(1, length)
    values.append("".join(parts))


def _constraint_product(
    left: tuple[str, ...], right: tuple[str, ...], budget: _NormalizationBudget
) -> tuple[str, ...]:
    count = len(left) * len(right)
    budget.check(count, 0)  # Check cardinality before visiting or allocating rows.
    characters = sum(
        len(a) + len(b) + (2 if a and b else 0) for a in left for b in right
    )
    budget.check(count, characters + 4 * max(0, count - 1))
    budget.reserve(count, characters)
    return tuple(f"{a}; {b}" if a and b else a or b for a in left for b in right)


def _canonical_resources_fit(values: tuple[str, ...]) -> None:
    # Every emitted canonical segment is one ordinary relation. Bound a fresh
    # normalization of that serialized form, without parsing it a second time.
    entries = len(values) + 1
    characters = sum(map(len, values)) + 4 * max(0, len(values) - 1)
    for alternative in values:
        segments = _split_constraint_segments(alternative)
        entries += 5 * len(segments)
        prefix = 0
        for segment in segments:
            prefix += len(segment) + (2 if prefix else 0)
            characters += 3 * len(segment) + prefix
        characters += len(alternative)
    if entries > _MAX_NORMALIZATION_ENTRIES:
        raise ValueError("formula exceeds canonical normalization work limit")
    if characters > _MAX_NORMALIZATION_TEXT:
        raise ValueError("formula exceeds canonical normalization text limit")


def _join_normalized(values: tuple[str, ...], budget: _NormalizationBudget) -> str:
    length = sum(map(len, values)) + 4 * max(0, len(values) - 1)
    budget.check(len(values), length)
    if length > _MAX_NORMALIZED_FORMULA_CHARACTERS:
        raise ValueError(
            f"formula exceeds {_MAX_NORMALIZED_FORMULA_CHARACTERS} normalized characters"
        )
    _canonical_resources_fit(values)
    budget.reserve(1, length)
    return " or ".join(values)


def normalize_formula(source: str) -> str:
    """Normalize canonical input; external dialects have separate importers."""
    return _normalize_formula(_prepare_formula_text(source), syntax=_CANONICAL_SYNTAX)


def _prepare_formula_text(source: str) -> str:
    if len(source) > _MAX_FORMULA_INPUT_CHARACTERS:
        raise ValueError(
            f"formula exceeds {_MAX_FORMULA_INPUT_CHARACTERS} input characters"
        )
    text = source.strip()
    if re.search(r"(?<=\d)_(?=\d)", text):
        raise _UnsupportedNumericLiteral(
            "digit separators are unsupported in numeric literals"
        )
    if "\\" in text or "$" in text:
        raise ValueError(
            "LaTeX-style formula entry is not supported; enter plain math such as y=sin(1/x)"
        )

    for old, new in {
        "π": "pi",
        "≤": "<=",
        "≥": ">=",
        "−": "-",
        "×": "*",
        "·": "*",
        "∛": "cbrt",
        "∈": " in ",
        "∨": " or ",
        "∞": "inf",
    }.items():
        text = text.replace(old, new)

    return text


def _normalize_formula(text: str, *, syntax: _FormulaSyntax) -> str:
    if len(text) > _MAX_FORMULA_INPUT_CHARACTERS:
        raise ValueError(
            f"formula exceeds {_MAX_FORMULA_INPUT_CHARACTERS} input characters"
        )
    try:
        return _normalize_formula_bounded(
            text, syntax=syntax, budget=_NormalizationBudget()
        )
    except RecursionError:
        raise ValueError("formula exceeds recursive normalization limit") from None


def _normalize_formula_bounded(
    text: str, *, syntax: _FormulaSyntax, budget: _NormalizationBudget
) -> str:
    text = _replace_integer_function_brackets(text)
    text = _replace_absolute_value_bars(text)
    source_alternatives = _split_relation_alternatives(text)
    normalized_alternatives: list[str] = []
    for alternative in source_alternatives:
        values = _normalize_formula_alternative(
            alternative, syntax=syntax, budget=budget
        )
        count = len(normalized_alternatives) + len(values)
        length = (
            sum(map(len, normalized_alternatives))
            + sum(map(len, values))
            + 4 * max(0, count - 1)
        )
        budget.check(count, length)
        budget.reserve(len(values), sum(map(len, values)))
        normalized_alternatives.extend(values)
    if len(source_alternatives) == 1 and len(normalized_alternatives) == 1:
        normalized_alternatives[0] = _lower_literal_local_constant(
            normalized_alternatives[0], budget=budget
        )
    return _join_normalized(tuple(normalized_alternatives), budget)


def _lower_literal_local_constant(
    canonical_alternative: str, *, budget: _NormalizationBudget
) -> str:
    segments = list(_split_constraint_segments(canonical_alternative))
    literal_definitions = [
        (index, match)
        for index, segment in enumerate(segments)
        for match in (_LITERAL_LOCAL_CONSTANT_DEFINITION.fullmatch(segment),)
        if match is not None
    ]
    if len(literal_definitions) != 1:
        return canonical_alternative

    definition_index, definition = literal_definitions[0]
    name = definition.group("name")
    literal = definition.group("literal")
    if (
        name in _LOCAL_CONSTANT_RESERVED_NAMES
        or abs(int(literal)) > _EXACT_BINARY64_INTEGER_LIMIT
    ):
        return canonical_alternative

    remaining = [
        segment for index, segment in enumerate(segments) if index != definition_index
    ]
    if any(
        (match := _LOCAL_DEFINITION_LEFT.match(segment)) is not None
        and match.group("name") not in _LOCAL_CONSTANT_RESERVED_NAMES
        for segment in remaining
    ):
        return canonical_alternative

    use_pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    if not any(use_pattern.search(segment) for segment in remaining):
        return canonical_alternative

    substituted_length = sum(
        len(segment)
        + sum(
            len(literal) + 2 - len(match.group())
            for match in use_pattern.finditer(segment)
        )
        for segment in remaining
    ) + 2 * max(0, len(remaining) - 1)
    budget.reserve(1, substituted_length)
    substituted = "; ".join(
        use_pattern.sub(f"({literal})", segment) for segment in remaining
    )
    renormalized = _normalize_formula_alternative(
        substituted, syntax=_CANONICAL_SYNTAX, budget=budget
    )
    if len(renormalized) != 1:
        return canonical_alternative
    return renormalized[0]


def _normalize_formula_alternative(
    source: str, *, syntax: _FormulaSyntax, budget: _NormalizationBudget | None = None
) -> tuple[str, ...]:
    budget = budget or _NormalizationBudget()
    alternatives = ("",)
    for segment in _split_constraint_segments(source):
        values = _normalize_relation_segment_alternatives(
            segment, syntax=syntax, budget=budget
        )
        alternatives = _constraint_product(alternatives, values, budget)
    return alternatives


def _normalize_relation_segment(segment: str) -> str:
    budget = _NormalizationBudget()
    return _join_normalized(
        _normalize_relation_segment_alternatives(
            segment, syntax=_CANONICAL_SYNTAX, budget=budget
        ),
        budget,
    )


def _normalize_relation_segment_alternatives(
    segment: str, *, syntax: _FormulaSyntax, budget: _NormalizationBudget | None = None
) -> tuple[str, ...]:
    budget = budget or _NormalizationBudget()
    relations = _find_relation_chain(segment, spellings=syntax.relation_operators)
    if not relations:
        result = syntax.normalize_expression(segment)
        budget.reserve(1, len(result))
        return (result,)
    alternatives = ("",)
    for left, operator, right in relations:
        values = _normalize_relation_alternatives(
            left, operator, right, syntax=syntax, budget=budget
        )
        alternatives = _constraint_product(alternatives, values, budget)
    return alternatives


def _normalize_relation_alternatives(
    left: str,
    operator: str,
    right: str,
    *,
    syntax: _FormulaSyntax,
    budget: _NormalizationBudget | None = None,
) -> tuple[str, ...]:
    budget = budget or _NormalizationBudget()
    if budget.relation_depth >= _MAX_NORMALIZATION_DEPTH:
        raise ValueError("formula exceeds nested guard normalization depth limit")
    budget.relation_depth += 1
    try:
        return _normalize_relation_alternatives_bounded(
            left, operator, right, syntax=syntax, budget=budget
        )
    finally:
        budget.relation_depth -= 1


def _normalize_relation_alternatives_bounded(
    left: str,
    operator: str,
    right: str,
    *,
    syntax: _FormulaSyntax,
    budget: _NormalizationBudget,
) -> tuple[str, ...]:
    budget = budget or _NormalizationBudget()
    if operator == "in":
        return _normalize_membership_relation_alternatives(
            left, right, syntax=syntax, budget=budget
        )
    normalized: list[str] = []
    left_pieces = _piecewise_expression_options(left, budget=budget)
    right_pieces = _piecewise_expression_options(right, budget=budget)
    budget.check(len(left_pieces) * len(right_pieces), 0)
    for left_expression, left_guards in left_pieces:
        for right_expression, right_guards in right_pieces:
            guards = _normalize_guard_alternatives(
                left_guards + right_guards, syntax=syntax, budget=budget
            )
            left_options = _compact_relation_side_options(left_expression)
            right_options = _compact_relation_side_options(right_expression)
            budget.check(len(left_options) * len(right_options) * len(guards), 0)
            for left_option in left_options:
                normalized_left = syntax.normalize_expression(left_option)
                for right_option in right_options:
                    normalized_right = syntax.normalize_expression(right_option)
                    relation_parts = (
                        normalized_left,
                        " ",
                        operator,
                        " ",
                        normalized_right,
                    )
                    for guard in guards:
                        _append_normalized(
                            normalized,
                            relation_parts + (("; ", guard) if guard else ()),
                            budget,
                        )
    return tuple(normalized)


def _piecewise_expression_options(
    source: str, *, budget: _NormalizationBudget | None = None, depth: int = 0
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    budget = budget or _NormalizationBudget()
    if depth + budget.relation_depth > _MAX_NORMALIZATION_DEPTH:
        raise ValueError("formula exceeds piecewise normalization depth limit")
    span = _find_piecewise_span(source)
    if span is None:
        budget.reserve(1, len(source))
        return ((source, ()),)
    start, end, branches = span
    prefix, suffix = source[:start], source[end:]
    options: list[tuple[str, tuple[str, ...]]] = []
    for value, guard in branches:
        length = len(prefix) + len(value) + len(suffix) + 2
        budget.reserve(1, length)  # Before constructing a recursive branch string.
        branch_source = f"{prefix}({value}){suffix}"
        for expression, guards in _piecewise_expression_options(
            branch_source, budget=budget, depth=depth + 1
        ):
            budget.check(
                len(options) + 1,
                sum(len(v) + sum(map(len, g)) for v, g in options)
                + len(expression)
                + len(guard)
                + sum(map(len, guards)),
            )
            budget.reserve(1, len(expression) + len(guard) + sum(map(len, guards)))
            options.append((expression, (guard,) + guards))
    return tuple(options)


def _find_piecewise_span(
    source: str,
) -> tuple[int, int, tuple[tuple[str, str], ...]] | None:
    index = 0
    while index < len(source):
        if source[index] != "{":
            index += 1
            continue
        end = _matching_group_end(source, index)
        if end is None:
            raise ValueError("unbalanced parentheses in formula")
        body = source[index + 1 : end]
        if _contains_top_level_word(body, "if"):
            return index, end + 1, _parse_piecewise_branches(body)
        index = end + 1
    return None


def _parse_piecewise_branches(body: str) -> tuple[tuple[str, str], ...]:
    branches: list[tuple[str, str]] = []
    for branch in _split_top_level_piecewise_terms(body):
        if_index = _top_level_word_index(branch, "if")
        if if_index is None:
            raise ValueError("piecewise branches must use '<value> if <condition>'")
        value = branch[:if_index].strip()
        guard = _strip_wrapping_group(branch[if_index + len("if") :].strip())
        if not value or not guard:
            raise ValueError("piecewise branches must include a value and condition")
        branches.append((value, guard))
    return tuple(branches)


def _normalize_guard_alternatives(
    guards: tuple[str, ...],
    *,
    syntax: _FormulaSyntax,
    budget: _NormalizationBudget | None = None,
) -> tuple[str, ...]:
    budget = budget or _NormalizationBudget()
    alternatives = ("",)
    for guard in guards:
        values = _normalize_relation_segment_alternatives(
            guard, syntax=syntax, budget=budget
        )
        alternatives = _constraint_product(alternatives, values, budget)
    return alternatives


def _normalize_membership_relation_alternatives(
    left: str,
    right: str,
    *,
    syntax: _FormulaSyntax,
    budget: _NormalizationBudget | None = None,
) -> tuple[str, ...]:
    budget = budget or _NormalizationBudget()
    normalized_left = syntax.normalize_expression(left)
    right_options = _compact_relation_side_options(right)
    budget.check(len(right_options), 0)
    normalized: list[str] = []
    for right_option in right_options:
        interval = _parse_interval_literal(right_option)
        if interval is None:
            _append_normalized(
                normalized,
                (normalized_left, " = ", syntax.normalize_expression(right_option)),
                budget,
            )
            continue
        lower, lower_closed, upper, upper_closed = interval
        relations: list[str] = []
        if not _is_negative_infinity_literal(lower):
            operator = "<=" if lower_closed else "<"
            _append_normalized(
                relations,
                (
                    syntax.normalize_expression(lower),
                    " ",
                    operator,
                    " ",
                    normalized_left,
                ),
                budget,
            )
        if not _is_positive_infinity_literal(upper):
            operator = "<=" if upper_closed else "<"
            _append_normalized(
                relations,
                (
                    normalized_left,
                    " ",
                    operator,
                    " ",
                    syntax.normalize_expression(upper),
                ),
                budget,
            )
        parts: list[str] = []
        for relation in relations:
            if parts:
                parts.append("; ")
            parts.append(relation)
        _append_normalized(normalized, tuple(parts) if parts else ("0 = 0",), budget)
    return tuple(normalized)


def _compact_relation_side_options(source: str) -> tuple[str, ...]:
    text = source.strip()
    set_options = _braced_set_elements(text)
    if set_options is not None:
        return set_options
    if text.startswith("±"):
        body = text[1:].strip()
        if not body:
            raise ValueError("plus-minus relation shorthand requires an expression")
        return (body, f"-({body})")
    if text.startswith("+/-"):
        body = text[3:].strip()
        if not body:
            raise ValueError("plus-minus relation shorthand requires an expression")
        return (body, f"-({body})")
    return (text,)


def _braced_set_elements(source: str) -> tuple[str, ...] | None:
    text = source.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return None
    body = text[1:-1].strip()
    if not body:
        raise ValueError("set notation must contain at least one expression")
    if _contains_top_level_word(body, "if"):
        raise ValueError("set notation alternatives cannot be conditional branches")
    return _split_top_level_commas(body)


def _parse_interval_literal(source: str) -> tuple[str, bool, str, bool] | None:
    text = source.strip()
    if len(text) < 5 or text[0] not in "[(" or text[-1] not in "])":
        return None
    elements = _split_top_level_commas(text[1:-1])
    if len(elements) != 2:
        return None
    return elements[0], text[0] == "[", elements[1], text[-1] == "]"


def _is_positive_infinity_literal(source: str) -> bool:
    return source.strip().lower() in {"inf", "+inf", "infinity", "+infinity"}


def _is_negative_infinity_literal(source: str) -> bool:
    return source.strip().lower() in {"-inf", "-infinity"}


_ELEMENTARY_UNARY_FUNCTIONS = frozenset(
    (
        "exp",
        "ln",
        "log10",
        "sinh",
        "cosh",
        "tanh",
        "asin",
        "acos",
        "asinh",
        "acosh",
        "atanh",
    )
)

_SUPPORTED_FUNCTIONS = frozenset(
    {
        *_ELEMENTARY_UNARY_FUNCTIONS,
        "abs",
        "atan",
        "atan2",
        "cbrt",
        "ceil",
        "cos",
        "factorial",
        "floor",
        "fmod",
        "gcd",
        "lcm",
        "log2",
        "max",
        "min",
        "mod",
        "sin",
        "sqrt",
        "tan",
    }
)
_FUNCTION_ARITIES = {
    "abs": (1,),
    "acos": (1,),
    "acosh": (1,),
    "asin": (1,),
    "asinh": (1,),
    "atan": (1,),
    "atanh": (1,),
    "atan2": (2,),
    "cbrt": (1,),
    "ceil": (1,),
    "cos": (1,),
    "cosh": (1,),
    "exp": (1,),
    "factorial": (1,),
    "floor": (1,),
    "fmod": (2,),
    "gcd": (),
    "lcm": (),
    "ln": (1,),
    "log10": (1,),
    "log2": (1,),
    "mod": (2,),
    "sin": (1,),
    "sinh": (1,),
    "sqrt": (1,),
    "tan": (1,),
    "tanh": (1,),
}
_VARIADIC_FUNCTION_MIN_ARITIES = {
    "gcd": 2,
    "lcm": 2,
    "max": 2,
    "min": 2,
}
_SUPPORTED_FUNCTIONS_MESSAGE = (
    "supported functions include exp(...), ln(...), log10(...), sinh(...), cosh(...), "
    "tanh(...), asin(...), acos(...), asinh(...), acosh(...), atanh(...), abs(...), atan(...), atan2(...,...), cbrt(...), "
    "ceil(...), cos(...), factorial(...), floor(...), fmod(...,...), gcd(...,...), "
    "lcm(...,...), log2(...), max(...,...), min(...,...), mod(...,...), sin(...), "
    "sqrt(...), and tan(...)"
)

_NAME_ALIASES = {
    **{name: name for name in _ELEMENTARY_UNARY_FUNCTIONS},
    "arctan": "atan",
    "atan": "atan",
    "atan2": "atan2",
    "cbrt": "cbrt",
    "ceil": "ceil",
    "ceiling": "ceil",
    "floor": "floor",
    "factorial": "factorial",
    "fmod": "fmod",
    "gcd": "gcd",
    "lcm": "lcm",
    "log2": "log2",
    "sqrt": "sqrt",
    "sin": "sin",
    "cos": "cos",
    "max": "max",
    "min": "min",
    "mod": "mod",
    "tan": "tan",
    "abs": "abs",
    "pi": "pi",
    "x": "x",
    "y": "y",
    "e": "e",
}
_NAME_SPELLINGS = tuple(sorted(_NAME_ALIASES, key=len, reverse=True))

# Explicit calls can name functions whose interval models are not implemented
# yet. Keep canonical/source-dialect ambiguities out of that open namespace.
_RESERVED_FUNCTION_NAMES = frozenset(
    {"log", "lg", "angle", "arctan2", "x", "y", "pi", "e"}
)
_FUNCTION_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")


def _is_fallback_function(name: str) -> bool:
    return (
        name not in _SUPPORTED_FUNCTIONS
        and name.lower() not in _RESERVED_FUNCTION_NAMES
        and name.lower() not in _NAME_ALIASES
        and bool(_FUNCTION_IDENTIFIER.fullmatch(name))
    )


@dataclass(frozen=True)
class _MathToken:
    kind: str
    value: str


@dataclass(frozen=True)
class _MathSource:
    text: str
    precedence: int


def _normalize_math_expression(source: str) -> str:
    return _MathParser(_tokenize_math(source)).parse()


def _replace_absolute_value_bars(text: str) -> str:
    if "|" not in text:
        return text
    if text.count("|") % 2:
        raise ValueError("unmatched absolute-value bar in formula")

    result: list[str] = []
    open_bar = False
    for char in text:
        if char != "|":
            result.append(char)
            continue
        if open_bar:
            result.append(")")
        else:
            result.append("abs(")
        open_bar = not open_bar
    return "".join(result)


def _replace_integer_function_brackets(text: str) -> str:
    if not any(char in text for char in "⌊⌋⌈⌉"):
        return text

    result: list[str] = []
    stack: list[str] = []
    for char in text:
        if char == "⌊":
            result.append("floor(")
            stack.append("⌊")
            continue
        if char == "⌈":
            result.append("ceil(")
            stack.append("⌈")
            continue
        if char == "⌋":
            if not stack or stack.pop() != "⌊":
                raise ValueError("unmatched floor bracket in formula")
            result.append(")")
            continue
        if char == "⌉":
            if not stack or stack.pop() != "⌈":
                raise ValueError("unmatched ceiling bracket in formula")
            result.append(")")
            continue
        result.append(char)

    if stack:
        bracket_name = "floor" if stack[-1] == "⌊" else "ceiling"
        raise ValueError(f"unmatched {bracket_name} bracket in formula")
    return "".join(result)


def _tokenize_math(
    source: str,
    *,
    read_name: Callable[[str, int], tuple[_MathToken, int]] | None = None,
) -> tuple[_MathToken, ...]:
    if read_name is None:
        read_name = _read_name
    tokens: list[_MathToken] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if char.isdigit() or (
            char == "." and index + 1 < len(source) and source[index + 1].isdigit()
        ):
            number, index = _read_number(source, index)
            tokens.append(_MathToken("number", number))
            continue
        if source.startswith("**", index):
            tokens.append(_MathToken("op", "^"))
            index += 2
            continue
        if char == ".":
            tokens.append(_MathToken("op", "."))
            index += 1
            continue
        if char == ",":
            tokens.append(_MathToken("comma", char))
            index += 1
            continue
        if char in "+-*/^!":
            tokens.append(_MathToken("op", char))
            index += 1
            continue
        if char in "([{":
            tokens.append(_MathToken("lparen", char))
            index += 1
            continue
        if char in ")]}":
            tokens.append(_MathToken("rparen", char))
            index += 1
            continue
        if char.isalpha():
            token, index = read_name(source, index)
            tokens.append(token)
            continue
        raise ValueError(f"unsupported character {char!r} in formula")

    tokens.append(_MathToken("eof", ""))
    return tuple(tokens)


def _read_number(source: str, index: int) -> tuple[str, int]:
    start = index
    while index < len(source) and source[index].isdigit():
        index += 1
    if index < len(source) and source[index] == ".":
        index += 1
        while index < len(source) and source[index].isdigit():
            index += 1
    if (
        index < len(source)
        and source[index] in "eE"
        and index + 1 < len(source)
        and (source[index + 1].isdigit() or source[index + 1] in "+-")
    ):
        exponent = index + 1
        if source[exponent] in "+-":
            exponent += 1
        if exponent < len(source) and source[exponent].isdigit():
            index = exponent + 1
            while index < len(source) and source[index].isdigit():
                index += 1
    return source[start:index], index


def _read_name(source: str, index: int) -> tuple[_MathToken, int]:
    if source[index:].lower().startswith("arctan2"):
        raise ValueError("unsupported function spelling 'arctan2'")
    explicit_call = re.match(r"([A-Za-z][A-Za-z0-9_]*)\s*\(", source[index:])
    if explicit_call is not None:
        name = explicit_call.group(1)
        if _is_fallback_function(name):
            return _MathToken("function", name), index + len(name)
    return _read_known_name(source, index)


def _read_known_name(source: str, index: int) -> tuple[_MathToken, int]:
    remaining = source[index:].lower()
    if remaining.startswith("arctan2"):
        raise ValueError("unsupported function spelling 'arctan2'")
    for spelling in _NAME_SPELLINGS:
        if remaining.startswith(spelling.lower()):
            name = _NAME_ALIASES[spelling]
            authored = source[index : index + len(spelling)]
            if name == "atan2" and authored != spelling:
                raise ValueError(
                    f"function {name} uses the exact lower-case spelling {spelling!r}"
                )
            kind = "function" if name in _SUPPORTED_FUNCTIONS else "name"
            return _MathToken(kind, name), index + len(spelling)

    start = index
    while index < len(source) and source[index].isalpha():
        index += 1
    return _MathToken("name", source[start:index]), index


class _MathParser:
    def __init__(self, tokens: tuple[_MathToken, ...]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse(self) -> str:
        if self._peek().kind == "eof":
            raise ValueError("formula must not be empty")
        result = self._parse_sum()
        if self._peek().kind != "eof":
            raise ValueError(f"unexpected token {self._peek().value!r} in formula")
        return result.text

    def _parse_sum(self) -> _MathSource:
        node = self._parse_product()
        while self._peek().kind == "op" and self._peek().value in {"+", "-"}:
            operator = self._advance().value
            right = self._parse_product()
            node = _binary_math_source(node, operator, right)
        return node

    def _parse_product(self) -> _MathSource:
        node = self._parse_unary()
        while self._peek().kind == "op" and self._peek().value in {"*", "/"}:
            operator = self._advance().value
            node = _binary_math_source(node, operator, self._parse_unary())
        token = self._peek()
        if _starts_implicit_factor(token) or token.value == ".":
            raise ValueError("multiplication requires '*' between factors")
        return node

    def _parse_unary(self) -> _MathSource:
        if self._peek().kind == "op" and self._peek().value in {"+", "-"}:
            operator = self._advance().value
            operand = self._parse_unary()
            return _MathSource(f"{operator}{_math_operand_source(operand, 4)}", 4)
        return self._parse_power()

    def _parse_power(self) -> _MathSource:
        left = self._parse_postfix()
        if self._peek().kind == "op" and self._peek().value == "^":
            self._advance()
            right = self._parse_unary()
            return _binary_math_source(left, "^", right)
        return left

    def _parse_postfix(self) -> _MathSource:
        left = self._parse_primary()
        if self._peek().kind == "op" and self._peek().value == "!":
            raise ValueError(
                "canonical factorial requires factorial(...); postfix '!' is source notation"
            )
        return left

    def _parse_primary(self) -> _MathSource:
        token = self._peek()
        if token.kind == "number":
            self._advance()
            return _MathSource(token.value, 5)
        if token.kind == "name":
            self._advance()
            return _MathSource(token.value, 5)
        if token.kind == "function":
            return self._parse_function()
        if token.kind == "lparen":
            self._advance()
            expression = self._parse_sum()
            self._expect("rparen")
            return _MathSource(f"({expression.text})", 5)
        raise ValueError(f"expected an expression, got {token.value!r}")

    def _parse_function(self) -> _MathSource:
        name = self._advance().value
        arguments = self._parse_function_arguments(name)
        if not _function_accepts_arity(name, len(arguments)):
            raise ValueError(_function_arity_error(name))
        return _MathSource(
            f"{name}({','.join(argument.text for argument in arguments)})", 5
        )

    def _parse_function_arguments(self, name: str) -> list[_MathSource]:
        if self._peek().kind != "lparen" or self._peek().value != "(":
            raise ValueError(f"function {name} requires parenthesized arguments")
        return self._parse_argument_list()

    def _parse_argument_list(self) -> list[_MathSource]:
        opening = self._advance().value
        arguments = [self._parse_sum()]
        while self._peek().kind == "comma":
            self._advance()
            arguments.append(self._parse_sum())
        closing = self._expect("rparen").value
        if closing != {"(": ")", "[": "]", "{": "}"}[opening]:
            raise ValueError("unbalanced parentheses in function arguments")
        return arguments

    def _expect(self, kind: str) -> _MathToken:
        token = self._peek()
        if token.kind != kind:
            raise ValueError("unbalanced parentheses in formula")
        return self._advance()

    def _peek(self) -> _MathToken:
        return self.tokens[self.index]

    def _advance(self) -> _MathToken:
        token = self.tokens[self.index]
        self.index += 1
        return token


def _starts_implicit_factor(token: _MathToken) -> bool:
    return token.kind in {"number", "name", "function", "lparen"}


def _function_arity_error(name: str) -> str:
    if _is_fallback_function(name) and name not in _FUNCTION_ARITIES:
        return f"function {name} takes at least 1 positional argument"
    if name in _VARIADIC_FUNCTION_MIN_ARITIES:
        minimum = _VARIADIC_FUNCTION_MIN_ARITIES[name]
        return f"function {name} takes at least {minimum} positional arguments"
    arities = _FUNCTION_ARITIES[name]
    if len(arities) == 1:
        arity = arities[0]
        noun = "argument" if arity == 1 else "arguments"
        return f"function {name} takes exactly {arity} positional {noun}"
    expected = " or ".join(str(arity) for arity in arities)
    return f"function {name} takes exactly {expected} positional arguments"


def _function_accepts_arity(name: str, arity: int) -> bool:
    if _is_fallback_function(name) and name not in _FUNCTION_ARITIES:
        return arity >= 1
    if name in _VARIADIC_FUNCTION_MIN_ARITIES:
        return arity >= _VARIADIC_FUNCTION_MIN_ARITIES[name]
    return arity in _FUNCTION_ARITIES[name]


def _binary_math_source(
    left: _MathSource, operator: str, right: _MathSource
) -> _MathSource:
    precedence = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 3}[operator]
    left_text = _math_operand_source(left, precedence, operator=operator, side="left")
    right_text = _math_operand_source(
        right, precedence, operator=operator, side="right"
    )
    return _MathSource(f"{left_text}{operator}{right_text}", precedence)


def _math_operand_source(
    operand: _MathSource,
    parent_precedence: int,
    *,
    operator: str | None = None,
    side: str = "left",
) -> str:
    needs_parens = operand.precedence < parent_precedence
    if (
        operator in {"-", "/"}
        and side == "right"
        and operand.precedence == parent_precedence
    ):
        needs_parens = True
    if operator == "^" and side == "left" and operand.precedence < 5:
        needs_parens = True
    if operator == "^" and side == "right" and operand.precedence < parent_precedence:
        needs_parens = True
    if needs_parens:
        return f"({operand.text})"
    return operand.text


def _split_relation(source: str) -> tuple[str, str, str]:
    relation = _find_relation(source)
    if relation is not None:
        return relation
    return source, "=", "0"


def _split_relation_alternatives(source: str) -> tuple[str, ...]:
    text = source.strip()
    if not text:
        raise ValueError("formula must not be empty")

    alternatives: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced parentheses in formula")
        elif depth == 0 and _word_operator_at(text, index, "or"):
            alternative = text[start:index].strip()
            if not alternative:
                raise ValueError("relation alternative must not be empty")
            if len(alternatives) >= _MAX_FORMULA_ALTERNATIVES:
                raise ValueError(
                    f"formula exceeds {_MAX_FORMULA_ALTERNATIVES} alternatives"
                )
            alternatives.append(alternative)
            index += 2
            start = index
            continue
        index += 1

    if depth != 0:
        raise ValueError("unbalanced parentheses in formula")

    alternative = text[start:].strip()
    if not alternative:
        raise ValueError("relation alternative must not be empty")
    if len(alternatives) >= _MAX_FORMULA_ALTERNATIVES:
        raise ValueError(f"formula exceeds {_MAX_FORMULA_ALTERNATIVES} alternatives")
    alternatives.append(alternative)
    return tuple(alternatives)


def _split_constraint_segments(source: str) -> tuple[str, ...]:
    text = source.strip()
    if not text:
        raise ValueError("formula must not be empty")

    segments: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced parentheses in formula")
        elif depth == 0 and char in ";\n":
            segment = text[start:index].strip()
            if not segment:
                raise ValueError("constraint must not be empty")
            segments.append(segment)
            start = index + 1

    if depth != 0:
        raise ValueError("unbalanced parentheses in formula")

    segment = text[start:].strip()
    if not segment:
        raise ValueError("constraint must not be empty")
    segments.append(segment)
    return tuple(segments)


def _split_top_level_commas(source: str) -> tuple[str, ...]:
    return _split_top_level_delimited(
        source,
        delimiters={","},
        empty_message="set notation must not contain empty elements",
    )


def _split_top_level_piecewise_terms(source: str) -> tuple[str, ...]:
    return _split_top_level_delimited(
        source,
        delimiters={",", ";"},
        empty_message="piecewise definitions must not contain empty branches",
    )


def _split_top_level_delimited(
    source: str,
    *,
    delimiters: set[str],
    empty_message: str,
) -> tuple[str, ...]:
    elements: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(source):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced parentheses in formula")
        elif depth == 0 and char in delimiters:
            element = source[start:index].strip()
            if not element:
                raise ValueError(empty_message)
            if len(elements) >= _MAX_FORMULA_ALTERNATIVES:
                raise ValueError(
                    f"formula exceeds {_MAX_FORMULA_ALTERNATIVES} alternatives"
                )
            elements.append(element)
            start = index + 1

    if depth != 0:
        raise ValueError("unbalanced parentheses in formula")

    element = source[start:].strip()
    if not element:
        raise ValueError(empty_message)
    if len(elements) >= _MAX_FORMULA_ALTERNATIVES:
        raise ValueError(f"formula exceeds {_MAX_FORMULA_ALTERNATIVES} alternatives")
    elements.append(element)
    return tuple(elements)


def _contains_top_level_word(source: str, word: str) -> bool:
    return _top_level_word_index(source, word) is not None


def _top_level_word_index(source: str, word: str) -> int | None:
    depth = 0
    index = 0
    while index < len(source):
        char = source[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced parentheses in formula")
        elif depth == 0 and _word_operator_at(source, index, word):
            return index
        index += 1

    if depth != 0:
        raise ValueError("unbalanced parentheses in formula")
    return None


def _matching_group_end(source: str, start: int) -> int | None:
    opening = source[start]
    if opening not in "([{":
        return None
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced parentheses in formula")
            if depth == 0:
                return index
    return None


def _strip_wrapping_group(source: str) -> str:
    text = source.strip()
    while text.startswith("("):
        end = _matching_group_end(text, 0)
        if end != len(text) - 1:
            break
        text = text[1:-1].strip()
    return text


def _word_operator_at(source: str, index: int, word: str) -> bool:
    if not source.startswith(word, index):
        return False
    before = source[index - 1] if index > 0 else ""
    after_index = index + len(word)
    after = source[after_index] if after_index < len(source) else ""
    return not _is_word_character(before) and not _is_word_character(after)


def _is_word_character(char: str) -> bool:
    return bool(char) and (char.isalpha() or char.isdigit() or char == "_")


def _find_relation(source: str) -> tuple[str, str, str] | None:
    relations = _find_relation_chain(source)
    if not relations:
        return None
    if len(relations) > 1:
        raise ValueError("chained relations must be normalized before parsing")
    return relations[0]


def _find_relation_chain(
    source: str,
    *,
    spellings: tuple[str, ...] = ("!=", "<=", ">=", "==", "<", ">", "="),
) -> tuple[tuple[str, str, str], ...]:
    text = source.strip()
    if not text:
        raise ValueError("formula must not be empty")

    operators: list[tuple[int, int, str]] = []
    depth = 0
    i = 0
    while i < len(text):
        char = text[i]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced parentheses in formula")
        elif depth == 0:
            if _word_operator_at(text, i, "in"):
                operators.append((i, i + len("in"), "in"))
                i += len("in") - 1
                continue
            for operator in spellings:
                if text.startswith(operator, i):
                    operators.append((i, i + len(operator), operator))
                    i += len(operator) - 1
                    break
        i += 1

    if depth != 0:
        raise ValueError("unbalanced parentheses in formula")
    if not operators:
        return ()

    relations: list[tuple[str, str, str]] = []
    for index, (operator_start, operator_end, operator) in enumerate(operators):
        previous_operator_end = 0 if index == 0 else operators[index - 1][1]
        next_operator_start = (
            len(text) if index + 1 == len(operators) else operators[index + 1][0]
        )
        left = text[previous_operator_end:operator_start].strip()
        right = text[operator_end:next_operator_start].strip()
        if not left or not right:
            raise ValueError("relation must have expressions on both sides")
        relations.append((left, operator, right))
    return tuple(relations)


class _UnsupportedNumericLiteral(ValueError):
    pass


_CANONICAL_SYNTAX = _FormulaSyntax(
    _normalize_math_expression,
    ("!=", "<=", ">=", "==", "<", ">", "="),
)
