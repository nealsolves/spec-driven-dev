#!/usr/bin/env python3
"""Render or verify the transitional compatibility projection."""

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


def render_findings(findings) -> None:
    for finding in findings:
        path = "-" if finding.path is None else finding.path.as_posix()
        print(f"ERROR: {finding.code}: {path}: {finding.message}")


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        from sdd.adapters.compatibility import (
            ProjectionFailure,
            build_projection,
            check_projection,
            write_projection,
        )
    except Exception as exc:
        print(f"ERROR: technical_block: {exc}")
        return 3

    try:
        root = arguments.root.resolve(strict=True)
        plan = build_projection(root)
        if arguments.check:
            findings = check_projection(root, plan)
            if findings:
                render_findings(findings)
                return 3 if any(item.code == "technical_block" for item in findings) else 1
            print("OK: compatibility projection is current")
            return 0
        write_projection(root, plan)
        print("OK: compatibility projection updated")
        return 0
    except ProjectionFailure as exc:
        render_findings(exc.findings)
        return 3 if any(item.code == "technical_block" for item in exc.findings) else 1
    except (OSError, RuntimeError, ValueError, UnicodeError) as exc:
        print(f"ERROR: technical_block: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
