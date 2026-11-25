"""The calculator (no Qt): sums as you type, never Python's eval. The text is parsed into Python's syntax tree and only
numbers, + - * / // % ** (and ^ × ÷), brackets, a few functions and pi / e / tau are allowed; a power is capped so
9**9**9 can't freeze the launcher."""

from __future__ import annotations

import ast
import math
import operator
import re

FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos,
         "atan": math.atan, "log": math.log, "ln": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp,
         "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil, "min": min, "max": max,
         "deg": math.degrees, "rad": math.radians}
CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
       ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
LOOKS = re.compile(r"^[\d\s.,+\-*/%^()×÷a-z]*\d[\d\s.,+\-*/%^()×÷a-z]*$", re.I)


class CalcError(ValueError):
    pass


def looks_like_math(text: str) -> bool:
    """Worth answering without the = keyword: digits and at least one operator, nothing else but function names."""
    t = text.strip()
    return bool(LOOKS.match(t)) and bool(re.search(r"\d\s*[-+*/%^×÷]|[)]\s*[-+*/%^×÷]|^\s*-?\s*\w+\(", t)) and \
        not re.fullmatch(r"[\d\s.,-]+", t)


def evaluate(text: str) -> float | int:
    t = text.strip().replace("×", "*").replace("÷", "/").replace("^", "**")
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)           # 1,000 = 1000
    t = t.replace(",", ".") if "." not in t and re.search(r"\d,\d", t) else t
    try:
        tree = ast.parse(t, mode="eval")
    except SyntaxError as e:
        raise CalcError("not a sum") from e
    return _eval(tree.body)


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id.lower() in CONSTS:
        return CONSTS[node.id.lower()]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp):
        a, b = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(b) > 1000 or (abs(a) > 1e6 and abs(b) > 50):
                raise CalcError("too big")
            return a ** b
        op = OPS.get(type(node.op))
        if op is None:
            raise CalcError("not allowed")
        try:
            return op(a, b)
        except ZeroDivisionError as e:
            raise CalcError("division by zero") from e
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.lower() in FUNCS \
            and not node.keywords:
        args = [_eval(a) for a in node.args]
        try:
            return FUNCS[node.func.id.lower()](*args)
        except (ValueError, TypeError) as e:
            raise CalcError(str(e)) from e
    raise CalcError("not allowed")


def show(v) -> str:
    """The answer as text: whole numbers without .0, others to 10 significant figures."""
    if isinstance(v, complex):
        raise CalcError("complex")
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        v = int(v)
    if isinstance(v, int):
        return str(v)
    return f"{v:.10g}"
