"""Pinned, byte-preserving upstream snapshots; never execute imported code.

Maintainer commands operate on candidates and the kit only. They do not rewrite
consumer MCP settings or activate new servers. Local adaptations live outside
the snapshot, so upstream updates cannot silently overwrite them.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import signal
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .core import KitError, resource_root


UPSTREAM_URL = "https://github.com/siliconpeasant/vibe_soc.git"
IMPORT_PATHS = (
    ".agents/agents", ".agents/rules", ".agents/scripts", ".agents/skills",
    ".agents/mcp-servers.json", ".agents/mcp-requirements.txt",
    ".agents/loop_policy.json", "scripts",
)
MAX_FILES = 10000
MAX_BYTES = 100 * 1024 * 1024


def bundled_snapshot() -> Path:
    return resource_root() / "upstream" / "vibe_soc"


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _run_git_process(command: list[str], *, input: bytes | None = None, timeout: float = 180):
    options: dict[str, Any] = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
    }
    process = subprocess.Popen(command, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1"},
                               **options)
    try:
        stdout, stderr = process.communicate(input, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # Kill the owned tree BEFORE killing the Git launcher. Otherwise helpers
        # can outlive it and keep stdout/stderr pipes open indefinitely on Windows.
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            raise KitError("Git timed out; helper cleanup could not be confirmed") from exc
        raise KitError("Upstream Git operation timed out; owned process tree stopped") from exc
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _git(repo: Path, *args: str) -> str:
    try:
        result = _run_git_process(["git", "-C", str(repo), *args])
    except subprocess.TimeoutExpired as exc:
        raise KitError("Upstream Git operation timed out") from exc
    if result.returncode:
        # Do not echo a remote's potentially credential-bearing error output.
        raise KitError(f"Git {args[0]} failed (exit {result.returncode})")
    return result.stdout.decode("utf-8")


def _safe_relative(name: str) -> PurePosixPath:
    if not isinstance(name, str):
        raise KitError("Snapshot paths must be strings")
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name
            or ":" in name or path.as_posix() != name
            or any(ord(c) < 32 for c in name)):
        raise KitError(f"Unsafe snapshot path: {name!r}")
    # Keep snapshots portable, including Windows case-insensitive filesystems.
    for part in path.parts:
        if (part.endswith((".", " ")) or part.upper().split(".")[0] in
                {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)], *[f"LPT{i}" for i in range(10)]}):
            raise KitError(f"Non-portable snapshot path: {name!r}")
    return path


def _allowed(name: str) -> bool:
    if any(name == item or name.startswith(item + "/") for item in IMPORT_PATHS):
        return True
    # Preserve upstream notices if they are added in a later release.
    return "/" not in name and bool(re.fullmatch(r"(?:LICENSE|COPYING|NOTICE)(?:[.\-_][A-Za-z0-9.\-_]+)?", name, re.I))


def _is_link(path: Path) -> bool:
    try:
        attrs = path.lstat()
    except FileNotFoundError:
        return False
    # Path.is_junction is absent on Python 3.11, still a supported runtime.
    return stat.S_ISLNK(attrs.st_mode) or bool(getattr(attrs, "st_file_attributes", 0) & 0x400)


def _real_directory(path: Path) -> None:
    for item in (path, *path.parents):
        if _is_link(item):
            raise KitError(f"Snapshot path traverses a link: {path}")
        if item.exists() and not item.is_dir():
            raise KitError(f"Snapshot parent is not a directory: {item}")


def _stable_ast(value: Any) -> str:
    """Version-independent compact AST representation for static contracts.

