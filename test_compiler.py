import unittest
from fz_compiler import FZCompiler


class MockBackend:
    """Мини-двойник FZBackend без PowerShell/CLI."""

    def __init__(self, monitors=None, layouts=None):
        self._monitors = monitors or []
        self._layouts = layouts or []
        self.cli_path = "FancyZonesCLI.exe"  # имитируем наличие CLI

    def get_monitors(self, force=False):
        return self._monitors

    def resolve_monitor(self, target):
        if target is None:
            return None, None
        t = str(target).strip()
        if t.lower() in ("all", "*"):
            return "all", None
        if t.isdigit():
            n = int(t)
            if n < 1:
                return None, f"Некорректный монитор '{t}': нумерация 1-based"
            if self._monitors and n > len(self._monitors):
                return None, f"Монитор '{t}' не найден"
            return n, None
        lowered = t.lower()
        exact = [m for m in self._monitors if m["name"].lower() == lowered]
        partial = [m for m in self._monitors if lowered in m["name"].lower()]
        chosen = exact[0] if exact else (partial[0] if len(partial) == 1 else None)
        if chosen:
            return chosen["number"], None
        return None, f"Монитор '{t}' не найден"

    def get_spacing_ref(self, monitor_spec):
        if not self._monitors:
            return 1920, 1080
        target = None
        if isinstance(monitor_spec, int):
            target = next(
                (m for m in self._monitors if m["number"] == monitor_spec), None
            )
        if target is None:
            target = next(
                (m for m in self._monitors if m.get("selected")), self._monitors[0]
            )
        return target["width"], target["height"]

    def get_custom_layouts(self):
        return self._layouts

    def get_layout_by_name(self, name):
        for l in self._layouts:
            if l.get("name", "").lower() == name.strip().lower():
                return l
        return None


TWO_MONITORS = [
    {
        "number": 1,
        "name": "MSI3DE1",
        "serial": "DE1M125600505",
        "width": 2560,
        "height": 1440,
        "position": (0, 0),
        "selected": True,
    },
    {
        "number": 2,
        "name": "BNQ78DD",
        "serial": "R7G03489019",
        "width": 1920,
        "height": 1080,
        "position": (-1920, 156),
        "selected": False,
    },
]

