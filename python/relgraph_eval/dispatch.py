# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Scalar/set AST dispatch with explicit caller-owned source and recursion services."""

from __future__ import annotations
import ast
from typing import Callable, Protocol
from fractions import Fraction
from .rational_refinement import _LinearRationalPlan
from .operations import _IntervalOps

from relgraph_parser.syntax import (
    _SUPPORTED_FUNCTIONS,
    _function_accepts_arity,
    _function_arity_error,
)
from .functions.common_factor import _common_factor_eval_set, _common_factor_result
from .functions.elementary import (
    _elementary_scalar_result,
    _unary_eval_set,
    _atan_eval_set,
    _sqrt_eval_set,
    _log2_eval_set,
    _elementary_unary_result,
    _elementary_unary_eval_set,
    _atan_result,
    _log2_result,
    _sqrt_result,
)
from .functions.atan2 import _atan2_eval_set, _atan2_result
from .functions.periodic import (
    _periodic_constant_eval_set,
    _periodic_unary_eval_set,
    _tan_eval_set,
    _tan_result,
    _periodic_scalar_result,
    _periodic_scalar_constant_result,
)
from .functions.discrete import (
    _factorial_eval_set,
    _integer_scalar_result,
    _factorial_result,
)
from .functions.remainders import _mod_eval_set, _fmod_eval_set, _remainder_result
from .functions.division import _division_eval_set, _division_result
from .functions.fallback import _fallback_function_result
from .functions.powers import (
    _integer_power_result,
    _zero_base_power_result,
    _self_power_result,
    _zero_base_power_eval_set,
    _self_power_eval_set,
    _rational_power_result,
    _rational_power_eval_set,
    _positive_integer_literal_power_result,
    _power_eval_set,
    _positive_base_power_result,
    _positive_base_power_eval_set,
    _positive_constant_base_power_eval_set,
)
from .arithmetic import (
    _binary_eval_set,
    _add_result,
    _subtract_result,
    _multiply_result,
    _negate_result,
    _minmax_result,
    _negate_eval_set,
)
from .metadata import _coordinate_affine, _make_interval_affine
from .sets import _eval_set, _eval_set_from_result
from .values import _ChartDomain, _EvalResult, _EvalSet
from relgraph_parser.syntax import _is_fallback_function
from .numeric import _BOOL_TRUE, _bool_and, _bool_is_true
from .values import _CInterval
from relgraph_parser.syntax import _ELEMENTARY_UNARY_FUNCTIONS


class DispatchOps(_IntervalOps, Protocol):
    @property
    def chart_loss_enabled(self) -> bool: ...

    def expression_dependency(self, node: ast.AST) -> str: ...
    def branch_site(
        self, node: ast.AST, *, x: _CInterval, y: _CInterval
    ) -> object | None: ...