ast.dump changed its empty-field defaults across supported Python releases.
Keep those presentation changes out of the pinned capability inventory.
"""
    if isinstance(value, ast.AST):
        fields = []
        for name, item in ast.iter_fields(value):
            if item == [] or (item is None and not (isinstance(value, ast.Constant) and name == "value")):
                continue
            fields.append(f"{name}={_stable_ast(item)}")
        return f"{type(value).__name__}({', '.join(fields)})"
    if isinstance(value, list):
        return "[" + ", ".join(_stable_ast(item) for item in value) + "]"
    return repr(value)


def _tool_contracts(script: Path) -> list[dict[str, str]]:
    try:
        tree = ast.parse(script.read_bytes(), filename=script.name)
    except (SyntaxError, ValueError) as exc:
        raise KitError(f"Cannot statically parse MCP script: {script.name}") from exc
    result = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            func = call.func if call else decorator
            if not isinstance(func, ast.Attribute) or func.attr != "tool":
                continue
            name = node.name
            if call:
                for kw in call.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        name = kw.value.value
            result.append({"name": name, "arguments": _stable_ast(node.args),
                           "returns": _stable_ast(node.returns) if node.returns else ""})
    return sorted(result, key=lambda item: item["name"])


def _capabilities(source: Path) -> dict[str, Any]:
    path = source / ".agents/mcp-servers.json"
    if not path.is_file():
        raise KitError("Snapshot has no .agents/mcp-servers.json")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise KitError("Invalid upstream MCP manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or not isinstance(manifest.get("servers"), list):
        raise KitError("Unsupported upstream MCP manifest schema")
    servers = {}
    for server in manifest["servers"]:
        if not isinstance(server, dict) or not isinstance(server.get("name"), str):
            raise KitError("Invalid upstream server entry")
        name = server["name"]
        if name in servers:
            raise KitError(f"Duplicate upstream server: {name}")
        entry: dict[str, Any] = {"definition": server, "tools": [], "validation": "not_run"}
        if "script" in server:
            relative = _safe_relative(server["script"])
            script = source.joinpath(*relative.parts)
            if not script.is_file():
                entry["inventory"] = "missing_script"
                entry["validation"] = "unavailable"
            else:
                entry["tools"] = _tool_contracts(script)
                entry["inventory"] = "static_python_decorators_not_runtime_schema"
        else:
            entry["inventory"] = "external_or_non_python_requires_runtime_probe"
        servers[name] = entry
    return {
        "servers": servers,
        "skills": sorted(p.parent.name for p in (source / ".agents/skills").glob("*/SKILL.md")),
        "roles": sorted(p.stem for p in (source / ".agents/agents").glob("*.md")),
        "requirements_sha256": hashlib.sha256((source / ".agents/mcp-requirements.txt").read_bytes()).hexdigest()
        if (source / ".agents/mcp-requirements.txt").exists() else None,
    }


def _source_inventory(source: Path) -> dict[str, Any]:
    result = {}
    folded = set()
    total = 0
    def files_below(directory: Path):
        for path in sorted(directory.iterdir()):
            if _is_link(path):
                raise KitError("Links are not supported in upstream snapshots")
            if path.is_dir():
                yield from files_below(path)
            else:
                yield path

    for path in files_below(source):
        if not path.is_file():
            raise KitError("Special files are not supported in upstream snapshots")
        relative = path.relative_to(source).as_posix()
        _safe_relative(relative)
        if not _allowed(relative) or relative.casefold() in folded:
            raise KitError(f"Out-of-scope or colliding snapshot file: {relative}")
        folded.add(relative.casefold())
        total += path.stat().st_size
        if len(result) >= MAX_FILES or total > MAX_BYTES:
            raise KitError("Snapshot exceeds import size limits")
        result[relative] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size}
    return result


def inspect_snapshot(root: Path) -> dict[str, Any]:
    """Verify integrity and static contracts, without importing or running code."""
    root = root.absolute()
    _real_directory(root)
    manifest_path = root / "manifest.json"
    if _is_link(manifest_path) or not manifest_path.is_file():
        raise KitError("Snapshot manifest is missing or is a link")
    if {p.name for p in root.iterdir()} != {"source", "manifest.json"}:
        raise KitError("Unexpected files in snapshot root; move adaptations outside it")
    _real_directory(root / "source")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise KitError("Cannot read snapshot manifest") from exc
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
            or manifest.get("upstream_url") != UPSTREAM_URL
            or not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("commit", "")))
            or manifest.get("import_paths") != list(IMPORT_PATHS)
            or not isinstance(manifest.get("files"), dict)):
        raise KitError("Unsupported snapshot manifest")
    actual = _source_inventory(root / "source")
    declared = manifest["files"]
    for name, info in declared.items():
        _safe_relative(name)
        if not isinstance(info, dict) or info.get("git_mode") not in ("100644", "100755"):
            raise KitError("Invalid snapshot file metadata")
    expected = {name: {k: info.get(k) for k in ("sha256", "size")} for name, info in declared.items()}
    if actual != expected:
        changed = sorted(k for k in actual.keys() | expected.keys() if actual.get(k) != expected.get(k))
        raise KitError(f"Snapshot drift; preserve local changes before updating: {', '.join(changed[:8])}")
    for name, info in declared.items():
        path = root / "source" / name
        if os.name != "nt" and bool(path.stat().st_mode & 0o111) != (info["git_mode"] == "100755"):
            raise KitError(f"Snapshot executable mode drift: {name}")
    if _capabilities(root / "source") != manifest.get("capabilities"):
        raise KitError("Snapshot capability inventory does not match source")
    return manifest


def _stage_from_repo(repo: Path, ref: str, output: Path, *, fetch_blobs: bool = False) -> dict[str, Any]:
    commit = _git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()
    # Select Git blobs, not mutable worktree files; preserve bytes despite EOL settings.
    # Do not use ls-tree -l here: asking for blob sizes before path filtering
    # lazily downloads excluded RTL blobs from a partial clone.
    entries = _git(repo, "ls-tree", "-r", "-z", commit).split("\0")
    selected = {}
    folded = set()
    for entry in entries:
        if not entry:
            continue
        header, name = entry.split("\t", 1)
        if not _allowed(name):
            continue
        _safe_relative(name)
        mode, kind, oid = header.split()
        if kind != "blob" or mode not in ("100644", "100755"):
            raise KitError(f"Unsupported upstream file type: {name}")
        if name.casefold() in folded:
            raise KitError(f"Case-colliding upstream file: {name}")
        selected[name] = (mode, oid)
        folded.add(name.casefold())
    if not selected or len(selected) > MAX_FILES:
        raise KitError("Empty or oversized upstream selection")
    # cat-file ignores export-ignore/export-subst and local checkout filters,
    # unlike git archive. Size is bounded before retrieving selected blobs.
    names = sorted(selected)
    if fetch_blobs:
        # Fetch selected blobs in bounded batches instead of lazily making one
        # network round trip per file or downloading the SoC/RTL blob tree.
        objects = sorted({selected[name][1] for name in names})
        for offset in range(0, len(objects), 64):
            _git(repo, "-c", "core.hooksPath=/dev/null", "fetch", "--no-tags", "--no-write-fetch-head",
                 "origin", *objects[offset:offset + 64])
    request = "".join(selected[name][1] + "\n" for name in names).encode("ascii")
    sizes = _run_git_process(["git", "-C", str(repo), "cat-file", "--batch-check"], input=request)
    if sizes.returncode:
        raise KitError("Git blob size query failed")
    headers = sizes.stdout.decode("ascii").splitlines()
    if len(headers) != len(names):
        raise KitError("Incomplete Git blob size inventory")
    total = 0
    for name, header in zip(names, headers):
        info = header.split()
        if len(info) != 3 or info[:2] != [selected[name][1], "blob"] or not info[2].isdigit():
            raise KitError("Invalid Git blob size inventory")
        size = int(info[2])
        total += size
        if total > MAX_BYTES:
            raise KitError("Snapshot exceeds import size limit")
        selected[name] = (*selected[name], size)
    try:
        result = _run_git_process(["git", "-C", str(repo), "cat-file", "--batch"], input=request)
    except subprocess.TimeoutExpired as exc:
        raise KitError("Upstream Git blob retrieval timed out") from exc
    if result.returncode:
        raise KitError("Git cat-file failed")
    stream = io.BytesIO(result.stdout)
    output.mkdir()
    try:
        source = output / "source"
        source.mkdir()
        for name in names:
            mode, oid, size = selected[name]
            if stream.readline() != f"{oid} blob {size}\n".encode("ascii"):
                raise KitError("Unexpected Git blob header")
            payload = stream.read(size)
            if len(payload) != size or stream.read(1) != b"\n":
                raise KitError("Incomplete Git blob")
            path = source.joinpath(*_safe_relative(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as target:
                target.write(payload)
            path.chmod(0o755 if mode == "100755" else 0o644)
        if stream.read(1):
            raise KitError("Unexpected Git blob output")
        files = _source_inventory(source)
        for name in files:
            files[name]["git_mode"] = selected[name][0]
        manifest = {
            "schema_version": 1, "upstream_url": UPSTREAM_URL, "commit": commit,
            "import_paths": list(IMPORT_PATHS), "files": files,
            "capabilities": _capabilities(source),
            "validation": "integrity_and_static_inventory_only",
        }
        (output / "manifest.json").write_text(_json(manifest), encoding="utf-8", newline="\n")
        inspect_snapshot(output)
        return {"status": "staged", "commit": commit, "path": str(output), "file_count": len(files),
                "server_count": len(manifest["capabilities"]["servers"]), "functional_validation": "not_run",
                "unavailable_servers": sorted(name for name, entry in manifest["capabilities"]["servers"].items()
                                              if entry["validation"] == "unavailable")}
    except BaseException:
        # Only this invocation's newly created candidate; preexisting output was rejected.
        shutil.rmtree(output)
        raise


def stage_snapshot(output: Path, *, source: Path | None = None, ref: str = "main") -> dict[str, Any]:
    """Build an isolated candidate; optional source is a read-only local Git repo.

