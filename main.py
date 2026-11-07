import json
import os
import sys
import uuid

# Добавляем пути к текущей директории и lib для встроенных зависимостей
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
lib_dir = os.path.join(current_dir, "lib")
if os.path.exists(lib_dir):
    sys.path.append(lib_dir)

from flowlauncher import FlowLauncher

from fz_backend import FZBackend
from fz_compiler import FZCompiler


class FancyZonesPlugin(FlowLauncher):
    def __init__(self):
        self.backend = FZBackend()
        super().__init__()

    def query(self, query_str: str):
        results = []
        q = (query_str or "").strip()

        # 0. Если ввод пустой — показываем список всех сохраненных макетов
        if not q:
            return self._get_existing_layouts_results("")

        # 1. Флаги -s/-k/-m вынимаем всегда: они работают и с именами
        #    («Wide Solo -m 2» = применить сохраненный макет на монитор №2)
        remainder, _spacing, hotkey, monitor, flag_err = (
            FZCompiler.extract_flags(q, self.backend)
        )
        if flag_err:
            return [self._error_item("Ошибка во флагах", flag_err)]

        # 2. Только флаги без текста: «-m all» — весь список макетов
        #    будет применен на выбранный монитор
        if not remainder:
            return self._get_existing_layouts_results(
                "", monitor=monitor, hotkey=hotkey
            )

        # 3. Точное совпадение с именем сохраненного макета — наивысший
        #    приоритет (имена могут содержать '2', '+', '/' и т.п.)
        exact = [
            l
            for l in self.backend.get_custom_layouts()
            if str(l.get("name", "")).strip().lower() == remainder.lower()
        ]
        if exact:
            return [
                self._layout_item(l, monitor=monitor, hotkey=hotkey)
                for l in exact
            ]

        # 4. Пробуем скомпилировать формулу DSL
        if FZCompiler.looks_like_dsl(remainder):
            parsed, parse_err = FZCompiler.parse_command(q, self.backend)
            if parse_err or not parsed:
                return (
                    [
                        self._error_item(
                            "Не удалось разобрать команду",
                            f"{parse_err} | Примеры: 1+2+1 -s 8, 2x2 -m 1, A B | C D",
                        )
                    ]
                    + self._get_existing_layouts_results(remainder)
                )

            layout, compile_err = FZCompiler.compile(parsed, self.backend)

            if compile_err:
                return (
                    [
                        self._error_item(
                            "Ошибка синтаксиса сетки",
                            f"{compile_err} | Примеры: 1+2+1 -s 8, 0(1)+1, 2x2 -m all",
                        )
                    ]
                    + self._get_existing_layouts_results(remainder)
                )

            sub_info = [layout.get("summary", "")]
            sub_info.append(f"Отступ: {parsed['spacing']}px")

            if parsed["hotkey"] is not None:
                sub_info.append(
                    f"Хоткей: Win+Ctrl+Alt+{parsed['hotkey']}"
                )
            if parsed["monitor"] is not None:
                if parsed["monitor"] == "all":
                    sub_info.append("Монитор: все")
                else:
                    sub_info.append(f"Монитор: №{parsed['monitor']}")

            is_temp = bool(FZCompiler.TEMP_PATTERN.match(layout["uuid"]))
            title = (
                f"Обновить и применить «{layout['name']}»"
                if is_temp
                else f"Сохранить и применить: «{parsed['name']}»"
            )

            results.append(
                {
                    "Title": title,
                    "SubTitle": " | ".join(sub_info),
                    "IcoPath": "Images/app.png",
                    "JsonRPCAction": {
                        "method": "create_and_apply",
                        "parameters": [
                            layout,
                            parsed["hotkey"],
                            parsed["monitor"],
                        ],
                    },
                }
            )

            if self.backend.cli_path is None:
                results.append(
                    {
                        "Title": "ВНИМАНИЕ: FancyZonesCLI.exe не найден",
                        "SubTitle": (
                            "Сохранение выполнится, но применить макет не "
                            "удастся. Установите PowerToys или добавьте "
                            "FancyZonesCLI.exe в PATH"
                        ),
                        "IcoPath": "Images/app.png",
                    }
                )

            return results

        # 5. Нечеткий поиск по имени (целевой монитор/-k сохраняются)
        saved_results = self._get_existing_layouts_results(
            remainder, monitor=monitor, hotkey=hotkey
        )
        if saved_results:
            return saved_results

        # 6. Ничего не найдено
        if monitor is not None or hotkey is not None:
            return [
                self._error_item(
                    "Макет не найден",
                    f"«{remainder}» нет среди сохраненных. Примеры: 1+2+1 -s 8, "
                    "2x2 -m all, Wide Solo -m 2",
                )
            ]

        return [
            {
                "Title": "FancyZones DSL",
                "SubTitle": "Примеры: 1+2+1, {1:0:1}+1, 2x2 -m all, A B | C D, Wide Solo -m 2",
                "IcoPath": "Images/app.png",
            }
        ]

    @staticmethod
    def _error_item(title: str, subtitle: str) -> dict:
        return {
            "Title": title,
            "SubTitle": subtitle,
            "IcoPath": "Images/app.png",
        }

    def _layout_item(self, l: dict, monitor=None, hotkey=None) -> dict:
        name = l.get("name", "Без имени")
        uuid_str = l.get("uuid", "")
        l_type = l.get("type", "grid")

        parts = [f"Тип: {l_type}", "Enter: применить"]
        if monitor is not None:
            parts.append(
                "→ все мониторы"
                if monitor == "all"
                else f"→ монитор №{monitor}"
            )
        if hotkey is not None:
            parts.append(f"+ хоткей Win+Ctrl+Alt+{hotkey}")

        return {
            "Title": name,
            "SubTitle": " | ".join(parts),
            "IcoPath": "Images/app.png",
            "JsonRPCAction": {
                "method": "apply_layout",
                "parameters": [uuid_str, monitor, hotkey],
            },
            "ContextData": uuid_str,
        }

    def _get_existing_layouts_results(
        self, filter_text: str, monitor=None, hotkey=None
    ):
        items = []
        layouts = self.backend.get_custom_layouts()
        q_lower = filter_text.lower()

        for l in layouts:
            name = l.get("name", "Без имени")
            if not filter_text or q_lower in name.lower():
                items.append(self._layout_item(l, monitor, hotkey))
        return items

    # Максимум целей слияния в контекстном меню (остальные — через '>' в запросе)
    MAX_MERGE_TARGETS = 8

    @staticmethod
    def _ctx(title, subtitle, method=None, params=None):
        item = {
            "Title": title,
            "SubTitle": subtitle,
            "IcoPath": "Images/app.png",
        }
        if method:
            item["JsonRPCAction"] = {"method": method, "parameters": params}
        return item

    def context_menu(self, data):
        uuid_str = data
        layout = self.backend.get_layout_by_uuid(uuid_str)
        name = (layout or {}).get("name") or "Без имени"

        items = [
            self._ctx(
                "Применить",
                f"«{name}» на активный монитор",
                "apply_layout",
                [uuid_str, None, None],
            ),
            self._ctx(
                "Применить ко всем мониторам",
                f"«{name}» сразу на всю рабочую область",
                "apply_layout",
                [uuid_str, "all", None],
            ),
        ]

        # Персональные пункты по мониторам (вместо ручного ввода -m)
        monitors = self.backend.get_monitors()
        if len(monitors) > 1:
            for m in monitors:
                meta = " | ".join(
                    x
                    for x in (
                        m.get("name", ""),
                        f"{m['width']}x{m['height']}" if m.get("width") else "",
                    )
                    if x
                )
                items.append(
                    self._ctx(
                        f"Применить к монитору №{m['number']}",
                        meta or "…",
                        "apply_layout",
                        [uuid_str, m["number"], None],
                    )
                )

        # Слияние с другими сохраненными макетами: порядок зон = Z-order
        # (верхний слой записан в массиве последним, как в операторе '>')
        others = sorted(
            (
                l
                for l in self.backend.get_custom_layouts()
                if str(l.get("uuid", "")).upper() != uuid_str.upper()
                and l.get("uuid")
            ),
            key=lambda l: str(l.get("name", "")).lower(),
        )
        shown = others[: self.MAX_MERGE_TARGETS]
        for l in shown:
            t = l.get("name", "Без имени")
            items.append(
                self._ctx(
                    f"Наложить на «{t}»",
                    f"Зоны «{name}» встанут поверх «{t}»: сохранить и применить",
                    "merge_layouts",
                    [uuid_str, l.get("uuid"), True],
                )
            )
        for l in shown:
            t = l.get("name", "Без имени")
            items.append(
                self._ctx(
                    f"Положить под «{t}»",
                    f"Зоны «{name}» встанут под «{t}»: сохранить и применить",
                    "merge_layouts",
                    [uuid_str, l.get("uuid"), False],
                )
            )
        if len(others) > len(shown):
            items.append(
                self._ctx(
                    f"…и ещё {len(others) - len(shown)} макетов",
                    f"В запросе: «цель > {name}» — наложить на, "
                    f"«{name} > цель» — положить под",
                )
            )

        items.append(
            self._ctx(
                "Сделать копию",
                f"Сохранить дубликат «{name}» с новым именем и GUID",
                "duplicate_layout",
                [uuid_str],
            )
        )

        used = self.backend.monitors_using_layout(uuid_str)
        if used:
            items.append(
                self._ctx(
                    "Сейчас применен на",
                    "Мониторы: " + ", ".join(f"№{n}" for n in sorted(used)),
                )
            )

        items.append(
            self._ctx(
                "Удалить макет",
                f"Удалить ({uuid_str}) из PowerToys",
                "delete_layout",
                [uuid_str],
            )
        )
        return items

    def _zones_of(self, layout, ref_w, ref_h):
        """Зоны макета в canvas-координатах; grid конвертится с его же отступом."""
        info = layout.get("info") or {}
        spacing = int(info.get("spacing", 16) or 16)
        return FZCompiler._extract_canvas_zones(layout, spacing, ref_w, ref_h)

    def merge_layouts(self, uuid_a: str, uuid_b: str, a_on_top=True):
        """
        Слить два сохраненных макета в новый canvas и применить на активный
        монитор. a_on_top=True: зоны «a» поверх «b» (в массиве — последними).
        Повторный слияние той же пары перезаписывает результат по имени.
        """
        a = self.backend.get_layout_by_uuid(uuid_a)
        b = self.backend.get_layout_by_uuid(uuid_b)
        if not a or not b:
            self.backend._log(
                f"merge_layouts: макет не найден ({uuid_a}, {uuid_b})"
            )
            return

        try:
            ref_w, ref_h = self.backend.get_spacing_ref(None)
        except Exception:
            ref_w, ref_h = 1920, 1080

        zones_a = self._zones_of(a, ref_w, ref_h)
        zones_b = self._zones_of(b, ref_w, ref_h)
        if not zones_a or not zones_b:
            self.backend._log(
                f"merge_layouts: пустые зоны ({uuid_a}, {uuid_b})"
            )
            return

        name_a = a.get("name", "Без имени")
        name_b = b.get("name", "Без имени")
        if a_on_top:
            zones, top, bottom = zones_b + zones_a, name_a, name_b
        else:
            zones, top, bottom = zones_a + zones_b, name_b, name_a

        layout = {
            "uuid": f"{{{str(uuid.uuid4()).upper()}}}",
            "name": f"{top} над {bottom}",
            "type": "canvas",
            "summary": f"Слияние: «{top}» над «{bottom}» ({len(zones)} зон)",
            "info": {
                "ref-width": 10000,
                "ref-height": 10000,
                "zones": zones,
                "sensitivity-radius": 20,
            },
        }

        if not self.backend.save_layout(layout):
            self.backend._log(
                f"merge_layouts: не удалось сохранить «{layout['name']}»"
            )
            return
        if not self.backend.apply_layout(layout["uuid"], None):
            self.backend._log(
                f"merge_layouts: сохранено, но не применено "
                f"({layout['uuid']})"
            )

    def duplicate_layout(self, uuid_str: str):
        """Клон макета с новым GUID и именем «… (копия)» (без применения)."""
        src = self.backend.get_layout_by_uuid(uuid_str)
        if not src:
            self.backend._log(
                f"duplicate_layout: источник не найден ({uuid_str})"
            )
            return

        clone = json.loads(json.dumps(src))  # deep copy
        clone.pop("summary", None)
        clone["uuid"] = f"{{{str(uuid.uuid4()).upper()}}}"

        base = str(clone.get("name", "Без имени"))
        existing = {
            str(l.get("name", "")).strip().lower()
            for l in self.backend.get_custom_layouts()
        }
        candidate = f"{base} (копия)"
        n = 2
        while candidate.lower() in existing:
            candidate = f"{base} (копия {n})"
            n += 1
        clone["name"] = candidate

        if not self.backend.save_layout(clone):
            self.backend._log(f"duplicate_layout: сохранение не удалось ({uuid_str})")

    def apply_layout(self, uuid_str: str, monitor=None, hotkey=None):
        # Применение сохраненного макета: monitor = None|'all'|int (1-based)
        applied = self.backend.apply_layout(uuid_str, monitor)
        if hotkey is not None:
            self.backend.set_hotkey(hotkey, uuid_str)
        if not applied:
            self.backend._log(
                f"apply_layout: не удалось применить "
                f"(uuid={uuid_str}, monitor={monitor!r})"
            )

    def create_and_apply(
        self, layout: dict, hotkey: int = None, monitor=None
    ):
        uuid_str = layout["uuid"]

        # Перезапись Temp-слота не должна «переезжать» чужие мониторы:
        # сначала пересаживаем другие мониторы на копию старого содержимого
        slot_match = FZCompiler.TEMP_PATTERN.match(uuid_str)
        if slot_match and monitor != "all":
            target = (
                monitor
                if isinstance(monitor, int)
                else self.backend.active_monitor_number()
            )
            self.backend.protect_shared_slot(uuid_str, target)

        saved = self.backend.save_layout(layout)
        if not saved:
            return

        applied = self.backend.apply_layout(uuid_str, monitor)

        if hotkey is not None:
            self.backend.set_hotkey(hotkey, uuid_str)

        if not applied:
            # UI не показывает результат RPC-действия; детали — в plugin.log
            self.backend._log(
                f"create_and_apply: сохранено, но не применено "
                f"(uuid={uuid_str}, monitor={monitor!r})"
            )

    def delete_layout(self, uuid_str: str):
        self.backend.delete_layout(uuid_str)


if __name__ == "__main__":
    FancyZonesPlugin()
