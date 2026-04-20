#!/usr/bin/env python3
"""PR consistency checker for sccfm-devkit.

Checks only Python files modified in the PR by default and validates:
  1. Local variable and parameter naming consistency.
  2. API response key -> Python name mapping consistency.
  3. Ansible DOCUMENTATION / EXAMPLES / RETURN contract consistency.
  4. CLI command naming and CLI <-> Ansible option alignment.
  5. Shared behavior consistency across paired ASA / FTD commands.
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    import yaml as _yaml

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

ROOT = Path(__file__).resolve().parent.parent
ANSIBLE_MODULES = ROOT / "sccfm-ansible" / "plugins" / "modules"
CLI_COMMANDS = ROOT / "sccfm_cli" / "commands"

_UPPER_SEQ_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
_LOWER_UPPER_RE = re.compile(r"([a-z0-9])([A-Z])")
_TRIPLE_ASSIGN_RE_TEMPLATE = r"^{name}\s*=\s*r?(?P<quote>'''|\"\"\")(?P<body>.*?)(?P=quote)"
_JINJA_REGISTER_REF_RE = re.compile(r"\b(?P<register>[A-Za-z_]\w*)\.(?P<key>[A-Za-z_]\w*)\b")
_JINJA_REGISTER_INDEX_RE = re.compile(
    r"""\b(?P<register>[A-Za-z_]\w*)\[['"](?P<key>[A-Za-z_]\w*)['"]\]"""
)

_DOC_MODULE_PREFIXES = (
    "create",
    "delete",
    "list",
    "get",
    "add",
    "remove",
    "update",
    "change",
    "check",
    "clear",
    "trigger",
    "execute",
    "show",
    "apply",
    "edit",
    "deploy",
    "onboard",
)

_SKIP_VAR_NAMES: frozenset[str] = frozenset(
    {"args", "kwargs", "cls", "self", "metavar", "nargs", "callback", "setUp", "tearDown"}
)
_ANSIBLE_META_RETURN_KEYS: frozenset[str] = frozenset(
    {
        "changed",
        "failed",
        "msg",
        "warnings",
        "deprecations",
        "invocation",
        "ansible_facts",
    }
)
_TASK_CTRL_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "register",
        "when",
        "loop",
        "loop_control",
        "become",
        "vars",
        "tags",
        "notify",
        "ignore_errors",
        "failed_when",
        "changed_when",
        "no_log",
        "check_mode",
        "block",
        "rescue",
        "always",
        "with_items",
        "with_list",
        "delegate_to",
        "run_once",
    }
)
_CLI_HELPER_OPTIONS: dict[str, frozenset[str]] = {
    "config_path_option": frozenset({"config_path"}),
    "format_option": frozenset({"format"}),
    "wait_option": frozenset({"wait"}),
    "timeout_option": frozenset({"timeout"}),
    "limit_option": frozenset({"limit"}),
    "offset_option": frozenset({"offset"}),
    "query_option": frozenset({"query"}),
    "device_name_option": frozenset({"device_name"}),
    "device_uids_option": frozenset({"device_uids"}),
    "asa_check_option": frozenset({"check"}),
    "ftd_check_option": frozenset({"check"}),
    "inventory_list_params": frozenset({"limit", "offset", "query", "format", "config_path"}),
}
_DEVICE_SPECIFIC_OPTION_EXTRAS: frozenset[str] = frozenset(
    {"asdm_version", "force_upgrade", "recommended"}
)
_DEVICE_SPECIFIC_OUTPUT_EXTRAS: frozenset[str] = frozenset({"mode", "skipped"})
_CLI_ANSIBLE_IGNORED_OPTIONS: frozenset[str] = frozenset(
    {"check", "config_path", "device_name", "format", "help"}
)
_CLI_TO_ANSIBLE_OPTION_ALIASES: dict[str, str] = {
    "device_uids": "uids",
}


@dataclass(frozen=True)
class Issue:
    file: Path
    line: int
    message: str
    level: str = "error"

    def as_annotation(self) -> str:
        rel = _display_path(self.file)
        return f"::{self.level} file={rel},line={self.line}::{self.message}"

    def as_text(self) -> str:
        rel = _display_path(self.file)
        return f"{self.level.upper()}: {rel}:{self.line}: {self.message}"


@dataclass(frozen=True)
class DocBlock:
    body: str
    start_line: int


@dataclass(frozen=True)
class MappingObservation:
    file: Path
    line: int
    json_key: str
    python_name: str


@dataclass(frozen=True)
class CliCommandMetadata:
    command_name: str | None
    command_name_line: int
    option_names: frozenset[str]
    json_keys: frozenset[str]
    operation_key: str | None
    device_family: str | None


@dataclass(frozen=True)
class AnsibleModuleMetadata:
    module_name: str | None
    module_name_line: int
    option_lines: dict[str, int]
    return_lines: dict[str, int]
    example_option_lines: dict[str, int]
    example_return_lines: dict[str, int]
    exit_json_keys: frozenset[str]
    operation_key: str | None
    device_family: str | None