Without source, fetch only the requested ref from the fixed upstream into a
temporary bare repo. No upstream launchers, hooks or install scripts are run.
"""
    if not ref or ref.startswith("-") or any(c.isspace() or ord(c) < 32 for c in ref):
        raise KitError("Invalid upstream ref")
    output = output.absolute()
    _real_directory(output.parent)
    if output.exists() or output.is_symlink():
        raise KitError("Candidate output already exists; use a new directory")
    if source is not None:
        source = source.resolve(strict=True)
        boundaries = [source]
        if _git(source, "rev-parse", "--is-bare-repository").strip() != "true":
            boundaries.append(Path(_git(source, "rev-parse", "--show-toplevel").strip()).resolve())
        for option in ("--absolute-git-dir", "--git-common-dir"):
            directory = Path(_git(source, "rev-parse", option).strip())
            boundaries.append((directory if directory.is_absolute() else source / directory).resolve())
        if any(output.resolve().is_relative_to(boundary) for boundary in boundaries):
            raise KitError("Candidate output must be outside the read-only source checkout and Git directories")
        return _stage_from_repo(source, ref, output)
    with tempfile.TemporaryDirectory(prefix="claude-kit-fetch-") as name:
        repo = Path(name)
        _git(repo, "init", "--bare", "--quiet", "--template=")
        _git(repo, "remote", "add", "origin", UPSTREAM_URL)
        _git(repo, "config", "remote.origin.promisor", "true")
        _git(repo, "config", "remote.origin.partialclonefilter", "blob:none")
        _git(repo, "-c", "core.hooksPath=/dev/null", "fetch", "--filter=blob:none", "--depth=1", "--no-tags", "origin", ref)
        return _stage_from_repo(repo, "FETCH_HEAD", output, fetch_blobs=True)


def diff_snapshots(current: Path | None, candidate: Path) -> dict[str, Any]:
    new = inspect_snapshot(candidate)
    old = inspect_snapshot(current) if current is not None else {"files": {}, "capabilities": {"servers": {}, "skills": [], "roles": []}}

    def delta(before: dict | list, after: dict | list) -> dict[str, Any]:
        return {"added": sorted(set(after) - set(before)), "removed": sorted(set(before) - set(after)),
                "changed": sorted(k for k in set(before) & set(after) if isinstance(before, dict) and before[k] != after[k])}

    tools = {}
    old_servers = old["capabilities"]["servers"]
    new_servers = new["capabilities"]["servers"]
    for name in sorted(old_servers.keys() | new_servers.keys()):
        before = {item["name"]: item for item in old_servers.get(name, {}).get("tools", [])}
        after = {item["name"]: item for item in new_servers.get(name, {}).get("tools", [])}
        change = delta(before, after)
        if any(change.values()):
            tools[name] = change
    return {
        "from_commit": old.get("commit"), "to_commit": new["commit"],
        "files": delta(old["files"], new["files"]),
        "servers": delta(old["capabilities"]["servers"], new["capabilities"]["servers"]),
        "tools": tools,
        "skills": delta(old["capabilities"]["skills"], new["capabilities"]["skills"]),
        "roles": delta(old["capabilities"]["roles"], new["capabilities"]["roles"]),
        "requirements_changed": old["capabilities"].get("requirements_sha256") != new["capabilities"].get("requirements_sha256"),
        "unavailable_servers": sorted(name for name, entry in new["capabilities"]["servers"].items()
                                      if entry["validation"] == "unavailable"),
        "functional_validation": "not_run", "consumer_configuration_changed": False,
    }


def apply_snapshot(candidate: Path, target: Path) -> dict[str, Any]:
    """Promote an integrity-checked candidate into an idle maintainer checkout.

