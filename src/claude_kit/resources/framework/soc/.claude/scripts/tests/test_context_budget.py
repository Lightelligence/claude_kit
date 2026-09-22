"""Budget regression tests: implicit rules and bounded artifact I/O."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from framework_project import project_root

ROOT = project_root()
sys.path.insert(0, str(ROOT / '.claude/scripts'))
sys.path.insert(0, str(ROOT / 'third_party/claude_kit/src'))
import loop_prompt_budget as budget
import kit_log_bridge as bridge


class RuleBudgetTest(unittest.TestCase):
    def test_new_unconditional_rule_cannot_escape_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rules = root / '.claude/rules/nested'
            rules.mkdir(parents=True)
            (rules / 'large.md').write_text('x' * 10001, encoding='utf-8')
            result = budget.automatic_rule_budget(root)
            self.assertFalse(result['pass'])
            self.assertEqual(result['utf8_bytes'], 10001)

    def test_scoped_and_malformed_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rules = root / '.claude/rules'
            rules.mkdir(parents=True)
            (rules / 'scoped.md').write_text('---\npaths:\n  - "hw/rtl/**"\n---\nRTL only\n', encoding='utf-8')
            (rules / 'bad.md').write_text('---\npaths:\n---\nRequired even with an empty scope\n', encoding='utf-8')
            result = budget.automatic_rule_budget(root)
            self.assertEqual(result['path_scoped_files'], ['.claude/rules/scoped.md'])
            self.assertIn('.claude/rules/bad.md', result['unconditional_files'])


class ArtifactReadBudgetTest(unittest.TestCase):
    def test_file_io_is_limited_not_just_returned_text(self):
        from claude_kit import core
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'large.log'
            path.write_bytes(b'x' * 100000)
            opened, requests = Path.open, []
            class Tracked:
                def __init__(self, stream): self.stream = stream
                def __enter__(self): return self
                def __exit__(self, *args): self.stream.close()
                def fileno(self): return self.stream.fileno()
                def read(self, size=-1):
                    requests.append(size)
                    if size < 0 or size > bridge.DEFAULT_READ_BYTES:
                        raise AssertionError('Unbounded artifact read')
                    return self.stream.read(size)
            def bounded_open(p, *args, **kwargs):
                stream = opened(p, *args, **kwargs)
                return Tracked(stream) if p == path and args == ('rb',) else stream
            with patch.object(core, 'load_profile', return_value=(root / 'profile', {})), patch.object(Path, 'open', bounded_open):
                result = bridge.read_bounded_artifact('read_artifact', {'path': 'large.log'}, root, '.claude/project.toml')
            value = json.loads(result['content'][0]['text'])
            self.assertEqual(requests, [12000])
            self.assertEqual(value['bytes'], 100000)
            self.assertEqual(value['bytes_read'], 12000)
            self.assertTrue(value['truncated'])

    def test_concurrent_shrink_remains_truncated_and_unstable(self):
        from claude_kit import core
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'shrinking.log'
            path.write_bytes(b'x' * 20000)
            opened = Path.open
            class Shrinking:
                def __init__(self, stream): self.stream = stream
                def __enter__(self): return self
                def __exit__(self, *args): self.stream.close()
                def fileno(self): return self.stream.fileno()
                def read(self, size=-1):
                    with opened(path, 'r+b') as writer:
                        writer.truncate(8000)
                    return self.stream.read(size)
            def changing_open(p, *args, **kwargs):
                stream = opened(p, *args, **kwargs)
                return Shrinking(stream) if p == path and args == ('rb',) else stream
            with patch.object(core, 'load_profile', return_value=(root / 'profile', {})), patch.object(Path, 'open', changing_open):
                result = bridge.read_bounded_artifact('read_artifact', {'path': 'shrinking.log'}, root, '.claude/project.toml')
            value = json.loads(result['content'][0]['text'])
            self.assertTrue(value['truncated'])
            self.assertFalse(value['stable'])
            self.assertEqual(value['bytes_read'], 8000)


if __name__ == '__main__':
    unittest.main()
