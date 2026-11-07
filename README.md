# ⚡ FancyZones DSL Tiler

**Tile PowerToys FancyZones layouts straight from the Flow Launcher search bar — with a compact, keyboard-only DSL.**

[![Flow Launcher](https://img.shields.io/badge/Flow%20Launcher-plugin-blue?style=flat-square)](https://flowlauncher.com)
[![PowerToys](https://img.shields.io/badge/PowerToys-FancyZones-0078D4?style=flat-square)](https://github.com/microsoft/PowerToys)
[![Python](https://img.shields.io/badge/Python-3.8%2B-yellow?style=flat-square)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![CI](https://github.com/RADiant-Git/FancyZones-DSL/actions/workflows/ci.yml/badge.svg)](https://github.com/RADiant-Git/FancyZones-DSL/actions/workflows/ci.yml)

**English** · [Русский](README.ru.md)

---

## Table of contents

- [Why](#why)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Command grammar](#command-grammar)
- [DSL reference](#dsl-reference)
  - [Building blocks: Shape(Weight)](#building-blocks-shapeweight)
  - [Voids: empty desktop space](#voids-empty-desktop-space)
  - [Columns](#columns)
  - [Rows](#rows)
  - [Quick grid](#quick-grid)
  - [Letter matrix](#letter-matrix)
  - [Layers](#layers)
  - [Multi-monitor targeting](#multi-monitor-targeting)
  - [Hotkeys](#hotkeys)
  - [Spacing](#spacing)
- [Recipes](#recipes)
- [Search, apply and manage](#search-apply-and-manage)
- [How it works](#how-it-works)
- [Files the plugin touches](#files-the-plugin-touches)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Development](#development)
- [Publishing and store submission](#publishing-and-store-submission)
- [License](#license)
- [Changelog](#changelog)

---

## Why

PowerToys FancyZones ships a visual layout editor: to get a new grid you open a settings window,
drag dividers with a mouse and click through dialogs. That is fine once, and tedious the tenth time.

**FancyZones DSL Tiler** moves the speed of tiling window managers (i3, bspwm, Hyprland) into Windows:

1. Press `Alt + Space` to open Flow Launcher.
2. Type a layout formula — for example `fz 1(3)+2(2) -s 8 Code`.
3. Press `Enter`. The layout is compiled, saved into PowerToys and applied to the target monitor.

No settings window, no mouse, no restart. Saved layouts stay addressable by name, so
`fz Code` becomes a one-word command you can bind to a global hotkey.

---

## Features

- 📐 **Flow splitting** — divide the screen into columns (`+`) or rows (`/`).
- ⚖️ **Relative weights** — size blocks with coefficients: `1(3)+2(2)` is a 3:2 split.
- 🎛️ **Custom inner proportions** — slice a block further with `{3:1}`, `{1:2:1}`.
- 🕳️ **Voids / spacers** — reserve desktop space for widgets, a video call, or a centered
  floating window: `0(2)`, `{1:0(1):1}`.
- 🥞 **Layered composition (`>`)** — stack saved layouts and formulas into one canvas with
  explicit Z-order, e.g. a full-screen focus zone on top of a `1+2` grid.
- 🧩 **2D letter matrices** — free-form layouts drawn as ASCII: `A A B | C . B | D . D`.
- ⚡ **Quick grids** — `2x2`, `3x4`, `4x2` in four keystrokes.
- 🧠 **Automatic engine selection** — gapless layouts compile to a native FancyZones `grid`;
  layouts with voids or layers compile to an adaptive `canvas` (10000×10000 reference space).
- 🖥️ **Multi-monitor targeting** — `-m 2`, `-m msi`, `-m all`, with `canvas` gaps recalculated
  from the real resolution of the target monitor.
- 🔄 **Per-monitor `Temp` slots** — unnamed formulas get a dedicated slot per screen, so
  overwriting a formula on one monitor never reshuffles another.
- 🛡️ **Safe slot migration** — before a shared slot is overwritten, other monitors are moved onto
  a copy of the previous content, so nothing is silently lost.
- ⌨️ **Hotkeys on the fly** — bind `Win + Ctrl + Alt + [0-9]` with `-k`.
- 🖱️ **Context menu** — per-monitor apply, merge on top of / under another layout, duplicate,
  inspect where a layout is currently applied, delete.
- 🔍 **Fuzzy search** — `fz` alone lists everything; `fz cod` finds `Code`.

---

## Requirements

| Component | Requirement |
| :--- | :--- |
| **Flow Launcher** | A recent release (tested on **2.1.4**). The plugin uses standard JSON-RPC only. |
| **Microsoft PowerToys** | Any build that ships `FancyZonesCLI.exe` (tested on **0.103.3062.0**) with the **FancyZones** module enabled. |
| **Python** | Python **3.8+**. In practice you need nothing installed: Flow Launcher runs Python plugins with its own embedded Python. |

The plugin talks to PowerToys exclusively through the official `FancyZonesCLI.exe`, so there is no
private API to break and no PowerToys settings file is patched behind PowerToys' back.

`FancyZonesCLI.exe` is located in this order:

1. `PATH`
2. `%ProgramFiles%\PowerToys\FancyZonesCLI.exe`
3. `%ProgramFiles%\PowerToys\modules\FancyZones\FancyZonesCLI.exe`
4. `%LOCALAPPDATA%\Programs\PowerToys\FancyZonesCLI.exe`

If it cannot be found, the plugin still compiles and saves layouts but shows a warning row in the
results, because applying them requires the CLI.

---

## Installation

### From the Flow Launcher plugin store

Once the plugin is published in the store, run:

```text
pm install FancyZones DSL Tiler
```

### From a release zip

1. Download `FancyZonesDSL.zip` from the [latest release](https://github.com/RADiant-Git/FancyZones-DSL/releases/latest).
2. In Flow Launcher, run `Settings → Plugins → Add plugin` and pick the zip, **or** unpack it into
   `%APPDATA%\FlowLauncher\Plugins\FancyZonesDSL\`.

### From source (for development)

```cmd
cd "%APPDATA%\FlowLauncher\Plugins"
git clone https://github.com/RADiant-Git/FancyZones-DSL.git FancyZonesDSL
cd FancyZonesDSL
pip install -r requirements.txt -t ./lib
```

`./lib` is committed to the repository, so the `pip install` step is only needed to refresh the
vendored dependency. Restart Flow Launcher afterwards (or press `Ctrl + R` in its search bar).

> **Note on the action keyword.** `plugin.json` declares `ActionKeyword: "fz"`. Every command below
> is written as `fz …`. You can change the keyword in Flow Launcher's plugin settings if `fz`
> collides with another plugin.

---

## Quick start

Open Flow Launcher and type any of these:

```text
fz 1+2+1                      three columns: 1 zone, 2 stacked, 1 zone
fz 1(3)+2(2) -s 8 Code        a saved 3:2 "Code" layout with 8 px gaps
fz 2x2 -s 0                   a gapless 2×2 grid on the active monitor
fz 3x2 -m 2 Docs              a 3×2 grid applied to monitor #2
fz 0(1) + 1(2) + 0(1) Wide    a wide zone in the middle, empty desktop at the sides
fz Code                       apply the saved "Code" layout (fuzzy search)
fz                            list every saved layout
```

---

## Command grammar

```text
fz <geometry | layers> [-s <px>] [-k <0-9>] [-m <monitor>] [Name]
```

| Flag | Meaning | Default | Validation |
| :--- | :--- | :--- | :--- |
| `-s <px>` | Gap between zones, in pixels | `16` | integer `0…200` |
| `-k <0-9>` | Bind the system hotkey `Win + Ctrl + Alt + <digit>` to the layout | — | exactly one digit |
| `-m <monitor>` | Target monitor | active monitor | `1…N`, a monitor name/serial substring, or `all` / `*` |

The optional trailing `Name` is the layout's display name. **If you omit it, the layout is written
into the reusable `Temp` slot** (see [Per-monitor `Temp` slots](#per-monitor-temp-slots)).

Flags are position-independent and may appear anywhere after the geometry. They also work with
saved layout names:

```text
fz Wide Solo -m 2      apply the saved "Wide Solo" to monitor #2
fz Master L -k 5       bind Win+Ctrl+Alt+5 to the saved "Master L"
fz -m all              list every saved layout, each applicable to all monitors
```

Malformed flags are reported instead of being ignored:

```text
fz 1+1 -s abc   →  Flag -s expects an integer number of pixels (0..200), got 'abc'
fz 1+1 -k 55    →  Flag -k expects a single digit 0-9, got '55'
fz 1+1 -s 999   →  Gap -s 999px is too large (maximum 200)
fz 1+1 -x 3     →  Looks like a flag '-x': only -s/-k/-m with a value are supported
```

---

## DSL reference

### Building blocks: Shape(Weight)

Every element in a column (`+`) or row (`/`) chain follows one rule: **how many zones it contains**
and **how much space it takes** relative to its siblings.

| Form | Zones inside | Relative weight | Meaning |
| :--- | :---: | :---: | :--- |
| `1` | 1 | 1 | A single zone of base size. |
| `1(2)` | 1 | 2 | A single zone twice as wide/tall as a base block. |
| `N` | N | 1 | `N` equal zones inside a base-size block (`2`, `3`, …). |
| `N(w)` | N | w | `N` equal zones inside a block `w` times base size. |
| `0` | 0 (void) | 1 | Empty desktop of base size. |
| `0(w)` | 0 (void) | w | Empty desktop of relative size `w`. |
| `{h₁:h₂:…}` | one per entry | 1 | A block sliced into zones with the given weights. |
| `{h₁:h₂:…}(w)` | one per entry | w | The same, with an outer weight of `w`. |

> **Weights, not counts.** Inside `{}` each number is a *weight*: `{3:1}` is **two** zones split
> 75 % / 25 %, not three zones. Outside braces a bare number *is* a count: `3` is three equal zones.

Examples:

```text
1 + 2 + 1          → 4 zones: one, then two stacked, then one
1(3) + 2(2)        → 3 zones, columns split 60 % / 40 %
{3:1}              → 2 zones, split 75 % / 25 %
{1:2:1}            → 3 zones, split 25 % / 50 % / 25 %
```

### Voids: empty desktop space

A void (`0`) reserves screen area that FancyZones will never snap a window into. Voids are what
turn a plain grid into a dashboard, a picture-in-picture frame or a centered floating window.

| Form | Meaning |
| :--- | :--- |
| `0` | Void of base weight. |
| `0(w)` | Void of relative weight `w`. |
| `{1:0:1}` | Inside a block: zone, void, zone — each a third. |
| `{1:0(2):1}` | Inside a block: zone 25 %, void 50 %, zone 25 %. |

A layout containing **any** void is compiled to `canvas` instead of `grid`, because native
FancyZones grids cannot express holes.

```text
fz 0(1) + 1(2) + 0(1) Wide        a single wide zone with empty desktop on both sides
fz 0(1) + {0(1):2:0(1)}(2) + 0(1) CenterFloat
                                   a 50 %×50 % zone dead-centre, everything else free
```

### Columns

The `+` operator splits the screen vertically into columns, left to right. Each column is then subdivided
top-to-bottom according to its own shape.

```text
fz 1 + 2 + 1
```

```text
┌───────┬───────┬───────┐
│       │   1   │       │
│   0   ├───────┤   3   │
│       │   2   │       │
└───────┴───────┴───────┘
```

### Rows

The `/` operator splits the screen horizontally into bands, top to bottom. Each band is subdivided left-to-right.

```text
fz 1 / 3 / 1
```

```text
┌───────────────────────┐
│           0           │
├───┬───┬───────────────┤
│ 1 │ 2 │       3       │
├───┴───┴───────────────┤
│           4           │
└───────────────────────┘
```

### Quick grid

The `RxC` form builds uniform tables in four characters. `R` is the number of rows, `C` the number of columns.

```text
fz 2x2 -s 0        gapless 2×2
fz 3x4             a 3×4 table of 12 zones
```

Both dimensions must be greater than zero; `0x2` is rejected with a clear error.

### Letter matrix

The `|` and `;` operators let you draw the layout as ASCII. Rows are separated by `|` (or `;`), cells within a row by spaces.
**Cells sharing a letter belong to the same zone**, so a letter repeated in adjacent cells grows
that zone. The symbols `0`, `.` and `_` mean *void*.

```text
fz A A B | C . B | D D D
```

```text
┌───────────┬───────┐
│     A     │   B   │
├───────┬───┤       │
│   C   │ . │       │
├───────┴───┴───────┤
│         D         │
└───────────────────┘
```

Rules:

- Every row must contain the same number of cells.
- A letter's cells must form a **rectangle** — FancyZones zones are rectangular, so
  `A A | A B` is rejected with `Zone 'A' does not form a rectangle`.
- A matrix containing voids is compiled to `canvas`; a gapless one becomes a `grid`.

### Layers

The `>` operator composes several layouts into a single `canvas`, stacking their zones in Z-order.
Later layers end up **on top**. Each layer may be either the name of a saved layout or a DSL formula.

```text
fz <layer 1> > <layer 2> [> <layer 3> …] [Name]
```

```text
   layer 1: "Master L"                layer 2: "1"
┌───────────┬───────────┐          ┌─────────────────────────┐
│           │   zone 1  │          │                         │
│  zone 0   ├───────────┤    >     │   zone 3 (overlapping)  │
│           │   zone 2  │          │                         │
└───────────┴───────────┘          └─────────────────────────┘
                       │
                       ▼
        resulting canvas (4 zones, zone 3 on top)
┌───────────┬───────────┐
│░░░░░░░░░░░│   zone 1  │
│░░ zone 3 ░├───────────┤
│░░░░░░░░░░░│   zone 2  │
└───────────┴───────────┘
```

```text
fz 1+2 > 1 -k 1 DevStack              a 1+2 grid with a full-screen focus zone on top
fz Master L > Solo Left Combined      merge two saved layouts
```

To snap a window into an overlapping zone, hold `Shift` while dragging (or `Ctrl`, depending on
your PowerToys "zone activation" setting). FancyZones highlights the topmost zone under the cursor.

### Multi-monitor targeting

The `-m` flag takes a monitor. Monitor numbers match PowerToys' own numbering (`FancyZonesCLI.exe get-monitors`) and are
**1-based**. You can also pass a substring of the monitor name or serial number, or `all` / `*`.

```text
fz 2x2 -m 1 First                 monitor #1
fz 1(3)+2(2) -m 2 Work            monitor #2
fz 3x3 -m all GridEverywhere      every monitor at once
fz 1+0(2)+1 -m msi WideOnly       by monitor name substring
fz 2x2 -m 0                       → error: numbering is 1-based
fz 2x2 -m 9                       → error: lists the available monitors
```

Without `-m` the layout is applied to the **active** monitor (the one FancyZones reports as
selected). For `canvas` layouts the `-s` gap is recalculated from the target monitor's real
resolution (via `get-monitors`, cached for 20 seconds), so 16 px really is 16 px on 1080p, 1440p
and 4K alike.

To discover the numbering:

```cmd
"C:\Program Files\PowerToys\FancyZonesCLI.exe" get-monitors
```

#### Per-monitor `Temp` slots

An unnamed formula is stored in a fixed, reusable slot rather than creating a new layout every time:

| Target | Slot name | Layout UUID |
| :--- | :--- | :--- |
| monitor #1, or `-m all` | `Temp` | `{00000000-0000-0000-0000-000000000001}` |
| monitor #N | `Temp N` | `{00000000-0000-0000-0000-00000000000N}` |

Because each monitor gets its own slot, `fz 2x2 -m 1` followed by `fz 1+1 -m 2` leaves two
different grids on the two screens. `-m all` intentionally uses the single shared `Temp` slot.

If a monitor still points at a slot you are about to overwrite (a leftover from older versions),
the plugin first copies the old content into a new layout named `Temp (M<n>)` and re-applies it
there — so the other screen keeps its grid instead of silently inheriting the new one.

Give the layout a name to keep it permanently:

```text
fz 1(3)+2(2) -s 8 Code      stored as a real, named layout — never recycled
```

### Hotkeys

The `-k` flag binds the layout to one of PowerToys' ten global layout shortcuts, `Win + Ctrl + Alt + [0-9]`.

```text
fz 1(3)+2(2) -s 8 -k 1 Code     bind Win+Ctrl+Alt+1 to "Code"
fz Code -k 3                    re-bind the saved "Code" to Win+Ctrl+Alt+3
```

### Spacing

The `-s` flag sets the gap FancyZones leaves between zones and around the screen edge.

```text
fz 2x2 -s 0      zones meet exactly, no gaps
fz 2x2 -s 24     a roomier grid
```

Accepted range is `0…200` px; larger values are rejected. For `grid` layouts the gap is stored in
the layout itself. For `canvas` layouts the pixel gap is baked into the zone coordinates relative
to the target monitor's real resolution.

---

## Recipes

| Goal | Command |
| :--- | :--- |
| **Master-stack for coding**<br>60 % editor on the left, two helpers on the right | `fz 1(3)+2(2) -s 8 Code` |
| **Centered floating window**<br>A 50 %×50 % zone dead-centre, free desktop around it | `fz 0(1) + {0(1):2:0(1)}(2) + 0(1) CenterFloat` |
| **Ultrawide split**<br>Work zones at the edges, free space in the middle | `fz 1(2) + 0(3) + 1(2) -s 10 WideSplit` |
| **Dashboard with widget space**<br>Full zone left, empty band on top in the middle | `fz 1 + {0(1):3}(2) + 1 DashLayout` |
| **Focus zone over a grid**<br>`1+2` underneath, full-screen zone on top | `fz 1+2 > 1 -k 1 DevStack` |
| **Merge two saved layouts**<br>Put "Solo Left" on top of "Master L" | `fz Master L > Solo Left Combined` |
| **Gapless grid**<br>A temporary 2×2 with no gaps at all | `fz 2x2 -s 0` |
| **Second monitor, own grid**<br>Apply a 3×2 to screen #2 only | `fz 3x2 -m 2 Docs` |
| **Same layout everywhere**<br>A master-stack across the whole desktop | `fz 1(3)+2(2) -s 8 -m all Code` |
| **Widget strip on the left**<br>Free 25 % column, then three equal zones | `fz 0(1) + 3 Widgets` |
| **Three-band workflow**<br>Top bar, three windows, bottom bar | `fz 1 / 3 / 1 Trio` |
| **ASCII layout**<br>A wide header, a sidebar and a footer | `fz A A B \| C . B \| D D D Dash` |

---

## Search, apply and manage

### The query box

| Input | What happens |
| :--- | :--- |
| `fz` | Lists every saved layout. |
| `fz cod` | Fuzzy-searches saved layouts by name. |
| `fz Code` | Applies the saved `Code` layout (exact match wins). |
| `fz 1+2+1` | Compiles and applies a new formula. |
| `fz Code -m 2` | Applies `Code` to monitor #2. |
| `fz -m all` | Lists every layout, each one applicable to all monitors. |

**Resolution order** for a non-empty query:

1. Flags `-s` / `-k` / `-m` are extracted and validated.
2. If only flags remain, every saved layout is listed with that target applied.
3. **An exact, case-insensitive match against a saved layout name wins** — this is why a layout
   literally named `2 Monitor` is applied instead of being parsed as a formula.
4. Otherwise, if the input looks like DSL, it is compiled and offered as a create/update action.
5. Otherwise a fuzzy name search is shown.
6. If nothing matches and a `-m` / `-k` flag was given, an explanatory error is returned.

Because exact names take priority, `fz Solo` applies the saved layout while `fz 1+2 Solo`
compiles a **new** layout and overwrites the existing `Solo` with it.

### The context menu

Press `Shift + Enter` (or right-click) on any result:

| Entry | Action |
| :--- | :--- |
| **Apply** | Apply to the active monitor. |
| **Apply to all monitors** | Apply across the whole desktop at once. |
| **Apply to monitor #N** | One entry per monitor, labelled with its name and resolution (only when more than one monitor is connected). |
| **Layer over «X»** | Merge this layout *on top of* `X` into a new canvas and apply it. |
| **Place under «X»** | Merge this layout *underneath* `X` into a new canvas and apply it. |
| **Duplicate layout** | Clone with a new GUID and the name `… (copy)`; the clone is **not** applied. |
| **Currently applied on** | Read-only: which monitors currently use this layout. |
| **Delete layout** | Remove the layout from PowerToys. Deliberately last, so it cannot be hit by accident. |

Merge targets are listed for up to 8 other layouts, sorted by name. With more layouts, merge
through the query box instead using `>`. Merging the same pair twice overwrites the previous
result, which is named `«A» over «B»`.

---

## How it works

```text
┌──────────────────────────┐
│  Flow Launcher (C#)      │
└────────────┬─────────────┘
             │ JSON-RPC over stdout
             ▼
┌──────────────────────────┐
│  main.py                 │   query() / context_menu() / RPC actions
│  FancyZonesPlugin        │   flags, name lookup, search, context menu
└────────────┬─────────────┘
             ▼
┌──────────────────────────┐
│  fz_compiler.py          │   DSL → FancyZones layout
│  FZCompiler              │   exact arithmetic via fractions.Fraction
│                          │   ├── no voids/layers → type "grid"
│                          │   └── voids/layers   → type "canvas" (10000×10000)
└────────────┬─────────────┘
             ▼
┌──────────────────────────┐
│  fz_backend.py           │   reads/writes custom-layouts.json
│  FZBackend               │   shells out to FancyZonesCLI.exe
└────────────┬─────────────┘
             ├──► %LOCALAPPDATA%\Microsoft\PowerToys\FancyZones\custom-layouts.json
             ├──► %LOCALAPPDATA%\Microsoft\PowerToys\FancyZones\applied-layouts.json  (read-only)
             └──► FancyZonesCLI.exe
                    ├── get-monitors                     monitors, resolutions, selection
                    ├── s <uuid> [--monitor N | --all]   apply a layout (N is 1-based)
                    └── shk <0-9> <uuid>                 bind Win+Ctrl+Alt+N
```

1. **Exact arithmetic.** Zone boundaries are computed with `fractions.Fraction`, not floats, so
   proportional splits land on exactly the intended percentages with no accumulated drift.
2. **Automatic engine selection.** A gapless layout becomes a native FancyZones `grid`. A layout
   with voids or layers becomes a `canvas` in a 10000×10000 reference space, which FancyZones
   scales to any resolution; the pixel gap `-s` is baked into the coordinates relative to the
   target monitor's real resolution.
3. **`Temp` slots.** Unnamed formulas reuse a fixed GUID per monitor instead of littering the
   layout database. Slots are overwritten in place; named layouts are isolated by UUID.
4. **Diagnostics.** CLI failures and internal errors are appended to `plugin.log` next to the
   plugin (truncated once it exceeds 256 KiB). A missing `FancyZonesCLI.exe` is surfaced directly
   in the search results.

### Module layout

| File | Responsibility |
| :--- | :--- |
| `main.py` | Flow Launcher entry point: query handling, result building, context menu, RPC actions. |
| `fz_compiler.py` | Pure DSL parsing and compilation. No I/O — fully unit-testable. |
| `fz_backend.py` | PowerToys integration: layout persistence, monitor discovery, CLI invocation, logging. |
| `lib/` | Vendored `flowlauncher` runtime package (pinned to 0.2.0). |
| `Images/app.png` | Plugin icon. |
| `store/` | Ready-to-submit entry for the Flow Launcher plugin manifest. |
| `test_*.py` | Unit test suite (70 tests). |

---

## Files the plugin touches

| Path | Access | Purpose |
| :--- | :--- | :--- |
| `%LOCALAPPDATA%\Microsoft\PowerToys\FancyZones\custom-layouts.json` | read/write | Where PowerToys stores custom layouts. |
| `%LOCALAPPDATA%\Microsoft\PowerToys\FancyZones\applied-layouts.json` | read | Which layout is applied to which monitor. |
| `plugin.log` (plugin folder) | append | Diagnostics; truncated past 256 KiB. |
| `FancyZonesCLI.exe` | execute | Applying layouts, listing monitors, binding hotkeys. |

The plugin never edits PowerToys settings or registry keys, and never touches any other
application's data.

---

## Troubleshooting

<details>
<summary><b>"FancyZonesCLI.exe not found" warning appears in the results</b></summary>

The layout is still compiled and saved, but applying it needs the CLI. Check that PowerToys is
installed and that the FancyZones module is enabled, then verify one of:

```cmd
where FancyZonesCLI.exe
dir "%ProgramFiles%\PowerToys\FancyZonesCLI.exe"
```

If the file exists in an unusual location, add its folder to `PATH` and restart Flow Launcher.
</details>

<details>
<summary><b>A layout saves but nothing changes on screen</b></summary>

- Make sure the target monitor is correct: `-m 1` is the first monitor as reported by
  `FancyZonesCLI.exe get-monitors`, which is not necessarily the one you expect.
- Check `plugin.log` in the plugin folder — CLI failures are recorded there with their stderr.
- Existing windows do not move automatically. FancyZones only snaps windows you drag (or that you
  move with `Win + Arrow`), so drag a window into the new grid to confirm it.
</details>

<details>
<summary><b>The wrong monitor got the new layout</b></summary>

Older versions shared a single `Temp` slot between monitors. Version 1.5.0 migrates such
references automatically: before overwriting the slot, other monitors are re-pointed at a copy
named `Temp (M<n>)`. If you upgraded and still see cross-talk, delete the stale `Temp` entries
from the context menu and apply the formulas again per monitor.
</details>

<details>
<summary><b>A saved layout is named like a formula, and typing it compiles instead</b></summary>

Exact, case-insensitive name matches always win over compilation, so a layout named `2 Monitor`
is applied when you type `fz 2 Monitor`. Only when the whole input is not an exact name does the
DSL parser run — `fz 1+2 Solo` therefore compiles a new layout and overwrites `Solo`.
</details>

<details>
<summary><b>An error like "Zone 'A' does not form a rectangle"</b></summary>

FancyZones zones must be rectangular. In a letter matrix every letter's cells have to form a solid
rectangle, so `A A | A B` is invalid while `A A | A A` is fine. Split the L-shape into two letters.
</details>

<details>
<summary><b>Where are the logs?</b></summary>

`plugin.log`, in the plugin's own folder:

```text
%APPDATA%\FlowLauncher\Plugins\FancyZonesDSL\plugin.log
```
</details>

---

## FAQ

<details>
<summary><b>How do I snap a window into an overlapping canvas zone?</b></summary>

Hold <kbd>Shift</kbd> while dragging (or <kbd>Ctrl</kbd>, depending on your PowerToys
"zone activation" setting). FancyZones highlights the topmost zone under the cursor, honouring the
Z-order produced by the <code>&gt;</code> operator.
</details>

<details>
<summary><b>Can two monitors keep different layouts?</b></summary>

Yes — that is native FancyZones behaviour, and this plugin supports it two ways. Unnamed formulas
use per-monitor <code>Temp</code> slots, so <code>fz 1(3)+2(2) -m 1</code> and
<code>fz 2x2 -m 2</code> coexist. Named layouts are isolated by UUID anyway.
</details>

<details>
<summary><b>Does the <code>Temp</code> layout survive a reboot?</b></summary>

Yes. <code>Temp</code> is a normal entry in <code>custom-layouts.json</code> with a fixed GUID, so
it persists across restarts and keeps its monitor binding.
</details>

<details>
<summary><b>What is the difference between <code>grid</code> and <code>canvas</code>?</b></summary>

<code>grid</code> is FancyZones' native percentage-based grid and cannot represent holes.
<code>canvas</code> places zones at free coordinates in a 10000×10000 reference space, which is
what voids and layers need. The plugin picks the right one automatically; you never choose.
</details>

<details>
<summary><b>How do I find out the monitor numbers for <code>-m</code>?</b></summary>

<pre><code>"C:\Program Files\PowerToys\FancyZonesCLI.exe" get-monitors</code></pre>

Numbering is 1-based and matches <code>-m</code>. It is usually easier to pass a name substring
(<code>-m msi</code>) or <code>-m all</code>.
</details>

<details>
<summary><b>Can I bind a layout to a global hotkey outside Flow Launcher?</b></summary>

Use <code>-k</code> to bind one of PowerToys' ten layout shortcuts
(<code>Win + Ctrl + Alt + [0-9]</code>). For anything else, point your own hotkey tool at
<code>Flow.Launcher.exe</code> with a query argument, or use Flow Launcher's own custom hotkeys.
</details>

<details>
<summary><b>Does the plugin work with a portable PowerToys install?</b></summary>

Yes, as long as <code>FancyZonesCLI.exe</code> is on <code>PATH</code> or in
<code>%LOCALAPPDATA%\Programs\PowerToys\</code>. Layout files are still read from
<code>%LOCALAPPDATA%\Microsoft\PowerToys\FancyZones\</code>.
</details>

---

## Development

### Getting started

```cmd
git clone https://github.com/RADiant-Git/FancyZones-DSL.git
cd FancyZones-DSL
pip install -r requirements.txt -t ./lib
```

The source has no third-party dependencies beyond the vendored `flowlauncher` package, and it
targets Python 3.8+ (`main.py` adds `./lib` to `sys.path` so the bundled package is always used).

### Running the tests

```cmd
python -m unittest discover -v
```

70 unit tests cover the compiler (parsing, weights, voids, matrices, layers, spacing, flag
validation), the backend (monitor parsing, apply-argument construction, slot migration) and the
plugin surface (query priority, context menu, merge and duplicate actions). No PowerToys install is
required — the tests use a mock backend.

### Manual smoke test

`main.py` speaks the same JSON-RPC protocol Flow Launcher uses, so you can drive it directly:

```cmd
python main.py "{\"method\":\"query\",\"parameters\":[\"2x2 -m 1 Test\"]}"
```

### Project conventions

- `fz_compiler.py` stays free of I/O so it remains trivially testable.
- All layout math goes through `fractions.Fraction`; avoid introducing floats into geometry.
- User-facing strings live in `main.py`; diagnostics go through `FZBackend._log`.

---

## Publishing and store submission

The repository is already wired for the Flow Launcher plugin store.

### How releases work

[`.github/workflows/publish-release.yml`](.github/workflows/publish-release.yml) runs on every push
to `main` (and can be triggered manually). It:

1. installs `requirements.txt` into `./lib`,
2. runs the unit test suite,
3. reads `Version` from `plugin.json`,
4. builds `FancyZonesDSL.zip` containing `plugin.json` at its root,
5. verifies the zip layout, and
6. publishes a GitHub Release tagged `v<version>` with the zip attached.

The asset name is intentionally version-less so the download URL stays stable across releases.

To cut a release:

1. Bump `Version` in `plugin.json`.
2. Merge to `main`.
3. Wait for the workflow to publish the release.

### Submitting to the store

1. Make sure the release exists and the zip downloads correctly.
2. Fork [`Flow-Launcher/Flow.Launcher.PluginsManifest`](https://github.com/Flow-Launcher/Flow.Launcher.PluginsManifest).
3. Copy [`store/FancyZones DSL Tiler-E9A1F3C4-7B2A-4D35-9C8E-2B6A1A78B091.json`](store/FancyZones%20DSL%20Tiler-E9A1F3C4-7B2A-4D35-9C8E-2B6A1A78B091.json)
   into the manifest repository's `plugins/` directory. The file name must stay exactly
   `<Name>-<ID>.json`, matching `plugin.json`.
4. Open a pull request against the default branch.

Once merged, the store's CI refreshes the entry automatically every few hours and keeps it in sync
with new releases — no further pull requests are needed for updates. CDN propagation across all
providers can take up to a week.

Until the plugin appears in the store, anyone can install it directly:

```text
pm install https://github.com/RADiant-Git/FancyZones-DSL/releases/latest/download/FancyZonesDSL.zip
```

---

## License

[MIT](LICENSE) © RADiant-Git

---

## Changelog

### 1.5.0 — 2026-11-07

**Per-monitor `Temp` slots, safe slot migration, richer context menu**

- Unnamed formulas now get a dedicated slot per monitor (`Temp`, `Temp 2`, …), so overwriting a
  formula on one screen no longer changes the grid on another. `-m all` deliberately keeps using
  the shared `Temp` slot.
- Before a shared slot is overwritten, monitors that still point at it are migrated onto a copy of
  the previous content (`Temp (M<n>)`) and re-applied — no layout is lost.
- The context menu gained per-monitor apply entries, *Layer over «X»* / *Place under «X»*,
  *Duplicate layout*, and a read-only *Currently applied on* entry.

### 1.4.0 — 2026-11-07

- First iteration of the per-monitor `Temp` buffer: layouts without a name are written into the
  target screen's own slot instead of a single global one.

### 1.3.1 — 2026-11-06

- `-s` / `-k` / `-m` now also work together with saved layout names, e.g. `fz Wide Solo -m 2`
  or `fz Master L -k 5`.

### 1.3.0 — 2026-11-06

- Multi-monitor targeting: `-m <number | name | all>`.
- `canvas` gaps are computed from the target monitor's real resolution (`get-monitors`, 20 s cache).
- Strict validation of `-s` / `-k` / `-m`, plus detection of orphaned or unknown flags.

### 1.2.0 — 2026-11-06

- Hardened flag handling and error reporting for malformed input.

### 1.1.0

- Floating-window layouts built from voids (`0(w)`, `{1:0:1}`).
- Multi-layer composition with the `>` operator.

### 1.0.0

- Initial release: columns, rows, quick grids and letter matrices compiled into FancyZones layouts,
  applied through the official PowerToys CLI.