def _display_path(path: Path) -> Path:
    candidate = path if path.is_absolute() else (ROOT / path)
    candidate = candidate.resolve()
    try:
        return candidate.relative_to(ROOT)
    except ValueError:
        return path


def _is_camel_case(name: str) -> bool:
    if not name or not name[0].islower():
        return False
    return bool(_LOWER_UPPER_RE.search(name))


def _camel_to_snake(name: str) -> str:
    s = _UPPER_SEQ_RE.sub(r"\1_\2", name)
    s = _LOWER_UPPER_RE.sub(r"\1_\2", s)
    return s.lower()


def _safe_parse(file: Path) -> ast.AST | None:
    try:
        return ast.parse(file.read_text(encoding="utf-8"))
    except SyntaxError:
        return None


def _extract_triple_quoted_assignment(source: str, name: str) -> DocBlock | None:
    pattern = re.compile(
        _TRIPLE_ASSIGN_RE_TEMPLATE.format(name=re.escape(name)),
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(source)
    if not match:
        return None
    start_line = source[: match.start("body")].count("\n") + 1
    return DocBlock(body=match.group("body"), start_line=start_line)


def _line_for_block_key(block: DocBlock, key: str) -> int:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*:", re.MULTILINE)
    match = pattern.search(block.body)
    if not match:
        return block.start_line
    return block.start_line + block.body[: match.start()].count("\n")


def _safe_yaml_load(raw: str) -> Any:
    if not _HAS_YAML:
        return None
    try:
        return _yaml.safe_load(raw)
    except _yaml.YAMLError:
        return None


def _string_value(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _bool_keyword(node: ast.Call, name: str, default: bool = False) -> bool:
    for keyword in node.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            if isinstance(keyword.value.value, bool):
                return keyword.value.value
    return default


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _long_option_name(flag: str) -> str | None:
    if not flag.startswith("--"):
        return None
    primary = flag.split("/", 1)[0]
    normalized = primary[2:].replace("-", "_")
    return normalized or None


def _extract_call_option_names(node: ast.Call) -> frozenset[str]:
    call_name = _call_name(node.func)
    if call_name == "click.Option" and node.args:
        flags_node = node.args[0]
        if isinstance(flags_node, (ast.List, ast.Tuple)):
            names = {
                name
                for element in flags_node.elts
                for name in [_long_option_name(_string_value(element) or "")]
                if name
            }
            return frozenset(names)
    if call_name in _CLI_HELPER_OPTIONS:
        return _CLI_HELPER_OPTIONS[call_name]
    if call_name in {"asa_device_filter_params", "ftd_device_filter_params"}:
        names = {"query", "limit", "offset", "device_uids"}
        if _bool_keyword(node, "include_device_name"):
            names.add("device_name")
        return frozenset(names)
    return frozenset()


def _extract_function_return_keys(tree: ast.AST) -> dict[str, frozenset[str]]:
    result: dict[str, set[str]] = defaultdict(set)

    class _ReturnVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.current_function: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.current_function.append(node.name)
            self.generic_visit(node)
            self.current_function.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Return(self, node: ast.Return) -> None:
            if not self.current_function:
                return
            function_name = self.current_function[-1]
            for key in _dict_literal_keys(node.value):
                result[function_name].add(key)

    _ReturnVisitor().visit(tree)
    return {name: frozenset(keys) for name, keys in result.items()}


def _dict_literal_keys(node: ast.AST | None) -> frozenset[str]:
    if not isinstance(node, ast.Dict):
        return frozenset()
    keys: set[str] = set()
    for key in node.keys:
        if key is None:
            continue
        key_value = _string_value(key)
        if key_value:
            keys.add(key_value)
    return frozenset(keys)


def _collect_assigned_key_sets(
    statements: Sequence[ast.stmt],
    function_return_keys: dict[str, frozenset[str]],
    assignments: dict[str, frozenset[str]] | None = None,
) -> dict[str, frozenset[str]]:
    local_assignments = dict(assignments or {})
    for statement in statements:
        if isinstance(statement, ast.Assign):
            key_set = _resolve_key_set(statement.value, local_assignments, function_return_keys)
            for target in statement.targets:
                if isinstance(target, ast.Name) and key_set:
                    local_assignments[target.id] = key_set
        elif isinstance(statement, ast.AnnAssign):
            if isinstance(statement.target, ast.Name) and statement.value is not None:
                key_set = _resolve_key_set(statement.value, local_assignments, function_return_keys)
                if key_set:
                    local_assignments[statement.target.id] = key_set
        for child_statements in _nested_statement_lists(statement):
            local_assignments.update(
                _collect_assigned_key_sets(
                    child_statements,
                    function_return_keys,
                    assignments=local_assignments,
                )
            )
    return local_assignments


def _nested_statement_lists(statement: ast.stmt) -> list[Sequence[ast.stmt]]:
    nested: list[Sequence[ast.stmt]] = []
    for attr in ("body", "orelse", "finalbody"):
        value = getattr(statement, attr, None)
        if isinstance(value, list):
            nested.append(value)
    if isinstance(statement, ast.Try):
        nested.extend(handler.body for handler in statement.handlers)
    if isinstance(statement, ast.Match):
        nested.extend(case.body for case in statement.cases)
    return nested


def _resolve_key_set(
    node: ast.AST,
    assignments: dict[str, frozenset[str]],
    function_return_keys: dict[str, frozenset[str]],
) -> frozenset[str]:
    if isinstance(node, ast.Dict):
        keys: set[str] = set()
        for key, value in zip(node.keys, node.values):
            if key is None:
                keys.update(_resolve_key_set(value, assignments, function_return_keys))
                continue
            key_value = _string_value(key)
            if key_value:
                keys.add(key_value)
        return frozenset(keys)
    if isinstance(node, ast.Name):
        return assignments.get(node.id, frozenset())
    if isinstance(node, ast.Call):
        call_name = _call_name(node.func)
        if call_name and call_name in function_return_keys:
            return function_return_keys[call_name]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _resolve_key_set(node.left, assignments, function_return_keys) | _resolve_key_set(
            node.right, assignments, function_return_keys
        )
    return frozenset()


def _extract_exit_json_keys(tree: ast.AST) -> frozenset[str]:
    function_return_keys = _extract_function_return_keys(tree)
    keys: set[str] = set()

    class _ExitJsonVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.assignment_stack: list[dict[str, frozenset[str]]] = [{}]

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            assignments = _collect_assigned_key_sets(node.body, function_return_keys)
            self.assignment_stack.append(assignments)
            self.generic_visit(node)
            self.assignment_stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node: ast.Call) -> None:
            call_name = _call_name(node.func)
            if call_name and call_name.endswith("exit_json"):
                current = self.assignment_stack[-1]
                for keyword in node.keywords:
                    if keyword.arg is None:
                        keys.update(_resolve_key_set(keyword.value, current, function_return_keys))
                        continue
                    if keyword.arg not in _ANSIBLE_META_RETURN_KEYS:
                        keys.add(keyword.arg)
            self.generic_visit(node)

    _ExitJsonVisitor().visit(tree)
    return frozenset(keys)


def _extract_json_output_keys(tree: ast.AST) -> frozenset[str]:
    function_return_keys = _extract_function_return_keys(tree)
    keys: set[str] = set()

    class _JsonVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.assignment_stack: list[dict[str, frozenset[str]]] = [{}]

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            assignments = _collect_assigned_key_sets(node.body, function_return_keys)
            self.assignment_stack.append(assignments)
            self.generic_visit(node)
            self.assignment_stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node: ast.Call) -> None:
            call_name = _call_name(node.func)
            if call_name == "json.dumps" and node.args:
                current = self.assignment_stack[-1]
                keys.update(_resolve_key_set(node.args[0], current, function_return_keys))
            self.generic_visit(node)

    _JsonVisitor().visit(tree)
    return frozenset(keys)