SAVED_GRID_LAYOUT = {
    "uuid": "{19AF681F-053C-40E1-A120-D67C9FF16B46}",
    "name": "Master L",
    "type": "grid",
    "info": {
        "rows": 1,
        "columns": 2,
        "rows-percentage": [10000],
        "columns-percentage": [7500, 2500],
        "cell-child-map": [[0, 1]],
        "show-spacing": True,
        "spacing": 16,
        "sensitivity-radius": 20,
    },
}


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

    # ------------------------------------------------------------------ #
    #  Персональные Temp-слоты по мониторам
    # ------------------------------------------------------------------ #

    def test_temp_slot_per_monitor(self):
        backend = MockBackend(TWO_MONITORS)
        parsed, err = FZCompiler.parse_command("1+1 -m 2", backend)
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed, backend)
        self.assertIsNone(comp_err)
        self.assertEqual(
            layout["uuid"], "{00000000-0000-0000-0000-000000000002}"
        )
        self.assertEqual(layout["name"], "Temp 2")

    def test_temp_slot_default_uses_selected_monitor(self):
        monitors = [
            dict(TWO_MONITORS[0], selected=False),
            dict(TWO_MONITORS[1], selected=True),
        ]
        backend = MockBackend(monitors)
        parsed, err = FZCompiler.parse_command("1+1", backend)
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed, backend)
        self.assertIsNone(comp_err)
        self.assertEqual(layout["name"], "Temp 2")

    def test_temp_slot_all_is_shared(self):
        backend = MockBackend(TWO_MONITORS)
        parsed, err = FZCompiler.parse_command("1+1 -m all", backend)
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed, backend)
        self.assertIsNone(comp_err)
        self.assertEqual(layout["uuid"], FZCompiler.TEMP_UUID)
        self.assertEqual(layout["name"], "Temp")

    def test_named_layout_not_renamed_to_slot(self):
        backend = MockBackend(TWO_MONITORS)
        parsed, err = FZCompiler.parse_command("1+1 -m 2 MyGrid", backend)
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed, backend)
        self.assertIsNone(comp_err)
        self.assertEqual(layout["name"], "MyGrid")
        self.assertNotEqual(
            layout["uuid"], "{00000000-0000-0000-0000-000000000002}"
        )

    def test_canvas_temp_slot(self):
        backend = MockBackend(TWO_MONITORS)
        parsed, err = FZCompiler.parse_command("0+1 -m 2", backend)
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed, backend)
        self.assertIsNone(comp_err)
        self.assertEqual(layout["type"], "canvas")
        self.assertEqual(layout["uuid"], "{00000000-0000-0000-0000-000000000002}")

    # ------------------------------------------------------------------ #
    #  Эвристика «формула или имя»
    # ------------------------------------------------------------------ #

    def test_looks_like_dsl(self):
        self.assertTrue(FZCompiler.looks_like_dsl("2x2"))
        self.assertTrue(FZCompiler.looks_like_dsl("1+2"))
        self.assertTrue(FZCompiler.looks_like_dsl("{3:1}"))          # одиночный блок
        self.assertTrue(FZCompiler.looks_like_dsl("0(5)"))           # одиночный блок с весом
        self.assertTrue(FZCompiler.looks_like_dsl("A B | C D"))
        self.assertTrue(FZCompiler.looks_like_dsl("A > B"))
        self.assertFalse(FZCompiler.looks_like_dsl("Master L"))
        self.assertFalse(FZCompiler.looks_like_dsl("Solo"))
        self.assertFalse(FZCompiler.looks_like_dsl(""))

    # ------------------------------------------------------------------ #
    #  Валидация флагов
    # ------------------------------------------------------------------ #

    def test_flag_validation(self):
        _, err = FZCompiler.parse_command("1+1 -s abc")
        self.assertIsNotNone(err)
        self.assertIn("-s", err)

        _, err = FZCompiler.parse_command("1+1 -k 55")
        self.assertIsNotNone(err)
        self.assertIn("-k", err)

        _, err = FZCompiler.parse_command("1+1 -x 3")
        self.assertIsNotNone(err)
        self.assertIn("-x", err)

        parsed, err = FZCompiler.parse_command("1+1 -s 8 -k 2")
        self.assertIsNone(err)
        self.assertEqual(parsed["spacing"], 8)
        self.assertEqual(parsed["hotkey"], 2)

    def test_monitor_flag(self):
        backend = MockBackend(TWO_MONITORS)
        parsed, err = FZCompiler.parse_command("2x2 -m all", backend)
        self.assertIsNone(err)
        self.assertEqual(parsed["monitor"], "all")

        parsed, err = FZCompiler.parse_command("2x2 -m 2", backend)
        self.assertIsNone(err)
        self.assertEqual(parsed["monitor"], 2)

        parsed, err = FZCompiler.parse_command("2x2 -m msi", backend)
        self.assertIsNone(err)
        self.assertEqual(parsed["monitor"], 1)

        _, err = FZCompiler.parse_command("2x2 -m 0", backend)
        self.assertIsNotNone(err)
        self.assertIn("1-based", err)

        _, err = FZCompiler.parse_command("2x2 -m 9", backend)
        self.assertIsNotNone(err)

        _, err = FZCompiler.parse_command("2x2 -m unknown", backend)
        self.assertIsNotNone(err)

    def test_monitor_flag_without_backend(self):
        parsed, err = FZCompiler.parse_command("2x2 -m all")
        self.assertIsNone(err)
        self.assertEqual(parsed["monitor"], "all")

        parsed, err = FZCompiler.parse_command("2x2 -m 3")
        self.assertIsNone(err)
        self.assertEqual(parsed["monitor"], 3)

        _, err = FZCompiler.parse_command("2x2 -m 0")
        self.assertIsNotNone(err)

    # ------------------------------------------------------------------ #
    #  Отступ canvas по реальному разрешению монитора
    # ------------------------------------------------------------------ #

    def test_spacing_uses_real_monitor_resolution(self):
        backend = MockBackend(TWO_MONITORS)
        parsed, err = FZCompiler.parse_command("0 + 1 -s 16", backend)
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed, backend)
        self.assertIsNone(comp_err)
        self.assertEqual(layout["type"], "canvas")
        zone = layout["info"]["zones"][0]
        # 2560x1440 (выбранный монитор): sx=round(16*10000/2560)=62, sy=111
        # срез 2 из 2: X начинается с 5000 + sx//2, ширина 5000 - sx
        self.assertEqual(zone["X"], 5031)
        self.assertEqual(zone["width"], 4938)
        self.assertEqual(zone["Y"], 55)
        self.assertEqual(zone["height"], 9889)

    def test_spacing_for_second_monitor_differs(self):
        backend = MockBackend(TWO_MONITORS)
        parsed, err = FZCompiler.parse_command("0 + 1 -s 16 -m 2", backend)
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed, backend)
        self.assertIsNone(comp_err)
        zone = layout["info"]["zones"][0]
        # 1920x1080: sx=83, sy=148 -> X=5000+41=5041, width=5000-83=4917
        self.assertEqual(zone["X"], 5041)
        self.assertEqual(zone["width"], 4917)

    # ------------------------------------------------------------------ #
    #  Валидация геометрии
    # ------------------------------------------------------------------ #

    def test_zero_weight_error(self):
        parsed, err = FZCompiler.parse_command("1(0)+1")
        self.assertIsNone(err)
        _, comp_err = FZCompiler.compile(parsed)
        self.assertIsNotNone(comp_err)
        self.assertIn("вес", comp_err.lower())

        parsed, err = FZCompiler.parse_command("{1:0(0):1}")
        self.assertIsNone(err)
        _, comp_err = FZCompiler.compile(parsed)
        self.assertIsNotNone(comp_err)

    def test_zero_grid_dims_error(self):
        parsed, err = FZCompiler.parse_command("0x2")
        self.assertIsNone(err)
        _, comp_err = FZCompiler.compile(parsed)
        self.assertIsNotNone(comp_err)

    def test_matrix_non_rect_error(self):
        # A занимает L-образные клетки -> не прямоугольник
        parsed, err = FZCompiler.parse_command("A A | A B")
        self.assertIsNone(err)
        _, comp_err = FZCompiler.compile(parsed)
        self.assertIsNotNone(comp_err)
        self.assertIn("прямоугольник", comp_err)

    def test_matrix_rect_ok(self):
        parsed, err = FZCompiler.parse_command("A A | A A")
        self.assertIsNone(err)
        layout, comp_err = FZCompiler.compile(parsed)
        self.assertIsNone(comp_err)
        self.assertEqual(len(layout["info"]["cell-child-map"]), 2)

    # ------------------------------------------------------------------ #
    #  Слои
    # ------------------------------------------------------------------ #

    def test_layered_with_saved_layout(self):
        backend = MockBackend(TWO_MONITORS, [SAVED_GRID_LAYOUT])
        parsed, err = FZCompiler.parse_command("Master L > 1 Combined", backend)
        self.assertIsNone(err)
        self.assertEqual(parsed["mode"], "layered")
        self.assertEqual(parsed["layers"], ["Master L", "1"])
        self.assertEqual(parsed["name"], "Combined")
        layout, comp_err = FZCompiler.compile(parsed, backend)
        self.assertIsNone(comp_err)
        self.assertEqual(layout["type"], "canvas")
        # 2 зоны из сохраненного grid + 1 зона из формулы '1'
        self.assertEqual(len(layout["info"]["zones"]), 3)

    def test_layered_unknown_layer_error(self):
        backend = MockBackend(TWO_MONITORS, [])
        parsed, err = FZCompiler.parse_command("NoSuch > 1", backend)
        self.assertIsNone(err)
        _, comp_err = FZCompiler.compile(parsed, backend)
        self.assertIsNotNone(comp_err)


if __name__ == "__main__":
    unittest.main()
