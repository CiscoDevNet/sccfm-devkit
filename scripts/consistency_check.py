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
from typing import Any, Callable, Iterable, Sequence

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
    "device_uid": "uids",
    "device_uids": "uids",
}


@dataclass(frozen=True)
class Issue:
    file: Path
    line: int | None
    message: str
    level: str = "error"

    def as_annotation(self) -> str:
        rel = _display_path(self.file)
        loc = f",line={self.line}" if self.line is not None else ""
        return f"::{self.level} file={rel}{loc}::{self.message}"

    def as_text(self) -> str:
        rel = _display_path(self.file)
        loc = f":{self.line}" if self.line is not None else ""
        return f"{self.level.upper()}: {rel}{loc}: {self.message}"


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
    command_name_line: int | None
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
            self.assignment_stack: list[dict[str, frozenset[str]]] = [{}]

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            assignments = _collect_assigned_key_sets(node.body, {})
            self.current_function.append(node.name)
            self.assignment_stack.append(assignments)
            self.generic_visit(node)
            self.assignment_stack.pop()
            self.current_function.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Return(self, node: ast.Return) -> None:
            if not self.current_function:
                return
            function_name = self.current_function[-1]
            keys = _dict_literal_keys(node.value) | _resolve_key_set(
                node.value,
                self.assignment_stack[-1],
                {},
            )
            for key in keys:
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
                elif isinstance(target, ast.Subscript):
                    target_name = _subscript_target_name(target)
                    target_key = _string_value(target.slice)
                    if target_name and target_key:
                        local_assignments[target_name] = local_assignments.get(
                            target_name, frozenset()
                        ) | {target_key}
        elif isinstance(statement, ast.AnnAssign):
            if isinstance(statement.target, ast.Name) and statement.value is not None:
                key_set = _resolve_key_set(statement.value, local_assignments, function_return_keys)
                if key_set:
                    local_assignments[statement.target.id] = key_set
            elif isinstance(statement.target, ast.Subscript):
                target_name = _subscript_target_name(statement.target)
                target_key = _string_value(statement.target.slice)
                if target_name and target_key:
                    local_assignments[target_name] = local_assignments.get(
                        target_name, frozenset()
                    ) | {target_key}
        for child_statements in _nested_statement_lists(statement):
            local_assignments.update(
                _collect_assigned_key_sets(
                    child_statements,
                    function_return_keys,
                    assignments=local_assignments,
                )
            )
    return local_assignments


def _subscript_target_name(target: ast.Subscript) -> str | None:
    if isinstance(target.value, ast.Name):
        return target.value.id
    return None


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
            if call_name and call_name.endswith("run_delete_with_idempotency"):
                keys.add("deleted_uid")
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
        if return_key in _ANSIBLE_META_RETURN_KEYS:
            continue
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
    actual = set(metadata.exit_json_keys) - _ANSIBLE_META_RETURN_KEYS

    undocumented = sorted(actual - documented)
    for key in undocumented:
        issues.append(
            Issue(
                file=file,
                line=None,
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
                line=None,
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


def _extract_cli_command_name(tree: ast.AST) -> tuple[str | None, int | None]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "name":
            continue
        for statement in node.body:
            if isinstance(statement, ast.Return):
                value = _string_value(statement.value)
                if value is not None:
                    return value, statement.lineno
    return None, None


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
            command_name_line=None,
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
                line=None,
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


def _normalize_cli_for_ansible(
    option_names: Iterable[str], file: Path | None = None
) -> frozenset[str]:
    aliases = dict(_CLI_TO_ANSIBLE_OPTION_ALIASES)
    if file is not None:
        parts = file.parts
        if parts[-4:-1] == ("asa", "user", "change_password"):
            aliases["password"] = "new_password"

    normalized: set[str] = set()
    for name in option_names:
        if name in _CLI_ANSIBLE_IGNORED_OPTIONS:
            continue
        normalized.add(aliases.get(name, name))
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
    if parts[:3] == ["inventory", "manager", "access_policies"] and parts[-1] == "list":
        return ANSIBLE_MODULES / "list_cdfmc_access_policies.py"
    if parts[:2] == ["inventory", "manager"] and parts[-1] == "list":
        return ANSIBLE_MODULES / "list_managers.py"
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
            "list_local_users": "list_asa_local_users",
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
        cli_options = _normalize_cli_for_ansible(cli_metadata.option_names, file=file)
        ansible_options = set(ansible_metadata.option_lines)
        ignored_ansible = {"api_token", "region"}

        for option_name in sorted(cli_options - ignored_ansible):
            if option_name not in ansible_options:
                issues.append(
                    Issue(
                        file=file,
                        line=None,
                        message=(
                            f"CLI option '{option_name}' has no matching Ansible option in "
                            f"'{ansible_module.name}'"
                        ),
                        level="warning",
                    )
                )
    return issues


def _paired_by_operation(
    root_dir: Path,
    glob_pattern: str,
    operation_key_fn: Callable[[Path], str | None],
    device_family_fn: Callable[[Path], str | None],
) -> dict[tuple[str, str], Path]:
    mapping: dict[tuple[str, str], Path] = {}
    for path in root_dir.glob(glob_pattern):
        if path.name == "__init__.py":
            continue
        operation = operation_key_fn(path)
        family = device_family_fn(path)
        if operation and family:
            mapping[(operation, family)] = path
    return mapping


def check_cross_device_cli_consistency(changed_files: Sequence[Path]) -> list[Issue]:
    paired = _paired_by_operation(
        CLI_COMMANDS,
        "**/command.py",
        _cli_operation_key,
        _cli_device_family,
    )
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
                    line=None,
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
                    line=None,
                    message=(
                        f"JSON output key '{key}' is missing from paired "
                        f"{other_family.upper()} command '{counterpart.relative_to(ROOT)}'"
                    ),
                    level="warning",
                )
            )
    return issues


