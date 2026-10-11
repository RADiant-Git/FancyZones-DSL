import unittest
from fz_compiler import FZCompiler


class TestFZCompiler(unittest.TestCase):

    def test_quick_grid(self):
        parsed, err = FZCompiler.parse_command("2x2 -s 0")
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed)
        self.assertIsNone(comp_err)
        self.assertEqual(layout["type"], "grid")
        self.assertEqual(len(layout["info"]["cell-child-map"]), 2)

    def test_columns_planar(self):
        parsed, err = FZCompiler.parse_command("1 + 2 + 1 TestCol")
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed)
        self.assertIsNone(comp_err)
        self.assertEqual(layout["type"], "grid")
        self.assertEqual(layout["name"], "TestCol")

    def test_void_column(self):
        parsed, err = FZCompiler.parse_command("0(1) + 1(2) + 0(1)")
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed)
        self.assertIsNone(comp_err)
        # При наличии пустот макет ОБЯЗАН стать canvas
        self.assertEqual(layout["type"], "canvas")
        # Из 3 срезов только 1 активная зона
        self.assertEqual(len(layout["info"]["zones"]), 1)

    def test_void_internal(self):
        parsed, err = FZCompiler.parse_command("{1:0(2):1} VoidStack")
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed)
        self.assertIsNone(comp_err)
        self.assertEqual(layout["type"], "canvas")
        # 2 активные зоны (пустота по центру пропущена)
        self.assertEqual(len(layout["info"]["zones"]), 2)

    def test_matrix_with_void(self):
        parsed, err = FZCompiler.parse_command("A 0 B | C 0 D")
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed)
        self.assertIsNone(comp_err)
        self.assertEqual(layout["type"], "canvas")
        self.assertEqual(len(layout["info"]["zones"]), 4)

    def test_temp_uuid(self):
        parsed, err = FZCompiler.parse_command("1+2")
        self.assertEqual(parsed["name"], "Temp")
        layout, comp_err = FZCompiler.compile(parsed)
        self.assertEqual(layout["uuid"], FZCompiler.TEMP_UUID)


if __name__ == "__main__":
    unittest.main()