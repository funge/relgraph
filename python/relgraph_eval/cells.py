# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Ordered headless evaluation records and the direct interval cell test."""

from __future__ import annotations
import ast
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, cast
from .dispatch import DispatchOps
from .values import _CInterval, _ChartDomain, _EvalResult, _EvalSet
from .definedness import (
    BoolInterval as _CBoolInterval,
    bool_and as _bool_and,
    bool_or as _bool_or,
    bool_is_false,
    bool_is_true,
)
from .comparisons import _compare_eval_sets


class RelationInput(Protocol):
    @property
    def left(self) -> ast.AST: ...
    @property
    def right(self) -> ast.AST: ...
    @property
    def operator(self) -> str: ...


class FormulaHost(Protocol):
    def _eval_expr_set(
        self, node: ast.AST, x: _CInterval, y: _CInterval, ops: DispatchOps
    ) -> _EvalSet: ...
    def _refine_constant_set_relation(
        self,
        relation: RelationInput,
        left: _EvalSet,
        right: _EvalSet,
        truth: _CBoolInterval,
    ) -> _CBoolInterval: ...


class BoxClassificationState(str, Enum):
    ABSENT = "absent"
    PRESENT = "present"
    UNDECIDED = "undecided"


class BoxClassificationProof(str, Enum):
    DIRECT_INTERVAL_FALSE = "direct_interval_false"
    DIRECT_INTERVAL_TRUE = "direct_interval_true"


@dataclass(frozen=True)
class IntervalRecord:
    lo: float
    hi: float


@dataclass(frozen=True)
class BoolIntervalRecord:
    lo: bool
    hi: bool


@dataclass(frozen=True)
class ChartRecord:
    x: IntervalRecord
    y: IntervalRecord


@dataclass(frozen=True)
class EvaluationBranch:
    interval: IntervalRecord
    defined: BoolIntervalRecord
    continuous: bool
    dependency: str
    chart: ChartRecord | None


@dataclass(frozen=True)
class ExpressionEvaluation:
    branches: tuple[EvaluationBranch, ...]
    defined: BoolIntervalRecord
    continuous: bool
    dependency: str


@dataclass(frozen=True)
class RelationEvaluation:
    operator: str
    left: ExpressionEvaluation
    right: ExpressionEvaluation
    truth: BoolIntervalRecord


@dataclass(frozen=True)
class AlternativeEvaluation:
    relation_offset: int
    relation_count: int
    truth: BoolIntervalRecord


@dataclass(frozen=True)
class EvaluationCounts:
    relation_count: int
    expression_count: int
    branch_count: int


def _interval_record(interval: Any) -> IntervalRecord:
    return IntervalRecord(float(interval.lo), float(interval.hi))


def _bool_record(value: Any) -> BoolIntervalRecord:
    return BoolIntervalRecord(bool(value.lo), bool(value.hi))


def _chart_record(chart: _ChartDomain | None) -> ChartRecord | None:
    if chart is None:
        return None
    return ChartRecord(_interval_record(chart.x), _interval_record(chart.y))


def _branch_record(branch: _EvalResult, dependency: str) -> EvaluationBranch:
    return EvaluationBranch(
        interval=_interval_record(branch.interval),
        defined=_bool_record(branch.defined),
        continuous=branch.continuous,
        dependency=dependency,
        chart=_chart_record(branch.chart),
    )


def _expression_record(value: _EvalSet, dependency: str) -> ExpressionEvaluation:
    return ExpressionEvaluation(
        branches=tuple(_branch_record(branch, dependency) for branch in value.branches),
        defined=_bool_record(value.defined),
        continuous=value.continuous,
        dependency=dependency,
    )


@dataclass(frozen=True)
class FormulaFold:
    truth: BoolIntervalRecord
    relations: tuple[RelationEvaluation, ...]
    alternatives: tuple[AlternativeEvaluation, ...]
    required_branch_capacity: int
    counts: EvaluationCounts


def evaluate_formula(
    alternatives_input: tuple[tuple[RelationInput, ...], ...],
    x: _CInterval,
    y: _CInterval,
    ops: DispatchOps,
    *,
    host: FormulaHost,
) -> FormulaFold:
    relations: list[RelationEvaluation] = []
    alternatives: list[AlternativeEvaluation] = []
    formula_truth = _CBoolInterval(False, False)
    required_capacity = 0

    for alternative in alternatives_input:
        relation_offset = len(relations)
        alternative_truth = _CBoolInterval(True, True)
        for relation in alternative:
            left_set = host._eval_expr_set(relation.left, x, y, ops)
            right_set = host._eval_expr_set(relation.right, x, y, ops)
            relation_truth = _compare_eval_sets(
                left_set,
                right_set,
                relation.operator,
                ops,
            )
            relation_truth = host._refine_constant_set_relation(
                relation, left_set, right_set, relation_truth
            )
            left_dependency = ops.expression_dependency(relation.left)
            right_dependency = ops.expression_dependency(relation.right)
            left = _expression_record(left_set, left_dependency)
            right = _expression_record(right_set, right_dependency)
            required_capacity += len(left.branches) + len(right.branches)
            alternative_truth = _bool_and(alternative_truth, relation_truth)
            relations.append(
                RelationEvaluation(
                    operator=relation.operator,
                    left=left,
                    right=right,
                    truth=_bool_record(relation_truth),
                )
            )
        alternatives.append(
            AlternativeEvaluation(
                relation_offset=relation_offset,
                relation_count=len(alternative),
                truth=_bool_record(alternative_truth),
            )
        )
        formula_truth = _bool_or(formula_truth, alternative_truth)

    counts = EvaluationCounts(
        relation_count=len(relations),
        expression_count=2 * len(relations),
        branch_count=required_capacity,
    )
    return FormulaFold(
        _bool_record(formula_truth),
        tuple(relations),
        tuple(alternatives),
        required_capacity,
        counts,
    )


def interval_cell_state(
    truth: BoolIntervalRecord | _CBoolInterval | None,
    *,
    valid: bool = True,
    has_witness: bool = True,
) -> BoxClassificationState:
    """False over the outer box proves absence; true needs a contained witness.

    Invalid/unknown results remain undecided. This is only the direct interval
    test, not a replacement for a caller's ordered existence/proof policies.
    """
    if not valid or truth is None:
        return BoxClassificationState.UNDECIDED
    if bool_is_false(cast(_CBoolInterval, truth)):
        return BoxClassificationState.ABSENT
    if has_witness and bool_is_true(cast(_CBoolInterval, truth)):
        return BoxClassificationState.PRESENT
    return BoxClassificationState.UNDECIDED
