"""Create deterministic, non-mutating compatibility projection plans."""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
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


@dataclass(frozen=True)
class _ParentIdentity:
    parent: Path
    resolved_anchor: Path
    device: int
    inode: int
    missing_parts: tuple[str, ...]


def build_projection(root: Path) -> ProjectionPlan:
    try:
        repository = _validated_repository_root(root)
        entries = _discover_projection_entries(repository)
        return _projection_plan(entries)
    except ProjectionFailure:
        raise
    except (OSError, RuntimeError, ValueError, UnicodeError):
        raise ProjectionFailure(
            (Finding("technical_block", None, "projection could not be planned safely"),)
        ) from None


def load_manifest(root: Path) -> ProjectionPlan:
    """Load the tracked ownership manifest only when it is safe and canonical."""
    try:
        return _load_manifest(root)
    except ProjectionFailure:
        raise
    except (OSError, RuntimeError, ValueError, UnicodeError):
        raise ProjectionFailure(
            (Finding("technical_block", MANIFEST_PATH, "manifest could not be loaded safely"),)
        ) from None


def _load_manifest(root: Path) -> ProjectionPlan:
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
    try:
        return _check_projection(root, plan)
    except ProjectionFailure:
        raise
    except (OSError, RuntimeError, ValueError, UnicodeError):
        return (
            Finding("technical_block", None, "projection could not be checked safely"),
        )


def _check_projection(root: Path, plan: ProjectionPlan) -> tuple[Finding, ...]:
    repository = _validated_repository_root(root)
    try:
        previous = load_manifest(repository)
    except ProjectionFailure as failure:
        return _sorted_check_findings(list(failure.findings))

    findings: list[Finding] = []
    if previous != plan:
        findings.append(
            Finding(
                "invalid_manifest",
                MANIFEST_PATH,
                "manifest does not match the desired projection",
            )
        )
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


def write_projection(root: Path, plan: ProjectionPlan) -> None:
    """Safely converge compatibility outputs to an already-built plan."""
    try:
        _write_projection(root, plan)
    except ProjectionFailure:
        raise
    except (OSError, RuntimeError, ValueError, UnicodeError):
        raise ProjectionFailure(
            _sorted_findings(
                [Finding("technical_block", None, "projection could not be applied safely")]
            )
        ) from None


