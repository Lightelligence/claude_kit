import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'dv_log_evidence.py'
spec = importlib.util.spec_from_file_location('log_evidence', SOURCE)
logs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logs)


class LogEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / 'sim.log'

    def write(self, text):
        self.file.write_text(text, encoding='utf-8')

    def summary(self, **kwargs):
        return logs.summarize(self.root, 'sim.log', **kwargs)

    def test_zero_uvm_counts_are_not_errors_or_pass_evidence(self):
        self.write('UVM_ERROR : 0\nUVM_FATAL : 0\nUVM_WARNING : 0\n')
        result = self.summary()
        self.assertEqual(result['status'], 'unknown')
        self.assertIsNone(result['first_error'])
        self.assertEqual(result['diagnostics'], [])
        self.assertEqual(result['diagnostic_counts'].get('warning', 0), 0)

    def test_multiline_diagnostic_and_exact_duplicate_counts(self):
        self.write('Parsing design file\nError-[SE] Syntax error\n  bad.sv, 12\n'
                   '  missing semicolon\nError-[SE] Syntax error\nTEST FAILED\n')
        result = self.summary()
        self.assertEqual(result['status'], 'failure_evidence')
        self.assertEqual(result['phase_hint'], 'compile')
        self.assertEqual(result['first_error']['line'], 2)
        self.assertEqual(result['diagnostics'][0]['count'], 2)
        self.assertIn('missing semicolon', str(result['diagnostics'][0]['excerpt']))
        self.assertEqual(result['diagnostics'][0]['last_line'], 5)

    def test_addresses_are_not_normalized_together(self):
        self.write('ERROR: mismatch at 0x1000\nERROR: mismatch at 0x2000\n')
        self.assertEqual(len(self.summary()['diagnostics']), 2)

    def test_error_and_pass_are_conflicting(self):
        self.write('UVM_ERROR file.sv(4) @ 5: [BAD] mismatch\nTEST PASSED\n')
        self.assertEqual(self.summary()['status'], 'conflicting')
        self.write('TEST FAILED\nTEST PASSED\n')
        self.assertEqual(self.summary()['status'], 'conflicting')

    def test_positive_uvm_summary_and_process_failure(self):
        for text in ('UVM_FATAL : 2\n', 'Exited with exit code 7\n',
                     'xmelab: *E,CUVMUR: unresolved instance\n',
                     'License checkout failed\n', 'Segmentation fault\n'):
            with self.subTest(text=text):
                self.write(text)
                self.assertEqual(self.summary()['status'], 'failure_evidence')

    def test_reported_pass_requires_complete_read(self):
        self.write('TEST PASSED\n' + 'filler\n' * 100)
        self.assertEqual(self.summary()['status'], 'reported_pass')
        incomplete = self.summary(max_scan_bytes=20)
        self.assertFalse(incomplete['scan_complete'])
        self.assertFalse(incomplete['tail_is_file_end'])
        self.assertEqual(incomplete['status'], 'unknown')
        self.assertIsNone(incomplete['sha256'])

    def test_late_failure_is_found_without_returning_the_log(self):
        self.write('ordinary progress\n' * 10000 + 'UVM_FATAL end.sv(8) @ 9: [BAD] failed\n')
        result = self.summary()
        self.assertEqual(result['first_error']['line'], 10001)
        self.assertTrue(result['scan_complete'])
        self.assertLess(len(json.dumps(result)), 12000)

    def test_range_preserves_ansi_while_summary_normalizes_it(self):
        self.write('\x1b[31mERROR: broken\x1b[0m\n')
        self.assertEqual(self.summary()['first_error']['text'], 'ERROR: broken')
        raw = logs.read_range(self.root, 'sim.log', 1, 1)
        self.assertIn('\x1b[31m', raw['lines'][0]['text'])

    def test_change_during_scan_prevents_pass(self):
        self.write('TEST PASSED\nold content\n')
        original = logs.Scan.rows
        def changing(scan):
            for number, text in original(scan):
                if number == 1:
                    self.write('TEST PASSED\nnew content appended\n')
                yield number, text
        with patch.object(logs.Scan, 'rows', changing):
            result = self.summary()
        self.assertFalse(result['stable'])
        self.assertEqual(result['status'], 'unknown')

    def test_group_and_output_limits_are_explicit(self):
        self.write(''.join('ERROR: '+str(i)+'x'*1000+'\n' for i in range(50)))
        result = self.summary(max_groups=20, max_output_chars=4000)
        self.assertEqual(result['diagnostic_counts']['error'], 50)
        self.assertGreater(result['omitted_diagnostic_events'], 0)
        self.assertTrue(result['output_truncated'])
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False)), 4000)
        self.assertEqual(result['first_error']['line'], 1)

    def test_ranges_reject_stale_evidence(self):
        self.write('one\ntwo\nthree\nfour\n')
        summary = self.summary()
        result = logs.read_range(self.root, 'sim.log', 2, 2,
                                expected_fingerprint=summary['fingerprint'])
        self.assertEqual([r['text'] for r in result['lines']], ['two', 'three'])
        self.assertEqual(result['next_line'], 4)
        self.assertLess(result['scanned_bytes'], self.file.stat().st_size)
        self.write('one\nNEW\nthree\nfour\n')
        with self.assertRaisesRegex(ValueError, 'stale'):
            logs.read_range(self.root, 'sim.log', 2, expected_fingerprint=summary['fingerprint'])

    def test_long_line_can_be_expanded_in_character_chunks(self):
        text = 'abcdef' * 3000
        self.write(text+'\nend\n')
        parts, column = [], 0
        while True:
            result = logs.read_range(self.root, 'sim.log', 1, 1,
                                     start_column=column, max_output_chars=4000)
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=False)), 4000)
            parts.extend(r['text'] for r in result['lines'])
            if result['next_line'] == 2:
                break
            self.assertGreater(result['next_column'], column)
            column = result['next_column']
        self.assertEqual(''.join(parts), text)

    def test_oversized_or_invalid_utf8_never_claim_pass(self):
        self.write('TEST PASSED\n' + 'x' * (logs.MAX_LINE_BYTES + 1) + '\n')
        self.assertEqual(self.summary()['stop_reason'], 'oversized_line')
        self.assertEqual(self.summary()['status'], 'unknown')
        self.file.write_bytes(b'TEST PASSED\n\xff\n')
        self.assertEqual(self.summary()['status'], 'unknown')

    def test_scope_and_parameter_validation(self):
        self.write('test\n')
        for path in ('../outside.log', str(self.root.parent/'outside.log')):
            with self.assertRaises((ValueError, FileNotFoundError)):
                logs.summarize(self.root, path)
        for kwargs in ({'max_groups': True}, {'context_lines': -1}, {'max_output_chars': 20}):
            with self.assertRaises(ValueError):
                self.summary(**kwargs)

    def test_symlink_cannot_escape_configured_root(self):
        with tempfile.TemporaryDirectory() as other:
            target = Path(other)/'outside.log'
            target.write_text('private')
            try:
                (self.root/'link.log').symlink_to(target)
            except OSError:
                self.skipTest('OS does not permit symlink creation')
            with self.assertRaises(ValueError):
                logs.summarize(self.root, 'link.log')


if __name__ == '__main__':
    unittest.main()
