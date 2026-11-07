import unittest

from main import FancyZonesPlugin
from test_compiler import MockBackend, TWO_MONITORS


LAYOUTS = [
    {"uuid": "{A1}", "name": "Wide Solo", "type": "grid"},
    {"uuid": "{A2}", "name": "Solo", "type": "grid"},
    {"uuid": "{A3}", "name": "2 Monitor", "type": "grid"},
    {"uuid": "{A4}", "name": "Temp", "type": "canvas"},
]

GRID_INFO = {
    "rows": 1,
    "columns": 2,
    "rows-percentage": [10000],
    "columns-percentage": [7500, 2500],
    "cell-child-map": [[0, 1]],
    "show-spacing": True,
    "spacing": 16,
    "sensitivity-radius": 20,
}

MERGE_LAYOUTS = [
    {"uuid": "{G1}", "name": "Master L", "type": "grid", "info": GRID_INFO},
    {
        "uuid": "{C1}",
        "name": "Float",
        "type": "canvas",
        "info": {
            "ref-width": 10000,
            "ref-height": 10000,
            "zones": [{"X": 2500, "Y": 2500, "width": 5000, "height": 5000}],
            "sensitivity-radius": 20,
        },
    },
]


class ActionMockBackend(MockBackend):
    """Мок с методами записи/чтения, которые дергает контекстное меню."""

    def __init__(self, monitors=None, layouts=None):
        super().__init__(monitors, layouts)
        self.saved = []
        self.applied = []
        self.logs = []

    def get_layout_by_uuid(self, layout_uuid):
        for l in self._layouts:
            if str(l.get("uuid", "")).upper() == str(layout_uuid).upper():
                return l
        return None

    def save_layout(self, layout):
        self.saved.append(layout)
        return True

    def apply_layout(self, layout_uuid, monitor=None):
        self.applied.append((layout_uuid, monitor))
        return True

    def monitors_using_layout(self, layout_uuid):
        return set()

    def _log(self, message):
        self.logs.append(message)


def make_plugin(monitors=None, layouts=None):
    p = FancyZonesPlugin.__new__(FancyZonesPlugin)  # мимо argv-инициализации
    p.backend = ActionMockBackend(
        TWO_MONITORS if monitors is None else monitors,
        LAYOUTS if layouts is None else layouts,
    )
    return p


class TestQueryNameWithFlags(unittest.TestCase):
    """Флаги -m/-k должны работать и с именами сохраненных макетов."""

    def test_name_with_monitor(self):
        res = make_plugin().query("Wide Solo -m 2")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["Title"], "Wide Solo")
        self.assertIn("монитор №2", res[0]["SubTitle"])
        act = res[0]["JsonRPCAction"]
        self.assertEqual(act["method"], "apply_layout")
        self.assertEqual(act["parameters"], ["{A1}", 2, None])

    def test_name_by_monitor_name(self):
        res = make_plugin().query("Temp -m bnq")
        self.assertEqual(res[0]["Title"], "Temp")
        self.assertEqual(res[0]["JsonRPCAction"]["parameters"], ["{A4}", 2, None])

    def test_name_with_hotkey(self):
        res = make_plugin().query("Solo -k 4")
        self.assertEqual(res[0]["JsonRPCAction"]["parameters"], ["{A2}", None, 4])
        self.assertIn("Win+Ctrl+Alt+4", res[0]["SubTitle"])

    def test_fuzzy_keeps_monitor(self):
        # «solo» — точное совпадение с макетом Solo (приоритет),
        # поэтому нечеткий ищем по подстроке «o»
        res = make_plugin().query("o -m all")
        titles = sorted(r["Title"] for r in res)
        self.assertIn("Solo", titles)
        self.assertIn("Wide Solo", titles)
        self.assertTrue(
            all(r["JsonRPCAction"]["parameters"][1] == "all" for r in res)
        )

    def test_exact_match_wins_over_fuzzy(self):
        res = make_plugin().query("solo -m all")
        self.assertEqual([r["Title"] for r in res], ["Solo"])

    def test_exact_name_beats_dsl(self):
        # «2 Monitor» похоже на формулу, но точное имя важнее
        res = make_plugin().query("2 Monitor")
        self.assertEqual(res[0]["Title"], "2 Monitor")
        self.assertEqual(res[0]["JsonRPCAction"]["method"], "apply_layout")

    def test_flags_only_lists_all(self):
        res = make_plugin().query("-m 1")
        self.assertEqual(len(res), len(LAYOUTS))
        self.assertTrue(
            all(r["JsonRPCAction"]["parameters"][1] == 1 for r in res)
        )

    def test_bad_monitor_flag(self):
        res = make_plugin().query("Wide Solo -m 0")
        self.assertEqual(res[0]["Title"], "Ошибка во флагах")
        self.assertIn("1-based", res[0]["SubTitle"])

    def test_unknown_name_with_flags(self):
        res = make_plugin().query("NoSuchLayout -m 2")
        self.assertEqual(res[0]["Title"], "Макет не найден")

    def test_plain_name_no_flags_still_works(self):
        res = make_plugin().query("Wide Solo")
        self.assertEqual(res[0]["JsonRPCAction"]["parameters"], ["{A1}", None, None])

    def test_dsl_still_works(self):
        res = make_plugin().query("1+2 -m 1 Test")
        act = res[0]["JsonRPCAction"]
        self.assertEqual(act["method"], "create_and_apply")
        self.assertIn("Монитор: №1", res[0]["SubTitle"])
        self.assertEqual(act["parameters"][2], 1)

    def test_unnamed_targets_per_monitor_slot(self):
        # безымянная формула на монитор 2 — слот «Temp 2», а не общий Temp
        res = make_plugin().query("1+1 -m 2")
        self.assertEqual(res[0]["Title"], "Обновить и применить «Temp 2»")
        layout = res[0]["JsonRPCAction"]["parameters"][0]
        self.assertEqual(
            layout["uuid"], "{00000000-0000-0000-0000-000000000002}"
        )
        self.assertEqual(layout["name"], "Temp 2")

    def test_dsl_name_collision(self):
        # формула с именем существующего макета в конце — компиляция
        res = make_plugin().query("1+2 Solo")
        self.assertEqual(res[0]["JsonRPCAction"]["method"], "create_and_apply")


