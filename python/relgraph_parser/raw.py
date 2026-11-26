# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only

"""Validated raw expressions; no simplification or evaluation policy."""

from __future__ import annotations
import ast
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterator, cast
from .syntax import (
    normalize_formula,
    _split_relation_alternatives,
    _split_constraint_segments,
    _split_relation,
    _SUPPORTED_FUNCTIONS,
    _SUPPORTED_FUNCTIONS_MESSAGE,
    _UnsupportedNumericLiteral,
    _function_accepts_arity,
    _function_arity_error,
    _is_fallback_function,
)

_EXACT_DECIMAL_NUMERATOR_ATTR = "_relgraph_exact_decimal_numerator"
_EXACT_DECIMAL_DENOMINATOR_ATTR = "_relgraph_exact_decimal_denominator"
_EXACT_DECIMAL_SPELLING_ATTR = "_relgraph_exact_decimal_spelling"
_EXACT_DECIMAL_MAX_DIGITS = 16384


@dataclass(frozen=True)
class RawRelation:
    left: ast.expr
    operator: str
    right: ast.expr


@dataclass(frozen=True)
class RawFormula:
    source: str
    alternatives: tuple[tuple[RawRelation, ...], ...]


def _iter_relations(source: str) -> Iterator[RawRelation]:
    for segment in _split_constraint_segments(source):
        left, operator, right = _split_relation(segment)
        yield RawRelation(_parse_expr(left), operator, _parse_expr(right))


def _iter_raw_alternatives(source: str) -> Iterator[Iterator[RawRelation]]:
    # Lazy raw relations allow adapters to preserve downstream error order.
    for alternative in _split_relation_alternatives(normalize_formula(source)):
        yield _iter_relations(alternative)


def parse_formula(source: str) -> RawFormula:
    """Return ordered unsimplified relations. AST representation is provisional."""
    return RawFormula(source, tuple(tuple(a) for a in _iter_raw_alternatives(source)))


def _parse_expr(source: str) -> ast.expr:
    python_source = source.replace("^", "**")
    try:
        node = ast.parse(python_source, mode="eval").body
    except SyntaxError as exc:
        raise ValueError(f"could not parse expression {source!r}") from exc
    _annotate_exact_decimal_literals(node, python_source)
    _validate_expr(node)
    return node


def _annotate_exact_decimal_literals(node: ast.AST, source: str) -> None:
    for candidate in ast.walk(node):
        if not isinstance(candidate, ast.Constant) or not isinstance(
            candidate.value,
            float,
        ):
            continue
        spelling = ast.get_source_segment(source, candidate)
        if spelling is None:
            raise ValueError("decimal literal has no retained source spelling")
        exact = _parse_exact_decimal_spelling(spelling)
        setattr(candidate, _EXACT_DECIMAL_NUMERATOR_ATTR, exact.numerator)
        setattr(candidate, _EXACT_DECIMAL_DENOMINATOR_ATTR, exact.denominator)
        setattr(candidate, _EXACT_DECIMAL_SPELLING_ATTR, spelling)


def _parse_exact_decimal_spelling(spelling: str) -> Fraction:
    """Retain base-ten value, including scientific notation, before rounding.

    The digit/scale budget bounds allocation even when Python parsed a tiny
    token such as 1e999999999 as infinity. Oversized input is rejected, never
    replaced by a rounded zero or infinity.
    """
    match = re.fullmatch(r"([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?", spelling)
    if match is None or not (match[1] or match[2]):
        raise _UnsupportedNumericLiteral(
            f"invalid decimal literal spelling: {spelling!r}"
        )
    integer_digits, fractional_digits = match[1], match[2] or ""
    digits = integer_digits + fractional_digits
    exponent_digits = (match[3] or "0").lstrip("+-").lstrip("0") or "0"
    if len(digits) > _EXACT_DECIMAL_MAX_DIGITS or len(exponent_digits) > 5:
        raise _UnsupportedNumericLiteral(
            "decimal literal exceeds the 16384-digit/scale budget"
        )
    exponent = int(exponent_digits) * (-1 if (match[3] or "").startswith("-") else 1)
    scale = exponent - len(fractional_digits)
    if max(abs(scale), len(digits) + max(scale, 0)) > _EXACT_DECIMAL_MAX_DIGITS:
        raise _UnsupportedNumericLiteral(
            "decimal literal exceeds the 16384-digit/scale budget"
        )
    numerator = _ascii_decimal_integer(digits)
    return (
        Fraction(numerator * 10**scale)
        if scale >= 0
        else Fraction(numerator, 10**-scale)
    )


def _ascii_decimal_integer(digits: str) -> int:
    value = 0
    chunk_size = 9
    for offset in range(0, len(digits), chunk_size):
        chunk = digits[offset : offset + chunk_size]
        value = value * (cast(int, 10 ** len(chunk))) + int(chunk)
    return value


def _exact_decimal_fraction(node: ast.AST) -> Fraction | None:
    if not isinstance(node, ast.Constant):
        return None
    numerator = getattr(node, _EXACT_DECIMAL_NUMERATOR_ATTR, None)
    denominator = getattr(node, _EXACT_DECIMAL_DENOMINATOR_ATTR, None)
    if not isinstance(numerator, int) or not isinstance(denominator, int):
        return None
    if denominator <= 0:
        return None
    return Fraction(numerator, denominator)


def _validate_expr(node: ast.AST) -> None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise ValueError("Boolean literals are not numeric constants")
        if not isinstance(node.value, (int, float)):
            raise ValueError("only numeric constants are supported")
        return
    if isinstance(node, ast.Name):
        if node.id not in {"x", "y", "pi", "e"}:
            raise ValueError(f"unsupported name {node.id!r}")
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        _validate_expr(node.operand)
        return
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
    ):
        _validate_expr(node.left)
        _validate_expr(node.right)
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or not (
            node.func.id in _SUPPORTED_FUNCTIONS or _is_fallback_function(node.func.id)
        ):
            raise ValueError(_SUPPORTED_FUNCTIONS_MESSAGE)
        if not _function_accepts_arity(node.func.id, len(node.args)) or node.keywords:
            raise ValueError(_function_arity_error(node.func.id))
        for argument in node.args:
            _validate_expr(argument)
        return
    raise ValueError(
        f"unsupported expression syntax: {ast.dump(node, include_attributes=False)}"
    )


def exact_decimal_value(node: ast.AST) -> Fraction | None:
    """Return the exact decimal leaf value, without binary64 conversion."""
    return _exact_decimal_fraction(node)


def decimal_spelling(node: ast.AST) -> str | None:
    """Return retained normalized decimal spelling, or None for other nodes."""
    value = getattr(node, _EXACT_DECIMAL_SPELLING_ATTR, None)
    return value if isinstance(value, str) else None
