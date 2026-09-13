"""Exercise catalog selection without importing optional EDA/Excel packages."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
import math
import tempfile
from datetime import datetime

SOURCE = Path(__file__).resolve().parents[1] / 'src/claude_kit/resources/upstream/vibe_soc/source/.agents/skills/gen-memwrap/scripts/gen_memwrap.py'

class CapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='match_macro')
        fn.returns=None
        for arg in fn.args.args: arg.annotation=None
        namespace={}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(SOURCE),'exec'),namespace)
        cls.match=staticmethod(namespace['match_macro'])
        names={'emit_capacity_wrap','emit_spram_wrap_fakeram','emit_spram_wrap_openram',
               'emit_tpram_wrap_openram','emit_beh_spram','addr_width','header_lines','write_text'}
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        for function in functions:
            function.returns=None
            for arg in function.args.args: arg.annotation=None
        namespace.update(math=math,datetime=datetime)
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(SOURCE),'exec'),namespace)
        cls.emit=staticmethod(namespace['emit_capacity_wrap'])
        cls.emit_model=staticmethod(namespace['emit_beh_spram'])

    def macro(self,name,depth,width,ports='1rw'):
        return SimpleNamespace(name=name,depth=depth,width=width,ports=ports)

    def test_nearest_area_must_not_reduce_depth(self):
        small=self.macro('small',32,64)
        large=self.macro('large',128,32)
        self.assertIs(self.match([small,large],96,24,strict=False),large)

    def test_insufficient_dimensions_are_rejected(self):
        for depth,width in [(32,64),(128,16)]:
            with self.assertRaises(ValueError):
                self.match([self.macro('bad',depth,width)],96,24,strict=False)

    def test_ports_cannot_silently_fall_back(self):
        with self.assertRaises(ValueError):
            self.match([self.macro('bad',128,32)],128,32,want_ports='1rw1r')

    def test_explicit_name_cannot_override_capacity(self):
        with self.assertRaises(ValueError):
            self.match([self.macro('small',32,64)],96,24,exact_name='small',strict=False)

    def test_exact_match_preserved(self):
        macro=self.macro('exact',96,24)
        self.assertIs(self.match([macro],96,24),macro)

    def test_logical_interface_is_not_resized(self):
        macro=self.macro('physical_ram',128,32)
        macro.write_size=1
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wrapper.v'
            self.emit(path,'logical_ram',macro,96,24,True,'nangate45')
            source=path.read_text(encoding='utf-8')
            logical=source.split('endmodule',1)[0]
            self.assertIn('input [6:0] addr',logical)
            self.assertIn('input [23:0] din',logical)
            self.assertIn(".din({8'b0, din})",logical)
            self.assertIn('physical_dout[23:0]',logical)
            self.assertIn("< 8'd96",logical)

    def test_dual_port_clock_and_address_padding(self):
        macro=self.macro('physical_ram',256,64,'1rw1r')
        macro.write_size=8
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wrapper.v'
            self.emit(path,'logical_ram',macro,64,32,True,'sky130',dual=True,async_clk=True)
            logical=path.read_text(encoding='utf-8').split('endmodule',1)[0]
            self.assertIn('input clka',logical)
            self.assertIn('input clkb',logical)
            self.assertIn(".addra({2'b0, addra})",logical)
            self.assertIn(".addrb({2'b0, addrb})",logical)
            self.assertIn('input [3:0] wem',logical)

    def test_partial_logical_byte_and_whole_physical_mask(self):
        macro=self.macro('physical_ram',128,32,'1rw1r')
        macro.write_size=8
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wrapper.v'
            self.emit(path,'logical_ram',macro,96,19,True,'sky130')
            logical=path.read_text(encoding='utf-8').split('endmodule',1)[0]
            self.assertIn('input [2:0] wem',logical)
            self.assertIn(".wem({1'b0, wem})",logical)

    def test_physical_fakeram_masks_every_bit(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.v'
            self.emit_model(path,'physical_ram',128,32,32)
            source=path.read_text(encoding='utf-8')
            self.assertIn('input  [31:0] w_mask_in',source)
            self.assertIn('w_mask_in[i]',source)

if __name__=='__main__': unittest.main()