class DispatchHost(Protocol):
    """Live source/recursion services; no callback snapshot or context replacement."""

    def _ast_equivalent(self, left: ast.AST, right: ast.AST) -> bool: ...
    def _constant_integer(self, node: ast.AST) -> int | None: ...
    def _constant_literal_interval(
        self, node: ast.Constant, ops: DispatchOps
    ) -> tuple[_CInterval, float | None]: ...
    def _constant_rational_exponent(self, node: ast.AST) -> Fraction | None: ...
    def _equal_operand_power(self, node: ast.BinOp) -> bool: ...
    def _eval_expr(
        self,
        node: ast.AST,
        x: _CInterval,
        y: _CInterval,
        ops: DispatchOps,
        *,
        cache: dict[str, _EvalResult] | None = None,
    ) -> _EvalResult: ...
    def _eval_expr_set(
        self, node: ast.AST, x: _CInterval, y: _CInterval, ops: DispatchOps
    ) -> _EvalSet: ...
    def _exact_direct_signed_pi(self, node: ast.AST) -> int | None: ...
    def _exact_named_constant_binary64_interval(
        self, node: ast.AST
    ) -> tuple[float, float] | None: ...
    def _exact_periodic_value(
        self,
        node: ast.AST,
        name: str,
        x: _CInterval,
        y: _CInterval,
        ops: DispatchOps,
        cache: dict[str, _EvalResult] | None = None,
    ) -> float | None: ...
    def _expr_source(self, node: ast.AST) -> str: ...
    def _integer_function_eval_set(
        self,
        argument: _EvalSet,
        operation: Callable[[_CInterval], _CInterval],
        ops: DispatchOps,
        *,
        operator_name: str,
        branch_site: object | None = None,
    ) -> _EvalSet: ...
    def _inverse_sinc_eval_set(
        self,
        phase: ast.AST,
        x: _CInterval,
        y: _CInterval,
        ops: DispatchOps,
        *,
        evaluate: Callable[[ast.AST, _CInterval, _CInterval, DispatchOps], _EvalSet],
        expression_source: str | None = None,
    ) -> _EvalSet | None: ...
    def _inverse_sinc_phase(self, node: ast.BinOp) -> ast.expr | None: ...
    def _linear_rational_plan(
        self, node: ast.BinOp, x: _CInterval, y: _CInterval, ops: DispatchOps
    ) -> _LinearRationalPlan | None: ...
    def _positive_integer_literal_base_value(self, node: ast.AST) -> int | None: ...
    def _positive_variable_base_power(self, node: ast.BinOp) -> bool: ...
    def _uses_bounded_literal_power(self, node: ast.BinOp) -> bool: ...
    def _zero_constant_base_power(self, node: ast.BinOp) -> bool: ...