def check_cross_device_ansible_consistency(changed_files: Sequence[Path]) -> list[Issue]:
    paired = _paired_by_operation(
        ANSIBLE_MODULES,
        "*.py",
        _ansible_operation_key,
        _ansible_device_family,
    )
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
    files: set[Path] = set()

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
            files.update(ROOT / line for line in result.stdout.splitlines() if line.endswith(".py"))
            break
        except subprocess.CalledProcessError:
            continue

    for cmd in (
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", "--", "*.py"],
        ["git", "ls-files", "--others", "--exclude-standard", "--", "*.py"],
    ):
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=ROOT,
        )
        files.update(ROOT / line for line in result.stdout.splitlines() if line.endswith(".py"))

    return sorted(files)


def _is_ansible_module(file: Path) -> bool:
    return (
        file.is_relative_to(ANSIBLE_MODULES)
        and not file.is_relative_to(ANSIBLE_MODULES / "tests")
        and file.name != "__init__.py"
    )


def _is_cli_command(file: Path) -> bool:
    return file.is_relative_to(CLI_COMMANDS) and file.name == "command.py"


# ── SDK API index (built once at import time if SDK is available) ─────────────


def _build_sdk_api_index() -> dict[str, dict[str, frozenset[str]]]:
    """Return {ApiClassName: {method_name: frozenset(param_names)}}.

    Includes both the canonical method and the *_without_preload_content variant
    since service files use the latter. Returns an empty dict when the SDK is
    not installed (CI environments without the venv active).
    """
    try:
        import importlib
        import inspect
        import pkgutil
        from pathlib import Path as _Path

        import scc_firewall_manager_sdk.api as _sdk_api_pkg

        _SKIP = frozenset(
            {
                "self",
                "_request_timeout",
                "_request_auth",
                "_content_type",
                "_headers",
                "_host_index",
            }
        )
        _SKIP_SUFFIX = ("_with_http_info",)

        api_dir = _Path(inspect.getfile(_sdk_api_pkg)).parent
        index: dict[str, dict[str, frozenset[str]]] = {}
        for _, mod_name, _ in pkgutil.iter_modules([str(api_dir)]):
            if mod_name == "__init__":
                continue
            mod = importlib.import_module(f"scc_firewall_manager_sdk.api.{mod_name}")
            for cls_name, cls in inspect.getmembers(mod, inspect.isclass):
                if not cls_name.endswith("Api"):
                    continue
                index[cls_name] = {}
                for mname, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                    if mname.startswith("_") or any(mname.endswith(s) for s in _SKIP_SUFFIX):
                        continue
                    sig = inspect.signature(method)
                    params = frozenset(p for p in sig.parameters if p not in _SKIP)
                    index[cls_name][mname] = params
        return index
    except Exception:
        return {}


_SDK_API_INDEX: dict[str, dict[str, frozenset[str]]] = _build_sdk_api_index()


def _sdk_params_for(api_class_name: str, method_name: str) -> frozenset[str] | None:
    """Return allowed param names for an SDK API method, or None if unknown.

    Tries the exact method name, then the *_without_preload_content variant,
    and the inverse — so callers don't need to know which form to look up.
    """
    cls = _SDK_API_INDEX.get(api_class_name)
    if cls is None:
        return None
    if method_name in cls:
        return cls[method_name]
    # Strip suffix and retry
    bare = method_name.removesuffix("_without_preload_content")
    if bare in cls:
        return cls[bare]
    # Add suffix and retry
    with_suffix = method_name + "_without_preload_content"
    if with_suffix in cls:
        return cls[with_suffix]
    return None


# ── Check E: SDK API call kwarg names must match SDK method parameters ─────────


def _collect_sdk_api_attr_types(tree: ast.AST) -> dict[str, str]:
    """Return {self_attr_name: SdkApiClassName} from __init__ assignments.

    Handles both:
      self.foo_api = SomeApi(...)
      self.foo_api = helper.some_api   ← indirect; we skip these (no class name)
    """
    result: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "__init__":
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1:
                continue
            target = stmt.targets[0]
            if not (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                continue
            attr_name = target.attr
            # RHS must be a direct instantiation: SomeApi(...)
            if isinstance(stmt.value, ast.Call):
                cls_name = _call_name(stmt.value.func)
                if cls_name and cls_name.endswith("Api"):
                    result[attr_name] = cls_name.split(".")[-1]
    return result


def check_sdk_api_call_kwargs(file: Path) -> list[Issue]:
    """Check E — kwargs passed to SDK API calls must match the SDK method's params."""
    if not _SDK_API_INDEX:
        return []  # SDK not available in this environment

    tree = _safe_parse(file)
    if tree is None:
        return []

    api_attr_types = _collect_sdk_api_attr_types(tree)
    if not api_attr_types:
        return []

    issues: list[Issue] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Pattern: self.<api_attr>.<method_name>(...)
        if not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Attribute)
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "self"
        ):
            continue

        api_attr = func.value.attr
        method_name = func.attr
        api_class_name = api_attr_types.get(api_attr)
        if api_class_name is None:
            continue

        allowed = _sdk_params_for(api_class_name, method_name)
        if allowed is None:
            continue  # Unknown method — skip rather than false-positive

        for kw in node.keywords:
            if kw.arg is None:
                continue  # **kwargs spread — skip
            if kw.arg not in allowed:
                issues.append(
                    Issue(
                        file=file,
                        line=node.lineno,
                        message=(
                            f"SDK call {api_class_name}.{method_name}() "
                            f"uses unknown kwarg '{kw.arg}' "
                            f"(allowed: {sorted(allowed)})"
                        ),
                    )
                )

    return issues


