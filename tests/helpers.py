import importlib.util
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_engine():
    spec = importlib.util.spec_from_file_location(
        "policy_engine", ROOT / "scripts/policy-engine.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@contextmanager
def temporary_repository():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        shutil.copytree(ROOT / ".claude", root / ".claude")
        yield root
