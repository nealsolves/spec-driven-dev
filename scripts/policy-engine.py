#!/usr/bin/env python3
"""Deterministic local policy validation for the modular delivery template."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any, Iterable

import jsonschema
import yaml
from referencing.exceptions import Unresolvable


CONTROL_FILES = {
    "project": ".claude/project.yaml",
    "routing": ".claude/routing.yaml",
    "policy": ".claude/policy.yaml",
    "lifecycle": ".claude/lifecycle.yaml",
}

SCHEMA_FILES = {
    "project": ".claude/schemas/project.schema.json",
    "routing": ".claude/schemas/routing.schema.json",
    "policy": ".claude/schemas/policy.schema.json",
    "context": ".claude/schemas/context.schema.json",
}


class PolicyInputError(ValueError):
    """A stable, user-actionable policy input error."""


class JsonArgumentParser(argparse.ArgumentParser):
    """Convert argparse failures into the CLI's single-JSON response contract."""

    def error(self, message: str) -> None:
        detail = message if message.startswith("argument ") else f"argument {message}"
        raise PolicyInputError(detail)


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that also rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def canonical_hash(value: Any) -> str:
    """Return a stable SHA-256 digest for a JSON-compatible value."""

    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _error(message: str) -> str:
    return f"ERROR: {message}"


def _unresolved_reference(exc: Unresolvable) -> str:
    reference = str(getattr(exc, "ref", None) or exc)
    return f"#{reference}" if reference.startswith("/") else reference