class _CamelCaseVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.hits: list[tuple[int, str]] = []

    def _check(self, name: str, lineno: int) -> None:
        bare = name.lstrip("_")
        if bare in _SKIP_VAR_NAMES:
            return
        if bare.startswith("visit_"):
            return
        if _is_camel_case(bare):
            self.hits.append((lineno, name))

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self._check(node.id, node.lineno)
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        self._check(node.arg, node.lineno)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check(node.name, node.lineno)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for child in ast.iter_child_nodes(node):
            self.visit(child)


def check_variable_naming(file: Path) -> list[Issue]:
    tree = _safe_parse(file)
    if tree is None:
        return []
    visitor = _CamelCaseVisitor()
    visitor.visit(tree)
    return [
        Issue(
            file=file,
            line=lineno,
            message=f"camelCase name '{name}' — use '{_camel_to_snake(name.lstrip('_'))}'",
            level="warning",
        )
        for lineno, name in visitor.hits
    ]


def _get_mapping_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        call_name = _call_name(node.func)
        if call_name and call_name.endswith(".get") and node.args:
            return _string_value(node.args[0])
    if isinstance(node, ast.Subscript):
        return _string_value(node.slice)
    return None


def _mapping_issue(
    file: Path,
    line: int,
    python_name: str,
    json_key: str,
) -> Issue | None:
    if not _is_camel_case(json_key):
        return None
    expected = _camel_to_snake(json_key)
    if python_name != expected:
        return Issue(
            file=file,
            line=line,
            message=f"API key '{json_key}' mapped to '{python_name}' but expected '{expected}'",
        )
    return None