This is not a production rollout. Keep an existing module release immutable;
build and validate a new kit release before consumers opt into it.
"""
    candidate = candidate.absolute()
    target = target.absolute()
    _real_directory(target)
    if (candidate.resolve() == target.resolve() or candidate.resolve().is_relative_to(target.resolve())
            or target.resolve().is_relative_to(candidate.resolve())):
        raise KitError("Candidate and target must be separate trees")
    inspect_snapshot(candidate)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent / f".{target.name}.update.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise KitError("Another updater or stale snapshot lock exists; inspect before retrying") from exc
    try:
        report = diff_snapshots(target if target.exists() else None, candidate)
        scratch = Path(tempfile.mkdtemp(prefix=f".{target.name}.update-", dir=target.parent))
        cleanup = True
        try:
            staged = scratch / "candidate"
            backup = scratch / "previous"
            shutil.copytree(candidate, staged, symlinks=True)
            inspect_snapshot(staged)
            had_previous = target.exists()
            if had_previous:
                # Detect edits made during staging rather than dropping them.
                inspect_snapshot(target)
                target.rename(backup)
            try:
                staged.rename(target)
            except BaseException:
                if had_previous:
                    try:
                        backup.rename(target)
                    except OSError as exc:
                        cleanup = False
                        raise KitError(f"Rollback failed; previous snapshot preserved at {backup}") from exc
                raise
        finally:
            if cleanup:
                shutil.rmtree(scratch)
        return {"status": "applied", **report}
    finally:
        owned = os.fstat(descriptor)
        os.close(descriptor)
        try:
            current = lock.lstat()
        except FileNotFoundError:
            current = None
        if current is not None and not _is_link(lock) and (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
            lock.unlink()
