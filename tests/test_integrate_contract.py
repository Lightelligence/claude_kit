"""Generated RTL and integration state must preserve the declared interface."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from claude_kit.adaptations import export_adapted


class IntegrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        target = Path(cls.directory.name) / 'adapted'
        export_adapted(target)
        cls.script = target / 'source/.agents/skills/soc-integrate/scripts/soc_integrate.py'
        spec = importlib.util.spec_from_file_location('tested_integrate', cls.script)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def parse(self, declarations):
        return self.module.parse_module('dut', f'module dut({declarations}); endmodule')

    def test_ansi_continuation_ports_preserve_all_fields(self):
        parsed = self.parse('input logic clk, rst_n, input wire [7:0] a, b, output logic ack')
        self.assertEqual(parsed.ports, [('input', '', 'clk'), ('input', '', 'rst_n'),
            ('input', '[7:0]', 'a'), ('input', '[7:0]', 'b'), ('output', '', 'ack')])

    def test_unsupported_declarations_do_not_become_truncated_ports(self):
        for declaration in ['input logic [7:0] data [0:3]', 'input int count',
            'input custom_t item', 'input logic [1:0][7:0] packed_bus',
            'input pkg::word_t item', 'a, y']:
            with self.subTest(declaration=declaration), self.assertRaises(ValueError):
                self.parse(declaration)

    def test_wrapper_keeps_parameter_declaration_and_child_override(self):
        parsed = self.module.parse_module('dut', 'module dut #(parameter W=8)('
            'input logic [W-1:0] d, output logic [W-1:0] q); assign q=d; endmodule')
        generated = self.module.generate_wrapper(parsed, 'dut_wrapper')
        header = generated.split(');', 1)[0]
        self.assertRegex(header, r'module dut_wrapper\s*#\s*\(')
        self.assertRegex(header, r'parameter\s+W\s*=\s*8')
        self.assertRegex(header, r'input\s+\[W-1:0\]\s+d')
        self.assertRegex(generated, r'\.W\s*\(W\)')
        self.assertRegex(generated, r'\.d\s*\(d(?:\[W-1:0\])?\)')

    def test_remove_does_not_reimport_removed_module_mappings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            producer = root / 'producer.sv'
            consumer = root / 'consumer.sv'
            producer.write_text('module producer(input clk, output [7:0] data); endmodule')
            consumer.write_text('module consumer(input clk, input [7:0] data, output ack); endmodule')
            mapping = root / 'map.json'
            mapping.write_text(json.dumps({'mappings': {'producer.data': 'payload', 'consumer.data': 'payload'}}))
            top = root / 'dut_top.sv'
            config = root / 'dut_top.integrate.json'

            def invoke(*args):
                result = subprocess.run([sys.executable, str(self.script), *map(str, args)],
                    cwd=root, env={**os.environ, 'PYTHONUTF8': '1'}, capture_output=True,
                    text=True, encoding='utf-8', timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            invoke('integrate', producer, consumer, '-n', 'dut_top', '-o', top, '--map', mapping)
            invoke('remove', config, 'consumer')
            value = json.loads(config.read_text())
            self.assertEqual([item['module_name'] for item in value['modules']], ['producer'])
            self.assertEqual(value['mappings']['producer.data'], 'payload')
            self.assertFalse(any(key.startswith('consumer.') for key in value['mappings']))
            self.assertFalse(any(item.startswith('consumer.') for values in value['shared_signals'].values() for item in values))
            self.assertNotIn('consumer', value['port_snapshot'])
            self.assertIsNone(re.search(r'consumer\s+u_consumer', top.read_text()))


if __name__ == '__main__':
    unittest.main()
