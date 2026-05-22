from __future__ import annotations
import ast
def ast_string_tuple(value: ast.AST) -> list[str]:
    if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        items: list[str] = []
        for element in value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                items.append(element.value)
        return items
    return []
def ast_string_list(value: ast.AST) -> list[str]:
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        items: list[str] = []
        for item in value.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                items.append(item.value)
        return items
    return []
def first_argument_name(call: ast.Call) -> str:
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return ""
__all__ = ["ast_string_tuple", "ast_string_list", "first_argument_name"]