class _ApiMappingVisitor(ast.NodeVisitor):
    def __init__(self, file: Path) -> None:
        self.file = file
        self.issues: list[Issue] = []
        self.observations: list[MappingObservation] = []

    def _record(self, python_name: str, json_key: str, line: int) -> None:
        self.observations.append(
            MappingObservation(
                file=self.file,
                line=line,
                json_key=json_key,
                python_name=python_name,
            )
        )
        issue = _mapping_issue(self.file, line, python_name, json_key)
        if issue:
            self.issues.append(issue)

    def visit_Assign(self, node: ast.Assign) -> None:
        key = _get_mapping_key(node.value)
        if key and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            self._record(node.targets[0].id, key, node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        key = _get_mapping_key(node.value) if node.value is not None else None
        if key and isinstance(node.target, ast.Name):
            self._record(node.target.id, key, node.lineno)
        self.generic_visit(node)

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg:
            key = _get_mapping_key(node.value)
            if key:
                line = getattr(node.value, "lineno", 1)
                self._record(node.arg, key, line)
        self.generic_visit(node)


def collect_api_key_mappings(file: Path) -> list[MappingObservation]:
    tree = _safe_parse(file)
    if tree is None:
        return []
    visitor = _ApiMappingVisitor(file)
    visitor.visit(tree)
    return visitor.observations


def check_api_key_mapping(file: Path) -> list[Issue]:
    tree = _safe_parse(file)
    if tree is None:
        return []
    visitor = _ApiMappingVisitor(file)
    visitor.visit(tree)
    return visitor.issues


def check_api_mapping_consistency(files: Sequence[Path]) -> list[Issue]:
    grouped: dict[str, list[MappingObservation]] = defaultdict(list)
    for file in files:
        if file.suffix != ".py":
            continue
        for observation in collect_api_key_mappings(file):
            if _is_camel_case(observation.json_key):
                grouped[observation.json_key].append(observation)

    issues: list[Issue] = []
    for json_key, observations in grouped.items():
        python_names = sorted({item.python_name for item in observations})
        if len(python_names) < 2:
            continue
        message = (
            f"API key '{json_key}' is mapped inconsistently across modified files: {python_names}"
        )
        for observation in observations:
            issues.append(
                Issue(
                    file=observation.file,
                    line=observation.line,
                    message=message,
                    level="warning",
                )
            )
    return issues


def _parse_documentation_options(source: str) -> tuple[dict[str, int], str | None, int]:
    block = _extract_triple_quoted_assignment(source, "DOCUMENTATION")
    if block is None:
        return {}, None, 1
    doc = _safe_yaml_load(block.body) or {}
    module_name = doc.get("module") if isinstance(doc, dict) else None
    options: dict[str, int] = {}
    option_names = doc.get("options") if isinstance(doc, dict) else None
    if isinstance(option_names, dict):
        for option_name in option_names:
            options[option_name] = _line_for_block_key(block, option_name)
    module_line = _line_for_block_key(block, "module")
    return options, module_name if isinstance(module_name, str) else None, module_line


def _parse_return_keys(source: str) -> dict[str, int]:
    block = _extract_triple_quoted_assignment(source, "RETURN")
    if block is None:
        return {}
    parsed = _safe_yaml_load(block.body) or {}
    if not isinstance(parsed, dict):
        return {}
    return {key: _line_for_block_key(block, key) for key in parsed if isinstance(key, str)}


def _parse_example_tasks(source: str) -> list[tuple[int, dict[str, Any]]]:
    block = _extract_triple_quoted_assignment(source, "EXAMPLES")
    if block is None:
        return []
    parsed = _safe_yaml_load(block.body) or []
    if not isinstance(parsed, list):
        return []
    tasks: list[tuple[int, dict[str, Any]]] = []
    for task in parsed:
        if not isinstance(task, dict):
            continue
        task_name = task.get("name")
        if isinstance(task_name, str):
            pattern = re.compile(rf"^\s*-\s*name:\s*{re.escape(task_name)}\s*$", re.MULTILINE)
            match = pattern.search(block.body)
            line = (
                block.start_line + block.body[: match.start()].count("\n")
                if match
                else block.start_line
            )
        else:
            line = block.start_line
        tasks.append((line, task))
    return tasks


def _extract_example_return_lines(source: str) -> dict[str, int]:
    block = _extract_triple_quoted_assignment(source, "EXAMPLES")
    if block is None:
        return {}
    lines: dict[str, int] = {}
    register_names = set(
        re.findall(r"^\s*register:\s*([A-Za-z_]\w*)\s*$", block.body, re.MULTILINE)
    )
    if not register_names:
        return lines

    for pattern in (_JINJA_REGISTER_REF_RE, _JINJA_REGISTER_INDEX_RE):
        for match in pattern.finditer(block.body):
            register = match.group("register")
            key = match.group("key")
            if register not in register_names:
                continue
            line = block.start_line + block.body[: match.start()].count("\n")
            lines.setdefault(key, line)
    return lines


def _build_ansible_metadata(file: Path) -> AnsibleModuleMetadata:
    source = file.read_text(encoding="utf-8")
    tree = _safe_parse(file)
    option_lines, module_name, module_name_line = _parse_documentation_options(source)
    return_lines = _parse_return_keys(source)
    example_option_lines: dict[str, int] = {}
    for task_line, task in _parse_example_tasks(source):
        module_options = _task_module_options(task, file.stem)
        if module_options is None:
            continue
        for key in module_options:
            example_option_lines.setdefault(key, task_line)
    exit_json_keys = _extract_exit_json_keys(tree) if tree is not None else frozenset()
    return AnsibleModuleMetadata(
        module_name=module_name,
        module_name_line=module_name_line,
        option_lines=option_lines,
        return_lines=return_lines,
        example_option_lines=example_option_lines,
        example_return_lines=_extract_example_return_lines(source),
        exit_json_keys=exit_json_keys,
        operation_key=_ansible_operation_key(file),
        device_family=_ansible_device_family(file),
    )


def _task_module_options(task: dict[str, Any], module_name: str) -> dict[str, Any] | None:
    for key, value in task.items():
        if key in _TASK_CTRL_KEYS:
            continue
        if key == module_name or key.endswith("." + module_name):
            return value if isinstance(value, dict) else {}
    return None


def check_ansible_examples(file: Path, metadata: AnsibleModuleMetadata) -> list[Issue]:
    issues: list[Issue] = []
    for option_name, line in metadata.example_option_lines.items():
        if option_name not in metadata.option_lines:
            issues.append(
                Issue(
                    file=file,
                    line=line,
                    message=f"EXAMPLES uses undeclared option '{option_name}'",
                )
            )
    for return_key, line in metadata.example_return_lines.items():
        if return_key not in metadata.return_lines:
            issues.append(
                Issue(
                    file=file,
                    line=line,
                    message=f"EXAMPLES references undocumented return key '{return_key}'",
                )
            )
    return issues


def check_ansible_return_contract(file: Path, metadata: AnsibleModuleMetadata) -> list[Issue]:
    issues: list[Issue] = []
    documented = set(metadata.return_lines)
    actual = set(metadata.exit_json_keys)

    undocumented = sorted(actual - documented)
    for key in undocumented:
        issues.append(
            Issue(
                file=file,
                line=1,
                message=f"RETURN is missing documented key '{key}' emitted by module.exit_json",
            )
        )

    stale = sorted(documented - actual)
    for key in stale:
        issues.append(
            Issue(
                file=file,
                line=metadata.return_lines[key],
                message=f"RETURN documents '{key}' but no module.exit_json path emits it",
                level="warning",
            )
        )
    return issues


def check_ansible_module_naming(file: Path, metadata: AnsibleModuleMetadata) -> list[Issue]:
    if metadata.module_name == file.stem:
        return []
    if metadata.module_name is None:
        return [
            Issue(
                file=file,
                line=1,
                message="DOCUMENTATION block is missing 'module'",
            )
        ]
    return [
        Issue(
            file=file,
            line=metadata.module_name_line,
            message=f"DOCUMENTATION module '{metadata.module_name}' should match filename '{file.stem}'",
        )
    ]


def _extract_cli_command_name(tree: ast.AST) -> tuple[str | None, int]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "name":
            continue
        for statement in node.body:
            if isinstance(statement, ast.Return):
                value = _string_value(statement.value)
                if value is not None:
                    return value, statement.lineno
    return None, 1


def _extract_cli_option_names(tree: ast.AST) -> frozenset[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            names.update(_extract_call_option_names(node))
    return frozenset(names)


def _cli_operation_key(file: Path) -> str | None:
    try:
        index = file.parts.index("commands")
    except ValueError:
        return None
    tail = list(file.parts[index + 1 : -1])
    if "devices" not in tail:
        return None
    devices_index = tail.index("devices")
    if len(tail) <= devices_index + 2:
        return None
    return "_".join(tail[devices_index + 2 :])


def _cli_device_family(file: Path) -> str | None:
    try:
        index = file.parts.index("devices")
    except ValueError:
        return None
    if len(file.parts) <= index + 1:
        return None
    family = file.parts[index + 1]
    return family if family in {"asa", "ftd"} else None


def _build_cli_metadata(file: Path) -> CliCommandMetadata:
    tree = _safe_parse(file)
    if tree is None:
        return CliCommandMetadata(
            command_name=None,
            command_name_line=1,
            option_names=frozenset(),
            json_keys=frozenset(),
            operation_key=_cli_operation_key(file),
            device_family=_cli_device_family(file),
        )
    command_name, command_name_line = _extract_cli_command_name(tree)
    return CliCommandMetadata(
        command_name=command_name,
        command_name_line=command_name_line,
        option_names=_extract_cli_option_names(tree),
        json_keys=_extract_json_output_keys(tree),
        operation_key=_cli_operation_key(file),
        device_family=_cli_device_family(file),
    )


def check_cli_command_naming(file: Path, metadata: CliCommandMetadata) -> list[Issue]:
    if file.name != "command.py":
        return []
    expected = file.parent.name.replace("_", "-")
    if metadata.command_name == expected:
        return []
    if metadata.command_name is None:
        return [
            Issue(
                file=file,
                line=1,
                message=f"CLI command in '{file.parent.name}' should expose name '{expected}'",
            )
        ]
    return [
        Issue(
            file=file,
            line=metadata.command_name_line,
            message=f"CLI command name '{metadata.command_name}' should match directory '{expected}'",
        )
    ]


def _ansible_device_family(file: Path) -> str | None:
    tokens = file.stem.split("_")
    if "asa" in tokens:
        return "asa"
    if "ftd" in tokens and "asa" not in tokens:
        return "ftd"
    return None


def _ansible_operation_key(file: Path) -> str | None:
    tokens = file.stem.split("_")
    family = _ansible_device_family(file)
    if family is None:
        return None
    trimmed = [token for token in tokens if token != family]
    if trimmed == tokens:
        return None
    return "_".join(trimmed)


def _normalize_cli_for_ansible(option_names: Iterable[str]) -> frozenset[str]:
    normalized: set[str] = set()
    for name in option_names:
        if name in _CLI_ANSIBLE_IGNORED_OPTIONS:
            continue
        normalized.add(_CLI_TO_ANSIBLE_OPTION_ALIASES.get(name, name))
    return frozenset(normalized)


def _cli_expected_ansible_module(file: Path) -> Path | None:
    try:
        index = file.parts.index("commands")
    except ValueError:
        return None
    parts = list(file.parts[index + 1 : -1])
    if parts[:2] == ["objects", "network"] and len(parts) == 3:
        action = parts[2]
        module_name = "list_network_objects" if action == "list" else f"{action}_network_object"
        return ANSIBLE_MODULES / f"{module_name}.py"
    if parts[:2] == ["objects", "network_group"] and len(parts) == 3:
        action = parts[2]
        special = {
            "add_member": "add_network_group_members",
            "remove_member": "remove_network_group_members",
            "list": "list_network_groups",
        }
        module_name = special.get(action, f"{action}_network_group")
        return ANSIBLE_MODULES / f"{module_name}.py"
    if parts[:2] == ["objects", "show"]:
        return ANSIBLE_MODULES / "get_object.py"
    if parts[:2] == ["objects", "update_default"]:
        return ANSIBLE_MODULES / "update_object_default.py"
    if parts[:2] == ["objects", "add_override"]:
        return ANSIBLE_MODULES / "add_object_override.py"
    if parts[:2] == ["objects", "delete_override"]:
        return ANSIBLE_MODULES / "delete_object_override.py"
    if parts[:2] == ["objects", "edit_override"]:
        return ANSIBLE_MODULES / "edit_object_override.py"
    if parts[:2] == ["objects", "apply_override_as_default"]:
        return ANSIBLE_MODULES / "apply_object_override_as_default.py"
    if parts[:2] == ["policies", "access_group"] and len(parts) == 3:
        action = parts[2]
        module_name = "list_access_groups" if action == "list" else f"{action}_access_group"
        return ANSIBLE_MODULES / f"{module_name}.py"
    if parts[:2] == ["policies", "access_rule"] and len(parts) == 3:
        action = parts[2]
        module_name = "list_access_rules" if action == "list" else f"{action}_access_rule"
        return ANSIBLE_MODULES / f"{module_name}.py"
    if parts[:2] == ["inventory", "manager"] and parts[-1] == "list":
        return ANSIBLE_MODULES / "list_managers.py"
    if parts[:3] == ["inventory", "manager", "access_policies"] and parts[-1] == "list":
        return ANSIBLE_MODULES / "list_cdfmc_access_policies.py"
    if parts[:4] == ["inventory", "devices", "asa", "disk"] and parts[-1] == "list_files":
        return ANSIBLE_MODULES / "list_asa_disk_files.py"
    if (
        parts[:4] == ["inventory", "devices", "asa", "upgrade"]
        and parts[-1] == "compatible_versions"
    ):
        return ANSIBLE_MODULES / "list_asa_compatible_versions.py"
    if (
        parts[:4] == ["inventory", "devices", "ftd", "upgrade"]
        and parts[-1] == "compatible_versions"
    ):
        return ANSIBLE_MODULES / "list_ftd_compatible_versions.py"
    if parts[:4] == ["inventory", "devices", "asa", "upgrade"] and parts[-1] == "trigger":
        return ANSIBLE_MODULES / "trigger_asa_upgrade.py"
    if parts[:4] == ["inventory", "devices", "ftd", "upgrade"] and parts[-1] == "trigger":
        return ANSIBLE_MODULES / "trigger_ftd_upgrade.py"
    if parts[:4] == ["inventory", "devices", "asa", "shun"] and len(parts) == 5:
        return ANSIBLE_MODULES / f"{parts[4]}_asa_shun.py"
    if parts[:4] == ["inventory", "devices", "asa", "cli"] and parts[-1] == "execute":
        return ANSIBLE_MODULES / "execute_asa_cli.py"
    if parts[:4] == ["inventory", "devices", "asa", "user"] and parts[-1] == "change_password":
        return ANSIBLE_MODULES / "change_asa_local_password.py"
    if parts[:3] == ["inventory", "devices", "asa"] and len(parts) == 4:
        special = {
            "ha_check": "asa_ha_check",
            "list_boot_registry": "list_asa_boot_registry",
            "list_asa_local_users": "list_asa_local_users",
            "list_not_on_version": "list_asa_not_on_version",
            "change_boot_image": "change_asa_boot_image",
            "onboard": "onboard_asa",
        }
        module_name = special.get(parts[3])
        return ANSIBLE_MODULES / f"{module_name}.py" if module_name else None
    if parts[:3] == ["inventory", "devices", "ftd"] and len(parts) == 4:
        special = {
            "list_not_on_version": "list_ftd_not_on_version",
        }
        module_name = special.get(parts[3])
        return ANSIBLE_MODULES / f"{module_name}.py" if module_name else None
    if parts[:3] == ["inventory", "devices", "cdfmc_managed_ftd"] and len(parts) == 4:
        special = {
            "onboard": "onboard_cdfmc_ftd",
            "onboard_ztp": "onboard_cdfmc_ftd_ztp",
            "deploy": "deploy_cdfmc_ftd",
        }
        module_name = special.get(parts[3])
        return ANSIBLE_MODULES / f"{module_name}.py" if module_name else None
    return None


def check_cli_ansible_alignment(changed_files: Sequence[Path]) -> list[Issue]:
    issues: list[Issue] = []
    for file in changed_files:
        if not file.is_relative_to(CLI_COMMANDS) or file.name != "command.py":
            continue
        ansible_module = _cli_expected_ansible_module(file)
        if ansible_module is None or not ansible_module.exists():
            continue

        cli_metadata = _build_cli_metadata(file)
        ansible_metadata = _build_ansible_metadata(ansible_module)
        cli_options = _normalize_cli_for_ansible(cli_metadata.option_names)
        ansible_options = set(ansible_metadata.option_lines)
        ignored_ansible = {"api_token", "region"}

        for option_name in sorted(cli_options - ignored_ansible):
            if option_name not in ansible_options:
                issues.append(
                    Issue(
                        file=file,
                        line=1,
                        message=(
                            f"CLI option '{option_name}' has no matching Ansible option in "
                            f"'{ansible_module.name}'"
                        ),
                        level="warning",
                    )
                )
    return issues


def _paired_cli_by_operation() -> dict[tuple[str, str], Path]:
    mapping: dict[tuple[str, str], Path] = {}
    for path in CLI_COMMANDS.rglob("command.py"):
        operation = _cli_operation_key(path)
        family = _cli_device_family(path)
        if operation and family:
            mapping[(operation, family)] = path
    return mapping


def _paired_ansible_by_operation() -> dict[tuple[str, str], Path]:
    mapping: dict[tuple[str, str], Path] = {}
    for path in ANSIBLE_MODULES.glob("*.py"):
        if path.name == "__init__.py":
            continue
        operation = _ansible_operation_key(path)
        family = _ansible_device_family(path)
        if operation and family:
            mapping[(operation, family)] = path
    return mapping


def check_cross_device_cli_consistency(changed_files: Sequence[Path]) -> list[Issue]:
    paired = _paired_cli_by_operation()
    issues: list[Issue] = []
    for file in changed_files:
        if not file.is_relative_to(CLI_COMMANDS) or file.name != "command.py":
            continue
        operation = _cli_operation_key(file)
        family = _cli_device_family(file)
        if operation is None or family not in {"asa", "ftd"}:
            continue
        other_family = "ftd" if family == "asa" else "asa"
        counterpart = paired.get((operation, other_family))
        if counterpart is None:
            continue

        current = _build_cli_metadata(file)
        other = _build_cli_metadata(counterpart)
        missing = sorted(
            (current.option_names - other.option_names) - _DEVICE_SPECIFIC_OPTION_EXTRAS
        )
        for option_name in missing:
            issues.append(
                Issue(
                    file=file,
                    line=1,
                    message=(
                        f"Shared CLI option '{option_name}' is missing from paired "
                        f"{other_family.upper()} command '{counterpart.relative_to(ROOT)}'"
                    ),
                    level="warning",
                )
            )

        missing_json = sorted(
            (current.json_keys - other.json_keys) - _DEVICE_SPECIFIC_OUTPUT_EXTRAS
        )
        for key in missing_json:
            issues.append(
                Issue(
                    file=file,
                    line=1,
                    message=(
                        f"JSON output key '{key}' is missing from paired "
                        f"{other_family.upper()} command '{counterpart.relative_to(ROOT)}'"
                    ),
                    level="warning",
                )
            )
    return issues


def check_cross_device_ansible_consistency(changed_files: Sequence[Path]) -> list[Issue]:
    paired = _paired_ansible_by_operation()
    issues: list[Issue] = []
    for file in changed_files:
        if not file.is_relative_to(ANSIBLE_MODULES) or file.name == "__init__.py":
            continue
        operation = _ansible_operation_key(file)
        family = _ansible_device_family(file)
        if operation is None or family not in {"asa", "ftd"}:
            continue
        other_family = "ftd" if family == "asa" else "asa"
        counterpart = paired.get((operation, other_family))
        if counterpart is None:
            continue

        current = _build_ansible_metadata(file)
        other = _build_ansible_metadata(counterpart)
        missing_options = sorted(
            (set(current.option_lines) - set(other.option_lines)) - _DEVICE_SPECIFIC_OPTION_EXTRAS
        )
        for option_name in missing_options:
            issues.append(
                Issue(
                    file=file,
                    line=current.option_lines.get(option_name, 1),
                    message=(
                        f"Shared Ansible option '{option_name}' is missing from paired "
                        f"{other_family.upper()} module '{counterpart.name}'"
                    ),
                    level="warning",
                )
            )

        missing_returns = sorted(
            (set(current.return_lines) - set(other.return_lines)) - _DEVICE_SPECIFIC_OUTPUT_EXTRAS
        )
        for return_key in missing_returns:
            issues.append(
                Issue(
                    file=file,
                    line=current.return_lines.get(return_key, 1),
                    message=(
                        f"Shared RETURN key '{return_key}' is missing from paired "
                        f"{other_family.upper()} module '{counterpart.name}'"
                    ),
                    level="warning",
                )
            )
    return issues


def _git_changed_files(base: str = "main") -> list[Path]:
    revisions = [f"origin/{base}...HEAD", f"{base}...HEAD"]
    for revision in revisions:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", revision, "--", "*.py"],
                capture_output=True,
                text=True,
                check=True,
                cwd=ROOT,
            )
            files = [ROOT / line for line in result.stdout.splitlines() if line.endswith(".py")]
            return files
        except subprocess.CalledProcessError:
            continue
    return []


def _is_ansible_module(file: Path) -> bool:
    return file.is_relative_to(ANSIBLE_MODULES) and file.name != "__init__.py"


def _is_cli_command(file: Path) -> bool:
    return file.is_relative_to(CLI_COMMANDS) and file.name == "command.py"


def run(
    files: list[Path],
    *,
    annotations: bool = False,
    fail_on_warning: bool = False,
) -> int:
    issues: list[Issue] = []

    for file in files:
        if not file.exists() or file.suffix != ".py":
            continue
        issues.extend(check_variable_naming(file))
        issues.extend(check_api_key_mapping(file))

        if _is_ansible_module(file):
            metadata = _build_ansible_metadata(file)
            issues.extend(check_ansible_examples(file, metadata))
            issues.extend(check_ansible_return_contract(file, metadata))
            issues.extend(check_ansible_module_naming(file, metadata))

        if _is_cli_command(file):
            metadata = _build_cli_metadata(file)
            issues.extend(check_cli_command_naming(file, metadata))

    issues.extend(check_api_mapping_consistency(files))
    issues.extend(check_cross_device_cli_consistency(files))
    issues.extend(check_cross_device_ansible_consistency(files))
    issues.extend(check_cli_ansible_alignment(files))

    issues.sort(key=lambda issue: (issue.file, issue.line, issue.message))

    for issue in issues:
        print(issue.as_annotation() if annotations else issue.as_text())

    errors = sum(1 for issue in issues if issue.level == "error")
    warnings = sum(1 for issue in issues if issue.level == "warning")
    print(f"\n{errors} error(s), {warnings} warning(s) across {len(files)} file(s).")

    if errors > 0:
        return 1
    if fail_on_warning and warnings > 0:
        return 1
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Python files to check. Defaults to files changed vs. the base branch.",
    )
    parser.add_argument(
        "--base",
        default="main",
        help="Base branch for git diff when no files are provided (default: main).",
    )
    parser.add_argument(
        "--annotations",
        action="store_true",
        help="Emit GitHub Actions annotations.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Return a non-zero exit code when warnings are found.",
    )
    args = parser.parse_args(argv)

    raw_files = args.files or _git_changed_files(args.base)
    files = [(file if file.is_absolute() else (ROOT / file)).resolve() for file in raw_files]
    if not files:
        print("No Python files to check.")
        sys.exit(0)

    sys.exit(run(files, annotations=args.annotations, fail_on_warning=args.fail_on_warning))


if __name__ == "__main__":
    main()
