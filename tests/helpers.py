import importlib.util
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


VALIDATOR_REPOSITORY_ARTIFACTS = (
    ".sdd",
    ".claude",
    ".specify",
    "scripts",
    "src",
    "CLAUDE.md",
    "AGENTS.md",
    "implementation_status.md",
    "requirements-policy.txt",
)


def load_engine():
    spec = importlib.util.spec_from_file_location(
        "policy_engine", ROOT / "scripts/policy-engine.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def copy_validator_repository(destination: Path) -> None:
    """Copy the complete instruction system used by validator integration tests."""
    for name in VALIDATOR_REPOSITORY_ARTIFACTS:
        source = ROOT / name
        target = destination / name
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            shutil.copy2(source, target)


@contextmanager
def temporary_repository():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        shutil.copytree(ROOT / ".sdd", root / ".sdd")
        shutil.copytree(ROOT / ".claude", root / ".claude")
        yield root