def _write_projection(root: Path, plan: ProjectionPlan) -> None:
    repository = _validated_repository_root(root)
    prior = _load_optional_manifest(repository)
    findings, parent_identities = _preflight_details(repository, prior, plan)
    if findings:
        raise ProjectionFailure(findings)

    staging_root: Path | None = None
    try:
        staging_root = _stage_projection(repository, plan)
        staged_findings = _validate_staged_bundle(repository, staging_root)
        if staged_findings:
            raise ProjectionFailure(staged_findings)

        previous = {} if prior is None else {entry.target: entry for entry in prior.entries}
        desired = {entry.target: entry for entry in plan.entries}
        created_parents: dict[Path, _ParentIdentity] = {}

        for target in sorted(desired, key=lambda item: item.as_posix()):
            entry = desired[target]
            path = repository / target
            payload = (staging_root / target).read_bytes()
            parent_identities[path.parent] = _recheck_parent(
                repository, parent_identities[path.parent], created_parents
            )
            current = _target_state(repository, path)
            accepted = {(entry.output_sha256, entry.executable), None}
            owned = previous.get(target)
            if owned is not None:
                accepted.add((owned.output_sha256, owned.executable))
            if current not in accepted:
                raise ProjectionFailure(
                    (
                        Finding(
                            "conflicting_output",
                            target,
                            "output changed after preflight",
                        ),
                    )
                )
            if current != (entry.output_sha256, entry.executable):
                parent_identities[path.parent] = _recheck_parent(
                    repository, parent_identities[path.parent], created_parents
                )
                _replace_file(path, payload, entry.executable)

        for target in sorted(previous.keys() - desired.keys(), key=lambda item: item.as_posix()):
            owned = previous[target]
            path = repository / target
            parent_identities[path.parent] = _recheck_parent(
                repository, parent_identities[path.parent], created_parents
            )
            current = _target_state(repository, path)
            if current not in (None, (owned.output_sha256, owned.executable)):
                raise ProjectionFailure(
                    (
                        Finding(
                            "conflicting_output",
                            target,
                            "removed output changed after preflight",
                        ),
                    )
                )
            if current is not None:
                parent_identities[path.parent] = _recheck_parent(
                    repository, parent_identities[path.parent], created_parents
                )
                _remove_owned_file(path)

        manifest = repository / MANIFEST_PATH
        parent_identities[manifest.parent] = _recheck_parent(
            repository, parent_identities[manifest.parent], created_parents
        )
        current_manifest = _manifest_state(manifest)
        accepted_manifests = {None, plan.manifest_bytes}
        if prior is not None:
            accepted_manifests.add(prior.manifest_bytes)
        if current_manifest not in accepted_manifests:
            raise ProjectionFailure(
                (
                    Finding(
                        "invalid_manifest",
                        MANIFEST_PATH,
                        "manifest changed after preflight",
                    ),
                )
            )
        _recheck_created_parents(repository, created_parents)
        final_findings = _verify_live_outputs(repository, plan, prior)
        if final_findings:
            raise ProjectionFailure(final_findings)
        current_manifest = _manifest_state(manifest)
        if current_manifest not in accepted_manifests:
            raise ProjectionFailure(
                (
                    Finding(
                        "invalid_manifest",
                        MANIFEST_PATH,
                        "manifest changed during final output verification",
                    ),
                )
            )
        _recheck_created_parents(repository, created_parents)
        if current_manifest != plan.manifest_bytes:
            _replace_file(manifest, plan.manifest_bytes, False)
    except ProjectionFailure:
        raise
    except (OSError, RuntimeError, ValueError, UnicodeError):
        raise ProjectionFailure(
            _sorted_findings(
                [Finding("technical_block", None, "projection could not be applied safely")]
            )
        ) from None
    finally:
        if staging_root is not None:
            shutil.rmtree(staging_root, ignore_errors=True)


def _load_optional_manifest(root: Path) -> ProjectionPlan | None:
    manifest = root / MANIFEST_PATH
    try:
        manifest.lstat()
    except FileNotFoundError:
        return None
    except (OSError, RuntimeError):
        raise _invalid_manifest() from None
    return load_manifest(root)


def _preflight_write(
    root: Path, prior: ProjectionPlan | None, desired: ProjectionPlan
) -> tuple[Finding, ...]:
    findings, _ = _preflight_details(root, prior, desired)
    return findings


def _preflight_details(
    root: Path, prior: ProjectionPlan | None, desired: ProjectionPlan
) -> tuple[tuple[Finding, ...], dict[Path, _ParentIdentity]]:
    findings = list(_validate_desired_plan(desired))
    artifacts = _discover_compatibility_artifacts(root, findings)
    expected = {entry.target: entry for entry in desired.entries}
    previous = {} if prior is None else {entry.target: entry for entry in prior.entries}

    for target in sorted(expected, key=lambda item: item.as_posix()):
        wanted = expected[target]
        owned = previous.get(target)
        artifact = artifacts.pop(target, None)
        if artifact is None or artifact is _UNSAFE_ARTIFACT:
            continue
        if _matches(artifact, wanted) or (owned is not None and _matches(artifact, owned)):
            continue
        findings.append(
            Finding(
                "conflicting_output",
                target,
                "output matches neither desired nor prior ownership",
            )
        )

    for target in sorted(previous.keys() - expected.keys(), key=lambda item: item.as_posix()):
        owned = previous[target]
        artifact = artifacts.pop(target, None)
        if artifact is None or artifact is _UNSAFE_ARTIFACT:
            continue
        if not _matches(artifact, owned):
            findings.append(
                Finding(
                    "conflicting_output",
                    target,
                    "removed output no longer matches prior ownership",
                )
            )

    for target, artifact in artifacts.items():
        if artifact is not _UNSAFE_ARTIFACT:
            findings.append(Finding("unexpected_output", target, "output is not managed"))

    identities: dict[Path, _ParentIdentity] = {}
    parent_paths = {
        (root / target).parent for target in expected.keys() | previous.keys()
    }
    parent_paths.add((root / MANIFEST_PATH).parent)
    for parent in sorted(parent_paths, key=lambda item: item.as_posix()):
        identity, parent_findings = _capture_parent_identity(root, parent)
        findings.extend(parent_findings)
        if identity is not None:
            identities[parent] = identity
    return _sorted_check_findings(findings), identities


