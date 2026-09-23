"""Exercise the shared SoC task helpers with consumer-owned settings."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from claude_kit.core import resource_root


SCRIPTS = resource_root() / "framework/soc/.claude/scripts"


def run(*argv, cwd, env=None, check=True):
    return subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True, check=check)


@unittest.skipUnless(os.name == "posix", "POSIX task helpers")
class TaskWorktreeHelpersTest(unittest.TestCase):
    def test_project_prefix_root_local_config_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote = root / "remote.git"
            seed = root / "seed"
            checkout = root / "checkout"
            tasks = root / "tasks"
            run("git", "init", "--bare", str(remote), cwd=root)
            run("git", "init", str(seed), cwd=root)
            run("git", "checkout", "-b", "main", cwd=seed)
            run("git", "config", "user.name", "Fixture", cwd=seed)
            run("git", "config", "user.email", "fixture@example.com", cwd=seed)
            (seed / ".claude").mkdir()
            (seed / ".claude/task-worktree.env").write_text(
                'CLAUDE_KIT_TASK_BRANCH_PREFIX=claude\n'
                'CLAUDE_KIT_WORKTREE_ROOT="$CLAUDE_KIT_TEST_ROOT"\n',
                encoding="utf-8",
            )
            (seed / ".gitignore").write_text("scripts/local.mk\n", encoding="utf-8")
            run("git", "add", ".", cwd=seed)
            run("git", "commit", "-m", "Seed", cwd=seed)
            run("git", "remote", "add", "origin", str(remote), cwd=seed)
            run("git", "push", "-u", "origin", "main", cwd=seed)
            run("git", "symbolic-ref", "HEAD", "refs/heads/main", cwd=remote)
            run("git", "clone", str(remote), str(checkout), cwd=root)
            (checkout / "scripts").mkdir()
            (checkout / "scripts/local.mk").write_text("LOCAL := yes\n", encoding="utf-8")
            env = dict(os.environ, CLAUDE_KIT_TEST_ROOT=str(tasks),
                       GIT_PUBLISH_TIMESTAMP="20260923-010203")

            prepared = run("bash", str(SCRIPTS / "prepare_task_worktree.sh"),
                           "dv-agent", cwd=checkout, env=env)
            worktree = Path(next(line.split("=", 1)[1] for line in
                                 prepared.stdout.splitlines() if line.startswith("WORKTREE=")))
            self.assertTrue(worktree.is_relative_to(tasks))
            self.assertEqual(run("git", "branch", "--show-current", cwd=worktree).stdout.strip(),
                             "claude/dv-agent-20260923-010203")
            self.assertEqual((worktree / "scripts/local.mk").read_text(), "LOCAL := yes\n")
            self.assertEqual(run("git", "branch", "--show-current", cwd=checkout).stdout.strip(),
                             "main")
            run("bash", str(SCRIPTS / "cleanup_task_worktree.sh"), str(worktree),
                cwd=checkout, env=env)
            self.assertFalse(worktree.exists())

    def test_invalid_project_prefix_is_rejected_before_switch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run("git", "init", str(root), cwd=root)
            (root / ".claude").mkdir()
            (root / ".claude/task-worktree.env").write_text(
                "CLAUDE_KIT_TASK_BRANCH_PREFIX=bad/prefix\n", encoding="utf-8")
            result = run("bash", str(SCRIPTS / "prepare_task_branch.sh"),
                         "dv-agent", cwd=root, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Invalid task branch prefix", result.stderr)


if __name__ == "__main__":
    unittest.main()
