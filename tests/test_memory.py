"""Memory recovery, bounded disclosure and preservation of concurrent/user data."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from claude_kit.core import KitError
from claude_kit import memory

ENTRY = Path(__file__).resolve().parents[1] / 'bin/claude-kit'


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def state(self):
        return memory.init_state(self.root, 'bounded-recovery')

    def test_checkpoint_survives_new_process_with_constraints_and_evidence(self):
        initial = self.state()
        body = initial['content'].replace('Not recorded.', 'Recover task without reading historical transcripts.', 1)
        body = body.replace('## Constraints\nNot recorded.', '## Constraints\nDo not merge; preserve user edits.')
        body = body.replace('## Evidence\nNot recorded.', '## Evidence\nNOT RUN: simulation. Raw artifacts: logs/run-42.log; source: abc123.')
        memory.checkpoint(self.root, 'bounded-recovery', body.encode(), initial['sha256'])
        result = subprocess.run([sys.executable, str(ENTRY), 'memory', 'read',
            '--project-root', str(self.root), '--task', 'bounded-recovery'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        recovered = json.loads(result.stdout)
        self.assertEqual(recovered['content'], body)
        self.assertIn('Do not merge', recovered['content'])
        self.assertIn('NOT RUN: simulation', recovered['content'])
        self.assertEqual(recovered['sha256'], hashlib.sha256(body.encode()).hexdigest())

    def test_wrong_revision_and_existing_init_preserve_current_state(self):
        initial = self.state()
        new = initial['content'].replace('Not recorded.', 'Updated by another writer.', 1).encode()
        updated = memory.checkpoint(self.root, 'bounded-recovery', new, initial['sha256'])
        with self.assertRaisesRegex(KitError, 'changed'):
            memory.checkpoint(self.root, 'bounded-recovery', initial['content'].encode(), initial['sha256'])
        with self.assertRaisesRegex(KitError, 'already exists'):
            self.state()
        self.assertEqual(memory.read_state(self.root, 'bounded-recovery'), updated)

    def test_busy_writer_is_not_overridden(self):
        initial = self.state()
        with memory._lock(self.root, memory.task_path(self.root, 'bounded-recovery')):
            with self.assertRaisesRegex(KitError, 'locked'):
                memory.checkpoint(self.root, 'bounded-recovery', initial['content'].encode(), initial['sha256'])

    def test_terminated_writer_releases_kernel_lock(self):
        initial = self.state()
        code = ('import sys,time; from pathlib import Path; from claude_kit.memory import _lock,task_path; '
                'root=Path(sys.argv[1]);\nwith _lock(root,task_path(root,"bounded-recovery")):\n'
                ' print("locked",flush=True)\n time.sleep(60)\n')
        process = subprocess.Popen([sys.executable, '-c', code, str(self.root)],
            env={**os.environ, 'PYTHONPATH': str(ENTRY.parent.parent / 'src')},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'locked')
            process.terminate()
            process.wait(timeout=10)
            body = initial['content'].replace('Not recorded.', 'Recovered after terminated writer.', 1).encode()
            self.assertEqual(memory.checkpoint(self.root, 'bounded-recovery', body, initial['sha256'])['content'], body.decode())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stdout.close()
            process.stderr.close()

    def test_external_settings_edit_before_publication_is_preserved(self):
        settings = self.root / '.claude/settings.json'
        settings.parent.mkdir()
        settings.write_text('{"model":"original"}')
        changed = b'{"model":"user-edited", "hooks":{"keep":true}}'
        original = memory.tempfile.mkstemp
        def edit_then_prepare(*args, **kwargs):
            settings.write_bytes(changed)
            return original(*args, **kwargs)
        with patch('claude_kit.memory.tempfile.mkstemp', side_effect=edit_then_prepare):
            with self.assertRaisesRegex(KitError, 'changed'):
                memory.enable_auto_memory(self.root)
        self.assertEqual(settings.read_bytes(), changed)

    def test_intervening_task_creation_is_not_overwritten(self):
        target = memory.task_path(self.root, 'bounded-recovery')
        original = memory.tempfile.mkstemp
        def edit_then_prepare(*args, **kwargs):
            target.write_text('User created this task.')
            return original(*args, **kwargs)
        with patch('claude_kit.memory.tempfile.mkstemp', side_effect=edit_then_prepare):
            with self.assertRaisesRegex(KitError, 'changed'):
                memory.init_state(self.root, 'bounded-recovery')
        self.assertEqual(target.read_text(), 'User created this task.')

    def test_budgets_and_missing_sections_do_not_destroy_old_evidence(self):
        initial = self.state()
        for data in (b'x' * 4097, (initial['content'] + '\n' * 51).encode(), b'Only a summary without constraints',
                     initial['content'].encode() + b'\x00'):
            with self.subTest(size=len(data)), self.assertRaises(KitError):
                memory.checkpoint(self.root, 'bounded-recovery', data, initial['sha256'])
        self.assertEqual(memory.read_state(self.root, 'bounded-recovery'), initial)
        self.assertFalse(list(memory.task_path(self.root, 'bounded-recovery').parent.glob('.memory-*')))

    def test_single_task_read_does_not_expand_with_unrelated_history(self):
        initial = self.state()
        unrelated = self.root / memory.STATE_ROOT / 'unrelated'
        unrelated.mkdir()
        (unrelated / 'STATE.md').write_bytes(b'PRIVATE-UNRELATED\n' * 100000)
        recovered = memory.read_state(self.root, 'bounded-recovery')
        self.assertEqual(recovered, initial)
        self.assertNotIn('PRIVATE-UNRELATED', json.dumps(recovered))
        self.assertLess(len(json.dumps(recovered).encode()), 5000)

    def test_utf8_bound_is_bytes_and_valid_state_is_lossless(self):
        initial = self.state()
        body = initial['content'].replace('Not recorded.', '中文状态：保留约束与证据。', 1).encode()
        recovered = memory.checkpoint(self.root, 'bounded-recovery', body, initial['sha256'])
        self.assertEqual(recovered['bytes'], len(body))
        with self.assertRaises(KitError):
            memory.checkpoint(self.root, 'bounded-recovery', body + ('中' * 1500).encode(), recovered['sha256'])

    def test_settings_merge_preserves_values_layout_and_explicit_false(self):
        settings = self.root / '.claude/settings.json'
        settings.parent.mkdir()
        original = b'{\r\n  "env": {"EXAMPLE": "keep"},\r\n  "permissions": {"deny": ["Write(secrets/**)"]}\r\n}\r\n'
        settings.write_bytes(original)
        result = memory.enable_auto_memory(self.root)
        self.assertTrue(result['changed'])
        updated = settings.read_bytes()
        self.assertIn(b'"env": {"EXAMPLE": "keep"}', updated)
        self.assertIn(b'\r\n', updated)
        self.assertEqual(json.loads(updated), {**json.loads(original), 'autoMemoryEnabled': True})
        self.assertFalse(memory.enable_auto_memory(self.root)['changed'])
        explicit = b'{"autoMemoryEnabled": false, "model": "keep-current-choice"}\n'
        settings.write_bytes(explicit)
        self.assertFalse(memory.enable_auto_memory(self.root)['autoMemoryEnabled'])
        self.assertEqual(settings.read_bytes(), explicit)
        self.assertNotIn('keep-current-choice', json.dumps(memory.memory_status(self.root)))

    def test_missing_project_settings_are_created_once(self):
        self.assertTrue(memory.enable_auto_memory(self.root)['changed'])
        path = self.root / '.claude/settings.json'
        self.assertEqual(json.loads(path.read_bytes()), {'autoMemoryEnabled': True})
        before = path.read_bytes()
        self.assertFalse(memory.enable_auto_memory(self.root)['changed'])
        self.assertEqual(path.read_bytes(), before)

    def test_settings_update_preserves_existing_permission_bits(self):
        path = self.root / '.claude/settings.json'
        path.parent.mkdir()
        path.write_text('{"env":{"EXAMPLE":"keep"}}')
        path.chmod(0o640)
        before = stat.S_IMODE(path.stat().st_mode)
        memory.enable_auto_memory(self.root)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), before)

    def test_bad_settings_and_secrets_do_not_leak_or_get_replaced(self):
        settings = self.root / '.claude/settings.json'
        settings.parent.mkdir()
        private = b'{"env":{"PRIVATE_VALUE":"keep-private"},"autoMemoryEnabled":true}'
        settings.write_bytes(private)
        self.assertNotIn('keep-private', json.dumps(memory.memory_status(self.root)))
        for invalid in (b'[]', b'{bad', b'{"autoMemoryEnabled":"yes"}'):
            settings.write_bytes(invalid)
            with self.assertRaises((KitError, ValueError)):
                memory.enable_auto_memory(self.root)
            self.assertEqual(settings.read_bytes(), invalid)
        for invalid in (b'{"autoMemoryEnabled":{"token":"PRIVATE"}}', b'{"autoMemoryEnabled":"PRIVATE"}', b'{"autoMemoryEnabled":null}'):
            settings.write_bytes(invalid)
            with self.assertRaisesRegex(KitError, 'boolean'):
                memory.memory_status(self.root)

    def test_task_names_and_external_inputs_cannot_escape_project(self):
        for task in ('../escape', '/tmp/outside', 'with space', 'CON', 'a' * 65):
            with self.subTest(task=task), self.assertRaises(KitError):
                memory.init_state(self.root, task)
        with self.assertRaises(KitError):
            memory.read_input(self.root, '../outside.md')

    def test_linked_parent_is_not_read_or_written(self):
        with tempfile.TemporaryDirectory() as other:
            (self.root / '.claude').mkdir()
            try:
                (self.root / '.claude/task-memory').symlink_to(other, target_is_directory=True)
            except OSError:
                self.skipTest('Symlinks unavailable on this Windows account')
            with self.assertRaises(KitError):
                memory.init_state(self.root, 'escape')
            self.assertEqual(list(Path(other).iterdir()), [])

    def test_cli_checkpoint_and_status_are_bounded(self):
        initial = self.state()
        body = initial['content'].replace('Not recorded.', 'CLI checkpoint.', 1)
        process = subprocess.run([sys.executable, str(ENTRY), 'memory', 'checkpoint',
            '--project-root', str(self.root), '--task', 'bounded-recovery', '--input', '-',
            '--expected-sha256', initial['sha256']], input=body.encode('utf-8'), capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['content'], body)
        result = memory.memory_status(self.root)
        self.assertEqual(result['state_root'], '.claude/task-memory')
        self.assertIn('Unverified', result['native_activation'])
        self.assertFalse((self.root / '.claude/settings.json').exists())


if __name__ == '__main__':
    unittest.main()
