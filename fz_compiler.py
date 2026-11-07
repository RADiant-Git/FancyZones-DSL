from fractions import Fraction
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid


class FZCompiler:
    # Базовые регулярные выражения грамматики
    FLAG_REGEX = re.compile(r"-(?P<flag>[skm])\s+(?P<val>[^\s]+)")
    BLOCK_REGEX = re.compile(r"^(\{[\d:() ]+\}|\d+)(?:\((?P<outer_w>\d+)\))?$")
    SUB_ITEM_REGEX = re.compile(r"^(?P<val>\d+)(?:\((?P<w>\d+)\))?$")
    GRID_REGEX = re.compile(r"^(?P<rows>\d+)x(?P<cols>\d+)$")

    TEMP_UUID = "{00000000-0000-0000-0000-000000000001}"
    TEMP_PATTERN = re.compile(r"^\{00000000-0000-0000-0000-(\d{12})\}$")

    @classmethod
    def temp_uuid_for(cls, slot_num: int) -> str:
        """Слот Temp для монитора: …0001, …0002, … (по номеру монитора)."""
        return f"{{00000000-0000-0000-0000-{max(1, int(slot_num)):012d}}}"

    @classmethod
    def temp_slot(
        cls, monitor_spec: Any, backend=None
    ) -> Tuple[str, str]:
        """
        (uuid, имя) безымянного слота под целевой монитор.
        'all' и неизвестный монитор -> общий слот №1 'Temp',
        монитор N>1 -> персональный слот 'Temp N', чтобы перезапись
        формулы на одном экране не меняла зоны на других.
        """
        num = 1
        if isinstance(monitor_spec, int):
            num = max(1, monitor_spec)
        elif monitor_spec is None and backend is not None:
            try:
                monitors = backend.get_monitors()
                selected = next(
                    (m for m in monitors if m.get("selected")), None
                )
                if selected:
                    num = max(1, selected["number"])
            except Exception:
                pass
        name = "Temp" if num == 1 else f"Temp {num}"
        return cls.temp_uuid_for(num), name

    @classmethod
    def looks_like_dsl(cls, text: str) -> bool:
        """
        Эвристика: похож ли ввод на формулу, а не на имя сохраненного макета.
        Учитывает одиночные блоки '{3:1}', '0(5)', а не только операторы.
        """
        if any(c in text for c in "+/|;>{}"):
            return True
        tokens = text.split()
        if not tokens:
            return False
        first = tokens[0]
        return bool(
            cls.GRID_REGEX.match(first) or cls.BLOCK_REGEX.match(first)
        )

    @classmethod
    def _canvas_gap(cls, spacing: int, ref_w: int, ref_h: int) -> Tuple[int, int]:
        """Отступ в единицах canvas-полотна 10000x10000 для данного разрешения."""
        if spacing <= 0:
            return 0, 0
        sx = int(round(spacing * 10000 / max(1, ref_w)))
        sy = int(round(spacing * 10000 / max(1, ref_h)))
        return sx, sy

    @classmethod
    def extract_flags(
        cls, raw_input: str, backend=None
    ) -> Tuple[str, int, Optional[int], Any, Optional[str]]:
        """
        Извлекает и валидирует флаги -s/-k/-m из строки.
        Возвращает (остаток_текста, spacing, hotkey, monitor_spec, ошибка).
        Работает и для формул, и для имен сохраненных макетов.
        """
        text = (raw_input or "").strip()
        if not text:
            return "", 16, None, None, None

        spacing = 16
        hotkey = None
        monitor_raw = None

        for match in cls.FLAG_REGEX.finditer(text):
            flag = match.group("flag")
            val = match.group("val")
            if flag == "s":
                if not val.isdigit():
                    return text, spacing, hotkey, None, (
                        f"Флаг -s требует целое число пикселей (0..200), "
                        f"получено '{val}'"
                    )
                spacing = int(val)
                if spacing > 200:
                    return text, spacing, hotkey, None, (
                        f"Отступ -s {spacing}px слишком велик (максимум 200)"
                    )
            elif flag == "k":
                if not (val.isdigit() and len(val) == 1):
                    return text, spacing, hotkey, None, (
                        f"Флаг -k требует одну цифру 0-9, получено '{val}'"
                    )
                hotkey = int(val)
            elif flag == "m":
                monitor_raw = val

        text = cls.FLAG_REGEX.sub(" ", text)
        text = " ".join(text.split()).strip()

        # Осиротевшие флаги без значения или неизвестные
        for token in text.split():
            if token.startswith("-") and len(token) > 1 and not token[1:].isdigit():
                return text, spacing, hotkey, None, (
                    f"Похоже на флаг '{token}': допустимы только -s/-k/-m "
                    "со значением"
                )

        monitor = None
        if monitor_raw is not None:
            if backend is not None:
                monitor, monitor_err = backend.resolve_monitor(monitor_raw)
                if monitor_err:
                    return text, spacing, hotkey, None, monitor_err
            else:
                t = monitor_raw.strip()
                if t.lower() in ("all", "*"):
                    monitor = "all"
                elif t.isdigit() and int(t) >= 1:
                    monitor = int(t)
                else:
                    return text, spacing, hotkey, None, (
                        f"Некорректный монитор '{t}': укажите номер >= 1 или 'all'"
                    )

        return text, spacing, hotkey, monitor, None

    @classmethod
    def parse_command(
        cls, raw_input: str, backend=None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Разбирает команду: <Выражение> [-s px] [-k 0-9] [-m <монитор>] [Имя]
        -m: номер монитора (1-based, как у FancyZonesCLI/get-monitors),
        его имя (подстрока) или 'all'. Без -m — активный монитор.
        """
        text = raw_input.strip()
        if not text:
            return None, "Пустой запрос"

        # 1. Извлечение и строгая валидация флагов (-s, -k, -m)
        text, spacing, hotkey, monitor, err = cls.extract_flags(text, backend)
        if err:
            return None, err
        if not text:
            return None, "Пустой запрос: указана только геометрия или имя"

        # 2. Многоуровневый режим (слои через >)
        if ">" in text:
            parts = [p.strip() for p in text.split(">") if p.strip()]
            if len(parts) < 2:
                return None, "Для оператора '>' требуется как минимум два слоя"

            last_tokens = parts[-1].split()
            known_names = []
            if backend:
                known_names = [
                    l.get("name", "").lower()
                    for l in backend.get_custom_layouts()
                ]

            matched_layer = None
            name = "Temp"

            # Выделяем, где заканчивается формула слоя и начинается имя
            for k in range(len(last_tokens), 0, -1):
                candidate = " ".join(last_tokens[:k])
                if (
                    candidate.lower() in known_names
                    or cls.BLOCK_REGEX.match(candidate)
                    or cls.GRID_REGEX.match(candidate)
                    or any(c in candidate for c in ["+", "/", "|", ";"])
                ):
                    matched_layer = candidate
                    remaining = " ".join(last_tokens[k:]).strip()
                    name = remaining if remaining else "Temp"
                    break

            if matched_layer:
                parts[-1] = matched_layer
            else:
                name = "Temp"

            return {
                "mode": "layered",
                "layers": parts,
                "name": name,
                "spacing": spacing,
                "hotkey": hotkey,
                "monitor": monitor,
            }, None

        # 3. Базовые режимы геометрии
        # А. Матрица (| или ;)
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

            return {
                "mode": "matrix",
                "geom": " | ".join(rows_raw),
                "name": name,
                "spacing": spacing,
                "hotkey": hotkey,
                "monitor": monitor,
            }, None

        # Б. Сетка RxC (например: 2x2, 2x3)
        tokens = text.split()
        if tokens and cls.GRID_REGEX.match(tokens[0]):
            geom = tokens[0]
            name = " ".join(tokens[1:]).strip() if len(tokens) > 1 else "Temp"
            return {
                "mode": "grid",
                "geom": geom,
                "name": name,
                "spacing": spacing,
                "hotkey": hotkey,
                "monitor": monitor,
            }, None

        # В. Строки (/)
        if "/" in text:
            parts = [p.strip() for p in text.split("/")]
            last_tokens = parts[-1].split()

            if len(last_tokens) > 1 and cls.BLOCK_REGEX.match(last_tokens[0]):
                parts[-1] = last_tokens[0]
                name = " ".join(last_tokens[1:])
            else:
                name = "Temp"

            return {
                "mode": "rows",
                "geom": " / ".join(parts),
                "name": name,
                "spacing": spacing,
                "hotkey": hotkey,
                "monitor": monitor,
            }, None

        # Г. Колонки (+) или одиночный блок (например: '1+2' или просто '2' / '{3:1}')
        parts = [p.strip() for p in text.split("+")]
        last_tokens = parts[-1].split()

        if len(last_tokens) > 1 and cls.BLOCK_REGEX.match(last_tokens[0]):
            parts[-1] = last_tokens[0]
            name = " ".join(last_tokens[1:])
        elif len(parts) == 1 and cls.BLOCK_REGEX.match(parts[0]):
            name = "Temp"
        elif len(parts) > 1 and cls.BLOCK_REGEX.match(last_tokens[0]):
            name = "Temp"
        else:
            return None, f"Не распознан синтаксис: {text}"

        return {
            "mode": "columns",
            "geom": " + ".join(parts),
            "name": name,
            "spacing": spacing,
            "hotkey": hotkey,
            "monitor": monitor,
        }, None

    @classmethod
    def compile(
        cls, parsed: Dict[str, Any], backend=None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Транслирует разобранный запрос в структуру FancyZones."""
        try:
            mode = parsed["mode"]
            name = parsed["name"]
            spacing = parsed["spacing"]
            monitor = parsed.get("monitor")

            # Безымянный макет: персональный Temp-слот целевого монитора
            fixed_uuid = None
            if name.strip().lower() == "temp":
                fixed_uuid, name = cls.temp_slot(monitor, backend)

            # Реальное разрешение целевого монитора — для точных отступов canvas
            ref_w, ref_h = 1920, 1080
            if backend is not None:
                try:
                    ref_w, ref_h = backend.get_spacing_ref(monitor)
                except Exception:
                    ref_w, ref_h = 1920, 1080

            if mode == "layered":
                return cls._compile_layered(
                    parsed["layers"], name, spacing, backend,
                    ref_w, ref_h, monitor, fixed_uuid,
                )
            elif mode == "columns":
                return cls._build_flow_layout(
                    parsed["geom"], name, spacing, is_cols=True,
                    ref_w=ref_w, ref_h=ref_h, fixed_uuid=fixed_uuid,
                )
            elif mode == "rows":
                return cls._build_flow_layout(
                    parsed["geom"], name, spacing, is_cols=False,
                    ref_w=ref_w, ref_h=ref_h, fixed_uuid=fixed_uuid,
                )
            elif mode == "matrix":
                return cls._build_matrix_layout(
                    parsed["geom"], name, spacing,
                    ref_w=ref_w, ref_h=ref_h, fixed_uuid=fixed_uuid,
                )
            elif mode == "grid":
                return cls._build_quick_grid(
                    parsed["geom"], name, spacing, fixed_uuid=fixed_uuid
                )

            return None, "Неизвестный режим разметки"
        except Exception as e:
            return None, str(e)

    @classmethod
    def _parse_block(cls, block_str: str) -> Tuple[List[Tuple[int, bool]], int]:
        """Парсит блок. Возвращает: ([(вес, is_void), ...], внешний_вес)."""
        match = cls.BLOCK_REGEX.match(block_str.strip())
        if not match:
            raise ValueError(f"Неверный синтаксис блока: '{block_str}'")

        inside = match.group(1)
        outer_w_str = match.group("outer_w")
        outer_weight = int(outer_w_str) if outer_w_str else 1
        if outer_weight < 1:
            raise ValueError(
                f"Вес блока '{block_str}' должен быть >= 1"
            )

        sub_items: List[Tuple[int, bool]] = []

        if inside.startswith("{") and inside.endswith("}"):
            tokens = [t.strip() for t in inside[1:-1].split(":") if t.strip()]
            if not tokens:
                raise ValueError("Пустое выражение в фигурных скобках {}")

            for token in tokens:
                sub_match = cls.SUB_ITEM_REGEX.match(token)
                if not sub_match:
                    raise ValueError(f"Неверный элемент внутри скобок: '{token}'")

                val = int(sub_match.group("val"))
                w_str = sub_match.group("w")

                if val == 0:
                    # Пустота: 0 или 0(w)
                    weight = int(w_str) if w_str else 1
                    if weight < 1:
                        raise ValueError(
                            f"Пустота '{token}' должна иметь вес >= 1"
                        )
                    sub_items.append((weight, True))
                else:
                    # Активная зона: val или val(w)
                    weight = int(w_str) if w_str else val
                    if weight < 1:
                        raise ValueError(
                            f"Элемент '{token}' должен иметь вес >= 1"
                        )
                    sub_items.append((weight, False))
        else:
            count = int(inside)
            if count == 0:
                sub_items.append((1, True))
            else:
                for _ in range(count):
                    sub_items.append((1, False))

        return sub_items, outer_weight

    @classmethod
    def _build_flow_layout(
        cls, geom: str, name: str, spacing: int, is_cols: bool,
        ref_w: int = 1920, ref_h: int = 1080, fixed_uuid: Optional[str] = None,
    ):
        delimiter = "+" if is_cols else "/"
        raw_blocks = [b.strip() for b in geom.split(delimiter) if b.strip()]
        slices = [cls._parse_block(b) for b in raw_blocks]

        has_voids = any(
            any(is_void for _, is_void in sub_items)
            for sub_items, _ in slices
        )

        main_weights = [w for _, w in slices]
        total_main_weight = sum(main_weights)

        # Если есть пустоты -> строим Canvas
        if has_voids:
            canvas_zones = []
            curr_main = Fraction(0, 1)

            sx, sy = cls._canvas_gap(spacing, ref_w, ref_h)

            for sub_items, weight in slices:
                slice_fraction = Fraction(weight, total_main_weight)
                slice_start = curr_main
                slice_end = curr_main + slice_fraction
                curr_main = slice_end

                total_sub = sum(w for w, _ in sub_items)
                curr_sub = Fraction(0, 1)

                for w_sub, is_void in sub_items:
                    sub_fraction = Fraction(w_sub, total_sub)
                    sub_start = curr_sub
                    sub_end = curr_sub + sub_fraction
                    curr_sub = sub_end

                    if is_void:
                        continue

                    if is_cols:
                        x = int(round(float(slice_start) * 10000))
                        w_val = int(round(float(slice_fraction) * 10000))
                        y = int(round(float(sub_start) * 10000))
                        h_val = int(round(float(sub_fraction) * 10000))
                    else:
                        y = int(round(float(slice_start) * 10000))
                        h_val = int(round(float(slice_fraction) * 10000))
                        x = int(round(float(sub_start) * 10000))
                        w_val = int(round(float(sub_fraction) * 10000))

                    if spacing > 0:
                        x = x + sx // 2
                        w_val = max(100, w_val - sx)
                        y = y + sy // 2
                        h_val = max(100, h_val - sy)

                    canvas_zones.append(
                        {
                            "X": x,
                            "Y": y,
                            "width": w_val,
                            "height": h_val,
                        }
                    )

            layout_uuid = fixed_uuid or f"{{{str(uuid.uuid4()).upper()}}}"
            summary = f"{'Колонки' if is_cols else 'Строки'} с пустотами: {geom} ({len(canvas_zones)} зон)"

            return {
                "uuid": layout_uuid,
                "name": name,
                "type": "canvas",
                "summary": summary,
                "info": {
                    "ref-width": 10000,
                    "ref-height": 10000,
                    "zones": canvas_zones,
                    "sensitivity-radius": 20,
                },
            }, None

        # Если пустот нет -> Grid
        main_fractions = [Fraction(w, total_main_weight) for w in main_weights]
        all_cuts = {Fraction(0, 1), Fraction(1, 1)}
        slice_cuts_map = []

        for sub_items, _ in slices:
            heights = [w for w, _ in sub_items]
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
            rows_count, cols_count = num_sub_layers, len(slices)
            rows_pct = fractions_to_percentages(sub_fractions)
            cols_pct = fractions_to_percentages(main_fractions)
            grid = [[0] * cols_count for _ in range(rows_count)]

            for c_idx, (sub_items, _) in enumerate(slices):
                cuts = slice_cuts_map[c_idx]
                for z_idx in range(len(sub_items)):
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
            rows_count, cols_count = len(slices), num_sub_layers
            rows_pct = fractions_to_percentages(main_fractions)
            cols_pct = fractions_to_percentages(sub_fractions)
            grid = [[0] * cols_count for _ in range(rows_count)]

            for r_idx, (sub_items, _) in enumerate(slices):
                cuts = slice_cuts_map[r_idx]
                for z_idx in range(len(sub_items)):
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
                fixed_uuid=fixed_uuid,
            ),
            None,
        )

    @classmethod
    def _build_matrix_layout(
        cls, geom: str, name: str, spacing: int,
        ref_w: int = 1920, ref_h: int = 1080, fixed_uuid: Optional[str] = None,
    ):
        rows_raw = [r.strip().split() for r in re.split(r"[|;]", geom) if r.strip()]
        rows_count = len(rows_raw)
        cols_count = len(rows_raw[0])

        if any(len(r) != cols_count for r in rows_raw):
            raise ValueError(
                "Все строки матрицы должны содержать одинаковое число элементов"
            )

        void_symbols = {"0", ".", "_"}
        has_voids = any(
            token in void_symbols for r in rows_raw for token in r
        )

        char_map = {}
        grid = []
        for r in rows_raw:
            row_ids = []
            for token in r:
                if token in void_symbols:
                    row_ids.append(-1)
                else:
                    if token not in char_map:
                        char_map[token] = len(char_map)
                    row_ids.append(char_map[token])
            grid.append(row_ids)

        # И FancyZones-grid, и FancyZones-canvas понимают только прямоугольные
        # зоны: проверяем, что клетки каждого символа образуют прямоугольник.
        cells: Dict[int, List[Tuple[int, int]]] = {}
        for r_idx, row in enumerate(grid):
            for c_idx, z_id in enumerate(row):
                if z_id >= 0:
                    cells.setdefault(z_id, []).append((r_idx, c_idx))
        id_to_symbol = {z_id: sym for sym, z_id in char_map.items()}
        for z_id, lst in cells.items():
            min_r = min(p[0] for p in lst)
            max_r = max(p[0] for p in lst)
            min_c = min(p[1] for p in lst)
            max_c = max(p[1] for p in lst)
            if len(lst) != (max_r - min_r + 1) * (max_c - min_c + 1):
                sym = id_to_symbol.get(z_id, z_id)
                raise ValueError(
                    f"Зона '{sym}' не образует прямоугольник: зоны FancyZones "
                    "должны быть прямоугольными"
                )

        def equal_pct(count: int) -> List[int]:
            base = 10000 // count
            res = [base] * count
            res[-1] += 10000 - sum(res)
            return res

        if has_voids:
            canvas_zones = []
            bounds = {}
            for r_idx, row in enumerate(grid):
                for c_idx, z_id in enumerate(row):
                    if z_id == -1:
                        continue
                    if z_id not in bounds:
                        bounds[z_id] = {
                            "min_r": r_idx,
                            "max_r": r_idx,
                            "min_c": c_idx,
                            "max_c": c_idx,
                        }
                    else:
                        b = bounds[z_id]
                        b["min_r"] = min(b["min_r"], r_idx)
                        b["max_r"] = max(b["max_r"], r_idx)
                        b["min_c"] = min(b["min_c"], c_idx)
                        b["max_c"] = max(b["max_c"], c_idx)

            cell_w = 10000 // cols_count
            cell_h = 10000 // rows_count
            sx, sy = cls._canvas_gap(spacing, ref_w, ref_h)

            for z_id in sorted(bounds.keys()):
                b = bounds[z_id]
                x = b["min_c"] * cell_w
                w = (b["max_c"] - b["min_c"] + 1) * cell_w
                y = b["min_r"] * cell_h
                h = (b["max_r"] - b["min_r"] + 1) * cell_h

                if spacing > 0:
                    x = x + sx // 2
                    w = max(100, w - sx)
                    y = y + sy // 2
                    h = max(100, h - sy)

                canvas_zones.append(
                    {"X": x, "Y": y, "width": w, "height": h}
                )

            layout_uuid = fixed_uuid or f"{{{str(uuid.uuid4()).upper()}}}"
            return {
                "uuid": layout_uuid,
                "name": name,
                "type": "canvas",
                "summary": f"Матрица с пустотами {rows_count}x{cols_count} ({len(char_map)} зон)",
                "info": {
                    "ref-width": 10000,
                    "ref-height": 10000,
                    "zones": canvas_zones,
                    "sensitivity-radius": 20,
                },
            }, None

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
                fixed_uuid=fixed_uuid,
            ),
            None,
        )

    @classmethod
    def _compile_layered(
        cls, layers: List[str], name: str, spacing: int, backend,
        ref_w: int = 1920, ref_h: int = 1080, monitor_spec: Any = None,
        fixed_uuid: Optional[str] = None,
    ):
        combined_zones = []
        layer_summaries = []

        for layer_str in layers:
            layout_data = None
            if backend:
                layout_data = backend.get_layout_by_name(layer_str)

            if not layout_data:
                parsed_sub, err = cls.parse_command(layer_str, backend)
                if not err and parsed_sub and parsed_sub["mode"] != "layered":
                    # Наследуем целевой монитор всей команды (учёт -m)
                    parsed_sub["monitor"] = monitor_spec
                    layout_data, comp_err = cls.compile(parsed_sub, backend)
                    if comp_err:
                        return (
                            None,
                            f"Ошибка в слое '{layer_str}': {comp_err}",
                        )
                else:
                    return (
                        None,
                        f"Слой '{layer_str}' не найден среди макетов и не является формулой",
                    )

            zones = cls._extract_canvas_zones(layout_data, spacing, ref_w, ref_h)
            if not zones:
                return None, f"Слой '{layer_str}' не содержит зон"

            combined_zones.extend(zones)
            layer_summaries.append(f"{layer_str} ({len(zones)}з)")

        summary = f"Холст: {' > '.join(layer_summaries)} (Всего {len(combined_zones)} зон)"
        layout_uuid = fixed_uuid or f"{{{str(uuid.uuid4()).upper()}}}"

        return {
            "uuid": layout_uuid,
            "name": name,
            "type": "canvas",
            "summary": summary,
            "info": {
                "ref-width": 10000,
                "ref-height": 10000,
                "zones": combined_zones,
                "sensitivity-radius": 20,
            },
        }, None

    @classmethod
    def _extract_canvas_zones(
        cls, layout: Dict[str, Any], spacing: int,
        ref_w: int = 1920, ref_h: int = 1080,
    ) -> List[Dict[str, int]]:
        l_type = layout.get("type", "grid")
        info = layout.get("info", {})

        if l_type == "canvas":
            ref_w = info.get("ref-width", 10000) or 10000
            ref_h = info.get("ref-height", 10000) or 10000
            res = []
            for z in info.get("zones", []):
                x = int(round(z["X"] * 10000 / ref_w))
                y = int(round(z["Y"] * 10000 / ref_h))
                w = int(round(z["width"] * 10000 / ref_w))
                h = int(round(z["height"] * 10000 / ref_h))
                res.append({"X": x, "Y": y, "width": w, "height": h})
            return res

        rows_pct = info.get("rows-percentage", [])
        cols_pct = info.get("columns-percentage", [])
        cell_map = info.get("cell-child-map", [])

        if not cell_map or not rows_pct or not cols_pct:
            return []

        bounds = {}
        for r, row in enumerate(cell_map):
            for c, z_id in enumerate(row):
                if z_id == -1:
                    continue
                if z_id not in bounds:
                    bounds[z_id] = {
                        "min_r": r,
                        "max_r": r,
                        "min_c": c,
                        "max_c": c,
                    }
                else:
                    b = bounds[z_id]
                    b["min_r"] = min(b["min_r"], r)
                    b["max_r"] = max(b["max_r"], r)
                    b["min_c"] = min(b["min_c"], c)
                    b["max_c"] = max(b["max_c"], c)

        sx, sy = cls._canvas_gap(spacing, ref_w, ref_h)

        canvas_zones = []
        for z_id in sorted(bounds.keys()):
            b = bounds[z_id]
            x = sum(cols_pct[: b["min_c"]])
            w = sum(cols_pct[b["min_c"] : b["max_c"] + 1])
            y = sum(rows_pct[: b["min_r"]])
            h = sum(rows_pct[b["min_r"] : b["max_r"] + 1])

            if spacing > 0:
                x = x + sx // 2
                w = max(100, w - sx)
                y = y + sy // 2
                h = max(100, h - sy)

            canvas_zones.append(
                {"X": int(x), "Y": int(y), "width": int(w), "height": int(h)}
            )

        return canvas_zones

    @classmethod
    def _build_quick_grid(
        cls, geom: str, name: str, spacing: int,
        fixed_uuid: Optional[str] = None,
    ):
        match = cls.GRID_REGEX.match(geom)
        if not match:
            raise ValueError(f"Неверный формат сетки: '{geom}'")

        rows = int(match.group("rows"))
        cols = int(match.group("cols"))

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
                fixed_uuid=fixed_uuid,
            ),
            None,
        )

    @classmethod
    def _create_fz_json(
        cls, name, rows, cols, rows_pct, cols_pct, grid, spacing, summary,
        fixed_uuid: Optional[str] = None,
    ):
        layout_uuid = fixed_uuid or f"{{{str(uuid.uuid4()).upper()}}}"
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