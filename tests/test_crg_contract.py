"""CRG-generated register ports must match its top and child failures must propagate."""
import ast
import copy
import getpass
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime

from claude_kit.adaptations import export_adapted


class CrgContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        target = Path(cls.directory.name) / 'adapted'
        export_adapted(target)
        cls.scripts = target / 'source/.agents/skills/crg-gen/scripts'

    def namespace(self, script):
        tree = ast.parse((self.scripts / script).read_text(encoding='utf-8'))
        # License/dependency-free function tests: no pandas/YAML/EDA imports.
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        namespace = {'sys': sys, 'os': os, 'datetime': datetime, 'getpass': getpass}
        exec(compile(tree, script, 'exec'), namespace)
        return namespace

    def fixture(self):
        return {'name': 'demo', 'registers': [
            {'name': 'first', 'offset': 0, 'fields': [
                {'name': 'status', 'access': 'ro', 'bits': 1, 'lsb': 0, 'reset': 0}]},
            {'name': 'second', 'offset': 4, 'fields': [
                {'name': 'status', 'access': 'ro', 'bits': 1, 'lsb': 0, 'reset': 0}]},
        ]}

    def test_register_qualified_ports_preserve_two_readback_mappings(self):
        namespace = self.namespace('yml2reg/yml2reg.py')
        data = self.fixture()
        before = copy.deepcopy(data)
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                namespace['yml2regfile'](data, 'apb')
                output = Path('DEMO_apb_regfile.v').read_text()
            finally:
                os.chdir(previous)
        header = output.split(');', 1)[0]
        for name in ['first', 'second']:
            self.assertRegex(header, r'input\s+' + name + '_status,?')
            self.assertRegex(output, name + r'_rdata\[0:0\]\s*=\s*' + name + '_status;')
        self.assertNotRegex(header, r'input\s+status[,\s]')
        self.assertEqual(data, before, 'Approved input model must not be mutated')

    def test_unimplemented_bus_rejected_before_replacing_existing_output(self):
        namespace = self.namespace('yml2reg/yml2reg.py')
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                for protocol in ['ahb', 'dab']:
                    target = Path('DEMO_' + protocol + '_regfile.v')
                    target.write_text('existing accepted design\n')
                    with self.subTest(protocol=protocol), self.assertRaisesRegex(ValueError, 'APB'):
                        namespace['yml2regfile'](self.fixture(), protocol)
                    self.assertEqual(target.read_text(), 'existing accepted design\n')
            finally:
                os.chdir(previous)

    def test_generator_child_nonzero_is_not_success(self):
        namespace = self.namespace('crg_gen.py')
        self.assertTrue(callable(namespace.get('_run_generator')), 'Missing checked child runner')
        with tempfile.TemporaryDirectory(prefix='crg child ') as directory:
            source = Path(directory) / 'child with spaces.py'
            source.write_text('raise SystemExit(7)\n')
            with self.assertRaises(subprocess.CalledProcessError) as context:
                namespace['_run_generator'](str(source), cwd=directory)
            self.assertEqual(context.exception.returncode, 7)

    def test_csv_module_and_apb_ports_match_regfile_preserving_instance_paths(self):
        namespace = self.namespace('crg_gen.py')
        convert = namespace['_crg_register_csv_contract']
        bus = {'clk': 'apb_clk', 'rst_n': 'apb_rst_n', 'psel': 'apb_sel',
               'penable': 'apb_enable', 'pwrite': 'apb_write', 'paddr': 'apb_addr',
               'pwdata': 'apb_wdata', 'prdata': 'apb_rdata', 'pready': 'apb_ready',
               'pslverr': 'apb_slverr'}
        inputs = ['inst DEMO_apb_reg u_DEMO_apb_reg',
                  'connect,DEMO_apb_reg.first_status  ,first,W,input,',
                  'connect,DEMO_apb_regfile.second_status,second,W,input,',
                  'connect,OTHER_apb_reg.clk,other,I,input,', '#user_code kept']
        inputs += ['connect,DEMO_apb_reg.' + port + '  ,wire_' + port + ',I,input,' for port in bus]
        before = list(inputs)
        output = convert(inputs, 'demo', 'apb')
        self.assertEqual(output[0], 'inst DEMO_apb_regfile u_DEMO_apb_reg')
        self.assertEqual(output[1], 'connect,DEMO_apb_regfile.first_status,first,W,input,')
        self.assertEqual(output[2:5], inputs[2:5])
        for index, (old, new) in enumerate(bus.items(), 5):
            self.assertEqual(output[index], 'connect,DEMO_apb_regfile.' + new + ',wire_' + old + ',I,input,')
        self.assertEqual(inputs, before)
        self.assertEqual(convert(output, 'demo', 'apb'), output)
        self.assertEqual(convert(inputs, 'demo', 'ahb'), inputs)


if __name__ == '__main__':
    unittest.main()
