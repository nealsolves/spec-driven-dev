#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CONTEXT=""

usage() {
  echo "Usage: scripts/validate-instructions.sh [--context PATH]" >&2
}

if [[ $# -eq 0 ]]; then
  :
elif [[ $# -eq 2 && "$1" == "--context" && -n "$2" ]]; then
  CONTEXT="$2"
else
  usage
  exit 2
fi

resolve_command() {
  case "$1" in
    */*)
      if [[ -x "$1" ]]; then
        printf '%s\n' "$1"
        return 0
      fi
      ;;
    *)
      command -v "$1" 2>/dev/null && return 0
      ;;
  esac
  return 1
}

if [[ -n "${POLICY_PYTHON:-}" ]]; then
  PYTHON="$(resolve_command "$POLICY_PYTHON" || true)"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="$(command -v python3 2>/dev/null || true)"
fi

technical_block() {
  echo "ERROR: BLOCKED_TECHNICAL: Python 3.11+ with PyYAML 6.x and jsonschema 4.x is required; install requirements-policy.txt or set POLICY_PYTHON to a compatible interpreter." >&2
  exit 3
}

if [[ -z "$PYTHON" ]]; then
  technical_block
fi
RUNTIME_SENTINEL="POLICY_RUNTIME_OK_3_11_PYYAML_6_JSONSCHEMA_4"
RUNTIME_PROBE_END="POLICY_RUNTIME_PROBE_END"
RUNTIME_PROBE_OUTPUT="$(
  "$PYTHON" -c '
import re
import sys
from importlib import metadata

import jsonschema
import yaml


def numeric_version(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value) is None:
        raise ValueError("distribution version is not a numeric release")
    return tuple(int(component) for component in value.split("."))


def in_range(value, minimum, maximum):
    parsed = numeric_version(value)
    return numeric_version(minimum) <= parsed < numeric_version(maximum)


if sys.version_info < (3, 11):
    raise SystemExit(1)
if not in_range(metadata.version("PyYAML"), "6.0", "7"):
    raise SystemExit(1)
if not in_range(metadata.version("jsonschema"), "4.23", "5"):
    raise SystemExit(1)
print("POLICY_RUNTIME_OK_3_11_PYYAML_6_JSONSCHEMA_4")
' 2>&1
  printf '%s' "$RUNTIME_PROBE_END"
)"
RUNTIME_EXPECTED="${RUNTIME_SENTINEL}
${RUNTIME_PROBE_END}"
if [[ "$RUNTIME_PROBE_OUTPUT" != "$RUNTIME_EXPECTED" ]]; then
  technical_block
fi

PROJECTION_OUTPUT="$("$PYTHON" -B "$ROOT/scripts/render-compatibility.py" --root "$ROOT" --check 2>&1)"
PROJECTION_STATUS=$?
if [[ $PROJECTION_STATUS -ne 0 ]]; then
  printf '%s\n' "$PROJECTION_OUTPUT"
fi
if [[ $PROJECTION_STATUS -eq 3 ]]; then
  exit 3
fi

ENGINE_ARGUMENTS=("$ROOT/scripts/policy-engine.py" validate --root "$ROOT")
if [[ -n "$CONTEXT" ]]; then
  ENGINE_ARGUMENTS+=(--context "$CONTEXT")
fi

ENGINE_OUTPUT="$("$PYTHON" "${ENGINE_ARGUMENTS[@]}" 2>&1)"
ENGINE_STATUS=$?
ENGINE_RENDERED="$(
  printf '%s\n' "$ENGINE_OUTPUT" | "$PYTHON" -c '
import json
import sys

engine_status = int(sys.argv[1])
raw = sys.stdin.read()
try:
    payload = json.loads(raw)
except (TypeError, ValueError) as exc:
    detail = " ".join(raw.strip().split())[:500]
    print(f"ERROR: policy engine returned invalid output: {exc}; {detail}")
    raise SystemExit(1)

if not isinstance(payload, dict):
    print("ERROR: policy engine response must be a JSON object")
    raise SystemExit(1)

errors = payload.get("errors")
valid = payload.get("valid")
if not isinstance(errors, list) or not isinstance(valid, bool):
    print("ERROR: policy engine response must contain boolean valid and list errors")
    raise SystemExit(1)
for error in errors:
    message = str(error)
    print(message if message.startswith("ERROR:") else f"ERROR: {message}")
if errors or not valid:
    raise SystemExit(1)
if engine_status != 0:
    print(f"ERROR: policy engine exited with status {engine_status} after reporting success")
    raise SystemExit(1)
' "$ENGINE_STATUS"
)"
ENGINE_VALIDATION_STATUS=$?
if [[ -n "$ENGINE_RENDERED" ]]; then
  printf '%s\n' "$ENGINE_RENDERED"
fi

"$PYTHON" - "$ROOT" <<'PY'
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


root = Path(sys.argv[1]).resolve()
errors = []
seen_errors = set()


def error(message):
    rendered = f"ERROR: {message}"
    if rendered not in seen_errors:
        seen_errors.add(rendered)
        errors.append(rendered)


def path_label(path):
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def safe_resolve(path):
    try:
        return path.resolve()
    except (OSError, RuntimeError) as exc:
        error(f"cannot resolve artifact {path_label(path)}: {exc}")
        return None


def safe_is_file(path):
    try:
        return path.is_file()
    except OSError as exc:
        error(f"cannot inspect artifact {path_label(path)}: {exc}")
        return False


def safe_is_dir(path):
    try:
        return path.is_dir()
    except OSError as exc:
        error(f"cannot inspect artifact directory {path_label(path)}: {exc}")
        return False


def safe_is_symlink(path):
    try:
        return path.is_symlink()
    except OSError as exc:
        error(f"cannot inspect artifact symlink {path_label(path)}: {exc}")
        return False


def read_bytes(path):
    try:
        return path.read_bytes()
    except (OSError, UnicodeError) as exc:
        error(f"cannot read instruction artifact {path_label(path)}: {exc}")
        return None


def read_utf8(path):
    payload = read_bytes(path)
    if payload is None:
        return None
    try:
        return payload.decode("utf-8")
    except UnicodeError as exc:
        error(f"cannot read instruction artifact {path_label(path)} as UTF-8: {exc}")
        return None


def stays_inside_repository(path):
    resolved = safe_resolve(path)
    if resolved is None:
        return False
    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    return True


def inventory(directory, expected_names):
    expected = set(expected_names)
    if safe_is_symlink(directory) and not stays_inside_repository(directory):
        error(f"artifact directory symlink escapes repository: {path_label(directory)}")
        for name in sorted(expected):
            error(f"missing artifact: {path_label(directory / name)}")
        return
    if not safe_is_dir(directory):
        for name in sorted(expected):
            error(f"missing artifact: {path_label(directory / name)}")
        return
    actual = set()
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        error(f"cannot enumerate artifact directory {path_label(directory)}: {exc}")
        return
    for path in entries:
        is_symlink = safe_is_symlink(path)
        if path.name == ".DS_Store" or not (safe_is_file(path) or is_symlink):
            continue
        actual.add(path.name)
        if is_symlink and not stays_inside_repository(path):
            error(f"artifact symlink escapes repository: {path_label(path)}")
    for name in sorted(expected - actual):
        error(f"missing artifact: {path_label(directory / name)}")
    for name in sorted(actual - expected):
        error(f"unexpected artifact: {path_label(directory / name)}")


required_root_files = (
    "CLAUDE.md",
    "implementation_status.md",
    "requirements-policy.txt",
    ".specify/memory/constitution.md",
    ".claude/README.md",
)
for relative in required_root_files:
    path = root / relative
    if safe_is_symlink(path) and not stays_inside_repository(path):
        error(f"artifact symlink escapes repository: {relative}")
    elif not safe_is_file(path):
        error(f"missing artifact: {relative}")

inventory(
    root / ".claude",
    {
        "README.md",
        "project.yaml",
        "routing.yaml",
        "policy.yaml",
        "lifecycle.yaml",
    },
)
inventory(
    root / ".claude/schemas",
    {
        "project.schema.json",
        "routing.schema.json",
        "policy.schema.json",
        "context.schema.json",
    },
)
inventory(
    root / ".claude/rules",
    {
        "engineering.md",
        "testing.md",
        "security.md",
        "architecture.md",
        "data-privacy.md",
        "production-readiness.md",
        "observability.md",
        "release-management.md",
        "compliance.md",
        "ownership.md",
        "ai-systems.md",
        "documentation.md",
    },
)
inventory(
    root / ".claude/workflows",
    {
        "project-initialization.md",
        "instruction-system-change.md",
        "feature-development.md",
        "bug-fix.md",
        "maintenance.md",
        "dependency-update.md",
        "brownfield-change.md",
        "release.md",
        "incident-hotfix.md",
    },
)
inventory(
    root / ".claude/profiles",
    {"solo-developer.md", "team.md", "regulated.md", "prototype.md"},
)
inventory(
    root / ".claude/templates",
    {
        "feature-instruction-context.md",
        "adr-template.md",
        "threat-model-template.md",
        "privacy-assessment-template.md",
        "production-readiness-template.md",
        "observability-plan-template.md",
        "compliance-mapping-template.md",
        "risk-exception-template.md",
        "release-readiness-template.md",
        "incident-record-template.md",
        "maintenance-record-template.md",
    },
)
inventory(
    root / "scripts",
    {
        "policy-engine.py",
        "render-agent-adapters.py",
        "render-compatibility.py",
        "validate-instructions.sh",
        "validate-feature-context.sh",
    },
)

for relative in (
    "scripts/policy-engine.py",
    "scripts/render-agent-adapters.py",
    "scripts/render-compatibility.py",
    "scripts/validate-instructions.sh",
    "scripts/validate-feature-context.sh",
):
    path = root / relative
    if safe_is_file(path) and not os.access(path, os.X_OK):
        error(f"script is not executable: {relative}")

claude_path = root / "CLAUDE.md"
claude_bytes = None
if safe_is_file(claude_path):
    claude_bytes = read_bytes(claude_path)
if safe_is_file(claude_path) and claude_bytes is not None:
    line_count = claude_bytes.count(b"\n")
    if line_count > 350:
        error(f"CLAUDE.md has {line_count} lines; maximum is 350 (wc -l semantics)")
    try:
        claude_text = claude_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        error(f"CLAUDE.md is not valid UTF-8: {exc}")
        claude_text = ""
    required_states = (
        "UNCLASSIFIED",
        "CLASSIFIED",
        "SPECIFIED",
        "CLARIFIED",
        "PLANNED",
        "TASKED",
        "ANALYZED",
        "IMPLEMENTING",
        "VALIDATING",
        "REVIEWING",
        "CONVERGING",
        "RELEASE_READY",
        "DEPLOYING",
        "VERIFYING",
        "COMPLETE",
        "BLOCKED_REQUIREMENT",
        "BLOCKED_POLICY",
        "BLOCKED_TECHNICAL",
        "HUMAN_DECISION_REQUIRED",
        "ROLLBACK_REQUIRED",
        "INCIDENT",
    )
    for state in required_states:
        if not re.search(rf"(?<![A-Z0-9_]){re.escape(state)}(?![A-Z0-9_])", claude_text):
            error(f"CLAUDE.md is missing required lifecycle term: {state}")
    ci_sentence = "Required CI on the exact merge candidate is authoritative for merge."
    if ci_sentence not in claude_text:
        error(f"CLAUDE.md must contain the exact CI rule: {ci_sentence}")

profile_requirements = {
    ".claude/profiles/solo-developer.md": (
        "One person may hold",
        "no default second-human count",
    ),
    ".claude/profiles/regulated.md": (
        "overlay may override solo allowances",
    ),
}
for relative, phrases in profile_requirements.items():
    path = root / relative
    if not safe_is_file(path):
        continue
    if safe_is_symlink(path) and not stays_inside_repository(path):
        continue
    content = read_utf8(path)
    if content is None:
        continue
    normalized_content = " ".join(content.split())
    for phrase in phrases:
        if phrase not in normalized_content:
            error(f"{relative} is missing required wording: {phrase}")

markdown_files = []
for relative in ("CLAUDE.md", "implementation_status.md", ".specify/memory/constitution.md"):
    path = root / relative
    if safe_is_file(path) and stays_inside_repository(path):
        markdown_files.append(path)
claude_root = root / ".claude"
if safe_is_dir(claude_root):
    try:
        markdown_candidates = list(claude_root.rglob("*.md"))
    except OSError as exc:
        error(f"cannot enumerate Markdown artifacts below .claude: {exc}")
        markdown_candidates = []
    markdown_files.extend(
        path
        for path in markdown_candidates
        if safe_is_file(path) and stays_inside_repository(path)
    )

def without_fenced_code(content):
    rendered = []
    fence_character = None
    fence_length = 0
    fence_pattern = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
    for line in content.splitlines(keepends=True):
        match = fence_pattern.match(line)
        if fence_character is None and match:
            marker = match.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            rendered.append("\n" if line.endswith("\n") else "")
            continue
        if fence_character is not None:
            stripped = line.lstrip(" ")
            marker_length = len(stripped) - len(stripped.lstrip(fence_character))
            if marker_length >= fence_length:
                fence_character = None
                fence_length = 0
            rendered.append("\n" if line.endswith("\n") else "")
            continue
        rendered.append(line)
    return "".join(rendered)


def unescape_destination(target):
    return re.sub(r"\\([\\()<> ])", r"\1", target)


def inline_destinations(content):
    """Yield bounded CommonMark-style inline destinations."""

    cursor = 0
    content_length = len(content)
    while cursor < content_length:
        separator = content.find("](", cursor)
        if separator < 0:
            return
        destination_start = separator + 2
        while destination_start < content_length and content[destination_start] in " \t":
            destination_start += 1
        if destination_start >= content_length or content[destination_start] == "\n":
            cursor = separator + 2
            continue

        scan_limit = min(content_length, destination_start + 8192)
        if content[destination_start] == "<":
            index = destination_start + 1
            escaped = False
            while index < scan_limit and content[index] != "\n":
                character = content[index]
                if character == ">" and not escaped:
                    yield unescape_destination(content[destination_start + 1 : index])
                    cursor = index + 1
                    break
                escaped = character == "\\" and not escaped
                if character != "\\":
                    escaped = False
                index += 1
            else:
                cursor = separator + 2
            continue

        depth = 1
        index = destination_start
        destination_end = None
        escaped = False
        while index < scan_limit:
            character = content[index]
            if character == "\n" and depth == 1:
                break
            if escaped:
                escaped = False
                index += 1
                continue
            if character == "\\":
                escaped = True
                index += 1
                continue
            if character == "(" and destination_end is None:
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    end = destination_end if destination_end is not None else index
                    yield unescape_destination(content[destination_start:end])
                    cursor = index + 1
                    break
            elif character in " \t" and depth == 1 and destination_end is None:
                destination_end = index
            index += 1
        else:
            cursor = separator + 2
            continue
        if index >= scan_limit or depth != 0:
            cursor = separator + 2


def reference_destination(remainder):
    remainder = remainder.lstrip(" \t")
    if not remainder:
        return None
    if remainder.startswith("<"):
        escaped = False
        for index, character in enumerate(remainder[1:], start=1):
            if character == ">" and not escaped:
                return unescape_destination(remainder[1:index])
            escaped = character == "\\" and not escaped
            if character != "\\":
                escaped = False
        return None

    depth = 0
    escaped = False
    destination = []
    for character in remainder[:8192]:
        if escaped:
            destination.append(character)
            escaped = False
            continue
        if character == "\\":
            destination.append(character)
            escaped = True
            continue
        if character in " \t" and depth == 0:
            break
        if character == "(":
            depth += 1
        elif character == ")":
            if depth == 0:
                break
            depth -= 1
        destination.append(character)
    if not destination or depth != 0:
        return None
    return unescape_destination("".join(destination))


def normalized_reference_label(label):
    return " ".join(label.split()).casefold()


def validate_markdown_target(document, target):
    if not target or target.startswith("#"):
        return
    try:
        parsed = urlsplit(target)
    except ValueError as exc:
        error(
            f"malformed Markdown link in {path_label(document)} -> {target}: {exc}"
        )
        return
    if parsed.scheme or parsed.netloc:
        return
    link_path = unquote(parsed.path)
    if not link_path:
        return
    if Path(link_path).is_absolute():
        error(
            f"local Markdown link must stay inside repository: "
            f"{path_label(document)} -> {target}"
        )
        return
    resolved = safe_resolve(document.parent / link_path)
    if resolved is None:
        return
    try:
        resolved.relative_to(root)
    except ValueError:
        error(
            f"local Markdown link escapes repository: "
            f"{path_label(document)} -> {target}"
        )
        return
    try:
        exists = resolved.exists()
    except OSError as exc:
        error(
            f"cannot inspect local Markdown link: "
            f"{path_label(document)} -> {target}: {exc}"
        )
        return
    if not exists:
        error(
            f"broken local Markdown link: "
            f"{path_label(document)} -> {target}"
        )


definition_pattern = re.compile(r"(?m)^[ \t]{0,3}\[([^\]\n]+)\]:[ \t]*(.*)$")
explicit_reference_pattern = re.compile(
    r"(?<![!\\])\[([^\]\n]+)\]\[([^\]\n]*)\]"
)
for document in sorted(set(markdown_files)):
    content = read_utf8(document)
    if content is None:
        continue
    scannable = without_fenced_code(content)
    definitions = {}
    for match in definition_pattern.finditer(scannable):
        label = normalized_reference_label(match.group(1))
        target = reference_destination(match.group(2))
        if target is None:
            error(
                f"malformed Markdown reference definition: "
                f"{path_label(document)} -> {match.group(1)}"
            )
            continue
        definitions.setdefault(label, target)
    for target in definitions.values():
        validate_markdown_target(document, target)
    for target in inline_destinations(scannable):
        validate_markdown_target(document, target)
    for match in explicit_reference_pattern.finditer(scannable):
        label_text = match.group(2) or match.group(1)
        label = normalized_reference_label(label_text)
        if label not in definitions:
            error(
                f"missing reference definition in {path_label(document)}: "
                f"{label_text}"
            )

for message in errors:
    print(message)
raise SystemExit(1 if errors else 0)
PY
DOCUMENT_STATUS=$?

if [[ -z "$CONTEXT" ]]; then
  echo "WARNING: no context supplied; repository-only validation performed"
fi

if [[ $PROJECTION_STATUS -ne 0 || $ENGINE_VALIDATION_STATUS -ne 0 || $DOCUMENT_STATUS -ne 0 ]]; then
  exit 1
fi

echo "OK: instruction system validation passed"
