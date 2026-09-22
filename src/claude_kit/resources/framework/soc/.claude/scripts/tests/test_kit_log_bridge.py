"""Run the real registered launcher with isolated synthetic logs; no EDA execution."""
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from framework_project import project_root


class BridgeContractTest(unittest.TestCase):
    def test_registered_stdio_tools_and_readonly_boundaries(self):
        root = project_root()
        if not (root/'third_party/claude_kit/src/claude_kit').is_dir():
            self.skipTest('Requires the pinned kit checkout (run on ETX)')
        with tempfile.TemporaryDirectory(prefix='dv-log-contract-') as temp:
            regression = Path(temp)
            run = regression/'sys__vcs__case__123'
            run.mkdir()
            log = run/'sim.log'
            log.write_text('UVM_INFO startup\nUVM_ERROR t.sv(2) @ 1: [BAD] mismatch\nTEST FAILED\n')
            env = dict(os.environ, REGRESSION_ROOT=str(regression), PYTHONDONTWRITEBYTECODE='1')
            process = subprocess.Popen(['sh', '.claude/kit-mcp.sh'], cwd=root, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            replies, errors = queue.Queue(), []
            def read_stdout():
                for line in process.stdout:
                    replies.put(json.loads(line))
            def read_stderr():
                for line in process.stderr:
                    if len(errors) < 20:
                        errors.append(line)
            readers = [threading.Thread(target=read_stdout, daemon=True),
                       threading.Thread(target=read_stderr, daemon=True)]
            for reader in readers:
                reader.start()
            next_id = 0
            def request(method, params):
                nonlocal next_id
                next_id += 1
                process.stdin.write(json.dumps({'jsonrpc':'2.0', 'id':next_id,
                    'method':method, 'params':params})+'\n')
                process.stdin.flush()
                try:
                    response = replies.get(timeout=20)
                except queue.Empty:
                    self.fail('MCP response timed out: '+''.join(errors))
                self.assertEqual(response['id'], next_id)
                return response
            def call(name, **args):
                response = request('tools/call', {'name':name, 'arguments':args})
                self.assertNotIn('error', response, response)
                return json.loads(response['result']['content'][0]['text'])
            try:
                request('initialize', {'protocolVersion':'2025-06-18','capabilities':{},
                    'clientInfo':{'name':'log-contract-test','version':'1'}})
                listed = request('tools/list', {})['result']['tools']
                names = {tool['name'] for tool in listed}
                self.assertTrue({'discover_regression_artifacts','read_regression_artifact',
                    'summarize_regression_log','read_regression_log_range','get_project_profile'} <= names, names)
                self.assertNotIn('run_check', names)
                found = call('discover_regression_artifacts', kind='simulation', test='case', run_id='123')
                self.assertEqual(len(found['artifacts']), 1)
                selected = found['artifacts'][0]['primary_log']
                summary = call('summarize_regression_log', path=selected)
                self.assertEqual(summary['status'], 'failure_evidence')
                detail = call('read_regression_log_range', path=selected, start_line=2, line_count=1,
                              expected_fingerprint=summary['fingerprint'])
                self.assertIn('[BAD] mismatch', detail['lines'][0]['text'])
                original = call('read_regression_artifact', path=selected, max_bytes=8)
                self.assertEqual(original['text'], 'UVM_INFO')
                log.write_text('x' * 20000)
                bounded = call('read_regression_artifact', path=selected)
                self.assertEqual(bounded['bytes'], 20000)
                self.assertEqual(bounded['bytes_read'], 12000)
                self.assertEqual(len(bounded['text']), 12000)
                self.assertTrue(bounded['truncated'])
                self.assertTrue(bounded['stable'])
                self.assertEqual(call('read_regression_artifact', path=selected, max_bytes=0)['text'], '')
                schema = next(t for t in listed if t['name'] == 'read_regression_artifact')
                self.assertEqual(schema['inputSchema']['properties']['max_bytes']['default'], 12000)
                context = call('resolve_context', task='Inspect one selected source')
                self.assertEqual(context['manifest']['roles'], [])
                self.assertEqual(context['manifest']['packs'], [])
                self.assertEqual(context['manifest']['skills'], [])
                explicit = call('resolve_context', task='Review RTL', roles=['reviewer'])
                self.assertEqual(explicit['manifest']['roles'], ['reviewer'])
                for name, arguments in [('resolve_context', {}),
                                        ('resolve_context', {'task': 'Review RTL', 'roles': None}),
                                        ('read_regression_artifact', {'path': selected, 'max_bytes': True}),
                                        ('read_regression_artifact', {'path': '../outside.log'}),
                                        ('read_artifact', {'path': '../outside.log'})]:
                    self.assertIn('error', request('tools/call', {'name': name, 'arguments': arguments}))
                log.write_text('TEST PASSED\n')
                stale = request('tools/call', {'name':'read_regression_log_range',
                    'arguments':{'path':selected,'start_line':2,'expected_fingerprint':summary['fingerprint']}})
                self.assertIn('error', stale)
                (regression/(run.name+'.run.lock')).touch()
                locked = call('summarize_regression_log', path=selected)
                self.assertTrue(locked['run_lock_present'])
                self.assertEqual(locked['status'], 'unknown')
                outside = request('tools/call', {'name':'summarize_regression_log',
                    'arguments':{'path':'../outside.log'}})
                self.assertIn('error', outside)
                invalid = request('tools/call', {'name':'summarize_regression_log',
                    'arguments':{'path':selected,'max_groups':True}})
                self.assertIn('error', invalid)
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                for reader in readers:
                    reader.join(timeout=5)
                process.stdout.close()
                process.stderr.close()


if __name__ == '__main__':
    unittest.main()
