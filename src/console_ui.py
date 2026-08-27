"""Terminal drawing helpers for Mirror's status panel.

status.py draws an amber-on-black framed box in a real console window, which
takes a fair amount of Win32 plumbing: it all lives here.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys

ESC = "\x1b"
HOME = f"{ESC}[H"
CLEAR_SCREEN = f"{ESC}[2J"
CLEAR_BELOW = f"{ESC}[J"
CLEAR_LINE = f"{ESC}[K"
RESET = f"{ESC}[0m"
HIDE_CURSOR = f"{ESC}[?25l"
SHOW_CURSOR = f"{ESC}[?25h"

kernel32 = ctypes.windll.kernel32

STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
ENABLE_PROCESSED_OUTPUT = 0x0001
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
ENABLE_EXTENDED_FLAGS = 0x0080
ENABLE_QUICK_EDIT_MODE = 0x0040


class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", ctypes.c_short),
        ("Top", ctypes.c_short),
        ("Right", ctypes.c_short),
        ("Bottom", ctypes.c_short),
    ]


# --------------------------------------------------------------------------- #
# console plumbing
# --------------------------------------------------------------------------- #

def std_handle(which: int = STD_OUTPUT_HANDLE) -> int:
    kernel32.GetStdHandle.restype = wt.HANDLE
    return kernel32.GetStdHandle(which)


def enable_vt(quiet_quick_edit: bool = True) -> None:
    """Turn on ANSI escape sequences; optionally kill QuickEdit.

    QuickEdit makes a stray click freeze the console until you press a key, which
    on a window the user cannot close would look like a hang.
    """
    try:
        handle = std_handle(STD_OUTPUT_HANDLE)
        mode = wt.DWORD()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(
                handle,
                mode.value | ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING,
            )
    except Exception:
        pass
    if not quiet_quick_edit:
        return
    try:
        handle = std_handle(STD_INPUT_HANDLE)
        mode = wt.DWORD()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(
                handle, (mode.value | ENABLE_EXTENDED_FLAGS) & ~ENABLE_QUICK_EDIT_MODE
            )
    except Exception:
        pass


def set_grid(cols: int, rows: int) -> bool:
    """Resize the console to exactly this many columns and rows.

    Only safe on a window that is not maximised. The window has to be shrunk
    before the buffer, otherwise Windows refuses a buffer smaller than the
    window it holds.
    """
    try:
        handle = std_handle()
        tiny = SMALL_RECT(0, 0, 1, 1)
        kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(tiny))
        kernel32.SetConsoleScreenBufferSize(handle, COORD(cols, rows))
        target = SMALL_RECT(0, 0, cols - 1, rows - 1)
        return bool(kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(target)))
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# colours
# --------------------------------------------------------------------------- #

def rgb(value: str) -> tuple[int, int, int]:
    text = str(value).lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return 255, 176, 0


def fg_seq(value: str) -> str:
    red, green, blue = rgb(value)
    return f"{ESC}[38;2;{red};{green};{blue}m"


def bg_seq(value: str) -> str:
    red, green, blue = rgb(value)
    return f"{ESC}[48;2;{red};{green};{blue}m"


class Palette:
    def __init__(self, colors: dict):
        colors = colors or {}
        self.bg = bg_seq(colors.get("bg", "#000000"))
        self.fg = fg_seq(colors.get("fg", "#ffb000"))
        self.dim = fg_seq(colors.get("dim", "#7a5200"))
        self.warn = fg_seq(colors.get("warn", "#ff5555"))


# --------------------------------------------------------------------------- #
# text
# --------------------------------------------------------------------------- #

def display_width(text: str) -> int:
    """Emoji outside the basic plane take two cells in a console."""
    return sum(2 if ord(char) > 0xFFFF else 1 for char in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - display_width(text))


def ellipsis(text: str, width: int) -> str:
    if display_width(text) <= width:
        return text
    return text[: max(0, width - 1)].rstrip() + "…"


# --------------------------------------------------------------------------- #
# box drawing
# --------------------------------------------------------------------------- #

def top_border(width: int, title: str, palette: Palette) -> str:
    label = f"─ {title} " if title else ""
    return f"{palette.dim}┌{label}{'─' * max(0, width - 2 - display_width(label))}┐"


def bottom_border(width: int, palette: Palette) -> str:
    return f"{palette.dim}└{'─' * max(0, width - 2)}┘"


def row(content: str, width: int, color: str, palette: Palette) -> str:
    return f"{palette.dim}│ {color}{pad(content, width - 4)}{palette.dim} │"


def paint(lines: list[str], palette: Palette) -> None:
    """Redraw the whole screen from the top left, without clearing it first.

    Clearing would flicker; CLEAR_LINE after each row extends the background to
    the right edge, and CLEAR_BELOW wipes whatever the previous frame left.
    """
    body = "\r\n".join(f"{palette.bg}{line}{CLEAR_LINE}" for line in lines)
    sys.stdout.write(HOME + body + CLEAR_BELOW + RESET)
    sys.stdout.flush()
