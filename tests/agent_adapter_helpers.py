import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path


CONFIG = """format: 1
kernel: .sdd/adapters/root-kernel.md
limits:
  max_lines: 280
  target_lines: 180
  max_bytes: 16384
outputs:
  claude: CLAUDE.md
  codex: AGENTS.md
"""


@contextmanager
def agent_adapter_repository(*, include_outputs: bool = False):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "repository"
        (root / ".sdd/controls").mkdir(parents=True)
        (root / ".sdd/adapters").mkdir()
        (root / ".sdd/controls/adapters.yaml").write_text(CONFIG, encoding="utf-8")
        (root / ".sdd/adapters/root-kernel.md").write_text(
            "## Purpose and Scope\n\nCanonical policy lives in `.sdd/`.\n",
            encoding="utf-8",
        )
        if include_outputs:
            (root / "AGENTS.md").write_text("existing Codex output\n", encoding="utf-8")
            (root / "CLAUDE.md").write_text("existing Claude output\n", encoding="utf-8")
        yield root


def tree_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    snapshot: dict[str, tuple[bytes, int]] = {}
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            snapshot[path.relative_to(root).as_posix()] = (
                path.read_bytes(),
                mode & 0o111,
            )
    return snapshot
