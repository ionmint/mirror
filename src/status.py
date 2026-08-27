"""Mirror - a small live status panel.

Opened by status.bat. Shows what the invisible process is up to and counts down
to the next question, refreshing once a second until you press a key.
"""

from __future__ import annotations

import msvcrt
import os
import sys
import time
from pathlib import Path

import console_ui as ui
import mirror_core as core

BOX_WIDTH = 60
LABEL_WIDTH = 16
MARGIN = "  "
HINT = "press any key to close · updates live"

STARTUP_SHORTCUT = (
    Path(os.environ.get("APPDATA", "")) /
    "Microsoft/Windows/Start Menu/Programs/Startup/Mirror.lnk"
)


def countdown(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds >= 3600:
        return f"in {seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
    return f"in {seconds // 60:02d}:{seconds % 60:02d}"


def describe(state: dict | None, cfg: dict) -> tuple[str, str]:
    """(state line, next question line)."""
    if state is None:
        return "stopped", "run start.bat"

    kind = str(state.get("state", "waiting"))
    remaining = core.num(state.get("next_due"), 0) - time.time()

    if kind == "asking":
        return "asking now", "on screen"
    if kind == "paused":
        return "paused", countdown(remaining)
    if kind == "deferred":
        reason = state.get("defer_reason") or "busy"
        return f"holding · {reason}", countdown(remaining)
    return "running", countdown(remaining)


def build(cfg: dict) -> list[str]:
    palette = ui.Palette(cfg.get("colors"))
    state = core.read_state()
    status_line, next_line = describe(state, cfg)

    entries, stamp, last = core.read_today(cfg)
    interval = core.num(
        (state or {}).get("interval_minutes", cfg.get("interval_minutes")), 15, minimum=0.05
    )

    fields = [
        ("next question", next_line),
        ("interval", f"{interval:g} min"),
        ("today's log", "no answers yet" if not entries else
                        f"{entries} answer{'s' if entries != 1 else ''}"),
        ("last answer", f"{stamp}  {last}" if last else "—"),
        ("autostart", "on" if STARTUP_SHORTCUT.exists() else "off"),
        ("log folder", str(core.resolve_log_dir(cfg))),
    ]

    inner = BOX_WIDTH - 4
    rows = [ui.top_border(BOX_WIDTH, f"mirror {core.VERSION}", palette)]
    rows.append(ui.row("", BOX_WIDTH, palette.fg, palette))
    rows.append(
        ui.row("STATUS".ljust(LABEL_WIDTH) + status_line, BOX_WIDTH, palette.fg, palette)
    )
    rows.append(ui.row("─" * inner, BOX_WIDTH, palette.dim, palette))
    for label, value in fields:
        text = label.ljust(LABEL_WIDTH) + ui.ellipsis(str(value), inner - LABEL_WIDTH)
        rows.append(ui.row(text, BOX_WIDTH, palette.dim, palette))
    rows.append(ui.row("", BOX_WIDTH, palette.fg, palette))
    rows.append(ui.bottom_border(BOX_WIDTH, palette))
    rows.append(palette.dim + " " * max(0, (BOX_WIDTH - len(HINT)) // 2) + HINT)
    return [MARGIN + line for line in rows]


def main() -> int:
    core.install_error_hooks()
    cfg = core.load_config()
    palette = ui.Palette(cfg.get("colors"))

    ui.enable_vt()
    try:
        ui.kernel32.SetConsoleTitleW("Mirror - status")
    except Exception:
        pass

    # a window at its normal size draws exactly the grid it reports, so it can be
    # sized to the panel and no centring maths is needed
    rows = build(cfg)
    ui.set_grid(BOX_WIDTH + 2 * len(MARGIN), len(rows) + 2)
    sys.stdout.write(palette.bg + ui.CLEAR_SCREEN + ui.HIDE_CURSOR)
    sys.stdout.flush()

    try:
        while True:
            cfg = core.load_config()
            ui.paint([""] + build(cfg), palette)
            for _ in range(4):
                if msvcrt.kbhit():
                    msvcrt.getwch()
                    return 0
                time.sleep(0.25)
    except KeyboardInterrupt:
        return 0
    finally:
        sys.stdout.write(ui.SHOW_CURSOR + ui.RESET + ui.CLEAR_SCREEN + ui.HOME)
        sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
