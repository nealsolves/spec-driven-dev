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
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
  technical_block
fi
if ! "$PYTHON" -c 'import yaml, jsonschema' >/dev/null 2>&1; then
  technical_block
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


def error(message):
    errors.append(f"ERROR: {message}")


def stays_inside_repository(path):
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True


def inventory(directory, expected_names):
    expected = set(expected_names)
    if directory.is_symlink() and not stays_inside_repository(directory):
        error(f"artifact directory symlink escapes repository: {directory.relative_to(root)}")
        for name in sorted(expected):
            error(f"missing artifact: {(directory / name).relative_to(root)}")
        return
    if not directory.is_dir():
        for name in sorted(expected):
            error(f"missing artifact: {(directory / name).relative_to(root)}")
        return
    actual = set()
    for path in directory.iterdir():
        if path.name == ".DS_Store" or not (path.is_file() or path.is_symlink()):
            continue
        actual.add(path.name)
        if path.is_symlink() and not stays_inside_repository(path):
            error(f"artifact symlink escapes repository: {path.relative_to(root)}")
    for name in sorted(expected - actual):
        error(f"missing artifact: {(directory / name).relative_to(root)}")
    for name in sorted(actual - expected):
        error(f"unexpected artifact: {(directory / name).relative_to(root)}")


required_root_files = (
    "CLAUDE.md",
    "implementation_status.md",
    "requirements-policy.txt",
    ".specify/memory/constitution.md",
    ".claude/README.md",
)
for relative in required_root_files:
    path = root / relative
    if path.is_symlink() and not stays_inside_repository(path):
        error(f"artifact symlink escapes repository: {relative}")
    elif not path.is_file():
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
        "validate-instructions.sh",
        "validate-feature-context.sh",
    },
)

for relative in (
    "scripts/policy-engine.py",
    "scripts/validate-instructions.sh",
    "scripts/validate-feature-context.sh",
):
    path = root / relative
    if path.is_file() and not os.access(path, os.X_OK):
        error(f"script is not executable: {relative}")

claude_path = root / "CLAUDE.md"
if claude_path.is_file():
    claude_bytes = claude_path.read_bytes()
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
    if not path.is_file():
        continue
    if path.is_symlink() and not stays_inside_repository(path):
        continue
    content = path.read_text(encoding="utf-8")
    normalized_content = " ".join(content.split())
    for phrase in phrases:
        if phrase not in normalized_content:
            error(f"{relative} is missing required wording: {phrase}")

markdown_files = []
for relative in ("CLAUDE.md", "implementation_status.md", ".specify/memory/constitution.md"):
    path = root / relative
    if path.is_file() and stays_inside_repository(path):
        markdown_files.append(path)
claude_root = root / ".claude"
if claude_root.is_dir():
    markdown_files.extend(
        path
        for path in claude_root.rglob("*.md")
        if path.is_file() and stays_inside_repository(path)
    )

link_pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
for document in sorted(set(markdown_files)):
    try:
        content = document.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        error(f"cannot read Markdown file {document.relative_to(root)}: {exc}")
        continue
    for match in link_pattern.finditer(content):
        raw_target = match.group(1).strip()
        if raw_target.startswith("<") and ">" in raw_target:
            target = raw_target[1 : raw_target.index(">")]
        else:
            target = raw_target.split(maxsplit=1)[0] if raw_target else ""
        if not target or target.startswith("#"):
            continue
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        link_path = unquote(parsed.path)
        if not link_path:
            continue
        if Path(link_path).is_absolute():
            error(
                f"local Markdown link must stay inside repository: "
                f"{document.relative_to(root)} -> {target}"
            )
            continue
        resolved = (document.parent / link_path).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            error(
                f"local Markdown link escapes repository: "
                f"{document.relative_to(root)} -> {target}"
            )
            continue
        if not resolved.exists():
            error(
                f"broken local Markdown link: "
                f"{document.relative_to(root)} -> {target}"
            )

for message in errors:
    print(message)
raise SystemExit(1 if errors else 0)
PY
DOCUMENT_STATUS=$?

if [[ -z "$CONTEXT" ]]; then
  echo "WARNING: no context supplied; repository-only validation performed"
fi

if [[ $ENGINE_VALIDATION_STATUS -ne 0 || $DOCUMENT_STATUS -ne 0 ]]; then
  exit 1
fi

echo "OK: instruction system validation passed"