# ── Check A: str(optional or "") on non-optional str dataclass field ──────────

_DATETIME_SUFFIXES = ("_date", "_time", "_at")
_SCCFM_CORE = ROOT / "sccfm_core"
_SCCFM_CLI = ROOT / "sccfm_cli"
_SCCFM_SERVICES = ROOT / "sccfm_core" / "services"


def _is_str_optional_or_call(node: ast.expr) -> bool:
    """True for  str(x or "")  or  str(x or '')  patterns."""
    if not (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str"
    ):
        return False
    if not node.args:
        return False
    inner = node.args[0]
    return (
        isinstance(inner, ast.BoolOp)
        and isinstance(inner.op, ast.Or)
        and len(inner.values) == 2
        and isinstance(inner.values[1], ast.Constant)
        and inner.values[1].value == ""
    )


def _collect_dataclass_str_fields(tree: ast.AST) -> dict[str, frozenset[str]]:
    """Return {ClassName: frozenset of field names typed plain `str`}."""
    result: dict[str, frozenset[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        plain_str_fields: set[str] = set()
        for item in node.body:
            if not isinstance(item, ast.AnnAssign):
                continue
            if not isinstance(item.target, ast.Name):
                continue
            ann = item.annotation
            # Accept bare `str` only — not `str | None`, not `Optional[str]`
            if isinstance(ann, ast.Name) and ann.id == "str":
                plain_str_fields.add(item.target.id)
        if plain_str_fields:
            result[node.name] = frozenset(plain_str_fields)
    return result


def _enclosing_class_name(tree: ast.AST, target_lineno: int) -> str | None:
    """Return the name of the ClassDef that contains the given line."""
    best: tuple[int, str] | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.lineno <= target_lineno:
                if best is None or node.lineno > best[0]:
                    best = (node.lineno, node.name)
    return best[1] if best else None


def check_optional_str_coercion(file: Path) -> list[Issue]:
    """Check A — flag str(x.get("key") or "") assigned to a non-optional `str` field."""
    tree = _safe_parse(file)
    if tree is None:
        return []
    plain_str_fields = _collect_dataclass_str_fields(tree)
    if not plain_str_fields:
        return []

    issues: list[Issue] = []

    def _check_pair(field_name: str, value_node: ast.expr, lineno: int) -> None:
        if not _is_str_optional_or_call(value_node):
            return
        # Only flag fields that are actually typed as plain str in their dataclass
        cls_name = _enclosing_class_name(tree, lineno)
        if cls_name is None:
            return
        if field_name not in plain_str_fields.get(cls_name, frozenset()):
            return
        # Extract the JSON key from data.get("key")
        inner_or = value_node.args[0]  # type: ignore[attr-defined]
        get_node = inner_or.values[0]
        json_key: str | None = None
        if isinstance(get_node, ast.Call) and get_node.args:
            json_key = _string_value(get_node.args[0])
        key_label = f"'{json_key}'" if json_key else "an optional API field"
        issues.append(
            Issue(
                file=file,
                line=lineno,
                message=(
                    f"from_dict assigns optional API field {key_label} to non-optional str field "
                    f"'{field_name}' — annotate as 'str | None' or document the empty-string "
                    f"sentinel explicitly"
                ),
                level="warning",
            )
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                _check_pair(node.targets[0].id, node.value, node.lineno)
        elif isinstance(node, ast.keyword):
            if node.arg and node.value is not None:
                _check_pair(node.arg, node.value, getattr(node.value, "lineno", 1))

    return issues


# ── Check B: datetime field stored as str | None without parsing ──────────────


def _is_str_optional_annotation(ann: ast.expr) -> bool:
    """True for `str | None` or `Optional[str]`."""
    # str | None  (BinOp with BitOr)
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        parts = {ast.unparse(ann.left), ast.unparse(ann.right)}
        return parts == {"str", "None"}
    # Optional[str]
    if isinstance(ann, ast.Subscript):
        if ast.unparse(ann.value) == "Optional":
            return ast.unparse(ann.slice) == "str"
    return False


def _from_dict_assigns_field_directly(tree: ast.AST, field_name: str) -> bool:
    """True if any from_dict method assigns field_name via bare data.get() with no conversion."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "from_dict":
            continue
        for child in ast.walk(node):
            # keyword argument:  field_name=data.get("...")
            if isinstance(child, ast.keyword) and child.arg == field_name:
                val = child.value
                if (
                    isinstance(val, ast.Call)
                    and isinstance(val.func, ast.Attribute)
                    and val.func.attr == "get"
                ):
                    return True
            # direct assignment:  field_name = data.get("...")
            if isinstance(child, ast.Assign):
                if (
                    len(child.targets) == 1
                    and isinstance(child.targets[0], ast.Name)
                    and child.targets[0].id == field_name
                ):
                    val = child.value
                    if (
                        isinstance(val, ast.Call)
                        and isinstance(val.func, ast.Attribute)
                        and val.func.attr == "get"
                    ):
                        return True
    return False


def check_datetime_as_str(file: Path) -> list[Issue]:
    """Check B — flag datetime-named fields annotated str | None without ISO parsing."""
    tree = _safe_parse(file)
    if tree is None:
        return []

    issues: list[Issue] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.AnnAssign):
                continue
            if not isinstance(item.target, ast.Name):
                continue
            field_name = item.target.id
            suffix = next((s for s in _DATETIME_SUFFIXES if field_name.endswith(s)), None)
            if suffix is None:
                continue
            if not _is_str_optional_annotation(item.annotation):
                continue
            if not _from_dict_assigns_field_directly(tree, field_name):
                continue
            issues.append(
                Issue(
                    file=file,
                    line=item.lineno,
                    message=(
                        f"Field '{field_name}' looks like a datetime (name ends in '{suffix}') "
                        f"but is stored as 'str | None' with no parsing — consider "
                        f"'datetime | None' with explicit ISO-8601 parsing, or rename to make "
                        f"the string intent clear"
                    ),
                    level="warning",
                )
            )
    return issues


# ── Check C: Ansible argument_spec vs DOCUMENTATION options ──────────────────

_ANSIBLE_BASE_KEYS: frozenset[str] = frozenset({"api_token", "region"})


def _extract_argument_spec_keys(tree: ast.AST) -> frozenset[str]:
    """Return literal string keys from build_argument_spec()'s return dict (ignoring **spreads)."""
    spread_helpers: dict[str, frozenset[str]] = {
        "base_argument_spec": _ANSIBLE_BASE_KEYS,
        "identifier_argument_spec": frozenset({"uid", "name"}),
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "build_argument_spec":
            continue
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
                keys: set[str] = set()
                for k, value in zip(stmt.value.keys, stmt.value.values, strict=False):
                    if k is None:
                        if isinstance(value, ast.Call):
                            helper_name = _call_name(value.func)
                            if helper_name:
                                keys.update(spread_helpers.get(helper_name, frozenset()))
                        continue  # **spread — known base, skip
                    val = _string_value(k)
                    if val:
                        keys.add(val)
                return frozenset(keys)
    return frozenset()


def check_ansible_argument_spec(file: Path, metadata: AnsibleModuleMetadata) -> list[Issue]:
    """Check C — flag mismatches between DOCUMENTATION options and argument_spec keys."""
    tree = _safe_parse(file)
    if tree is None:
        return []

    spec_keys = _extract_argument_spec_keys(tree)
    if not spec_keys:
        return []  # No build_argument_spec found — skip rather than false-positive

    doc_keys = frozenset(metadata.option_lines) - _ANSIBLE_BASE_KEYS
    spec_non_base = spec_keys - _ANSIBLE_BASE_KEYS

    issues: list[Issue] = []

    for opt in sorted(doc_keys - spec_non_base):
        issues.append(
            Issue(
                file=file,
                line=metadata.option_lines.get(opt, 1),
                message=(
                    f"DOCUMENTATION declares option '{opt}' but it is not in the module's "
                    f"argument_spec (and is not a base option) — add it to argument_spec or "
                    f"remove it from DOCUMENTATION"
                ),
                level="warning",
            )
        )

    for key in sorted(spec_non_base - doc_keys):
        issues.append(
            Issue(
                file=file,
                line=None,
                message=(
                    f"argument_spec key '{key}' is not documented in DOCUMENTATION — "
                    f"add an entry or remove the key"
                ),
                level="warning",
            )
        )

    return issues


# ── Check D: list_* / get_* service methods must have keyword-only limit/offset/query ──

_LIST_STANDARD_PARAMS: dict[str, Any] = {"limit": 50, "offset": 0, "query": None}


def check_service_list_signatures(files: Sequence[Path]) -> list[Issue]:
    """Check D — list_* and get_* methods on Service classes must use keyword-only
    args with standard limit/offset/query parameters and defaults."""
    service_files = [f for f in files if f.suffix == ".py" and f.is_relative_to(_SCCFM_SERVICES)]
    if not service_files:
        return []

    issues: list[Issue] = []

    for file in service_files:
        tree = _safe_parse(file)
        if tree is None:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            is_service = node.name.endswith("Service") or any(
                (isinstance(b, ast.Name) and b.id.endswith("Service"))
                or (isinstance(b, ast.Attribute) and b.attr.endswith("Service"))
                for b in node.bases
            )
            if not is_service:
                continue

            for item in node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                if not (item.name.startswith("list_") or item.name.startswith("get_")):
                    continue
                if item.name.startswith("_"):
                    continue

                args = item.args
                kwonly_names = [a.arg for a in args.kwonlyargs]

                # 1. keyword-only separator
                if not args.kwonlyargs:
                    issues.append(
                        Issue(
                            file=file,
                            line=item.lineno,
                            message=(
                                f"list/get method '{item.name}' in '{node.name}' should use "
                                f"keyword-only arguments (add '*' separator)"
                            ),
                            level="warning",
                        )
                    )
                    continue  # remaining checks need kwonly args

                kw_defaults_raw = args.kw_defaults
                kw_defaults: dict[str, Any] = {}
                for i, default_node in enumerate(kw_defaults_raw):
                    if default_node is not None:
                        param_name = args.kwonlyargs[i].arg
                        kw_defaults[param_name] = (
                            default_node.value
                            if isinstance(default_node, ast.Constant)
                            else ...  # non-literal default
                        )

                if not item.name.startswith("list_"):
                    continue

                # 2. missing standard params
                for param in ("limit", "offset", "query"):
                    if param not in kwonly_names:
                        issues.append(
                            Issue(
                                file=file,
                                line=item.lineno,
                                message=(
                                    f"list method '{item.name}' is missing parameter "
                                    f"'{param}' (present on all other list methods)"
                                ),
                                level="warning",
                            )
                        )

                # 3. non-standard defaults
                for param, expected in _LIST_STANDARD_PARAMS.items():
                    if param not in kw_defaults:
                        continue
                    actual = kw_defaults[param]
                    if actual is ... or actual != expected:
                        issues.append(
                            Issue(
                                file=file,
                                line=item.lineno,
                                message=(
                                    f"list method '{item.name}' has non-standard default for "
                                    f"'{param}': {actual!r} (expected {expected!r})"
                                ),
                                level="warning",
                            )
                        )

    return issues


# ── Check F: Region vocabulary drift ─────────────────────────────────────────

_CLI_CONFIGURE = ROOT / "sccfm_cli" / "commands" / "configure.py"
_ANSIBLE_CONFIG = ROOT / "sccfm-ansible" / "plugins" / "module_utils" / "config.py"
_CORE_CONSTANTS = ROOT / "sccfm_core" / "constants.py"
_RUNTIME_YML = ROOT / "sccfm-ansible" / "meta" / "runtime.yml"


def _extract_regions_tuple(file: Path, var_name: str) -> tuple[frozenset[str], int]:
    """Return (region_set, lineno) for a tuple/list literal assigned to var_name."""
    tree = _safe_parse(file)
    if tree is None:
        return frozenset(), 1
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Name) and target.id == var_name):
            continue
        if isinstance(node.value, (ast.Tuple, ast.List)):
            regions = {_string_value(elt) for elt in node.value.elts}
            return frozenset(r for r in regions if r), node.lineno
    return frozenset(), 1


def check_region_vocabulary_drift(files: Sequence[Path]) -> list[Issue]:
    """Check F — region definitions stay aligned with the shared core constant."""
    touched = {f.resolve() for f in files}
    relevant = {
        _CLI_CONFIGURE.resolve(),
        _ANSIBLE_CONFIG.resolve(),
        _CORE_CONSTANTS.resolve(),
    }
    if not (touched & relevant):
        return []

    core_regions, _ = _extract_regions_tuple(_CORE_CONSTANTS, "SCCFM_REGIONS")
    cli_regions, cli_line = _extract_regions_tuple(_CLI_CONFIGURE, "_REGIONS")
    ansible_regions, ansible_line = _extract_regions_tuple(_ANSIBLE_CONFIG, "ALLOWED_REGIONS")

    if not core_regions:
        return []

    issues: list[Issue] = []

    for file, line, var_name, regions in (
        (_CLI_CONFIGURE, cli_line, "_REGIONS", cli_regions),
        (_ANSIBLE_CONFIG, ansible_line, "ALLOWED_REGIONS", ansible_regions),
    ):
        if not regions:
            continue

        missing_from_local = sorted(core_regions - regions)
        for region in missing_from_local:
            issues.append(
                Issue(
                    file=file,
                    line=line,
                    message=(
                        f"Region '{region}' is in shared SCCFM_REGIONS but missing from "
                        f"{var_name} — region vocabulary must be kept in sync"
                    ),
                )
            )

        extra_in_local = sorted(regions - core_regions)
        for region in extra_in_local:
            issues.append(
                Issue(
                    file=file,
                    line=line,
                    message=(
                        f"Region '{region}' is in {var_name} but missing from shared "
                        f"SCCFM_REGIONS — region vocabulary must be kept in sync"
                    ),
                )
            )

    return issues


# ── Check G: Ansible module contract ─────────────────────────────────────────


def _extract_runtime_action_group(runtime_yml: Path) -> frozenset[str]:
    """Return module names listed under cisco.sccfm.all in runtime.yml."""
    if not runtime_yml.exists():
        return frozenset()
    content = runtime_yml.read_text(encoding="utf-8")
    parsed = _safe_yaml_load(content)
    if not isinstance(parsed, dict):
        return frozenset()
    action_groups = parsed.get("action_groups") or {}
    members = action_groups.get("cisco.sccfm.all") or []
    if not isinstance(members, list):
        return frozenset()
    return frozenset(str(m) for m in members)


def _module_uses_helper(tree: ast.AST, helper_name: str) -> bool:
    """True if the module calls helper_name() anywhere."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name == helper_name or (name and name.endswith("." + helper_name)):
                return True
    return False


def _module_uses_config(tree: ast.AST) -> bool:
    """True if the module uses create_config() OR constructs Config(region=module.params...)."""
    if _module_uses_helper(tree, "create_config"):
        return True
    # Accept direct Config(region=module.params..., api_token=module.params...) as equivalent
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name not in ("Config", "config.Config"):
            continue
        kw_names = {kw.arg for kw in node.keywords if kw.arg}
        if {"region", "api_token"} <= kw_names:
            return True
    return False


def _module_declares_check_mode(tree: ast.AST) -> bool:
    """True if AnsibleModule(supports_check_mode=True) appears in the file."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name not in ("AnsibleModule", "ansible.module_utils.basic.AnsibleModule"):
            continue
        if _bool_keyword(node, "supports_check_mode"):
            return True
    return False


def _examples_use_shared_module_defaults(source: str) -> bool:
    def _task_uses_module_defaults(task: dict[str, Any]) -> bool:
        module_defaults = task.get("module_defaults")
        if isinstance(module_defaults, dict) and "group/cisco.sccfm.all" in module_defaults:
            return True

        nested_tasks = task.get("tasks")
        if not isinstance(nested_tasks, list):
            return False
        return any(
            isinstance(nested_task, dict) and _task_uses_module_defaults(nested_task)
            for nested_task in nested_tasks
        )

    example_tasks = _parse_example_tasks(source)
    if any(_task_uses_module_defaults(task) for _, task in example_tasks):
        return True

    block = _extract_triple_quoted_assignment(source, "EXAMPLES")
    if block is None:
        return False
    return "module_defaults" in block.body and "group/cisco.sccfm.all" in block.body


def check_ansible_module_contract(file: Path) -> list[Issue]:
    """Check G — new/edited Ansible modules must follow the shared module contract."""
    if not _is_ansible_module(file):
        return []

    tree = _safe_parse(file)
    if tree is None:
        return []
    source = file.read_text(encoding="utf-8")

    issues: list[Issue] = []
    module_name = file.stem

    # Only check modules that use AnsibleModule at all
    has_ansible_module_instantiation = any(
        isinstance(node, ast.Call)
        and _call_name(node.func) in ("AnsibleModule", "ansible.module_utils.basic.AnsibleModule")
        for node in ast.walk(tree)
    )
    if not has_ansible_module_instantiation:
        return []

    if not _module_uses_helper(tree, "base_argument_spec"):
        issues.append(
            Issue(
                file=file,
                line=None,
                message=(
                    f"Ansible module '{module_name}' does not use base_argument_spec() — "
                    f"all standard modules should build on the shared argument spec"
                ),
                level="warning",
            )
        )

    if not _module_uses_config(tree):
        issues.append(
            Issue(
                file=file,
                line=None,
                message=(
                    f"Ansible module '{module_name}' does not use create_config(module) — "
                    f"use the shared config helper for consistent auth/env handling"
                ),
                level="warning",
            )
        )

    if not _module_declares_check_mode(tree):
        issues.append(
            Issue(
                file=file,
                line=None,
                message=(
                    f"Ansible module '{module_name}' does not declare supports_check_mode=True "
                    f"in AnsibleModule()"
                ),
                level="warning",
            )
        )

    if not _examples_use_shared_module_defaults(source):
        issues.append(
            Issue(
                file=file,
                line=None,
                message=(
                    f"Ansible module '{module_name}' EXAMPLES does not show "
                    "module_defaults: group/cisco.sccfm.all usage — include one example so "
                    "shared defaults are documented"
                ),
                level="warning",
            )
        )

    return issues


def check_ansible_runtime_membership(files: Sequence[Path]) -> list[Issue]:
    """Check G (runtime.yml) — modules in changed files must be in cisco.sccfm.all."""
    if not _RUNTIME_YML.exists():
        return []

    action_group = _extract_runtime_action_group(_RUNTIME_YML)
    issues: list[Issue] = []

    for file in files:
        if not _is_ansible_module(file) or not file.exists():
            continue
        module_name = file.stem
        if module_name not in action_group:
            issues.append(
                Issue(
                    file=file,
                    line=None,
                    message=(
                        f"Ansible module '{module_name}' is not listed in the "
                        f"cisco.sccfm.all action group in meta/runtime.yml — "
                        f"add it so module_defaults inheritance works"
                    ),
                    level="warning",
                )
            )

    return issues


def _caught_exception_name(node: ast.AST | None) -> str | None:
    if node is None or isinstance(node, ast.Tuple):
        return None
    name = _call_name(node)
    if not name:
        return None
    return name.split(".")[-1]


def _handler_uses_scc_api_error_conversion(handler: ast.ExceptHandler) -> bool:
    return any(
        isinstance(node, ast.Call) and _call_name(node.func) == "SccApiError.from_exception"
        for node in ast.walk(handler)
    )


def _handler_fails_with_message(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(handler):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node.func)
        if call_name is None or not call_name.endswith("fail_json"):
            continue
        if any(keyword.arg == "msg" for keyword in node.keywords):
            return True
    return False


# ── Check J: Ansible SDK error handling ──────────────────────────────────────


def check_ansible_sdk_error_handling(file: Path) -> list[Issue]:
    """Check J — SDK failures should have a structured ApiException handler."""
    if not _is_ansible_module(file):
        return []

    tree = _safe_parse(file)
    if tree is None:
        return []

    issues: list[Issue] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue

        api_handler = next(
            (
                handler
                for handler in node.handlers
                if _caught_exception_name(handler.type) == "ApiException"
            ),
            None,
        )
        generic_handler = next(
            (
                handler
                for handler in node.handlers
                if _caught_exception_name(handler.type) == "Exception"
            ),
            None,
        )
        if generic_handler is None or not _handler_fails_with_message(generic_handler):
            continue
        if api_handler is not None and _handler_uses_scc_api_error_conversion(api_handler):
            continue
        issues.append(
            Issue(
                file=file,
                line=generic_handler.lineno,
                message=(
                    "Generic except Exception handler catches module failures without a "
                    "preceding ApiException handler that uses SccApiError.from_exception()"
                ),
                level="warning",
            )
        )

    return issues


# ── Check I: Inline pagination click options instead of shared factories ──────

_SHARED_PAGINATION_FACTORIES = frozenset({"limit_option", "offset_option", "query_option"})
_INLINE_PAGINATION_FLAGS: frozenset[str] = frozenset({"--limit", "--offset", "--query"})


def _has_inline_pagination_option(tree: ast.AST) -> list[tuple[int, str]]:
    """Return (lineno, flag) pairs for click.Option(['--limit'/'--offset'/'--query']) calls."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name != "click.Option":
            continue
        if not node.args:
            continue
        flags_node = node.args[0]
        if not isinstance(flags_node, (ast.List, ast.Tuple)):
            continue
        for elt in flags_node.elts:
            flag = _string_value(elt)
            if flag and flag in _INLINE_PAGINATION_FLAGS:
                hits.append((node.lineno, flag))
                break
    return hits


def check_inline_pagination_options(file: Path) -> list[Issue]:
    """Check I — CLI list commands must use shared option factories, not inline click.Option."""
    if not file.is_relative_to(CLI_COMMANDS):
        return []
    if file == CLI_COMMANDS / "shared_options.py":
        return []

    tree = _safe_parse(file)
    if tree is None:
        return []

    # If the file already uses the shared factories, don't warn further
    uses_factory = any(
        isinstance(node, ast.Call) and _call_name(node.func) in _SHARED_PAGINATION_FACTORIES
        for node in ast.walk(tree)
    )
    if uses_factory:
        return []

    hits = _has_inline_pagination_option(tree)
    issues: list[Issue] = []
    for lineno, flag in hits:
        opt_name = flag.lstrip("-")
        issues.append(
            Issue(
                file=file,
                line=lineno,
                message=(
                    f"CLI command declares inline click.Option('{flag}') instead of using "
                    f"the shared {opt_name}_option() factory — "
                    f"use shared factories so pagination behavior and short flags stay consistent"
                ),
                level="warning",
            )
        )
    return issues


def _module_body_without_docstring(tree: ast.AST) -> list[ast.stmt]:
    if not isinstance(tree, ast.Module):
        return []
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and _string_value(body[0].value) is not None:
        return body[1:]
    return body


def _has_future_annotations_import(tree: ast.AST) -> bool:
    return any(
        isinstance(stmt, ast.ImportFrom)
        and stmt.module == "__future__"
        and any(alias.name == "annotations" for alias in stmt.names)
        for stmt in _module_body_without_docstring(tree)
    )


def _has_future_annotations_as_first_import(tree: ast.AST) -> bool:
    for stmt in _module_body_without_docstring(tree):
        if not isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        return (
            isinstance(stmt, ast.ImportFrom)
            and stmt.module == "__future__"
            and any(alias.name == "annotations" for alias in stmt.names)
        )
    return False


_LEGACY_TYPING_NAMES: frozenset[str] = frozenset(
    {"List", "Dict", "Optional", "Tuple", "Set", "Union"}
)
_LEGACY_TYPING_REPLACEMENTS: dict[str, str] = {
    "List": "list[...]",
    "Dict": "dict[...]",
    "Optional": "X | None",
    "Tuple": "tuple[...]",
    "Set": "set[...]",
    "Union": "A | B",
}
_ANSIBLE_MODULE_TESTS = ANSIBLE_MODULES / "tests"
_SCCFM_CORE_TESTS = _SCCFM_CORE / "tests"


def _collect_legacy_typing_imports(
    tree: ast.AST,
) -> tuple[dict[str, tuple[str, int]], dict[str, int]]:
    imported_names: dict[str, tuple[str, int]] = {}
    typing_modules: dict[str, int] = {}

    for node in _module_body_without_docstring(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            for alias in node.names:
                if alias.name not in _LEGACY_TYPING_NAMES:
                    continue
                imported_names[alias.asname or alias.name] = (alias.name, node.lineno)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != "typing":
                    continue
                typing_modules[alias.asname or alias.name] = node.lineno

    return imported_names, typing_modules


def _legacy_typing_name(
    node: ast.AST,
    imported_names: dict[str, tuple[str, int]],
    typing_modules: dict[str, int],
) -> str | None:
    if not isinstance(node, ast.Subscript):
        return None

    if isinstance(node.value, ast.Name):
        imported = imported_names.get(node.value.id)
        return imported[0] if imported else None

    if (
        isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id in typing_modules
        and node.value.attr in _LEGACY_TYPING_NAMES
    ):
        return node.value.attr

    return None


def _annotation_nodes(tree: ast.AST) -> list[ast.AST]:
    nodes: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            nodes.append(node.annotation)
        elif isinstance(node, ast.arg) and node.annotation is not None:
            nodes.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
            nodes.append(node.returns)
    return nodes


# ── Check K: Legacy typing syntax ─────────────────────────────────────────────


def check_legacy_typing_syntax(file: Path) -> list[Issue]:
    """Check K — future-annotations files should use modern built-in generic syntax."""
    if not (file.is_relative_to(_SCCFM_CORE) or file.is_relative_to(_SCCFM_CLI)):
        return []

    tree = _safe_parse(file)
    if tree is None or not _has_future_annotations_import(tree):
        return []

    imported_names, typing_modules = _collect_legacy_typing_imports(tree)
    if not imported_names and not typing_modules:
        return []

    issues: list[Issue] = []
    imports_by_line: dict[int, set[str]] = defaultdict(set)
    for legacy_name, lineno in imported_names.values():
        imports_by_line[lineno].add(legacy_name)

    for lineno, legacy_names in sorted(imports_by_line.items()):
        display_names = ", ".join(sorted(legacy_names))
        issues.append(
            Issue(
                file=file,
                line=lineno,
                message=(
                    f"Legacy typing import(s) {display_names} used in a future-annotations file — "
                    "prefer built-in generics and '|' syntax"
                ),
                level="warning",
            )
        )

    seen_hits: set[tuple[int, str]] = set()
    for annotation in _annotation_nodes(tree):
        for node in ast.walk(annotation):
            legacy_name = _legacy_typing_name(node, imported_names, typing_modules)
            if legacy_name is None:
                continue
            lineno = getattr(node, "lineno", getattr(annotation, "lineno", 1))
            hit = (lineno, legacy_name)
            if hit in seen_hits:
                continue
            seen_hits.add(hit)
            issues.append(
                Issue(
                    file=file,
                    line=lineno,
                    message=(
                        f"Legacy typing annotation '{legacy_name}[...]' used in a future-annotations "
                        f"file — use '{_LEGACY_TYPING_REPLACEMENTS[legacy_name]}' instead"
                    ),
                    level="warning",
                )
            )

    return issues


# ── Check L: Missing future annotations import ───────────────────────────────


def check_missing_future_annotations(file: Path) -> list[Issue]:
    """Check L — shared Python surfaces should declare future annotations first."""
    if not (
        file.is_relative_to(_SCCFM_CORE)
        or file.is_relative_to(_SCCFM_CLI)
        or file.is_relative_to(ANSIBLE_MODULES)
    ):
        return []

    tree = _safe_parse(file)
    if tree is None:
        return []
    if _has_future_annotations_as_first_import(tree):
        return []

    return [
        Issue(
            file=file,
            line=None,
            message=(
                "File does not declare 'from __future__ import annotations' as the first import"
            ),
            level="warning",
        )
    ]


# ── Check M: Advisory test file parity ───────────────────────────────────────


def check_test_file_parity(files: Sequence[Path]) -> list[Issue]:
    """Check M — changed modules/services should have a matching test file."""
    issues: list[Issue] = []

    for file in files:
        if file.suffix != ".py" or not file.exists():
            continue
        if _safe_parse(file) is None:
            continue

        expected_test: Path | None = None
        message: str | None = None

        if file.parent == ANSIBLE_MODULES and file.name != "__init__.py":
            expected_test = _ANSIBLE_MODULE_TESTS / f"test_{file.stem}.py"
            message = (
                f"Ansible module '{file.name}' has no matching test file at "
                f"'{expected_test.relative_to(ROOT)}'"
            )
        elif file.is_relative_to(_SCCFM_SERVICES) and file.name != "__init__.py":
            expected_test = _SCCFM_CORE_TESTS / f"test_{file.stem}.py"
            message = (
                f"Core service '{file.relative_to(ROOT)}' has no matching test file at "
                f"'{expected_test.relative_to(ROOT)}'"
            )

        if expected_test is None or message is None or expected_test.exists():
            continue

        issues.append(
            Issue(
                file=file,
                line=None,
                message=message,
                level="warning",
            )
        )

    return issues


def collect_issues(files: Sequence[Path]) -> list[Issue]:
    issues: list[Issue] = []

    for file in files:
        if not file.exists() or file.suffix != ".py":
            continue
        issues.extend(check_variable_naming(file))
        issues.extend(check_api_key_mapping(file))
        issues.extend(check_missing_future_annotations(file))

        if file.is_relative_to(_SCCFM_CORE):
            issues.extend(check_optional_str_coercion(file))
            issues.extend(check_datetime_as_str(file))
            issues.extend(check_sdk_api_call_kwargs(file))

        if file.is_relative_to(_SCCFM_CORE) or file.is_relative_to(_SCCFM_CLI):
            issues.extend(check_legacy_typing_syntax(file))

        if _is_ansible_module(file):
            metadata = _build_ansible_metadata(file)
            issues.extend(check_ansible_examples(file, metadata))
            issues.extend(check_ansible_return_contract(file, metadata))
            issues.extend(check_ansible_module_naming(file, metadata))
            issues.extend(check_ansible_argument_spec(file, metadata))
            issues.extend(check_ansible_module_contract(file))
            issues.extend(check_ansible_sdk_error_handling(file))

        if _is_cli_command(file):
            metadata = _build_cli_metadata(file)
            issues.extend(check_cli_command_naming(file, metadata))

        if file.is_relative_to(CLI_COMMANDS):
            issues.extend(check_inline_pagination_options(file))

    issues.extend(check_api_mapping_consistency(files))
    issues.extend(check_service_list_signatures(files))
    issues.extend(check_cross_device_cli_consistency(files))
    issues.extend(check_cross_device_ansible_consistency(files))
    issues.extend(check_cli_ansible_alignment(files))
    issues.extend(check_region_vocabulary_drift(files))
    issues.extend(check_ansible_runtime_membership(files))
    issues.extend(check_test_file_parity(files))

    issues.sort(key=lambda issue: (issue.file, issue.line or 0, issue.message))
    return issues


def _group_issues_by_file(issues: Sequence[Issue]) -> dict[Path, list[Issue]]:
    by_file: dict[Path, list[Issue]] = {}
    for issue in issues:
        by_file.setdefault(issue.file, []).append(issue)
    return by_file


def _issue_counts(issues: Sequence[Issue]) -> tuple[int, int]:
    errors = sum(1 for issue in issues if issue.level == "error")
    warnings = sum(1 for issue in issues if issue.level == "warning")
    return errors, warnings


def run(
    files: list[Path],
    *,
    annotations: bool = False,
    fail_on_warning: bool = False,
) -> int:
    issues = collect_issues(files)
    errors, warnings = _issue_counts(issues)

    if annotations:
        for issue in issues:
            print(issue.as_annotation())
        files_with_issues = len({issue.file for issue in issues})
        print(f"\n{errors} error(s), {warnings} warning(s) across {files_with_issues} file(s).")
    else:
        _print_readable(issues, files)

    if errors > 0:
        return 1
    if fail_on_warning and warnings > 0:
        return 1
    return 0


def _print_readable(issues: list[Issue], files: list[Path]) -> None:
    errors, warnings = _issue_counts(issues)

    if not issues:
        print(f"✓ No issues found across {len(files)} file(s).")
        return

    by_file = _group_issues_by_file(issues)

    for file, file_issues in by_file.items():
        rel = _display_path(file)
        file_errors, file_warnings = _issue_counts(file_issues)
        parts = []
        if file_errors:
            parts.append(f"{file_errors} error(s)")
        if file_warnings:
            parts.append(f"{file_warnings} warning(s)")
        print(f"\n── {rel}  [{', '.join(parts)}]")
        for issue in file_issues:
            icon = "✖" if issue.level == "error" else "⚠"
            loc = f"line {issue.line:>4}" if issue.line is not None else "          "
            print(f"   {icon}  {loc}  {issue.message}")

    print(f"\n{'─' * 60}")
    files_with_issues = len(by_file)
    print(f"  {errors} error(s)  {warnings} warning(s)  across {files_with_issues} file(s).")
    print(f"{'─' * 60}")


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

    sys.exit(
        run(
            files,
            annotations=args.annotations,
            fail_on_warning=args.fail_on_warning,
        )
    )


if __name__ == "__main__":
    main()