def _validate_desired_plan(desired: ProjectionPlan) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    entries = list(desired.entries)
    if (
        desired.format_version != FORMAT_VERSION
        or desired.renderer != RENDERER
        or tuple(entry.source.as_posix() for entry in entries)
        != tuple(sorted(entry.source.as_posix() for entry in entries))
        or _projection_plan(desired.entries).manifest_bytes != desired.manifest_bytes
    ):
        findings.append(Finding("invalid_source", None, "projection plan is not canonical"))
        return _sorted_findings(findings)
    for entry in entries:
        if (
            not _allowed_source(entry.source)
            or _target_for_source(entry.source) != entry.target
            or not _sha256(entry.source_sha256)
            or not _sha256(entry.output_sha256)
            or type(entry.executable) is not bool
        ):
            findings.append(
                Finding("invalid_source", entry.source, "projection entry is invalid")
            )
    _append_collision_findings(entries, findings)
    return _sorted_findings(findings)


def _verify_live_outputs(
    root: Path, desired: ProjectionPlan, prior: ProjectionPlan | None
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    artifacts = _discover_compatibility_artifacts(root, findings)
    expected = {entry.target: entry for entry in desired.entries}
    previous = {} if prior is None else {entry.target: entry for entry in prior.entries}

    for target in sorted(expected, key=lambda item: item.as_posix()):
        wanted = expected[target]
        artifact = artifacts.pop(target, None)
        if artifact is None:
            findings.append(Finding("missing_output", target, "expected output is missing"))
            continue
        if artifact is _UNSAFE_ARTIFACT:
            continue
        if _matches(artifact, wanted):
            continue
        owned = previous.get(target)
        if owned is not None and _matches(artifact, owned) and not _same_output(wanted, owned):
            findings.append(Finding("stale_output", target, "output matches prior ownership"))
        else:
            findings.append(
                Finding("conflicting_output", target, "output matches neither desired nor prior")
            )

    for target, artifact in artifacts.items():
        if artifact is _UNSAFE_ARTIFACT:
            continue
        if target in previous:
            findings.append(
                Finding("extra_managed_output", target, "removed output is still present")
            )
        else:
            findings.append(Finding("unexpected_output", target, "output is not managed"))
    return _sorted_check_findings(findings)


def _stage_projection(root: Path, desired: ProjectionPlan) -> Path:
    staging_root = Path(tempfile.mkdtemp(prefix="sdd-projection-"))
    try:
        for entry in desired.entries:
            payload = _read_source_payload(root, entry)
            target = staging_root / entry.target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            target.chmod(0o755 if entry.executable else 0o644)
        manifest = staging_root / MANIFEST_PATH
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(desired.manifest_bytes)
        manifest.chmod(0o644)
        return staging_root
    except BaseException:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def _read_source_payload(root: Path, entry: ProjectionEntry) -> bytes:
    source = root / entry.source
    _, parent_findings = _capture_parent_identity(root, source.parent)
    if parent_findings:
        raise ProjectionFailure(parent_findings)
    try:
        info = source.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ProjectionFailure(
                (Finding("unsafe_path", entry.source, "source is no longer a regular file"),)
            )
        payload = source.read_bytes()
    except FileNotFoundError:
        raise ProjectionFailure(
            (Finding("invalid_source", entry.source, "source disappeared after planning"),)
        ) from None
    if (
        hashlib.sha256(payload).hexdigest() != entry.source_sha256
        or hashlib.sha256(payload).hexdigest() != entry.output_sha256
        or bool(info.st_mode & 0o111) != entry.executable
    ):
        raise ProjectionFailure(
            (Finding("invalid_source", entry.source, "source changed after planning"),)
        )
    return payload


def _validate_staged_bundle(root: Path, staging_root: Path) -> tuple[Finding, ...]:
    try:
        staged_plan = load_manifest(staging_root)
        findings = list(check_projection(staging_root, staged_plan))
        for entry in staged_plan.entries:
            mode = (staging_root / entry.target).stat().st_mode & 0o777
            expected_mode = 0o755 if entry.executable else 0o644
            if mode != expected_mode:
                findings.append(
                    Finding("invalid_source", entry.target, "staged output mode is invalid")
                )
        if findings:
            return _sorted_check_findings(findings)
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/policy-engine.py"),
                "validate",
                "--root",
                str(staging_root),
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except ProjectionFailure as failure:
        return _sorted_check_findings(list(failure.findings))
    except (OSError, RuntimeError, UnicodeError):
        return (
            Finding("technical_block", None, "staged policy validation could not execute"),
        )

    try:
        result = json.loads(completed.stdout)
    except (TypeError, ValueError, json.JSONDecodeError):
        return (
            Finding("technical_block", None, "staged policy validation returned invalid JSON"),
        )
    if (
        not isinstance(result, dict)
        or type(result.get("valid")) is not bool
        or not isinstance(result.get("errors"), list)
    ):
        return (
            Finding("technical_block", None, "staged policy validation returned invalid JSON"),
        )
    if completed.returncode == 1 and result["valid"] is False and result["errors"]:
        return (
            Finding("invalid_source", None, "staged policy bundle is invalid"),
        )
    if completed.returncode == 0 and result["valid"] is True and result["errors"] == []:
        return ()
    return (
        Finding(
            "technical_block",
            None,
            "staged policy validation returned a contradictory result",
        ),
    )


def _replace_file(path: Path, payload: bytes, executable: bool) -> None:
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            os.fchmod(temporary.fileno(), 0o755 if executable else 0o644)
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def _remove_owned_file(path: Path) -> None:
    path.unlink()


def _capture_parent_identity(
    root: Path, parent: Path
) -> tuple[_ParentIdentity | None, tuple[Finding, ...]]:
    try:
        relative = parent.relative_to(root)
    except ValueError:
        return None, (
            Finding("unsafe_path", None, "target parent escapes repository root"),
        )

    current = root
    missing: list[str] = []
    try:
        info = current.lstat()
        for part in relative.parts:
            if missing:
                missing.append(part)
                continue
            candidate = current / part
            try:
                info = candidate.lstat()
            except FileNotFoundError:
                missing.append(part)
                continue
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                path = PurePosixPath(candidate.relative_to(root).as_posix())
                return None, (
                    Finding("unsafe_path", path, "target parent is not a safe directory"),
                )
            current = candidate
        resolved = current.resolve(strict=True)
        return (
            _ParentIdentity(
                parent=parent,
                resolved_anchor=resolved,
                device=info.st_dev,
                inode=info.st_ino,
                missing_parts=tuple(missing),
            ),
            (),
        )
    except (OSError, RuntimeError):
        path = PurePosixPath(parent.relative_to(root).as_posix())
        return None, (
            Finding("technical_block", path, "target parent cannot be inspected"),
        )


def _recheck_parent(
    root: Path,
    expected: _ParentIdentity,
    created_parents: dict[Path, _ParentIdentity],
) -> _ParentIdentity:
    _recheck_created_parents(root, created_parents)
    current, findings = _capture_parent_identity(root, expected.parent)
    if findings or current is None:
        raise ProjectionFailure(findings)
    if not expected.missing_parts and current != expected:
        path = PurePosixPath(expected.parent.relative_to(root).as_posix())
        raise ProjectionFailure(
            (Finding("unsafe_path", path, "target parent changed after preflight"),)
        )
    if not expected.missing_parts:
        return current

    relative_parts = expected.parent.relative_to(root).parts
    existing_count = len(relative_parts) - len(expected.missing_parts)
    directory = root.joinpath(*relative_parts[:existing_count])
    try:
        anchor = directory.lstat()
        resolved_anchor = directory.resolve(strict=True)
    except (OSError, RuntimeError):
        path = PurePosixPath(directory.relative_to(root).as_posix())
        raise ProjectionFailure(
            (Finding("technical_block", path, "target parent anchor cannot be inspected"),)
        ) from None
    if (
        stat.S_ISLNK(anchor.st_mode)
        or not stat.S_ISDIR(anchor.st_mode)
        or resolved_anchor != expected.resolved_anchor
        or anchor.st_dev != expected.device
        or anchor.st_ino != expected.inode
    ):
        path = PurePosixPath(directory.relative_to(root).as_posix())
        raise ProjectionFailure(
            (Finding("unsafe_path", path, "target parent anchor changed after preflight"),)
        )

    for part in expected.missing_parts:
        candidate = directory / part
        _recheck_created_parents(root, created_parents)
        try:
            candidate.mkdir(mode=0o755)
        except FileExistsError:
            if candidate not in created_parents:
                path = PurePosixPath(candidate.relative_to(root).as_posix())
                raise ProjectionFailure(
                    (Finding("unsafe_path", path, "target parent changed during creation"),)
                )
            _recheck_created_parents(root, created_parents)
        else:
            created, created_findings = _capture_parent_identity(root, candidate)
            if created_findings or created is None:
                raise ProjectionFailure(created_findings)
            if created.missing_parts:
                path = PurePosixPath(candidate.relative_to(root).as_posix())
                raise ProjectionFailure(
                    (Finding("technical_block", path, "target parent could not be created"),)
                )
            created_parents[candidate] = created
        directory = candidate

    _recheck_created_parents(root, created_parents)
    created, created_findings = _capture_parent_identity(root, expected.parent)
    if created_findings or created is None:
        raise ProjectionFailure(created_findings)
    if created.missing_parts:
        path = PurePosixPath(expected.parent.relative_to(root).as_posix())
        raise ProjectionFailure(
            (Finding("technical_block", path, "target parent could not be created"),)
        )
    return created


def _recheck_created_parents(
    root: Path, created_parents: dict[Path, _ParentIdentity]
) -> None:
    for path in sorted(created_parents, key=lambda item: item.as_posix()):
        expected = created_parents[path]
        current, findings = _capture_parent_identity(root, path)
        if findings:
            raise ProjectionFailure(findings)
        if current is None or current.missing_parts or current != expected:
            target = PurePosixPath(path.relative_to(root).as_posix())
            raise ProjectionFailure(
                (Finding("unsafe_path", target, "created target parent changed during write"),)
            )


def _target_state(root: Path, path: Path) -> tuple[str, bool] | None:
    target = PurePosixPath(path.relative_to(root).as_posix())
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ProjectionFailure(
            (Finding("unsafe_path", target, "target is no longer a regular file"),)
        )
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, RuntimeError):
        raise ProjectionFailure(
            (Finding("technical_block", target, "target cannot be read safely"),)
        ) from None
    return digest, bool(info.st_mode & 0o111)


def _manifest_state(path: Path) -> bytes | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise _invalid_manifest()
    try:
        return path.read_bytes()
    except (OSError, RuntimeError):
        raise ProjectionFailure(
            (Finding("technical_block", MANIFEST_PATH, "manifest cannot be read safely"),)
        ) from None


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
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise _invalid_manifest()
    try:
        os.fsencode(value)
    except (ValueError, UnicodeError):
        raise _invalid_manifest() from None
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
    seen_paths: dict[str, PurePosixPath] = {}
    output_root = repository / ".claude"

    def relative(path: Path) -> PurePosixPath:
        return PurePosixPath(path.relative_to(repository).as_posix())

    def collides(target: PurePosixPath) -> bool:
        folded = target.as_posix().casefold()
        previous = seen_paths.get(folded)
        if previous is None:
            seen_paths[folded] = target
            return False
        findings.append(
            Finding(
                "unsafe_path",
                target,
                f"output path collides with {previous.as_posix()}",
            )
        )
        return True

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
            case_collision = collides(target)
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
                if case_collision:
                    artifacts[target] = _UNSAFE_ARTIFACT
                else:
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
