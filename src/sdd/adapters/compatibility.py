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


def load_manifest(root: Path) -> ProjectionPlan:
    """Load the tracked ownership manifest only when it is safe and canonical."""
    repository = _validated_repository_root(root)
    manifest = repository / MANIFEST_PATH
    _require_manifest_file(repository, manifest)
    try:
        raw = manifest.read_bytes()
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (OSError, RuntimeError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise _invalid_manifest() from None

    if not isinstance(payload, dict) or set(payload) != {
        "format_version",
        "renderer",
        "files",
    }:
        raise _invalid_manifest()
    if type(payload["format_version"]) is not int or payload["format_version"] != FORMAT_VERSION:
        raise _invalid_manifest()
    if payload["renderer"] != RENDERER or not isinstance(payload["files"], list):
        raise _invalid_manifest()

    entries = tuple(_manifest_entry(value) for value in payload["files"])
    if tuple(entry.source.as_posix() for entry in entries) != tuple(
        sorted(entry.source.as_posix() for entry in entries)
    ):
        raise _invalid_manifest()
    collisions: list[Finding] = []
    _append_collision_findings(list(entries), collisions)
    if collisions:
        raise _invalid_manifest()

    plan = _projection_plan(entries)
    if raw != plan.manifest_bytes:
        raise _invalid_manifest()
    return plan


def check_projection(root: Path, plan: ProjectionPlan) -> tuple[Finding, ...]:
    """Return output-state differences without modifying the repository."""
    repository = _validated_repository_root(root)
    try:
        previous = load_manifest(repository)
    except ProjectionFailure as failure:
        return _sorted_check_findings(list(failure.findings))

    findings: list[Finding] = []
    artifacts = _discover_compatibility_artifacts(repository, findings)
    expected = {entry.target: entry for entry in plan.entries}
    prior = {entry.target: entry for entry in previous.entries}

    for target in sorted(expected, key=lambda item: item.as_posix()):
        desired = expected[target]
        owned = prior.get(target)
        artifact = artifacts.pop(target, None)
        if artifact is None:
            findings.append(Finding("missing_output", target, "expected output is missing"))
            continue
        if artifact is _UNSAFE_ARTIFACT:
            continue
        if owned is None:
            findings.append(
                Finding(
                    "invalid_manifest",
                    target,
                    "expected output has no prior ownership record",
                )
            )
            continue
        if _matches(artifact, desired):
            continue
        if _matches(artifact, owned) and not _same_output(desired, owned):
            findings.append(Finding("stale_output", target, "output matches prior ownership"))
        else:
            findings.append(
                Finding("conflicting_output", target, "output matches neither desired nor prior")
            )

    for target in sorted(prior.keys() - expected.keys(), key=lambda item: item.as_posix()):
        artifacts.pop(target, None)
        findings.append(
            Finding("extra_managed_output", target, "output belongs to a removed source")
        )

    for target, artifact in artifacts.items():
        if artifact is not _UNSAFE_ARTIFACT:
            findings.append(Finding("unexpected_output", target, "output is not managed"))
    return _sorted_check_findings(findings)


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


_UNSAFE_ARTIFACT = object()


def _invalid_manifest() -> ProjectionFailure:
    return ProjectionFailure(
        (Finding("invalid_manifest", MANIFEST_PATH, "manifest is missing, unsafe, or invalid"),)
    )


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _require_manifest_file(repository: Path, manifest: Path) -> None:
    canonical = repository / ".sdd"
    try:
        canonical_mode = canonical.lstat().st_mode
        manifest_mode = manifest.lstat().st_mode
    except (OSError, RuntimeError):
        raise _invalid_manifest() from None
    if (
        stat.S_ISLNK(canonical_mode)
        or not stat.S_ISDIR(canonical_mode)
        or stat.S_ISLNK(manifest_mode)
        or not stat.S_ISREG(manifest_mode)
    ):
        raise _invalid_manifest()


def _manifest_entry(value) -> ProjectionEntry:
    required = {
        "source",
        "target",
        "source_sha256",
        "output_sha256",
        "executable",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise _invalid_manifest()
    if type(value["executable"]) is not bool:
        raise _invalid_manifest()
    source = _manifest_path(value["source"])
    target = _manifest_path(value["target"])
    if (
        not _allowed_source(source)
        or _target_for_source(source) != target
        or not _sha256(value["source_sha256"])
        or not _sha256(value["output_sha256"])
    ):
        raise _invalid_manifest()
    return ProjectionEntry(
        source=source,
        target=target,
        source_sha256=value["source_sha256"],
        output_sha256=value["output_sha256"],
        executable=value["executable"],
    )


def _manifest_path(value) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise _invalid_manifest()
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(
        part in ("", ".", "..") for part in path.parts
    ):
        raise _invalid_manifest()
    return path


def _allowed_source(source: PurePosixPath) -> bool:
    parts = source.parts
    if source == PurePosixPath(".sdd/README.md"):
        return True
    if len(parts) == 3 and parts[:2] == (".sdd", "controls"):
        return parts[2] in CONTROL_NAMES
    if len(parts) >= 3 and parts[:2] == (".sdd", "schemas"):
        return parts[-1].endswith(".json") and len(parts[-1]) > len(".json")
    return (
        len(parts) == 4
        and parts[:2] == (".sdd", "modules")
        and parts[2] in MODULE_NAMESPACES
        and parts[3].endswith(".md")
        and len(parts[3]) > len(".md")
    )


def _target_for_source(source: PurePosixPath) -> PurePosixPath:
    parts = source.parts
    if source == PurePosixPath(".sdd/README.md"):
        return PurePosixPath(".claude/README.md")
    if parts[:2] == (".sdd", "controls"):
        return PurePosixPath(".claude") / parts[2]
    if parts[:2] == (".sdd", "schemas"):
        return PurePosixPath(".claude/schemas").joinpath(*parts[2:])
    return PurePosixPath(".claude") / parts[2] / parts[3]


def _sha256(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _discover_compatibility_artifacts(
    repository: Path, findings: list[Finding]
) -> dict[PurePosixPath, tuple[str, bool] | object]:
    artifacts: dict[PurePosixPath, tuple[str, bool] | object] = {}
    output_root = repository / ".claude"

    def relative(path: Path) -> PurePosixPath:
        return PurePosixPath(path.relative_to(repository).as_posix())

    def walk(directory: Path) -> None:
        try:
            children = sorted(directory.iterdir(), key=lambda path: path.name)
        except (OSError, RuntimeError):
            findings.append(
                Finding("technical_block", relative(directory), "directory cannot be inspected")
            )
            return
        for child in children:
            target = relative(child)
            try:
                info = child.lstat()
            except (OSError, RuntimeError):
                findings.append(Finding("technical_block", target, "path cannot be inspected"))
                artifacts[target] = _UNSAFE_ARTIFACT
                continue
            if stat.S_ISLNK(info.st_mode):
                findings.append(Finding("unsafe_path", target, "symlinks are not allowed"))
                artifacts[target] = _UNSAFE_ARTIFACT
            elif stat.S_ISDIR(info.st_mode):
                walk(child)
            elif stat.S_ISREG(info.st_mode):
                try:
                    artifacts[target] = (
                        hashlib.sha256(child.read_bytes()).hexdigest(),
                        bool(info.st_mode & 0o111),
                    )
                except (OSError, RuntimeError):
                    findings.append(Finding("technical_block", target, "file cannot be read"))
                    artifacts[target] = _UNSAFE_ARTIFACT
            else:
                findings.append(Finding("unsafe_path", target, "unsupported file type"))
                artifacts[target] = _UNSAFE_ARTIFACT

    try:
        info = output_root.lstat()
    except FileNotFoundError:
        return artifacts
    except (OSError, RuntimeError):
        findings.append(Finding("technical_block", PurePosixPath(".claude"), "path cannot be inspected"))
        return artifacts
    if stat.S_ISLNK(info.st_mode):
        findings.append(Finding("unsafe_path", PurePosixPath(".claude"), "symlinks are not allowed"))
    elif not stat.S_ISDIR(info.st_mode):
        findings.append(Finding("unsafe_path", PurePosixPath(".claude"), "expected a directory"))
    else:
        walk(output_root)
    return artifacts


def _matches(output: tuple[str, bool], entry: ProjectionEntry) -> bool:
    return output == (entry.output_sha256, entry.executable)


def _same_output(first: ProjectionEntry, second: ProjectionEntry) -> bool:
    return (
        first.output_sha256 == second.output_sha256
        and first.executable == second.executable
    )


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


def _sorted_check_findings(findings: list[Finding]) -> tuple[Finding, ...]:
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                "" if finding.path is None else finding.path.as_posix(),
                finding.code,
                finding.message,
            ),
        )
    )
