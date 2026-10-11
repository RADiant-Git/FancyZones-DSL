from fractions import Fraction
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid


class FZCompiler:
    # Регулярное выражение для блока: 1, 2, 1(2), {3:1}, {3:1}(2)
    BLOCK_REGEX = re.compile(r"^(\{[\d:]+\}|\d+)(?:\((\d+)\))?$")

    # Постоянный детерминированный GUID для перезаписываемого Temp
    TEMP_UUID = "{00000000-0000-0000-0000-000000000001}"

    @classmethod
    def parse_command(
        cls, raw_input: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Разбирает строку ввода на геометрию, флаги и имя.

        Формула: [Геометрия] [-s <px>] [-k <0-9>] [-m <id>] [Имя]
        """
        text = raw_input.strip()
        if not text:
            return None, "Пустой запрос"

        # 1. Извлечение флагов (-s, -k, -m)
        spacing = 16
        hotkey = None
        monitor = None

        def extract_flag(pattern, val_type=int):
            nonlocal text
            match = re.search(pattern, text)
            if match:
                text = text[: match.start()] + " " + text[match.end() :]
                return val_type(match.group(1))
            return None

        s_val = extract_flag(r"-s\s+(\d+)", int)
        if s_val is not None:
            spacing = s_val

        k_val = extract_flag(r"-k\s+([0-9])", int)
        if k_val is not None:
            hotkey = k_val

        m_val = extract_flag(r"-m\s+([a-zA-Z0-9]+)", str)
        if m_val is not None:
            monitor = m_val

        text = " ".join(text.split()).strip()

        # 2. Определение типа разметки и выделение имени
        # А. Матрица (символы | или ;)
        if "|" in text or ";" in text:
            rows_raw = [
                r.strip() for r in re.split(r"[|;]", text) if r.strip()
            ]
            if len(rows_raw) < 1:
                return None, "Некорректная матрица"

            first_cols = len(rows_raw[0].split())
            last_tokens = rows_raw[-1].split()

            if len(last_tokens) > first_cols:
                name = " ".join(last_tokens[first_cols:])
                rows_raw[-1] = " ".join(last_tokens[:first_cols])
            else:
                name = "Temp"

            geom = " | ".join(rows_raw)
            mode = "matrix"

        # Б. Сплит колонок (+)
        elif "+" in text:
            parts = [p.strip() for p in text.split("+")]
            last_tokens = parts[-1].split()

            if len(last_tokens) > 1 and cls.BLOCK_REGEX.match(last_tokens[0]):
                parts[-1] = last_tokens[0]
                name = " ".join(last_tokens[1:])
            else:
                name = "Temp"

            geom = " + ".join(parts)
            mode = "columns"

        # В. Сплит строк (/)
        elif "/" in text:
            parts = [p.strip() for p in text.split("/")]
            last_tokens = parts[-1].split()

            if len(last_tokens) > 1 and cls.BLOCK_REGEX.match(last_tokens[0]):
                parts[-1] = last_tokens[0]
                name = " ".join(last_tokens[1:])
            else:
                name = "Temp"

            geom = " / ".join(parts)
            mode = "rows"

        # Г. Быстрая сетка (2x3 или 2)
        else:
            match = re.match(r"^(\d+(?:x\d+)?)(?:\s+(.*))?$", text)
            if match:
                geom = match.group(1)
                name = match.group(2).strip() if match.group(2) else "Temp"
                mode = "grid"
            else:
                return None, f"Не распознан синтаксис: {text}"

        return {
            "mode": mode,
            "geom": geom,
            "name": name,
            "spacing": spacing,
            "hotkey": hotkey,
            "monitor": monitor,
        }, None

    @classmethod
    def compile(
        cls, parsed: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Транслирует разобранные параметры в JSON FancyZones."""
        try:
            mode = parsed["mode"]
            geom = parsed["geom"]
            name = parsed["name"]
            spacing = parsed["spacing"]

            if mode == "columns":
                return cls._build_flow_layout(
                    geom, name, spacing, is_cols=True
                )
            elif mode == "rows":
                return cls._build_flow_layout(
                    geom, name, spacing, is_cols=False
                )
            elif mode == "matrix":
                return cls._build_matrix_layout(geom, name, spacing)
            elif mode == "grid":
                return cls._build_quick_grid(geom, name, spacing)

            return None, "Неизвестный режим разметки"
        except Exception as e:
            return None, str(e)

    @classmethod
    def _parse_block(cls, block_str: str) -> Tuple[List[int], int]:
        match = cls.BLOCK_REGEX.match(block_str.strip())
        if not match:
            raise ValueError(f"Неверный синтаксис блока: '{block_str}'")

        inside, weight_str = match.groups()
        weight = int(weight_str) if weight_str else 1

        if inside.startswith("{") and inside.endswith("}"):
            sub = [int(x) for x in inside[1:-1].split(":") if x.isdigit()]
            if not sub or any(x <= 0 for x in sub):
                raise ValueError(
                    f"Веса внутри скобок должны быть > 0: '{inside}'"
                )
            heights = sub
        else:
            count = int(inside)
            if count <= 0:
                raise ValueError("Число зон должно быть больше 0")
            heights = [1] * count

        return heights, weight

    @classmethod
    def _build_flow_layout(
        cls, geom: str, name: str, spacing: int, is_cols: bool
    ):
        delimiter = "+" if is_cols else "/"
        raw_blocks = [b.strip() for b in geom.split(delimiter) if b.strip()]

        slices = [cls._parse_block(b) for b in raw_blocks]
        num_slices = len(slices)

        main_weights = [s[1] for s in slices]
        total_main_weight = sum(main_weights)
        main_fractions = [
            Fraction(w, total_main_weight) for w in main_weights
        ]

        all_cuts = {Fraction(0, 1), Fraction(1, 1)}
        slice_cuts_map = []

        for heights, _ in slices:
            total_h = sum(heights)
            curr = Fraction(0, 1)
            cuts = [curr]
            for h in heights:
                curr += Fraction(h, total_h)
                cuts.append(curr)
                all_cuts.add(curr)
            slice_cuts_map.append(cuts)

        sorted_cuts = sorted(list(all_cuts))
        num_sub_layers = len(sorted_cuts) - 1

        def fractions_to_percentages(fracs: List[Fraction]) -> List[int]:
            pcts = [int(round(float(f) * 10000)) for f in fracs]
            diff = 10000 - sum(pcts)
            pcts[-1] += diff
            return pcts

        sub_fractions = [
            sorted_cuts[i + 1] - sorted_cuts[i] for i in range(num_sub_layers)
        ]

        zone_counter = 0
        if is_cols:
            rows_count, cols_count = num_sub_layers, num_slices
            rows_pct = fractions_to_percentages(sub_fractions)
            cols_pct = fractions_to_percentages(main_fractions)
            grid = [[0] * cols_count for _ in range(rows_count)]

            for c_idx, (heights, _) in enumerate(slices):
                cuts = slice_cuts_map[c_idx]
                for z_idx in range(len(heights)):
                    z_start, z_end = cuts[z_idx], cuts[z_idx + 1]
                    for r_idx in range(rows_count):
                        midpoint = (
                            sorted_cuts[r_idx] + sorted_cuts[r_idx + 1]
                        ) / 2
                        if z_start <= midpoint <= z_end:
                            grid[r_idx][c_idx] = zone_counter
                    zone_counter += 1
            summary = f"Колонки: {geom} ({zone_counter} зон)"
        else:
            rows_count, cols_count = num_slices, num_sub_layers
            rows_pct = fractions_to_percentages(main_fractions)
            cols_pct = fractions_to_percentages(sub_fractions)
            grid = [[0] * cols_count for _ in range(rows_count)]

            for r_idx, (widths, _) in enumerate(slices):
                cuts = slice_cuts_map[r_idx]
                for z_idx in range(len(widths)):
                    z_start, z_end = cuts[z_idx], cuts[z_idx + 1]
                    for c_idx in range(cols_count):
                        midpoint = (
                            sorted_cuts[c_idx] + sorted_cuts[c_idx + 1]
                        ) / 2
                        if z_start <= midpoint <= z_end:
                            grid[r_idx][c_idx] = zone_counter
                    zone_counter += 1
            summary = f"Строки: {geom} ({zone_counter} зон)"

        return (
            cls._create_fz_json(
                name,
                rows_count,
                cols_count,
                rows_pct,
                cols_pct,
                grid,
                spacing,
                summary,
            ),
            None,
        )

    @classmethod
    def _build_matrix_layout(cls, geom: str, name: str, spacing: int):
        rows_raw = [r.strip().split() for r in re.split(r"[|;]", geom) if r.strip()]
        rows_count = len(rows_raw)
        cols_count = len(rows_raw[0])

        if any(len(r) != cols_count for r in rows_raw):
            raise ValueError(
                "Все строки матрицы должны содержать одинаковое количество элементов"
            )

        char_map = {}
        grid = []
        for r in rows_raw:
            row_ids = []
            for token in r:
                if token not in char_map:
                    char_map[token] = len(char_map)
                row_ids.append(char_map[token])
            grid.append(row_ids)

        def equal_pct(count: int) -> List[int]:
            base = 10000 // count
            res = [base] * count
            res[-1] += 10000 - sum(res)
            return res

        summary = (
            f"Матрица {rows_count}x{cols_count} ({len(char_map)} уникальных зон)"
        )
        return (
            cls._create_fz_json(
                name,
                rows_count,
                cols_count,
                equal_pct(rows_count),
                equal_pct(cols_count),
                grid,
                spacing,
                summary,
            ),
            None,
        )

    @classmethod
    def _build_quick_grid(cls, geom: str, name: str, spacing: int):
        if "x" in geom:
            r_str, c_str = geom.split("x")
            rows, cols = int(r_str), int(c_str)
        else:
            rows = cols = int(geom)

        if rows <= 0 or cols <= 0:
            raise ValueError("Размеры сетки должны быть > 0")

        grid = []
        zone_id = 0
        for _ in range(rows):
            grid.append(list(range(zone_id, zone_id + cols)))
            zone_id += cols

        def equal_pct(count: int) -> List[int]:
            base = 10000 // count
            res = [base] * count
            res[-1] += 10000 - sum(res)
            return res

        summary = f"Сетка {rows}x{cols} ({rows * cols} зон)"
        return (
            cls._create_fz_json(
                name,
                rows,
                cols,
                equal_pct(rows),
                equal_pct(cols),
                grid,
                spacing,
                summary,
            ),
            None,
        )

    @classmethod
    def _create_fz_json(
        cls, name, rows, cols, rows_pct, cols_pct, grid, spacing, summary
    ):
        # Temp всегда имеет постоянный системный UUID, а сохраняемые макеты — свой уникальный
        if name.strip().lower() == "temp":
            layout_uuid = cls.TEMP_UUID
        else:
            layout_uuid = f"{{{str(uuid.uuid4()).upper()}}}"

        return {
            "uuid": layout_uuid,
            "name": name,
            "type": "grid",
            "summary": summary,
            "info": {
                "rows": rows,
                "columns": cols,
                "rows-percentage": rows_pct,
                "columns-percentage": cols_pct,
                "cell-child-map": grid,
                "show-spacing": spacing > 0,
                "spacing": spacing,
                "sensitivity-radius": 20,
            },
        }