def _eval_expr_uncached(
    node: ast.AST,
    x: _CInterval,
    y: _CInterval,
    ops: DispatchOps,
    *,
    host: DispatchHost,
    cache: dict[str, _EvalResult] | None,
) -> _EvalResult:
    if isinstance(node, ast.Constant):
        interval, scalar = host._constant_literal_interval(node, ops)
        return _EvalResult(
            interval,
            _BOOL_TRUE,
            True,
            constant=scalar,
        )
    if isinstance(node, ast.Name):
        if node.id == "x":
            return _EvalResult(x, _BOOL_TRUE, True)
        if node.id == "y":
            return _EvalResult(y, _BOOL_TRUE, True)
        exact_interval = host._exact_named_constant_binary64_interval(node)
        if exact_interval is not None:
            return _EvalResult(ops.make(*exact_interval), _BOOL_TRUE, True)

    if isinstance(node, ast.UnaryOp):
        operand = host._eval_expr(node.operand, x, y, ops, cache=cache)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return _negate_result(operand, ops)

    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Sub) and host._ast_equivalent(node.left, node.right):
            operand = host._eval_expr(node.left, x, y, ops, cache=cache)
            return _EvalResult(
                ops.point(0.0),
                operand.defined,
                operand.continuous,
                constant=0.0,
            )
        left = host._eval_expr(node.left, x, y, ops, cache=cache)
        right = host._eval_expr(node.right, x, y, ops, cache=cache)
        defined = _bool_and(left.defined, right.defined)
        continuous = left.continuous and right.continuous and _bool_is_true(defined)
        if isinstance(node.op, ast.Add):
            return _add_result(left, right, defined, continuous, ops)
        if isinstance(node.op, ast.Sub):
            return _subtract_result(left, right, defined, continuous, ops)
        if isinstance(node.op, ast.Mult):
            return _multiply_result(left, right, defined, continuous, ops)
        if isinstance(node.op, ast.Div):
            plan = host._linear_rational_plan(node, x, y, ops)
            if plan is None:
                return _division_result(left, right, defined, continuous, ops)
            return _division_result(
                left, right, defined, continuous, ops, rational_plan=plan
            )
        if isinstance(node.op, ast.Pow):
            literal_base = host._positive_integer_literal_base_value(node.left)
            if literal_base is not None and not host._uses_bounded_literal_power(node):
                return _positive_integer_literal_power_result(literal_base, right, ops)
            exponent = host._constant_integer(node.right)
            pow_defined = left.defined
            pow_continuous = left.continuous
            if exponent is None:
                dependency = ops.expression_dependency(node.left)
                if dependency == "constant" and left.interval.lo > 0.0:
                    return _positive_base_power_result(left, right, ops)
                exact = host._constant_rational_exponent(node.right)
                if exact is not None:
                    return _rational_power_result(left, right, exact, ops)
                if host._zero_constant_base_power(node):
                    return _zero_base_power_result(left, right, ops)
                if dependency != "constant":
                    if host._positive_variable_base_power(node):
                        return _positive_base_power_result(left, right, ops)
                    if host._equal_operand_power(node):
                        return _self_power_result(left, right, ops)
                    raise ValueError(
                        "exponents must be integer constants unless the base is positive constant"
                    )
                if host._equal_operand_power(node):
                    return _self_power_result(left, right, ops)
                return _positive_base_power_result(left, right, ops)
            return _integer_power_result(
                left, exponent, pow_defined, pow_continuous, ops
            )

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        name = node.func.id
        if name in _SUPPORTED_FUNCTIONS or _is_fallback_function(name):
            if node.keywords or any(
                isinstance(argument, ast.Starred) for argument in node.args
            ):
                raise ValueError(
                    f"function {name} accepts only positional, non-starred arguments"
                )
            arity = len(node.args)
            if not _function_accepts_arity(name, arity):
                raise ValueError(f"{_function_arity_error(name)} (got {arity})")
        if name in _ELEMENTARY_UNARY_FUNCTIONS:
            argument = host._eval_expr(node.args[0], x, y, ops, cache=cache)
            return _elementary_unary_result(name, argument, ops)
        if _is_fallback_function(name):
            arguments = tuple(
                host._eval_expr(argument, x, y, ops, cache=cache)
                for argument in node.args
            )
            return _fallback_function_result(
                tuple(argument.defined for argument in arguments),
                ops,
            )
        if name in {
            "abs",
            "atan",
            "cbrt",
            "ceil",
            "cos",
            "factorial",
            "floor",
            "log2",
            "sin",
            "sqrt",
            "tan",
        }:
            argument = host._eval_expr(node.args[0], x, y, ops, cache=cache)
            if name == "abs":
                return _elementary_scalar_result(
                    _EvalResult, ops.abs(argument.interval), argument
                )
            if name == "atan":
                return _atan_result(argument, ops)
            if name == "cbrt":
                return _elementary_scalar_result(
                    _EvalResult, ops.cbrt(argument.interval), argument
                )
            if name in {"ceil", "floor"}:
                operation = ops.ceil if name == "ceil" else ops.floor
                return _integer_scalar_result(operation, argument, ops)
            if name == "cos":
                if (
                    host._exact_direct_signed_pi(phase_argument := node.args[0])
                    is not None
                ):
                    return _periodic_scalar_constant_result(
                        _EvalResult,
                        ops.point(-1.0),
                        argument,
                        -1.0,
                    )
                exact_constant = host._exact_periodic_value(
                    phase_argument, "cos", x, y, ops, cache
                )
                if exact_constant is not None:
                    return _periodic_scalar_constant_result(
                        _EvalResult, ops.point(exact_constant), argument, exact_constant
                    )
                return _periodic_scalar_result(
                    _EvalResult, ops.cos(argument.interval), argument
                )
            if name == "factorial":
                return _factorial_result(argument, ops)
            if name == "log2":
                return _log2_result(argument, ops)
            if name == "sin":
                if (
                    host._exact_direct_signed_pi(phase_argument := node.args[0])
                    is not None
                ):
                    return _periodic_scalar_constant_result(
                        _EvalResult,
                        ops.point(0.0),
                        argument,
                        0.0,
                    )
                exact_constant = host._exact_periodic_value(
                    phase_argument, "sin", x, y, ops, cache
                )
                if exact_constant is not None:
                    return _periodic_scalar_constant_result(
                        _EvalResult, ops.point(exact_constant), argument, exact_constant
                    )
                return _periodic_scalar_result(
                    _EvalResult, ops.sin(argument.interval), argument
                )
            if name == "sqrt":
                return _sqrt_result(argument, ops)
            if name == "tan":
                return _tan_result(argument, ops)
        if name == "atan2":
            y_result = host._eval_expr(node.args[0], x, y, ops, cache=cache)
            x_result = host._eval_expr(node.args[1], x, y, ops, cache=cache)
            return _atan2_result(y_result, x_result, ops)
        if name in {"max", "min"}:
            operation = ops.max if name == "max" else ops.min
            result = host._eval_expr(node.args[0], x, y, ops, cache=cache)
            for argument_node in node.args[1:]:
                argument = host._eval_expr(argument_node, x, y, ops, cache=cache)
                result = _minmax_result(result, argument, operation)
            return result
        if name in {"gcd", "lcm"}:
            arguments = tuple(
                host._eval_expr(argument, x, y, ops, cache=cache)
                for argument in node.args
            )
            return _common_factor_result(name, arguments, ops)
        if name in {"mod", "fmod"}:
            left = host._eval_expr(node.args[0], x, y, ops, cache=cache)
            right = host._eval_expr(node.args[1], x, y, ops, cache=cache)
            return _remainder_result(name, left, right, ops)

    raise ValueError(
        f"unsupported expression syntax: {ast.dump(node, include_attributes=False)}"
    )


