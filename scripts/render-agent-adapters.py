#!/usr/bin/env python3
"""Render or verify the generated root agent adapters."""

import argparse
import sys
from pathlib import Path


sys.dont_write_bytecode = True
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser.parse_args(argv)


def render_finding(code, path, message) -> None:
    rendered_path = "-" if path is None else path.as_posix()
    print(f"ERROR: {code}: {rendered_path}: {message}")


def render_findings(findings) -> None:
    for finding in findings:
        render_finding(finding.code, finding.path, finding.message)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        from sdd.adapters.agent import (
            AdapterFailure,
            build_adapter_plan,
            check_agent_adapters,
            write_agent_adapters,
        )
    except Exception as exc:
        render_finding("technical_block", None, exc)
        return 3

    try:
        root = arguments.root.resolve(strict=True)
        plan = build_adapter_plan(root)
        if arguments.check:
            findings = check_agent_adapters(root, plan)
            if findings:
                render_findings(findings)
                return 3 if any(item.code == "technical_block" for item in findings) else 1
            print("OK: root agent adapters are current")
            return 0
        write_agent_adapters(root, plan)
        print("OK: root agent adapters updated")
        return 0
    except AdapterFailure as exc:
        render_findings(exc.findings)
        return 3 if any(item.code == "technical_block" for item in exc.findings) else 1
    except (OSError, RuntimeError, ValueError, UnicodeError) as exc:
        render_finding("technical_block", None, exc)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
