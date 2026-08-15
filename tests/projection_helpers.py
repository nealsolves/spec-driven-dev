import hashlib
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from tests.helpers import ROOT


CONTROL_NAMES = ("project.yaml", "routing.yaml", "policy.yaml", "lifecycle.yaml")
MODULE_NAMESPACES = ("rules", "workflows", "profiles", "templates")


def copy_legacy_as_canonical(destination: Path) -> None:
    canonical = destination / ".sdd"
    (canonical / "controls").mkdir(parents=True)
    shutil.copy2(ROOT / ".claude/README.md", canonical / "README.md")
    for name in CONTROL_NAMES:
        shutil.copy2(ROOT / ".claude" / name, canonical / "controls" / name)
    shutil.copytree(ROOT / ".claude/schemas", canonical / "schemas")
    for namespace in MODULE_NAMESPACES:
        shutil.copytree(
            ROOT / ".claude" / namespace,
            canonical / "modules" / namespace,
        )


@contextmanager
def projection_repository(*, include_outputs: bool = True):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "repository"
        root.mkdir()
        copy_legacy_as_canonical(root)
        if include_outputs:
            shutil.copytree(ROOT / ".claude", root / ".claude")
        (root / "scripts").mkdir()
        for script in ("policy-engine.py", "render-compatibility.py"):
            shutil.copy2(ROOT / "scripts" / script, root / "scripts" / script)
        yield root


def tree_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        path.relative_to(root).as_posix(): (
            path.read_bytes(),
            path.stat().st_mode & 0o111,
        )
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