def _read_text(path: Path, label: str) -> str:
    if not path.is_file():
        raise PolicyInputError(f"{label}: file does not exist: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PolicyInputError(f"{label}: cannot read {path}: {exc}") from exc


def _load_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        value = yaml.load(_read_text(path, label), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        detail = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        raise PolicyInputError(f"{label}: invalid YAML: {detail}") from exc
    if not isinstance(value, dict):
        raise PolicyInputError(f"{label}: YAML document must be an object")
    return value


def _json_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PolicyInputError(f"schema: duplicate JSON key {key!r}")
        value[key] = item
    return value


def _load_schema(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            _read_text(path, label), object_pairs_hook=_json_object_pairs
        )
    except json.JSONDecodeError as exc:
        raise PolicyInputError(
            f"{label}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise PolicyInputError(f"{label}: JSON document must be an object")
    return value


def load_control_plane(root: Path) -> dict[str, Any]:
    """Load the four controls and four schemas rooted at ``root``."""

    root = Path(root).resolve()
    if not root.is_dir():
        raise PolicyInputError(f"root directory does not exist: {root}")

    bundle: dict[str, Any] = {"root": root}
    for name, relative_path in CONTROL_FILES.items():
        bundle[name] = _load_yaml(root / relative_path, name)
    bundle["schemas"] = {
        name: _load_schema(root / relative_path, f"{name} schema")
        for name, relative_path in SCHEMA_FILES.items()
    }
    return bundle


def _json_path(parts: Iterable[Any]) -> str:
    path = ""
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += ("." if path else "") + str(part)
    return path


def _schema_validation_errors(
    name: str, value: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        return [_error(f"{name} schema: invalid Draft 2020-12 schema: {exc.message}")]

    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    try:
        validation_errors = sorted(
            validator.iter_errors(value),
            key=lambda item: tuple(str(p) for p in item.path),
        )
    except Unresolvable as exc:
        reference = _unresolved_reference(exc)
        return [_error(f"{name}: unresolved schema reference: {reference}")]
    for validation_error in validation_errors:
        location = _json_path(validation_error.path)
        label = f"{name}.{location}" if location else name
        errors.append(_error(f"{label}: {validation_error.message}"))
    return errors


def _control_schema_errors(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schemas = bundle["schemas"]
    for name in ("project", "routing", "policy"):
        errors.extend(_schema_validation_errors(name, bundle[name], schemas[name]))

    policy_schema = schemas["policy"]
    try:
        jsonschema.Draft202012Validator.check_schema(policy_schema)
        lifecycle_validator = jsonschema.Draft202012Validator(
            policy_schema, format_checker=jsonschema.FormatChecker()
        ).evolve(schema={"$ref": "#/$defs/lifecycle"})
        try:
            lifecycle_errors = sorted(
                lifecycle_validator.iter_errors(bundle["lifecycle"]),
                key=lambda item: tuple(str(p) for p in item.path),
            )
        except Unresolvable as exc:
            reference = _unresolved_reference(exc)
            errors.append(
                _error(f"lifecycle: unresolved schema reference: {reference}")
            )
            lifecycle_errors = []
        for validation_error in lifecycle_errors:
            location = _json_path(validation_error.path)
            label = f"lifecycle.{location}" if location else "lifecycle"
            errors.append(_error(f"{label}: {validation_error.message}"))
    except jsonschema.SchemaError as exc:
        errors.append(
            _error(f"policy schema: invalid Draft 2020-12 schema: {exc.message}")
        )

    # The context schema is a contract even when no live context is supplied.
    try:
        jsonschema.Draft202012Validator.check_schema(schemas["context"])
    except jsonschema.SchemaError as exc:
        errors.append(
            _error(f"context schema: invalid Draft 2020-12 schema: {exc.message}")
        )
    return errors


def _routing_reference_errors(bundle: dict[str, Any]) -> list[str]:
    routing = bundle["routing"]
    policy = bundle["policy"]
    facts = routing.get("facts")
    routes = routing.get("routes")
    classification_rules = routing.get("classification_rules")
    if not isinstance(facts, dict) or not isinstance(routes, dict):
        return []

    errors: list[str] = []
    if isinstance(classification_rules, list):
        for index, rule in enumerate(classification_rules):
            if not isinstance(rule, dict):
                continue
            fact = rule.get("fact")
            if isinstance(fact, str) and fact not in facts:
                errors.append(
                    _error(
                        f"routing.classification_rules[{index}].fact: unknown fact {fact!r}"
                    )
                )
            additions = rule.get("add")
            if isinstance(additions, list):
                for route in additions:
                    if isinstance(route, str) and route not in routes:
                        errors.append(
                            _error(
                                f"routing.classification_rules[{index}].add: unknown route {route!r}"
                            )
                        )

    risk = policy.get("risk")
    if isinstance(risk, dict):
        factor_names = risk.get("factors")
        if isinstance(factor_names, dict):
            for fact in factor_names:
                if fact not in facts:
                    errors.append(_error(f"policy.risk.factors: unknown fact {fact!r}"))
        automatic = risk.get("automatic_critical")
        if isinstance(automatic, list):
            for fact in automatic:
                if isinstance(fact, str) and fact not in facts:
                    errors.append(
                        _error(f"policy.risk.automatic_critical: unknown fact {fact!r}")
                    )
        escalation = risk.get("escalation")
        if isinstance(escalation, list):
            for index, rule in enumerate(escalation):
                if not isinstance(rule, dict):
                    continue
                for fact in rule.get("when_all", []):
                    if isinstance(fact, str) and fact not in facts:
                        errors.append(
                            _error(
                                f"policy.risk.escalation[{index}].when_all: unknown fact {fact!r}"
                            )
                        )
    return errors


def _markdown_reference_errors(bundle: dict[str, Any]) -> list[str]:
    routing = bundle["routing"]
    root = bundle["root"]
    references: list[str] = []

    always = routing.get("always")
    if isinstance(always, dict) and isinstance(always.get("rules"), list):
        references.extend(always["rules"])
    workflow_rules = routing.get("workflow_rules")
    if isinstance(workflow_rules, dict):
        references.extend(workflow_rules.values())
    routes = routing.get("routes")
    if isinstance(routes, dict):
        for route in routes.values():
            if not isinstance(route, dict):
                continue
            for key in ("rules", "workflows"):
                values = route.get(key)
                if isinstance(values, list):
                    references.extend(values)

    errors: list[str] = []
    seen: set[str] = set()
    instruction_system = bundle["project"].get("instruction_system", {})
    module_state = (
        instruction_system.get("module_state")
        if isinstance(instruction_system, dict)
        else None
    )
    for reference in references:
        if not isinstance(reference, str) or reference in seen:
            continue
        seen.add(reference)
        namespace = reference.partition("/")[0]
        namespace_root = root / ".claude" / namespace
        namespace_is_enforced = (
            module_state == "complete" or namespace_root.is_dir()
        )
        if namespace_is_enforced and not (root / ".claude" / reference).is_file():
            errors.append(
                _error(f"routing markdown path does not exist: .claude/{reference}")
            )
    return errors


def _vocabulary_errors(bundle: dict[str, Any]) -> list[str]:
    context_properties = bundle["schemas"]["context"].get("properties")
    if not isinstance(context_properties, dict):
        return []

    comparisons = (
        (
            "workflow_family",
            bundle["routing"].get("workflow_rules"),
            context_properties.get("workflow_family"),
        ),
        (
            "action",
            bundle["policy"].get("authority", {}).get("actions"),
            context_properties.get("action"),
        ),
    )
    errors: list[str] = []
    for name, configured_mapping, schema_property in comparisons:
        if not isinstance(configured_mapping, dict) or not isinstance(
            schema_property, dict
        ):
            continue
        schema_values = schema_property.get("enum")
        if not isinstance(schema_values, list) or not all(
            isinstance(value, str) for value in schema_values
        ):
            continue
        configured = set(configured_mapping)
        declared = set(schema_values)
        configured_only = sorted(configured - declared)
        schema_only = sorted(declared - configured)
        if configured_only:
            errors.append(
                _error(
                    f"vocabulary.{name}: configured-only values: {', '.join(configured_only)}"
                )
            )
        if schema_only:
            errors.append(
                _error(
                    f"vocabulary.{name}: schema-only values: {', '.join(schema_only)}"
                )
            )
    return errors


def _lifecycle_errors(bundle: dict[str, Any]) -> list[str]:
    lifecycle = bundle["lifecycle"]
    normal_states = lifecycle.get("normal_states")
    exceptional_states = lifecycle.get("exceptional_states")
    transitions = lifecycle.get("transitions")
    paths = lifecycle.get("paths")
    if not all(
        isinstance(item, expected)
        for item, expected in (
            (normal_states, list),
            (exceptional_states, list),
            (transitions, list),
            (paths, dict),
        )
    ):
        return []

    errors: list[str] = []
    declared_states = set(normal_states) | set(exceptional_states)
    edges: set[tuple[str, str]] = set()
    adjacency: dict[str, set[str]] = {state: set() for state in declared_states}
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            continue
        source = transition.get("from")
        target = transition.get("to")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        edge = (source, target)
        if edge in edges:
            errors.append(
                _error(
                    f"lifecycle.transitions[{index}]: duplicate transition {source} -> {target}"
                )
            )
        edges.add(edge)
        if source not in declared_states:
            errors.append(
                _error(f"lifecycle.transitions[{index}].from: undeclared state {source}")
            )
        if target not in declared_states:
            errors.append(
                _error(f"lifecycle.transitions[{index}].to: undeclared state {target}")
            )
        adjacency.setdefault(source, set()).add(target)

    for path_name, states in paths.items():
        if not isinstance(states, list) or not states:
            continue
        if states[0] != "UNCLASSIFIED":
            errors.append(
                _error(f"lifecycle.paths.{path_name}: path must start at UNCLASSIFIED")
            )
        if states[-1] != "COMPLETE":
            errors.append(
                _error(f"lifecycle.paths.{path_name}: path must end at COMPLETE")
            )
        for source, target in zip(states, states[1:]):
            if (source, target) not in edges:
                errors.append(
                    _error(
                        f"lifecycle.paths.{path_name}: transition {source} -> {target} is not declared"
                    )
                )

    reachable: set[str] = set()
    queue: deque[str] = deque(["UNCLASSIFIED"])
    while queue:
        state = queue.popleft()
        if state in reachable:
            continue
        reachable.add(state)
        queue.extend(adjacency.get(state, set()) - reachable)
    for state in normal_states:
        if state not in reachable:
            errors.append(_error(f"lifecycle.normal_states: state {state} is unreachable"))

    reverse_adjacency: dict[str, set[str]] = {
        state: set() for state in declared_states
    }
    for source, target in edges:
        reverse_adjacency.setdefault(target, set()).add(source)
    can_complete: set[str] = set()
    queue = deque(["COMPLETE"])
    while queue:
        state = queue.popleft()
        if state in can_complete:
            continue
        can_complete.add(state)
        queue.extend(reverse_adjacency.get(state, set()) - can_complete)
    for state in normal_states:
        if state not in can_complete:
            errors.append(
                _error(
                    f"lifecycle.normal_states: state {state} cannot reach COMPLETE"
                )
            )
    return errors


def _resolve_context_path(root: Path, context_path: Path) -> Path:
    context_path = Path(context_path)
    return context_path if context_path.is_absolute() else root / context_path


def _context_errors(bundle: dict[str, Any], context_path: Path) -> list[str]:
    root = bundle["root"]
    context = _load_yaml(_resolve_context_path(root, context_path), "context")
    errors = _schema_validation_errors(
        "context", context, bundle["schemas"]["context"]
    )
    if errors:
        return errors

    routing = bundle["routing"]
    policy = bundle["policy"]
    lifecycle = bundle["lifecycle"]
    known_facts = set(routing["facts"])
    for fact in context["facts"]:
        if fact not in known_facts:
            errors.append(_error(f"context.facts: unknown fact {fact!r}"))
    workflow = context["workflow_family"]
    if workflow not in routing["workflow_rules"]:
        errors.append(
            _error(f"context.workflow_family: unknown workflow family {workflow!r}")
        )
    action = context["action"]
    if action not in policy["authority"]["actions"]:
        errors.append(_error(f"context.action: unknown authority action {action!r}"))
    states = set(lifecycle["normal_states"]) | set(lifecycle["exceptional_states"])
    if context["current_state"] not in states:
        errors.append(
            _error(f"context.current_state: undeclared state {context['current_state']!r}")
        )
    return errors


def validate_bundle(root: Path, context_path: Path | None) -> list[str]:
    """Validate configuration, references, lifecycle, and an optional context."""

    try:
        bundle = load_control_plane(Path(root))
        errors = _control_schema_errors(bundle)
        errors.extend(_routing_reference_errors(bundle))
        errors.extend(_markdown_reference_errors(bundle))
        errors.extend(_vocabulary_errors(bundle))
        errors.extend(_lifecycle_errors(bundle))
        if context_path is not None:
            errors.extend(_context_errors(bundle, Path(context_path)))
        return sorted(set(errors))
    except PolicyInputError as exc:
        return [_error(str(exc))]
    except Unresolvable as exc:
        reference = _unresolved_reference(exc)
        return [_error(f"unresolved schema reference: {reference}")]
    except (KeyError, TypeError, ValueError) as exc:
        # Malformed user data should remain a stable validation result, not a traceback.
        return [_error(f"invalid control-plane structure: {exc}")]


def _build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate_parser = commands.add_parser("validate", help="validate policy files")
    validate_parser.add_argument("--root", required=True, type=Path)
    validate_parser.add_argument("--context", type=Path)
    return parser


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _build_parser().parse_args(argv)
        errors = validate_bundle(arguments.root, arguments.context)
        payload = {"valid": not errors, "errors": errors}
        _emit(payload)
        return 0 if not errors else 1
    except PolicyInputError as exc:
        _emit({"valid": False, "errors": [_error(str(exc))]})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
