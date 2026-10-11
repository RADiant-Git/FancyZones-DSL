import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional


class FZBackend:
    def __init__(self):
        self.appdata = os.environ.get("LOCALAPPDATA", "")
        self.fz_dir = os.path.join(
            self.appdata, "Microsoft", "PowerToys", "FancyZones"
        )
        self.custom_layouts_path = os.path.join(
            self.fz_dir, "custom-layouts.json"
        )
        self.cli_path = self._find_cli()

    def _find_cli(self) -> Optional[str]:
        """Ищет FancyZonesCLI.exe в PATH и по путям установки PowerToys."""
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

    def get_custom_layouts(self) -> List[Dict[str, Any]]:
        """Возвращает список пользовательских макетов."""
        if not os.path.exists(self.custom_layouts_path):
            return []
        try:
            with open(self.custom_layouts_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("custom-layouts", [])
        except Exception:
            return []

    def save_layout(self, layout: Dict[str, Any]) -> bool:
        """Сохраняет макет.

        Если макет с таким именем или UUID уже есть — бесшовно перезаписывает
        его.
        """
        os.makedirs(self.fz_dir, exist_ok=True)
        data = {"custom-layouts": []}

        if os.path.exists(self.custom_layouts_path):
            try:
                with open(self.custom_layouts_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {"custom-layouts": []}

        clean_layout = {k: v for k, v in layout.items() if k != "summary"}

        layouts = data.setdefault("custom-layouts", [])
        # Удаляем старые записи с аналогичным именем или UUID (гарантирует перезапись Temp)
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
        except Exception:
            return False

    def delete_layout(self, uuid_str: str) -> bool:
        """Удаляет макет по его UUID."""
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
        except Exception:
            return False

    def apply_layout(
        self, layout_uuid: str, monitor: Optional[str] = None
    ) -> bool:
        """Применяет макет через официальный CLI PowerToys."""
        if not self.cli_path:
            return False
        try:
            cmd = [self.cli_path, "s", layout_uuid]
            if monitor is not None:
                cmd.extend(["--monitor", str(monitor)])

            subprocess.run(
                cmd, creationflags=subprocess.CREATE_NO_WINDOW, check=True
            )
            return True
        except Exception:
            return False

    def set_hotkey(self, key_num: int, layout_uuid: str) -> bool:
        """Назначает хоткей (0-9) на макет."""
        if not self.cli_path:
            return False
        try:
            subprocess.run(
                [self.cli_path, "shk", str(key_num), layout_uuid],
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=True,
            )
            return True
        except Exception:
            return False