import os
import sys

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
        q = query_str.strip()

        # 1. Если ввод пустой — показываем список всех сохраненных макетов
        if not q:
            return self._get_existing_layouts_results("")

        # 2. Проверяем, является ли ввод выражением для компиляции
        first_token = q.split()[0]
        is_dsl = any(c in q for c in ["+", "/", "|", ";", ">"]) or (
            first_token.replace("x", "").isdigit()
        )

        if is_dsl:
            # Передаем self.backend для поиска слоев в операторе '>'
            parsed, parse_err = FZCompiler.parse_command(q, self.backend)
            if not parse_err and parsed:
                layout, compile_err = FZCompiler.compile(parsed, self.backend)

                if compile_err:
                    results.append(
                        {
                            "Title": "Ошибка синтаксиса сетки",
                            "SubTitle": compile_err,
                            "IcoPath": "Images/app.png",
                        }
                    )
                else:
                    sub_info = [layout.get("summary", "")]
                    sub_info.append(f"Отступ: {parsed['spacing']}px")

                    if parsed["hotkey"] is not None:
                        sub_info.append(
                            f"Хоткей: Win+Ctrl+Alt+{parsed['hotkey']}"
                        )
                    if parsed["monitor"]:
                        sub_info.append(f"Монитор: {parsed['monitor']}")

                    is_temp = parsed["name"].lower() == "temp"
                    title = (
                        "Обновить и применить «Temp»"
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
                    return results

        # 3. Поиск по существующим макетам (если введен обычный текст)
        saved_results = self._get_existing_layouts_results(q)
        if saved_results:
            results.extend(saved_results)
        else:
            results.append(
                {
                    "Title": "FancyZones DSL",
                    "SubTitle": "Примеры: 1+2+1, {1:0:1}+1, 1+0(5)+1, LayerA > LayerB, 2x2, A B | A C",
                    "IcoPath": "Images/app.png",
                }
            )

        return results

    def _get_existing_layouts_results(self, filter_text: str):
        items = []
        layouts = self.backend.get_custom_layouts()
        q_lower = filter_text.lower()

        for l in layouts:
            name = l.get("name", "Без имени")
            uuid_str = l.get("uuid", "")
            l_type = l.get("type", "grid")

            if not filter_text or q_lower in name.lower():
                items.append(
                    {
                        "Title": name,
                        "SubTitle": f"Тип: {l_type} | Enter: применить",
                        "IcoPath": "Images/app.png",
                        "JsonRPCAction": {
                            "method": "apply_layout",
                            "parameters": [uuid_str],
                        },
                        "ContextData": uuid_str,
                    }
                )
        return items

    def context_menu(self, data):
        uuid_str = data
        return [
            {
                "Title": "Удалить макет",
                "SubTitle": f"Удалить ({uuid_str}) из PowerToys",
                "IcoPath": "Images/app.png",
                "JsonRPCAction": {
                    "method": "delete_layout",
                    "parameters": [uuid_str],
                },
            }
        ]

    def apply_layout(self, uuid_str: str):
        self.backend.apply_layout(uuid_str)

    def create_and_apply(
        self, layout: dict, hotkey: int = None, monitor: str = None
    ):
        uuid_str = layout["uuid"]
        self.backend.save_layout(layout)
        self.backend.apply_layout(uuid_str, monitor)

        if hotkey is not None:
            self.backend.set_hotkey(hotkey, uuid_str)

    def delete_layout(self, uuid_str: str):
        self.backend.delete_layout(uuid_str)


if __name__ == "__main__":
    FancyZonesPlugin()