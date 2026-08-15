"""Create deterministic, non-mutating compatibility projection plans."""

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


FORMAT_VERSION = 1
RENDERER = "sdd.adapters.compatibility:v1"
MANIFEST_PATH = PurePosixPath(".sdd/generated-files.json")
CONTROL_NAMES = ("project.yaml", "routing.yaml", "policy.yaml", "lifecycle.yaml")
MODULE_NAMESPACES = ("rules", "workflows", "profiles", "templates")


@dataclass(frozen=True)
class Finding:
    code: str
    path: PurePosixPath | None
    message: str


@dataclass(frozen=True)
class ProjectionEntry:
    source: PurePosixPath
    target: PurePosixPath
    source_sha256: str
    output_sha256: str
    executable: bool


@dataclass(frozen=True)
class ProjectionPlan:
    format_version: int
    renderer: str
    entries: tuple[ProjectionEntry, ...]
    manifest_bytes: bytes


class ProjectionFailure(Exception):
    def __init__(self, findings: tuple[Finding, ...]):
        super().__init__("compatibility projection failed")
        self.findings = findings


def build_projection(root: Path) -> ProjectionPlan:
    repository = _validated_repository_root(root)
    entries = _discover_projection_entries(repository)
    return _projection_plan(entries)


def _validated_repository_root(root: Path) -> Path:
    repository = Path(root)
    try:
        mode = repository.lstat().st_mode
    except (OSError, RuntimeError):
        raise ProjectionFailure(
            (Finding("technical_block", None, "repository root cannot be inspected"),)
        ) from None

    if not repository.is_absolute() or stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ProjectionFailure(
            (Finding("technical_block", None, "repository root must be an absolute directory"),)
        )
    return repository


def _discover_projection_entries(repository: Path) -> tuple[ProjectionEntry, ...]:
    findings: list[Finding] = []
    entries: list[ProjectionEntry] = []
    canonical = repository / ".sdd"

    def relative(path: Path) -> PurePosixPath:
        return PurePosixPath(path.relative_to(repository).as_posix())

    def inspect(path: Path, *, directory: bool) -> os.stat_result | None:
        try:
            info = path.lstat()
        except (OSError, RuntimeError):
            findings.append(
                Finding("technical_block", relative(path), "path cannot be inspected")
            )
            return None
        if stat.S_ISLNK(info.st_mode):
            findings.append(Finding("unsafe_path", relative(path), "symlinks are not allowed"))
            return None
        if directory:
            if not stat.S_ISDIR(info.st_mode):
                findings.append(
                    Finding("unsafe_path", relative(path), "expected a directory")
                )
                return None
        elif not stat.S_ISREG(info.st_mode):
            findings.append(
                Finding("unsafe_path", relative(path), "expected a regular file")
            )
            return None
        return info

    def children(path: Path) -> list[Path]:
        try:
            return sorted(path.iterdir(), key=lambda item: item.name)
        except (OSError, RuntimeError):
            findings.append(
                Finding("technical_block", relative(path), "directory cannot be inspected")
            )
            return []

    def invalid(
        path: Path,
        message: str = "path is not an allowed canonical source",
        *,
        exists: bool = True,
    ) -> None:
        if exists:
            try:
                mode = path.lstat().st_mode
            except (OSError, RuntimeError):
                findings.append(
                    Finding("technical_block", relative(path), "path cannot be inspected")
                )
                return
            if stat.S_ISLNK(mode):
                findings.append(
                    Finding("unsafe_path", relative(path), "symlinks are not allowed")
                )
                return
            if not stat.S_ISREG(mode) and not stat.S_ISDIR(mode):
                findings.append(
                    Finding("unsafe_path", relative(path), "unsupported file type")
                )
                return
        findings.append(Finding("invalid_source", relative(path), message))

    def add_entry(path: Path, target: PurePosixPath) -> None:
        info = inspect(path, directory=False)
        if info is None:
            return
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, RuntimeError):
            findings.append(
                Finding("technical_block", relative(path), "file cannot be read")
            )
            return
        entries.append(
            ProjectionEntry(
                source=relative(path),
                target=target,
                source_sha256=digest,
                output_sha256=digest,
                executable=bool(info.st_mode & 0o111),
            )
        )

    if inspect(canonical, directory=True) is None:
        raise ProjectionFailure(_sorted_findings(findings))

    root_children = {child.name: child for child in children(canonical)}
    allowed_root_names = {
        "README.md",
        "controls",
        "schemas",
        "modules",
        "generated-files.json",
        "migrations",
        "state",
    }
    for name, child in root_children.items():
        if name not in allowed_root_names:
            invalid(child)

    readme = root_children.get("README.md")
    if readme is None:
        invalid(
            canonical / "README.md", "required canonical source is missing", exists=False
        )
    else:
        add_entry(readme, PurePosixPath(".claude/README.md"))

    controls = root_children.get("controls")
    if controls is None:
        invalid(
            canonical / "controls", "required canonical directory is missing", exists=False
        )
    elif inspect(controls, directory=True) is not None:
        control_children = {child.name: child for child in children(controls)}
        for name, child in control_children.items():
            if name not in CONTROL_NAMES:
                invalid(child)
        for name in CONTROL_NAMES:
            source = control_children.get(name)
            if source is None:
                invalid(
                    controls / name,
                    "required canonical source is missing",
                    exists=False,
                )
            else:
                add_entry(source, PurePosixPath(".claude") / name)

    schemas = root_children.get("schemas")
    if schemas is None:
        invalid(
            canonical / "schemas", "required canonical directory is missing", exists=False
        )
    elif inspect(schemas, directory=True) is not None:
        _discover_schema_entries(schemas, canonical, inspect, children, invalid, add_entry)

    modules = root_children.get("modules")
    if modules is None:
        invalid(
            canonical / "modules", "required canonical directory is missing", exists=False
        )
    elif inspect(modules, directory=True) is not None:
        module_children = {child.name: child for child in children(modules)}
        for name, child in module_children.items():
            if name not in MODULE_NAMESPACES:
                invalid(child)
        for namespace in MODULE_NAMESPACES:
            module_directory = module_children.get(namespace)
            if module_directory is None:
                invalid(
                    modules / namespace,
                    "required canonical directory is missing",
                    exists=False,
                )
                continue
            if inspect(module_directory, directory=True) is None:
                continue
            for child in children(module_directory):
                if child.suffix != ".md":
                    invalid(child)
                    continue
                info = inspect(child, directory=False)
                if info is None:
                    continue
                add_entry(child, PurePosixPath(".claude") / namespace / child.name)

    for ignored_name in ("generated-files.json", "migrations", "state"):
        ignored = root_children.get(ignored_name)
        if ignored is not None:
            inspect(ignored, directory=ignored_name != "generated-files.json")

    _append_collision_findings(entries, findings)
    if findings:
        raise ProjectionFailure(_sorted_findings(findings))
    return tuple(sorted(entries, key=lambda entry: entry.source.as_posix()))