class TestContextMenu(unittest.TestCase):
    """Контекстное меню сохраненного макета."""

    def test_items_and_order(self):
        items = make_plugin().context_menu("{A1}")
        titles = [i["Title"] for i in items]

        self.assertEqual(titles[0], "Применить")
        self.assertEqual(titles[1], "Применить ко всем мониторам")
        self.assertIn("Применить к монитору №1", titles)
        self.assertIn("Применить к монитору №2", titles)
        self.assertIn("Наложить на «2 Monitor»", titles)  # сортировка по имени
        self.assertIn("Положить под «Temp»", titles)
        self.assertIn("Сделать копию", titles)
        self.assertEqual(titles[-1], "Удалить макет")

        act = items[0]["JsonRPCAction"]
        self.assertEqual(act["method"], "apply_layout")
        self.assertEqual(act["parameters"], ["{A1}", None, None])

    def test_monitor_actions(self):
        items = make_plugin().context_menu("{A1}")
        m2 = next(
            i for i in items if i["Title"] == "Применить к монитору №2"
        )
        self.assertEqual(
            m2["JsonRPCAction"]["parameters"], ["{A1}", 2, None]
        )

    def test_no_self_merge_target(self):
        items = make_plugin().context_menu("{A1}")
        titles = [i["Title"] for i in items]
        self.assertFalse(any("Wide Solo»" in t for t in titles))

    def test_single_monitor_hides_per_monitor_items(self):
        items = make_plugin(monitors=[TWO_MONITORS[0]]).context_menu("{A1}")
        titles = [i["Title"] for i in items]
        self.assertNotIn("Применить к монитору №1", titles)

    def test_merge_action_params(self):
        items = make_plugin().context_menu("{A1}")
        over = next(
            i for i in items if i["Title"] == "Наложить на «2 Monitor»"
        )
        self.assertEqual(over["JsonRPCAction"]["method"], "merge_layouts")
        self.assertEqual(over["JsonRPCAction"]["parameters"], ["{A1}", "{A3}", True])
        under = next(
            i for i in items if i["Title"] == "Положить под «2 Monitor»"
        )
        self.assertEqual(under["JsonRPCAction"]["parameters"], ["{A1}", "{A3}", False])


class TestMergeAndDuplicate(unittest.TestCase):
    """Слияние макетов и копирование через RPC-действия меню."""

    def test_merge_a_on_top_zones_last(self):
        p = make_plugin(layouts=[dict(l) for l in MERGE_LAYOUTS])
        p.merge_layouts("{G1}", "{C1}", True)
        self.assertEqual(len(p.backend.saved), 1)
        saved = p.backend.saved[0]
        self.assertEqual(saved["type"], "canvas")
        self.assertEqual(saved["name"], "Master L над Float")
        # «G1» сверху: его зоны идут последними, Float — низ (первая зона)
        zones = saved["info"]["zones"]
        self.assertEqual(len(zones), 3)
        self.assertEqual(zones[0], {"X": 2500, "Y": 2500, "width": 5000, "height": 5000})
        # применено на активный монитор
        self.assertEqual(p.backend.applied, [(saved["uuid"], None)])

    def test_merge_a_under(self):
        p = make_plugin(layouts=[dict(l) for l in MERGE_LAYOUTS])
        p.merge_layouts("{G1}", "{C1}", False)
        saved = p.backend.saved[0]
        self.assertEqual(saved["name"], "Float над Master L")
        zones = saved["info"]["zones"]
        # теперь верхняя (последняя) — зона Float
        self.assertEqual(zones[-1]["X"], 2500)

    def test_merge_missing_layout_logs_and_noop(self):
        p = make_plugin(layouts=[dict(l) for l in MERGE_LAYOUTS])
        p.merge_layouts("{G1}", "{NOPE}", True)
        self.assertEqual(p.backend.saved, [])
        self.assertEqual(p.backend.applied, [])
        self.assertTrue(any("merge_layouts" in m for m in p.backend.logs))

    def test_duplicate_new_uuid_and_name(self):
        p = make_plugin(layouts=[dict(l) for l in MERGE_LAYOUTS])
        p.duplicate_layout("{C1}")
        clone = p.backend.saved[0]
        self.assertEqual(clone["name"], "Float (копия)")
        self.assertNotEqual(clone["uuid"], "{C1}")
        self.assertEqual(clone["info"], MERGE_LAYOUTS[1]["info"])
        self.assertEqual(p.backend.applied, [])  # копия не применяется

    def test_duplicate_avoids_name_collision(self):
        layouts = [dict(l) for l in MERGE_LAYOUTS]
        layouts.append(
            {"uuid": "{C2}", "name": "Float (копия)", "type": "canvas", "info": {}}
        )
        p = make_plugin(layouts=layouts)
        p.duplicate_layout("{C1}")
        self.assertEqual(p.backend.saved[0]["name"], "Float (копия 2)")


if __name__ == "__main__":
    unittest.main()
