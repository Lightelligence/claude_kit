"""Liberty stubs must preserve supported port widths or reject unsupported syntax."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

from claude_kit.adaptations import export_adapted


class LibraryStubPortsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        target = Path(cls.directory.name) / 'adapted'
        export_adapted(target)
        path = target / 'source/.agents/skills/lib-db-gen/scripts/lib_db_gen.py'
        spec = importlib.util.spec_from_file_location('tested_lib_stub', path)
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        cls.addClassCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(cls.module)

    def parse(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dut.sv'
            path.write_text(content, encoding='utf-8')
            return self.module.parse_verilog_ports(path, 'dut')

    def test_numeric_bus_whitespace_and_continuation(self):
        for declaration in ['input logic [7:0] a,b', 'input logic [7 : 0] a,b',
                            'input logic [ 7 : 0 ] a,b', 'input logic[7:0]a,b']:
            with self.subTest(declaration=declaration):
                _, ports, warnings = self.parse(f'module dut({declaration}, output ack); endmodule')
                self.assertEqual([(p.name, p.direction, p.width) for p in ports],
                                 [('a', 'input', 8), ('b', 'input', 8), ('ack', 'output', 1)])
                self.assertEqual(warnings, [])
                liberty = self.module.generate_stub_lib('test_lib', 'dut', ports)
                self.assertIn('bus (a)', liberty)
                self.assertIn('bit_width : 8;', liberty)

    def test_non_ansi_bus_whitespace(self):
        _, ports, warnings = self.parse('module dut(a,b,ack); input logic [7 : 0] a,b; output ack; endmodule')
        self.assertEqual([(p.name, p.width) for p in ports], [('a', 8), ('b', 8), ('ack', 1)])
        self.assertEqual(warnings, [])

    def test_unsupported_types_and_dimensions_fail(self):
        declarations = ['input logic [7:0] data [0:3]', 'input int count',
                        'input pkg::word_t data', 'input custom_t data', 'input logic [1:0][7:0] data']
        for declaration in declarations:
            for old_style in [False, True]:
                name = 'count' if 'count' in declaration else 'data'
                text = (f'module dut({name},ack); {declaration}; output ack; endmodule' if old_style
                        else f'module dut({declaration}, output ack); endmodule')
                with self.subTest(declaration=declaration, old_style=old_style), self.assertRaises(ValueError):
                    self.parse(text)

    def test_symbolic_width_retains_explicit_existing_warning(self):
        _, ports, warnings = self.parse('module dut #(parameter W=8)(input [W-1:0] data, output ack); endmodule')
        self.assertEqual([p.name for p in ports], ['data', 'ack'])
        self.assertEqual(ports[0].range_text, '[W-1:0]')
        self.assertEqual(len(warnings), 1)
        self.assertIn('scalar', warnings[0])

    def test_undeclared_non_ansi_header_port_is_not_dropped(self):
        with self.assertRaises(ValueError):
            self.parse('module dut(a,missing,ack); input a; output ack; endmodule')


if __name__ == '__main__':
    unittest.main()