def _projection_plan(entries: tuple[ProjectionEntry, ...]) -> ProjectionPlan:
    payload = {
        "format_version": FORMAT_VERSION,
        "renderer": RENDERER,
        "files": [
            {
                "source": entry.source.as_posix(),
                "target": entry.target.as_posix(),
                "source_sha256": entry.source_sha256,
                "output_sha256": entry.output_sha256,
                "executable": entry.executable,
            }
            for entry in entries
        ],
    }
    manifest_bytes = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    return ProjectionPlan(FORMAT_VERSION, RENDERER, entries, manifest_bytes)


def _discover_schema_entries(
    directory: Path,
    canonical: Path,
    inspect,
    children,
    invalid,
    add_entry,
) -> None:
    for child in children(directory):
        try:
            mode = child.lstat().st_mode
        except (OSError, RuntimeError):
            inspect(child, directory=False)
            continue
        if stat.S_ISDIR(mode):
            if inspect(child, directory=True) is not None:
                _discover_schema_entries(child, canonical, inspect, children, invalid, add_entry)
        elif child.suffix == ".json":
            add_entry(
                child,
                PurePosixPath(".claude/schemas")
                / child.relative_to(canonical / "schemas").as_posix(),
            )
        else:
            invalid(child)


def _append_collision_findings(
    entries: list[ProjectionEntry], findings: list[Finding]
) -> None:
    for attribute in ("source", "target"):
        seen: dict[str, PurePosixPath] = {}
        for entry in entries:
            path = getattr(entry, attribute)
            folded = path.as_posix().casefold()
            previous = seen.get(folded)
            if previous is not None:
                findings.append(
                    Finding(
                        "unsafe_path",
                        path,
                        f"{attribute} path collides with {previous.as_posix()}",
                    )
                )
            else:
                seen[folded] = path


def _sorted_findings(findings: list[Finding]) -> tuple[Finding, ...]:
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.code,
                "" if finding.path is None else finding.path.as_posix(),
                finding.message,
            ),
        )
    )
