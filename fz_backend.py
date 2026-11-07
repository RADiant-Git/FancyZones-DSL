import json
import os
import re
import shutil
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple


class FZBackend:
    # Кэш списка мониторов: CLI запускается на каждый «горячий» запрос,
    # поэтому держим результат короткое время.
    MONITORS_CACHE_TTL = 20.0

    LOG_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "plugin.log"
    )

    def __init__(self):
        self.appdata = os.environ.get("LOCALAPPDATA", "")
        self.fz_dir = os.path.join(
            self.appdata, "Microsoft", "PowerToys", "FancyZones"
        )
        self.custom_layouts_path = os.path.join(
            self.fz_dir, "custom-layouts.json"
        )
        self.applied_layouts_path = os.path.join(
            self.fz_dir, "applied-layouts.json"
        )
        self.cli_path = self._find_cli()
        self._monitors_cache: Optional[List[Dict[str, Any]]] = None
        self._monitors_cache_ts = 0.0

    # ------------------------------------------------------------------ #
    #  Служебное
    # ------------------------------------------------------------------ #

    def _find_cli(self) -> Optional[str]:
        """Ищет FancyZonesCLI.exe в PATH и по стандартным путям PowerToys."""
        in_path = shutil.which("FancyZonesCLI.exe")
        if in_path:
            return in_path

        candidates = [
            os.path.join(
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                "PowerToys",
                "FancyZonesCLI.exe",
            ),
            os.path.join(
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                "PowerToys",
                "modules",
                "FancyZones",
                "FancyZonesCLI.exe",
            ),
            os.path.join(
                self.appdata, "Programs", "PowerToys", "FancyZonesCLI.exe"
            ),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

    def _log(self, message: str) -> None:
        """Аппендицирует сообщение в plugin.log рядом с плагином."""
        try:
            if os.path.exists(self.LOG_PATH) and os.path.getsize(self.LOG_PATH) > 262144:
                open(self.LOG_PATH, "w").close()
            with open(self.LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception:
            pass

    def _run_cli(self, args: List[str]) -> Tuple[bool, str, str]:
        """Выполняет FancyZonesCLI без окна. Возвращает (успех, stdout, stderr)."""
        if not self.cli_path:
            return False, "", "FancyZonesCLI.exe не найден"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(
                [self.cli_path] + list(args),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                creationflags=creationflags,
            )
            return (
                proc.returncode == 0,
                proc.stdout or "",
                proc.stderr or "",
            )
        except Exception as e:
            return False, "", str(e)

    # ------------------------------------------------------------------ #
    #  Мониторы
    # ------------------------------------------------------------------ #

    MONITOR_HEADER_RE = re.compile(r"^Monitor (\d+):\s*$")
    MONITOR_NAME_RE = re.compile(r"^Monitor: (\S+)\s*$")
    MONITOR_SERIAL_RE = re.compile(r"^Serial Number: (.+?)\s*$")
    MONITOR_RES_RE = re.compile(r"^Resolution: (\d+)x(\d+)\s*$")
    MONITOR_POS_RE = re.compile(r"^Position: \((-?\d+),\s*(-?\d+)\)\s*$")
    MONITOR_SELECTED_RE = re.compile(r"^Selected: (True|False)\s*$")

    @classmethod
    def parse_monitors_output(cls, text: str) -> List[Dict[str, Any]]:
        """Разбирает вывод `FancyZonesCLI get-monitors` (ASCII-метки стабильны)."""
        monitors: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            m = cls.MONITOR_HEADER_RE.match(line)
            if m:
                current = {
                    "number": int(m.group(1)),
                    "name": "",
                    "serial": "",
                    "width": 0,
                    "height": 0,
                    "position": None,
                    "selected": False,
                }
                monitors.append(current)
                continue
            if current is None:
                continue
            m = cls.MONITOR_NAME_RE.match(line)
            if m:
                current["name"] = m.group(1)
                continue
            m = cls.MONITOR_SERIAL_RE.match(line)
            if m:
                current["serial"] = m.group(1)
                continue
            m = cls.MONITOR_RES_RE.match(line)
            if m:
                current["width"] = int(m.group(1))
                current["height"] = int(m.group(2))
                continue
            m = cls.MONITOR_POS_RE.match(line)
            if m:
                current["position"] = (int(m.group(1)), int(m.group(2)))
                continue
            m = cls.MONITOR_SELECTED_RE.match(line)
            if m:
                current["selected"] = m.group(1) == "True"
        return monitors

    def get_monitors(self, force: bool = False) -> List[Dict[str, Any]]:
        """Список мониторов с разрешением. Пустой список, если CLI недоступен."""
        now = time.time()
        if (
            not force
            and self._monitors_cache is not None
            and now - self._monitors_cache_ts < self.MONITORS_CACHE_TTL
        ):
            return self._monitors_cache

        ok, out, err = self._run_cli(["get-monitors"])
        monitors = self.parse_monitors_output(out) if ok else []
        if not ok:
            self._log(f"get-monitors failed: {err.strip()[:300]}")
        self._monitors_cache = monitors
        self._monitors_cache_ts = now
        return monitors

    def resolve_monitor(self, target: Optional[str]) -> Tuple[Optional[Any], Optional[str]]:
        """
        Приводит значение флага -m к спецификации:
        None (активный), "all" либо int >= 1 (1-based номер как у FancyZonesCLI).
        """
        if target is None:
            return None, None
        t = str(target).strip()
        if not t:
            return None, None

        if t.lower() in ("all", "*"):
            return "all", None

        if t.isdigit():
            n = int(t)
            if n < 1:
                return None, (
                    f"Некорректный монитор '{t}': нумерация 1-based. "
                    "Используйте 1..N, имя монитора или 'all'."
                )
            monitors = self.get_monitors()
            if monitors and n > len(monitors):
                return None, self._no_monitor_error(t, monitors)
            return n, None

        # Имя / серийник: точное совпадение, затем уникальное подвхождение.
        monitors = self.get_monitors()
        if not monitors:
            return None, (
                f"Не удалось распознать монитор '{t}': список мониторов "
                "недоступен (PowerToys CLI не найден)."
            )
        lowered = t.lower()
        exact = [m for m in monitors if m["name"].lower() == lowered]
        partial = [
            m
            for m in monitors
            if lowered in m["name"].lower() or (m["serial"] and lowered in m["serial"].lower())
        ]
        chosen = exact[0] if exact else (partial[0] if len(partial) == 1 else None)
        if chosen:
            return chosen["number"], None
        if len(partial) > 1:
            names = ", ".join(f"{m['number']}={m['name']}" for m in partial)
            return None, f"Имя монитора '{t}' неоднозначно: {names}"
        return None, self._no_monitor_error(t, monitors)

    @staticmethod
    def _no_monitor_error(target: str, monitors: List[Dict[str, Any]]) -> str:
        avail = ", ".join(
            f"{m['number']}={m['name']} ({m['width']}x{m['height']})"
            for m in monitors
        )
        return f"Монитор '{target}' не найден. Доступно: all, {avail or 'нет данных'}"

    @staticmethod
    def _primary_or_first(monitors: List[Dict[str, Any]]) -> Dict[str, Any]:
        for m in monitors:
            if m.get("position") == (0, 0):
                return m
        return monitors[0]

    def get_spacing_ref(self, monitor_spec: Any) -> Tuple[int, int]:
        """
        Разрешение монитора (px), относительно которого запекаются отступы
        canvas-зон. Fallback: 1920x1080.
        """
        monitors = self.get_monitors()
        if not monitors:
            return 1920, 1080

        target: Optional[Dict[str, Any]] = None
        if isinstance(monitor_spec, int):
            target = next((m for m in monitors if m["number"] == monitor_spec), None)
        elif monitor_spec == "all":
            target = self._primary_or_first(monitors)
        else:
            target = next((m for m in monitors if m.get("selected")), None)
            if target is None:
                target = self._primary_or_first(monitors)

        if target and target.get("width") and target.get("height"):
            return target["width"], target["height"]
        return 1920, 1080

    def active_monitor_number(self) -> int:
        """Номер монитора, который FancyZones считает активным (fallback: 1)."""
        monitors = self.get_monitors()
        if not monitors:
            return 1
        selected = next((m for m in monitors if m.get("selected")), None)
        return (selected or monitors[0])["number"]

    def get_applied_entries(self) -> List[Dict[str, Any]]:
        """Записи applied-layouts.json: какой макет на каком мониторе висит."""
        if not os.path.exists(self.applied_layouts_path):
            return []
        try:
            with open(
                self.applied_layouts_path, "r", encoding="utf-8"
            ) as f:
                data = json.load(f)
            return data.get("applied-layouts", [])
        except Exception as e:
            self._log(f"read applied-layouts failed: {e}")
            return []

    def monitors_using_layout(self, layout_uuid: str) -> set:
        """Номеры мониторов, на которых сейчас применен данный GUID."""
        result = set()
        for entry in self.get_applied_entries():
            applied = entry.get("applied-layout", {})
            if applied.get("uuid", "").upper() == layout_uuid.upper():
                num = entry.get("device", {}).get("monitor-number")
                if isinstance(num, int) and num >= 1:
                    result.add(num)
        return result

    def get_layout_by_uuid(self, layout_uuid: str) -> Optional[Dict[str, Any]]:
        for l in self.get_custom_layouts():
            if l.get("uuid", "").upper() == layout_uuid.upper():
                return l
        return None

    def protect_shared_slot(
        self, slot_uuid: str, target_monitor: int
    ) -> List[int]:
        """
        Перед перезаписью общего Temp-слота: мониторы (кроме целевого),
        которые сейчас ссылаются на этот GUID, пересаживаются на копию
        его старого содержимого. Возвращает список защищенных номеров.
        """
        users = self.monitors_using_layout(slot_uuid) - {target_monitor}
        if not users:
            return []

        old = self.get_layout_by_uuid(slot_uuid)
        if not old:
            return []

        migrated = []
        for num in sorted(users):
            clone = json.loads(json.dumps(old))  # deep copy
            clone["uuid"] = f"{{{str(uuid.uuid4()).upper()}}}"
            base_name = str(clone.get("name", "Temp"))
            if base_name.lower() == "temp":
                base_name = "Temp"
            clone["name"] = f"{base_name} (M{num})"
            if self.save_layout(clone) and self.apply_layout(
                clone["uuid"], num
            ):
                migrated.append(num)
                self._log(
                    f"protect_shared_slot: монитор {num} пересажен на "
                    f"копию {clone['uuid']} перед перезаписью {slot_uuid}"
                )
        return migrated

    # ------------------------------------------------------------------ #
    #  Макеты
    # ------------------------------------------------------------------ #

    def get_custom_layouts(self) -> List[Dict[str, Any]]:
        """Возвращает список сохраненных пользовательских макетов."""
        if not os.path.exists(self.custom_layouts_path):
            return []
        try:
            with open(self.custom_layouts_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("custom-layouts", [])
        except Exception as e:
            self._log(f"read custom-layouts failed: {e}")
            return []

    def get_layout_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Ищет макет по имени (без учета регистра)."""
        target = name.strip().lower()
        for l in self.get_custom_layouts():
            if l.get("name", "").strip().lower() == target:
                return l
        return None

    def save_layout(self, layout: Dict[str, Any]) -> bool:
        """Сохраняет макет. Перезаписывает макеты с идентичным именем или UUID."""
        os.makedirs(self.fz_dir, exist_ok=True)
        data = {"custom-layouts": []}

        if os.path.exists(self.custom_layouts_path):
            try:
                with open(self.custom_layouts_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                self._log(f"custom-layouts unreadable, rewriting: {e}")
                data = {"custom-layouts": []}

        clean_layout = {k: v for k, v in layout.items() if k != "summary"}

        layouts = data.setdefault("custom-layouts", [])
        layouts = [
            l
            for l in layouts
            if l.get("name", "").lower() != clean_layout["name"].lower()
            and l.get("uuid", "").upper() != clean_layout["uuid"].upper()
        ]
        layouts.append(clean_layout)
        data["custom-layouts"] = layouts

        try:
            with open(self.custom_layouts_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self._log(f"save_layout failed: {e}")
            return False

    def delete_layout(self, uuid_str: str) -> bool:
        """Удаляет макет по UUID."""
        if not os.path.exists(self.custom_layouts_path):
            return False
        try:
            with open(self.custom_layouts_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["custom-layouts"] = [
                l
                for l in data.get("custom-layouts", [])
                if l.get("uuid", "").upper() != uuid_str.upper()
            ]
            with open(self.custom_layouts_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self._log(f"delete_layout failed: {e}")
            return False

    @staticmethod
    def build_apply_args(layout_uuid: str, monitor: Any = None) -> List[str]:
        """
        Формирует аргументы `FancyZonesCLI set-layout`:
        None -> активный монитор; "all" -> --all; int -> --monitor N (1-based).
        """
        args = ["s", layout_uuid]
        if monitor == "all":
            args.append("--all")
        elif isinstance(monitor, int) and monitor >= 1:
            args.extend(["--monitor", str(monitor)])
        return args

    def apply_layout(self, layout_uuid: str, monitor: Any = None) -> bool:
        """Применяет макет через официальный CLI PowerToys на целевой монитор."""
        ok, out, err = self._run_cli(
            self.build_apply_args(layout_uuid, monitor)
        )
        if not ok:
            self._log(
                f"apply_layout({layout_uuid}, {monitor!r}) failed: "
                f"{(err or out).strip()[:300]}"
            )
        return ok

    def set_hotkey(self, key_num: int, layout_uuid: str) -> bool:
        """Назначает хоткей Win+Ctrl+Alt+[0-9] на макет (команда shk)."""
        ok, out, err = self._run_cli(["shk", str(key_num), layout_uuid])
        if not ok:
            self._log(
                f"set_hotkey({key_num}, {layout_uuid}) failed: "
                f"{(err or out).strip()[:300]}"
            )
        return ok
