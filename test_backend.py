import json
import os
import shutil
import tempfile
import unittest

from fz_backend import FZBackend


SAMPLE_OUTPUT = """\
=== Monitors (2 total) ===

Monitor 1:
  Monitor: MSI3DE1
  Monitor Instance: 5&29139328&0&UID4353
  Monitor Number: 1
  Serial Number: DE1M125600505
  Virtual Desktop: {9262A3C2-8D8A-49BA-AB70-D7E1870B2211}
  DPI: 96
  Resolution: 2560x1440
  Work Area: 2560x1440
  Position: (0, 0)
  Selected: True

  Active Layout: custom
  Zone Count: 3
  Sensitivity Radius: 20px
  Layout UUID: {00000000-0000-0000-0000-000000000001}

Monitor 2:
  Monitor: BNQ78DD
  Monitor Instance: 5&29139328&0&UID4352
  Monitor Number: 2
  Serial Number: R7G03489019
  Virtual Desktop: {9262A3C2-8D8A-49BA-AB70-D7E1870B2211}
  DPI: 96
  Resolution: 1920x1080
  Work Area: 1920x1080
  Position: (-1920, 156)
  Selected: False

  Active Layout: custom
  Zone Count: 3
  Sensitivity Radius: 20px
"""


class TestParseMonitors(unittest.TestCase):
    def test_parse(self):
        monitors = FZBackend.parse_monitors_output(SAMPLE_OUTPUT)
        self.assertEqual(len(monitors), 2)

        m1 = monitors[0]
        self.assertEqual(m1["number"], 1)
        self.assertEqual(m1["name"], "MSI3DE1")
        self.assertEqual(m1["serial"], "DE1M125600505")
        self.assertEqual((m1["width"], m1["height"]), (2560, 1440))
        self.assertEqual(m1["position"], (0, 0))
        self.assertTrue(m1["selected"])

        m2 = monitors[1]
        self.assertEqual(m2["name"], "BNQ78DD")
        self.assertEqual((m2["width"], m2["height"]), (1920, 1080))
        self.assertEqual(m2["position"], (-1920, 156))
        self.assertFalse(m2["selected"])

    def test_parse_empty(self):
        self.assertEqual(FZBackend.parse_monitors_output(""), [])


class TestApplyArgs(unittest.TestCase):
    def test_active_monitor_default(self):
        self.assertEqual(
            FZBackend.build_apply_args("{U}", None), ["s", "{U}"]
        )

    def test_all_flag(self):
        self.assertEqual(
            FZBackend.build_apply_args("{U}", "all"), ["s", "{U}", "--all"]
        )

    def test_monitor_number_1_based(self):
        self.assertEqual(
            FZBackend.build_apply_args("{U}", 2), ["s", "{U}", "--monitor", "2"]
        )

    def test_invalid_zero_is_dropped(self):
        # 0 — недопустимый индекс, аргумент не добавляется
        self.assertEqual(FZBackend.build_apply_args("{U}", 0), ["s", "{U}"])


class TestSpacingRef(unittest.TestCase):
    def setUp(self):
        self.backend = FZBackend.__new__(FZBackend)  # без __init__/CLI
        self.monitors = [
            {"number": 1, "name": "A", "serial": "", "width": 2560,
             "height": 1440, "position": (0, 0), "selected": False},
            {"number": 2, "name": "B", "serial": "", "width": 1920,
             "height": 1080, "position": (2560, 0), "selected": True},
        ]
        self.backend.get_monitors = lambda force=False: self.monitors

    def test_selected_for_default(self):
        self.assertEqual(self.backend.get_spacing_ref(None), (1920, 1080))

    def test_explicit_number(self):
        self.assertEqual(self.backend.get_spacing_ref(1), (2560, 1440))

    def test_all_uses_primary(self):
        # primary = позиция (0,0)
        self.assertEqual(self.backend.get_spacing_ref("all"), (2560, 1440))

    def test_unknown_number_falls_back_to_selected(self):
        self.assertEqual(self.backend.get_spacing_ref(99), (1920, 1080))

    def test_no_monitors_fallback(self):
        self.backend.get_monitors = lambda force=False: []
        self.assertEqual(self.backend.get_spacing_ref(None), (1920, 1080))


