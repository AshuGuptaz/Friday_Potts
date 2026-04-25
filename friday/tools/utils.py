"""
Utility tools — text processing, formatting, calculations, unit conversions.
"""

import ast
import json
import math
import operator as _op

# AST-based safe evaluator — no eval(), no sandbox-escape risk.
_SAFE_OPS = {
    ast.Add: _op.add, ast.Sub: _op.sub, ast.Mult: _op.mul,
    ast.Div: _op.truediv, ast.Pow: _op.pow, ast.Mod: _op.mod,
    ast.FloorDiv: _op.floordiv, ast.USub: _op.neg, ast.UAdd: _op.pos,
}
_SAFE_NAMES = {
    "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "abs": abs,
    "round": round, "pow": pow, "floor": math.floor, "ceil": math.ceil,
}

def _safe_eval_node(node):
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _SAFE_NAMES:
        return _SAFE_NAMES[node.id]
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Operator not allowed: {type(node.op).__name__}")
        return op(_safe_eval_node(node.left), _safe_eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Operator not allowed: {type(node.op).__name__}")
        return op(_safe_eval_node(node.operand))
    if isinstance(node, ast.Call):
        fn = _safe_eval_node(node.func)
        if not callable(fn):
            raise ValueError("Not a callable")
        args = [_safe_eval_node(a) for a in node.args]
        return fn(*args)
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def register(mcp):

    @mcp.tool()
    def format_json(data: str) -> str:
        """Pretty-print a JSON string."""
        try:
            parsed = json.loads(data)
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"

    @mcp.tool()
    def word_count(text: str) -> dict:
        """Count words, characters, and lines in a block of text."""
        lines = text.splitlines()
        words = text.split()
        return {
            "characters": len(text),
            "words": len(words),
            "lines": len(lines),
        }

    @mcp.tool()
    def calculate(expression: str) -> str:
        """Evaluate a math expression. Supports +, -, *, /, **, sqrt, sin, cos, log, etc."""
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = _safe_eval_node(tree)
            return f"{expression} = {result}"
        except Exception as e:
            return f"Calculation error: {e}"

    @mcp.tool()
    def convert_units(value: float, from_unit: str, to_unit: str) -> str:
        """Convert between units: km/miles, kg/lbs, celsius/fahrenheit, meters/feet, liters/gallons."""
        conversions = {
            ("km", "miles"): lambda x: x * 0.621371,
            ("miles", "km"): lambda x: x * 1.60934,
            ("kg", "lbs"): lambda x: x * 2.20462,
            ("lbs", "kg"): lambda x: x / 2.20462,
            ("celsius", "fahrenheit"): lambda x: x * 9/5 + 32,
            ("fahrenheit", "celsius"): lambda x: (x - 32) * 5/9,
            ("meters", "feet"): lambda x: x * 3.28084,
            ("feet", "meters"): lambda x: x / 3.28084,
            ("liters", "gallons"): lambda x: x * 0.264172,
            ("gallons", "liters"): lambda x: x / 0.264172,
            ("cm", "inches"): lambda x: x / 2.54,
            ("inches", "cm"): lambda x: x * 2.54,
        }
        key = (from_unit.lower(), to_unit.lower())
        if key in conversions:
            result = conversions[key](value)
            return f"{value} {from_unit} = {round(result, 4)} {to_unit}"
        return f"Conversion from {from_unit} to {to_unit} not supported, sir."
