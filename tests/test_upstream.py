from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_kit.core import KitError
from claude_kit.upstream import (
    apply_snapshot,
    diff_snapshots,
    inspect_snapshot,
    stage_snapshot,
)


class UpstreamSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.workspace = Path(self._temporary.name)
        self.repo = self.workspace / "upstream-repo"
        self.repo.mkdir()
        initialized = self._git("init", "--quiet", "--initial-branch=main", check=False)
        if initialized.returncode:
            self._git("init", "--quiet")
            self._git("checkout", "--quiet", "-B", "main")
        self._git("config", "user.name", "claude-kit test")
        self._git("config", "user.email", "claude-kit-test@example.invalid")
        self._git("config", "commit.gpgSign", "false")
        self._git("config", "core.autocrlf", "false")
        hooks = self.workspace / "empty-hooks"
        hooks.mkdir()
        self._git("config", "core.hooksPath", str(hooks))

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True,
            check=False,
        )
        if check and result.returncode:
            message = result.stderr.decode("utf-8", errors="replace")
            self.fail(f"git {' '.join(args)} failed ({result.returncode}): {message}")
        return result

    def _commit(self, message: str) -> str:
        self._git("add", "--all")
        self._git("commit", "--quiet", "--no-verify", "-m", message)
        return self._git("rev-parse", "HEAD").stdout.decode("ascii").strip()

    def _write(self, relative: str, content: bytes | str) -> Path:
        path = self.repo.joinpath(*Path(relative).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            content = content.encode("utf-8")
        path.write_bytes(content)
        return path

    def _server_manifest(self, servers: list[dict[str, str]]) -> bytes:
        return (json.dumps({"schema_version": 1, "servers": servers}, indent=2) + "\n").encode("utf-8")

    def _create_fixture(self, *, include_obsolete: bool = False) -> str:
        self._write(
            ".agents/scripts/server.py",
            b"from typing import Any\r\n\r\n@mcp.tool\r\ndef ping(name: str) -> str:\r\n    return name\r\n",
        )
        self._write(
            ".agents/mcp-servers.json",
            self._server_manifest([{"name": "fixture", "script": ".agents/scripts/server.py"}]),
        )
        self._write(".agents/mcp-requirements.txt", b"fixture==1.0\r\n")
        self._write(".agents/loop_policy.json", b'{"mode":"manual"}\n')
        self._write(".agents/agents/reviewer.md", "# Reviewer\n")
        self._write(".agents/rules/general.md", "# General rules\n")
        self._write(".agents/skills/fixture/SKILL.md", "# Fixture skill\n")
        self._write("scripts/helper.sh", b"#!/bin/sh\r\necho helper\r\n")
        self._write("LICENSE", b"fixture license\n")
        self._write("NOTICE.txt", b"fixture notice\n")
        self._write(
            ".gitattributes",
            b".agents/scripts/subst.py export-subst\n.agents/scripts/export-ignored.py export-ignore\n",
        )
        self._write(".agents/scripts/subst.py", b"marker = '$Format:%H$'\n")
        self._write(".agents/scripts/export-ignored.py", b"marker = 'still selected'\n")

        # These files are deliberately tracked but outside the import contract.
        self._write(".agents/targets/consumer-only.md", "consumer target\n")
        self._write("rtl/top.sv", "module top; endmodule\n")
        self._write("chip/design.sv", "module chip; endmodule\n")
        self._write("ip/vendor.sv", "module vendor; endmodule\n")

        if include_obsolete:
            self._write(
                ".agents/scripts/obsolete.py",
                b"@mcp.tool\ndef old_tool() -> None:\n    pass\n",
            )
            self._write(
                ".agents/mcp-servers.json",
                self._server_manifest([
                    {"name": "fixture", "script": ".agents/scripts/server.py"},
                    {"name": "obsolete", "script": ".agents/scripts/obsolete.py"},
                ]),
            )
        return self._commit("fixture")

    def _stage(self, name: str, ref: str = "main") -> Path:
        output = self.workspace / name
        stage_snapshot(output, source=self.repo, ref=ref)
        return output

    def _source_bytes(self, snapshot: Path) -> dict[str, bytes]:
        source = snapshot / "source"
        return {
            path.relative_to(source).as_posix(): path.read_bytes()
            for path in source.rglob("*")
            if path.is_file()
        }

    def _manifest_bytes(self, snapshot: Path) -> bytes:
        return (snapshot / "manifest.json").read_bytes()

    def test_stage_uses_pinned_git_bytes_and_leaves_dirty_repo_untouched(self) -> None:
        commit = self._create_fixture()
        status_before = self._git("status", "--porcelain").stdout
        self.assertEqual(status_before, b"")

        # A dirty selected file and an untracked file must not affect a pinned snapshot.
        self._write(".agents/scripts/server.py", b"raise RuntimeError('dirty worktree')\n")
        self._write(".agents/scripts/untracked.py", b"untracked = True\n")
        status_dirty = self._git("status", "--porcelain").stdout
        self.assertTrue(status_dirty)
        candidate = self._stage("candidate")

        manifest = inspect_snapshot(candidate)
        self.assertEqual(manifest["commit"], commit)
        self.assertEqual(manifest["validation"], "integrity_and_static_inventory_only")
        for relative in manifest["files"]:
            expected = self._git("show", f"{commit}:{relative}").stdout
            self.assertEqual((candidate / "source" / Path(relative)).read_bytes(), expected, relative)
        source_names = set(self._source_bytes(candidate))
        self.assertNotIn(".agents/targets/consumer-only.md", source_names)
        self.assertNotIn("rtl/top.sv", source_names)
        self.assertNotIn("chip/design.sv", source_names)
        self.assertNotIn("ip/vendor.sv", source_names)
        self.assertNotIn(".agents/scripts/untracked.py", source_names)
        self.assertNotIn(".gitattributes", source_names)
        self.assertEqual(
            (candidate / "source/.agents/scripts/subst.py").read_bytes(),
            b"marker = '$Format:%H$'\n",
        )
        self.assertIn(".agents/scripts/export-ignored.py", manifest["files"])
        self.assertEqual(self._git("rev-parse", "HEAD").stdout.decode("ascii").strip(), commit)
        self.assertEqual(self._git("status", "--porcelain").stdout, status_dirty)

    def test_repeat_staging_is_deterministic_and_duplicate_output_is_rejected(self) -> None:
        self._create_fixture()
        first = self._stage("candidate-one")
        second = self._stage("candidate-two")

        self.assertEqual(self._manifest_bytes(first), self._manifest_bytes(second))
        self.assertEqual(self._source_bytes(first), self._source_bytes(second))
        manifest_before = self._manifest_bytes(first)
        with self.assertRaisesRegex(KitError, "already exists"):
            stage_snapshot(first, source=self.repo)
        self.assertEqual(self._manifest_bytes(first), manifest_before)

    def test_ref_option_injection_is_rejected_before_output_creation(self) -> None:
        self._create_fixture()
        for ref in ("--upload-pack=touch", "main --upload-pack=touch", "main\nother"):
            with self.subTest(ref=ref):
                output = self.workspace / ("candidate-" + str(len(ref)))
                with self.assertRaisesRegex(KitError, "Invalid upstream ref"):
                    stage_snapshot(output, source=self.repo, ref=ref)
                self.assertFalse(output.exists())

    def test_stage_rejects_output_inside_read_only_source_or_git_directory(self) -> None:
        self._create_fixture()
        with self.assertRaisesRegex(KitError, "outside the read-only source"):
            stage_snapshot(self.repo / "candidate", source=self.repo)
        with self.assertRaisesRegex(KitError, "outside the read-only source"):
            stage_snapshot(self.repo / ".git/candidate", source=self.repo)

    def test_inspect_rejects_tampering_additions_missing_files_and_unsafe_metadata(self) -> None:
        self._create_fixture()

        tampered = self._stage("tampered")
        script = tampered / "source/.agents/scripts/server.py"
        script.write_bytes(script.read_bytes() + b"# changed\n")
        with self.assertRaisesRegex(KitError, "Snapshot drift"):
            inspect_snapshot(tampered)

        added = self._stage("added")
        self._write_snapshot_file(added, ".agents/scripts/extra.py", b"extra = True\n")
        with self.assertRaisesRegex(KitError, "Snapshot drift"):
            inspect_snapshot(added)

        missing = self._stage("missing")
        (missing / "source/.agents/scripts/server.py").unlink()
        with self.assertRaisesRegex(KitError, "Snapshot drift"):
            inspect_snapshot(missing)

        unsafe = self._stage("unsafe")
        manifest_path = unsafe / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["../outside"] = {"sha256": "", "size": 0, "git_mode": "100644"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(KitError, "Unsafe snapshot path"):
            inspect_snapshot(unsafe)

    def _write_snapshot_file(self, snapshot: Path, relative: str, content: bytes) -> Path:
        path = snapshot / "source" / Path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_inspect_rejects_symlinked_snapshot_files(self) -> None:
        self._create_fixture()
        candidate = self._stage("symlinked")
        outside = self.workspace / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        link = candidate / "source/.agents/scripts/escape.py"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"file symlinks are unavailable: {exc}")
        with self.assertRaisesRegex(KitError, "Links are not supported"):
            inspect_snapshot(candidate)

    def test_diff_reports_changed_files_and_server_capabilities(self) -> None:
        old_commit = self._create_fixture(include_obsolete=True)
        old = self._stage("old")

        self._write(
            ".agents/scripts/server.py",
            b"@mcp.tool\ndef pong(name: str) -> str:\n    return name\n",
        )
        (self.repo / ".agents/scripts/obsolete.py").unlink()
        self._write(
            ".agents/scripts/added.py",
            b"@mcp.tool\ndef added(value: int) -> int:\n    return value\n",
        )
        new_servers = [
            {"name": "fixture", "script": ".agents/scripts/server.py"},
            {"name": "added", "script": ".agents/scripts/added.py"},
        ]
        self._write(".agents/mcp-servers.json", self._server_manifest(new_servers))
        new_commit = self._commit("change capabilities")
        candidate = self._stage("new")

        delta = diff_snapshots(old, candidate)
        self.assertEqual(delta["from_commit"], old_commit)
        self.assertEqual(delta["to_commit"], new_commit)
        self.assertIn(".agents/scripts/added.py", delta["files"]["added"])
        self.assertIn(".agents/scripts/obsolete.py", delta["files"]["removed"])
        self.assertIn(".agents/mcp-servers.json", delta["files"]["changed"])
        self.assertIn(".agents/scripts/server.py", delta["files"]["changed"])
        self.assertEqual(delta["servers"]["added"], ["added"])
        self.assertEqual(delta["servers"]["removed"], ["obsolete"])
        self.assertEqual(delta["servers"]["changed"], ["fixture"])
        self.assertEqual(delta["tools"]["fixture"]["added"], ["pong"])
        self.assertEqual(delta["tools"]["fixture"]["removed"], ["ping"])
        self.assertEqual(delta["tools"]["added"]["added"], ["added"])
        self.assertEqual(delta["tools"]["obsolete"]["removed"], ["old_tool"])

        old_tools = inspect_snapshot(old)["capabilities"]["servers"]["fixture"]["tools"]
        new_tools = inspect_snapshot(candidate)["capabilities"]["servers"]["fixture"]["tools"]
        self.assertEqual([tool["name"] for tool in old_tools], ["ping"])
        self.assertEqual([tool["name"] for tool in new_tools], ["pong"])

    def test_missing_script_is_inventory_unavailable_without_execution(self) -> None:
        self._create_fixture()
        self._write(
            ".agents/mcp-servers.json",
            self._server_manifest([
                {"name": "fixture", "script": ".agents/scripts/server.py"},
                {"name": "missing", "script": ".agents/scripts/not-present.py"},
            ]),
        )
        self._commit("record unavailable server")

        candidate = self.workspace / "missing-script"
        result = stage_snapshot(candidate, source=self.repo)
        manifest = inspect_snapshot(candidate)
        entry = manifest["capabilities"]["servers"]["missing"]
        self.assertEqual(entry["validation"], "unavailable")
        self.assertEqual(entry["inventory"], "missing_script")
        self.assertEqual(entry["tools"], [])
        self.assertEqual(result["unavailable_servers"], ["missing"])

    def test_null_script_path_is_rejected_as_unsafe(self) -> None:
        self._create_fixture()
        self._write(
            ".agents/mcp-servers.json",
            self._server_manifest([{"name": "bad", "script": ".agents/scripts/\x00bad.py"}]),
        )
        self._commit("record invalid script path")
        candidate = self.workspace / "null-script"

        with self.assertRaisesRegex(KitError, "Unsafe snapshot path"):
            stage_snapshot(candidate, source=self.repo)
        self.assertFalse(candidate.exists())

    def test_apply_refuses_local_modification_drift_and_cleans_lock(self) -> None:
        self._create_fixture()
        candidate = self._stage("candidate")
        target = self.workspace / "target"
        shutil.copytree(candidate, target)
        changed = target / "source/.agents/scripts/server.py"
        changed.write_bytes(changed.read_bytes() + b"# local adaptation\n")
        lock = target.parent / f".{target.name}.update.lock"

        with self.assertRaisesRegex(KitError, "Snapshot drift"):
            apply_snapshot(candidate, target)
        self.assertTrue(changed.read_bytes().endswith(b"# local adaptation\n"))
        self.assertFalse(lock.exists())

    def test_apply_preserves_unrelated_neighboring_adapter_file(self) -> None:
        self._create_fixture()
        candidate = self._stage("candidate")
        install = self.workspace / "install"
        install.mkdir()
        adapter = install / "adapter.py"
        adapter.write_bytes(b"# project-owned adapter\n")
        target = install / "claude-kit"

        result = apply_snapshot(candidate, target)

        self.assertEqual(result["status"], "applied")
        self.assertEqual(adapter.read_bytes(), b"# project-owned adapter\n")
        self.assertEqual(inspect_snapshot(target)["commit"], result["to_commit"])
        self.assertFalse((install / ".claude-kit.update.lock").exists())

    def test_apply_honors_existing_update_lock(self) -> None:
        self._create_fixture()
        candidate = self._stage("candidate")
        install = self.workspace / "locked-install"
        install.mkdir()
        lock = install / ".target.update.lock"
        lock.write_bytes(b"another updater")

        with self.assertRaisesRegex(KitError, "Another updater"):
            apply_snapshot(candidate, install / "target")
        self.assertEqual(lock.read_bytes(), b"another updater")
        self.assertFalse((install / "target").exists())

    def test_failed_target_swap_restores_previous_snapshot(self) -> None:
        self._create_fixture()
        previous = self._stage("previous-candidate")
        target = self.workspace / "target"
        shutil.copytree(previous, target)
        before = self._source_bytes(target)

        self._write(
            ".agents/scripts/server.py",
            b"@mcp.tool\ndef changed(value: str) -> str:\n    return value\n",
        )
        self._commit("new snapshot")
        candidate = self._stage("new-candidate")
        original_rename = Path.rename

        def fail_new_tree(self: Path, destination: str | Path) -> Path:
            if self.name == "candidate" and Path(destination) == target:
                raise OSError("injected target swap failure")
            return original_rename(self, destination)

        with patch.object(Path, "rename", new=fail_new_tree):
            with self.assertRaisesRegex(OSError, "target swap failure"):
                apply_snapshot(candidate, target)

        self.assertEqual(self._source_bytes(target), before)
        self.assertFalse((target.parent / ".target.update.lock").exists())

    def test_failed_rollback_preserves_previous_snapshot_for_recovery(self) -> None:
        self._create_fixture()
        previous = self._stage("previous-candidate")
        target = self.workspace / "target"
        shutil.copytree(previous, target)
        before = self._source_bytes(target)
        self._write(
            ".agents/scripts/server.py",
            b"@mcp.tool\ndef changed(value: str) -> str:\n    return value\n",
        )
        self._commit("new snapshot")
        candidate = self._stage("new-candidate")
        original_rename = Path.rename

        def fail_swap_and_rollback(self: Path, destination: str | Path) -> Path:
            if Path(destination) == target and self.name in {"candidate", "previous"}:
                raise OSError("injected rollback failure")
            return original_rename(self, destination)

        with patch.object(Path, "rename", new=fail_swap_and_rollback):
            with self.assertRaisesRegex(KitError, "Rollback failed; previous snapshot preserved at") as context:
                apply_snapshot(candidate, target)

        backup = Path(str(context.exception).rsplit(" at ", 1)[1])
        self.assertTrue(backup.is_dir())
        self.assertEqual(self._source_bytes(backup), before)
        self.assertFalse(target.exists())
        self.assertFalse((target.parent / ".target.update.lock").exists())

    @unittest.skipIf(__import__("os").name == "nt", "replacing an open lock is not portable on Windows")
    def test_lock_replacement_is_not_unlinked_by_finished_updater(self) -> None:
        self._create_fixture()
        candidate = self._stage("candidate")
        install = self.workspace / "lock-replacement"
        install.mkdir()
        target = install / "target"
        lock = install / ".target.update.lock"

        def replace_lock(_current: Path | None, _candidate: Path) -> dict:
            lock.unlink()
            lock.write_bytes(b"replacement updater")
            raise KitError("injected updater failure")

        with patch("claude_kit.upstream.diff_snapshots", side_effect=replace_lock):
            with self.assertRaisesRegex(KitError, "injected updater failure"):
                apply_snapshot(candidate, target)
        self.assertEqual(lock.read_bytes(), b"replacement updater")

    def test_apply_rejects_candidate_and_target_aliasing(self) -> None:
        self._create_fixture()
        candidate = self._stage("candidate")
        with self.assertRaisesRegex(KitError, "separate trees"):
            apply_snapshot(candidate, candidate)


if __name__ == "__main__":
    unittest.main()