class TestResolveMonitor(unittest.TestCase):
    def setUp(self):
        self.backend = FZBackend.__new__(FZBackend)
        self.backend._log = lambda msg: None
        self.backend.get_monitors = lambda force=False: [
            {"number": 1, "name": "MSI3DE1", "serial": "DE1M125600505",
             "width": 2560, "height": 1440, "position": (0, 0), "selected": True},
            {"number": 2, "name": "BNQ78DD", "serial": "R7G03489019",
             "width": 1920, "height": 1080, "position": (-1920, 156),
             "selected": False},
        ]

    def test_none(self):
        self.assertEqual(self.backend.resolve_monitor(None), (None, None))

    def test_all(self):
        self.assertEqual(self.backend.resolve_monitor("all"), ("all", None))

    def test_number(self):
        self.assertEqual(self.backend.resolve_monitor("2"), (2, None))

    def test_zero_rejected(self):
        spec, err = self.backend.resolve_monitor("0")
        self.assertIsNone(spec)
        self.assertIn("1-based", err)

    def test_out_of_range(self):
        spec, err = self.backend.resolve_monitor("3")
        self.assertIsNone(spec)
        self.assertIn("не найден", err)

    def test_name_partial(self):
        self.assertEqual(self.backend.resolve_monitor("bnq"), (2, None))

    def test_name_full_ci(self):
        self.assertEqual(self.backend.resolve_monitor("msi3de1"), (1, None))

    def test_serial_partial(self):
        self.assertEqual(self.backend.resolve_monitor("R7G03489"), (2, None))

    def test_unknown_name(self):
        spec, err = self.backend.resolve_monitor("zzz")
        self.assertIsNone(spec)
        self.assertIn("не найден", err)


class TestProtectSharedSlot(unittest.TestCase):
    SLOT = "{00000000-0000-0000-0000-000000000001}"

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="fzdsl_test_")
        b = FZBackend.__new__(FZBackend)  # без поиска CLI
        b.fz_dir = self.dir
        b.custom_layouts_path = os.path.join(self.dir, "custom-layouts.json")
        b.applied_layouts_path = os.path.join(self.dir, "applied-layouts.json")
        b.cli_path = "fake"
        b._log = lambda msg: None
        self.backend = b
        self.applied_calls = []
        b.apply_layout = lambda u, m=None: (
            self.applied_calls.append((u, m)) or True
        )

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _seed(self, applied_entries):
        self._write(
            self.backend.custom_layouts_path,
            {
                "custom-layouts": [
                    {
                        "uuid": self.SLOT,
                        "name": "Temp",
                        "type": "grid",
                        "info": {
                            "rows": 1,
                            "columns": 2,
                            "rows-percentage": [10000],
                            "columns-percentage": [5000, 5000],
                            "cell-child-map": [[0, 1]],
                        },
                    }
                ]
            },
        )
        self._write(
            self.backend.applied_layouts_path,
            {"applied-layouts": applied_entries},
        )

    def test_migrates_other_monitors(self):
        self._seed(
            [
                {
                    "device": {"monitor-number": 1},
                    "applied-layout": {"uuid": self.SLOT},
                },
                {
                    "device": {"monitor-number": 2},
                    "applied-layout": {"uuid": self.SLOT},
                },
            ]
        )
        migrated = self.backend.protect_shared_slot(self.SLOT, 1)
        self.assertEqual(migrated, [2])

        layouts = self.backend.get_custom_layouts()
        names = [l["name"] for l in layouts]
        self.assertIn("Temp (M2)", names)
        clone = next(l for l in layouts if l["name"] == "Temp (M2)")
        # копия старого содержимого применена на монитор 2
        self.assertIn((clone["uuid"], 2), self.applied_calls)
        # исходный слот пока не тронут
        self.assertIsNotNone(self.backend.get_layout_by_uuid(self.SLOT))

    def test_noop_when_only_target_uses_slot(self):
        self._seed(
            [
                {
                    "device": {"monitor-number": 1},
                    "applied-layout": {"uuid": self.SLOT},
                }
            ]
        )
        self.assertEqual(self.backend.protect_shared_slot(self.SLOT, 1), [])
        self.assertEqual(self.applied_calls, [])

    def test_monitors_using_layout(self):
        self._seed(
            [
                {
                    "device": {"monitor-number": 1},
                    "applied-layout": {"uuid": self.SLOT},
                },
                {
                    "device": {"monitor-number": 2},
                    "applied-layout": {"uuid": "{OTHER}"},
                },
                {
                    "device": {"monitor-number": 0},
                    "applied-layout": {"uuid": self.SLOT},
                },
            ]
        )
        # monitor-number 0 (фантомный DISPLAY5) игнорируется
        self.assertEqual(self.backend.monitors_using_layout(self.SLOT), {1})

    def test_missing_files_safe(self):
        self.assertEqual(self.backend.get_applied_entries(), [])
        self.assertEqual(self.backend.protect_shared_slot(self.SLOT, 1), [])


if __name__ == "__main__":
    unittest.main()
