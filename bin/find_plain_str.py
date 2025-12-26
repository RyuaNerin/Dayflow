import ast
from pathlib import Path
import re

import pathspec


re_zh_cn = re.compile("[\u4e00-\u9fff]")


class HardcodedStringFinder(ast.NodeVisitor):
    def __init__(self):
        self.results = []
        self.context_stack = []
        self.docstrings = set()

    def _mark_docstring(self, body):
        """바디의 첫 번째 문이 문자열이면 docstring으로 마킹"""
        if body and isinstance(body[0], ast.Expr):
            expr = body[0].value
            if isinstance(expr, (ast.Constant, ast.Constant)):
                self.docstrings.add(id(expr))

    def visit_Module(self, node):
        self._mark_docstring(node.body)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._mark_docstring(node.body)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._mark_docstring(node.body)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._mark_docstring(node.body)
        self.generic_visit(node)

    def visit_Call(self, node):
        # _() i18n 함수
        if isinstance(node.func, ast.Name) and node.func.id == "_":
            self.context_stack.append("i18n")
            self.generic_visit(node)
            self.context_stack.pop()
            return

        # logging/logger
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id in ("logging", "logger", "log", "_log"):
                    self.context_stack.append("logging")
                    self.generic_visit(node)
                    self.context_stack.pop()
                    return

        self.generic_visit(node)

    def visit_Str(self, node):
        self.visit_Constant(node)

    def visit_Constant(self, node):
        if not isinstance(node.value, str):
            return

        if not node.value.strip():
            return

        if id(node) in self.docstrings:
            return

        if "i18n" in self.context_stack or "logging" in self.context_stack:
            return

        if re_zh_cn.match(node.value) is None:
            return

        self.results.append(
            {"line": node.lineno, "col": node.col_offset, "value": node.value}
        )


def find_hardcoded_strings(file_path: str):
    code = Path(file_path).read_text(encoding="utf-8")
    tree = ast.parse(code)
    finder = HardcodedStringFinder()
    finder.visit(tree)
    return finder.results


def main():
    local_dir = Path(__file__).parent
    root_dir = local_dir.parent

    gitignore_path = root_dir / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, encoding="utf-8") as f:
            spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
    else:
        spec = pathspec.PathSpec.from_lines("gitwildmatch", [])

    for file_path in root_dir.rglob("*.py"):
        if file_path.is_relative_to(local_dir):
            continue

        rel_path = file_path.relative_to(root_dir)
        if spec.match_file(rel_path):
            continue

        results = find_hardcoded_strings(str(file_path))
        if results:
            lines = [
                "=" * 50,
            ]
            for r in results:
                lines.append(f"{file_path}#{r['line']}: {r['value']!r}")

            print("\n".join(lines))


if __name__ == "__main__":
    main()