def _eval_expr_set_uncached(
    node: ast.AST,
    x: _CInterval,
    y: _CInterval,
    ops: DispatchOps,
    *,
    host: DispatchHost,
) -> _EvalSet:
    chart = _ChartDomain(x, y)
    if isinstance(node, ast.Constant):
        interval, constant = host._constant_literal_interval(node, ops)
        return _eval_set_from_result(
            _EvalResult(
                interval,
                _BOOL_TRUE,
                True,
                chart,
                constant=constant,
                interval_affine=_make_interval_affine(None, 0, interval),
            ),
            ops,
        )
    if isinstance(node, ast.Name):
        if node.id == "x":
            return _eval_set_from_result(
                _EvalResult(
                    x,
                    _BOOL_TRUE,
                    True,
                    chart,
                    "x",
                    _coordinate_affine("x"),
                    interval_affine=_make_interval_affine("x", 1, ops.point(0.0)),
                ),
                ops,
            )
        if node.id == "y":
            return _eval_set_from_result(
                _EvalResult(
                    y,
                    _BOOL_TRUE,
                    True,
                    chart,
                    "y",
                    _coordinate_affine("y"),
                    interval_affine=_make_interval_affine("y", 1, ops.point(0.0)),
                ),
                ops,
            )
        exact_interval = host._exact_named_constant_binary64_interval(node)
        if exact_interval is not None:
            interval = ops.make(*exact_interval)
            return _eval_set_from_result(
                _EvalResult(
                    interval,
                    _BOOL_TRUE,
                    True,
                    chart,
                    interval_affine=_make_interval_affine(None, 0, interval),
                ),
                ops,
            )

    if isinstance(node, ast.UnaryOp):
        operand = host._eval_expr_set(node.operand, x, y, ops)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return _negate_eval_set(operand, ops)

    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Sub) and host._ast_equivalent(node.left, node.right):
            operand = host._eval_expr_set(node.left, x, y, ops)
            return _EvalSet(
                tuple(
                    _EvalResult(
                        ops.point(0.0),
                        branch.defined,
                        branch.continuous,
                        branch.chart,
                        constant=0.0,
                        branch_map=branch.branch_map,
                        interval_affine=_make_interval_affine(None, 0, ops.point(0.0)),
                    )
                    for branch in operand.branches
                ),
                operand.defined,
                operand.continuous,
            )
        if isinstance(node.op, ast.Div):
            inverse_sinc_phase = host._inverse_sinc_phase(node)
            if inverse_sinc_phase is not None:
                inverse_sinc = host._inverse_sinc_eval_set(
                    inverse_sinc_phase,
                    x,
                    y,
                    ops,
                    evaluate=host._eval_expr_set,
                    expression_source=(
                        host._expr_source(node) if ops.chart_loss_enabled else None
                    ),
                )
                if inverse_sinc is not None:
                    return inverse_sinc
        left = host._eval_expr_set(node.left, x, y, ops)
        right = host._eval_expr_set(node.right, x, y, ops)
        expression_source = host._expr_source(node) if ops.chart_loss_enabled else None
        if isinstance(node.op, ast.Add):
            return _binary_eval_set(
                left,
                right,
                ops.add,
                ops,
                affine_operation="add",
                expression_source=expression_source,
            )
        if isinstance(node.op, ast.Sub):
            return _binary_eval_set(
                left,
                right,
                ops.sub,
                ops,
                affine_operation="sub",
                expression_source=expression_source,
            )
        if isinstance(node.op, ast.Mult):
            return _binary_eval_set(
                left,
                right,
                ops.mul,
                ops,
                affine_operation="mul",
                expression_source=expression_source,
            )
        if isinstance(node.op, ast.Div):
            plan = host._linear_rational_plan(node, x, y, ops)
            if plan is None:
                return _division_eval_set(
                    left, right, ops, expression_source=expression_source
                )
            return _division_eval_set(
                left,
                right,
                ops,
                expression_source=expression_source,
                rational_plan=plan,
            )
        if isinstance(node.op, ast.Pow):
            literal_base = host._positive_integer_literal_base_value(node.left)
            if literal_base is not None and not host._uses_bounded_literal_power(node):
                return _positive_constant_base_power_eval_set(
                    float(literal_base),
                    right,
                    ops,
                    exact_base=bool(left.branches)
                    and all(
                        branch.constant == float(literal_base)
                        for branch in left.branches
                    ),
                )
            exponent = host._constant_integer(node.right)
            if exponent is None:
                dependency = ops.expression_dependency(node.left)
                if (
                    dependency == "constant"
                    and bool(left.branches)
                    and all(branch.interval.lo > 0.0 for branch in left.branches)
                ):
                    return _positive_base_power_eval_set(left, right, ops)
                exact = host._constant_rational_exponent(node.right)
                if exact is not None:
                    return _rational_power_eval_set(left, right, exact, ops)
                if host._zero_constant_base_power(node):
                    return _zero_base_power_eval_set(left, right, ops)
                if dependency != "constant":
                    if host._positive_variable_base_power(node):
                        return _positive_base_power_eval_set(left, right, ops)
                    if host._equal_operand_power(node):
                        return _self_power_eval_set(left, right, ops)
                    raise ValueError(
                        "exponents must be integer constants unless the base is positive constant"
                    )
                if host._equal_operand_power(node):
                    return _self_power_eval_set(left, right, ops)
                return _positive_base_power_eval_set(left, right, ops)
            return _power_eval_set(left, exponent, ops)

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        name = node.func.id
        if name in _SUPPORTED_FUNCTIONS or _is_fallback_function(name):
            if node.keywords or any(
                isinstance(argument, ast.Starred) for argument in node.args
            ):
                raise ValueError(
                    f"function {name} accepts only positional, non-starred arguments"
                )
            arity = len(node.args)
            if not _function_accepts_arity(name, arity):
                raise ValueError(f"{_function_arity_error(name)} (got {arity})")
        if name in _ELEMENTARY_UNARY_FUNCTIONS:
            argument = host._eval_expr_set(node.args[0], x, y, ops)
            return _elementary_unary_eval_set(name, argument, ops)
        if _is_fallback_function(name):
            arguments = tuple(
                host._eval_expr_set(argument, x, y, ops) for argument in node.args
            )
            return _eval_set_from_result(
                _fallback_function_result(
                    tuple(argument.defined for argument in arguments),
                    ops,
                ),
                ops,
            )
        if name in {
            "abs",
            "atan",
            "cbrt",
            "ceil",
            "cos",
            "factorial",
            "floor",
            "log2",
            "sin",
            "sqrt",
            "tan",
        }:
            argument = host._eval_expr_set(node.args[0], x, y, ops)
            if name == "abs":
                return _unary_eval_set(argument, ops.abs, ops)
            if name == "atan":
                return _atan_eval_set(argument, ops)
            if name == "cbrt":
                return _unary_eval_set(argument, ops.cbrt, ops)
            if name in {"ceil", "floor"}:
                operation = ops.ceil if name == "ceil" else ops.floor
                return host._integer_function_eval_set(
                    argument,
                    operation,
                    ops,
                    operator_name=name,
                    branch_site=ops.branch_site(node, x=x, y=y),
                )
            if name == "factorial":
                return _factorial_eval_set(argument, ops)
            if name == "log2":
                return _log2_eval_set(argument, ops)
            if name == "cos":
                if (
                    host._exact_direct_signed_pi(phase_argument := node.args[0])
                    is not None
                ):
                    return _periodic_constant_eval_set(_eval_set, argument, ops, -1.0)
                exact_constant = host._exact_periodic_value(
                    phase_argument, "cos", x, y, ops
                )
                if exact_constant is not None:
                    return _periodic_constant_eval_set(
                        _eval_set, argument, ops, exact_constant
                    )
                return _periodic_unary_eval_set(
                    argument,
                    ops.cos,
                    ops,
                    operator_name="cos",
                    expression_source=host._expr_source(node)
                    if ops.chart_loss_enabled
                    else None,
                    phase_numerator=0,
                    period_numerator=1,
                    denominator=1,
                )
            if name == "sin":
                if (
                    host._exact_direct_signed_pi(phase_argument := node.args[0])
                    is not None
                ):
                    return _periodic_constant_eval_set(_eval_set, argument, ops, 0.0)
                exact_constant = host._exact_periodic_value(
                    phase_argument, "sin", x, y, ops
                )
                if exact_constant is not None:
                    return _periodic_constant_eval_set(
                        _eval_set, argument, ops, exact_constant
                    )
                return _periodic_unary_eval_set(
                    argument,
                    ops.sin,
                    ops,
                    operator_name="sin",
                    expression_source=host._expr_source(node)
                    if ops.chart_loss_enabled
                    else None,
                    phase_numerator=1,
                    period_numerator=2,
                    denominator=2,
                )
            if name == "sqrt":
                return _sqrt_eval_set(argument, ops)
            if name == "tan":
                return _tan_eval_set(argument, ops)
        if name == "atan2":
            y_result = host._eval_expr_set(node.args[0], x, y, ops)
            x_result = host._eval_expr_set(node.args[1], x, y, ops)
            return _atan2_eval_set(y_result, x_result, ops)
        if name in {"max", "min"}:
            operation = ops.max if name == "max" else ops.min
            result = host._eval_expr_set(node.args[0], x, y, ops)
            expression_source = (
                host._expr_source(node) if ops.chart_loss_enabled else None
            )
            for argument_node in node.args[1:]:
                result = _binary_eval_set(
                    result,
                    host._eval_expr_set(argument_node, x, y, ops),
                    operation,
                    ops,
                    affine_operation=name,
                    operator_name=name,
                    expression_source=expression_source,
                )
            return result
        if name in {"gcd", "lcm"}:
            arguments = tuple(
                host._eval_expr_set(argument, x, y, ops) for argument in node.args
            )
            operation = ops.gcd if name == "gcd" else ops.lcm
            return _common_factor_eval_set(arguments, operation, ops)
        if name == "fmod":
            left = host._eval_expr_set(node.args[0], x, y, ops)
            right = host._eval_expr_set(node.args[1], x, y, ops)
            return _fmod_eval_set(left, right, ops)
        if name == "mod":
            left = host._eval_expr_set(node.args[0], x, y, ops)
            right = host._eval_expr_set(node.args[1], x, y, ops)
            return _mod_eval_set(
                left, right, ops, branch_site=ops.branch_site(node, x=x, y=y)
            )

    raise ValueError(
        f"unsupported expression syntax: {ast.dump(node, include_attributes=False)}"
    )
