"""Mirror - the shared logic behind the app.

Config handling, the daily journal, the wall-clock timer and the checks that
decide whether the question should wait for a better moment all live here.
"""

from __future__ import annotations

import atexit
import copy
import ctypes
import ctypes.wintypes as wt
import json
import os
import socket
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
# one level up: the folder the user actually opens. Everything they may want to
# see or edit - the config, the journal, the log - belongs there, not in here
BASE_DIR = SRC_DIR.parent
CONFIG_PATH = BASE_DIR / "config.json"
PID_PATH = BASE_DIR / "mirror.pid"
ERROR_LOG = BASE_DIR / "mirror.log"
STATE_PATH = BASE_DIR / ".mirror_state.json"

VERSION = "1.0.0"
LOCK_PORT = 49731          # bound only to act as a single-instance lock
TICK_SECONDS = 5           # how often the clock is checked
SHEEP_EMOJI = "\U0001F411"
SHEEP_ASCII = "{~^..^}"

# the right Shift and one of these open the pause row: the keyboard twin of the
# sheep button. They all sit on the right of an Italian or a UK keyboard, under
# the same hand as the right Shift - and out of the way of typing, because the
# shifted character of a right hand key is one you reach for with the left Shift
PAUSE_KEYS = (
    ("-", ",", ".") + tuple("67890") + tuple("yuiophjklnm")
    + tuple(f"f{n}" for n in range(7, 13))
)

DEFAULTS = {
    "question": "What are you doing?",
    "interval_minutes": 15,
    "default_pause_minutes": 60,
    "pause_key": "-",
    "min_chars": 30,
    "log_dir": "log",
    "ask_on_start": False,
    "width_fraction": 0.3333,
    "on_fullscreen_app": "defer",
    "defer_retry_minutes": 5,
    "always_defer_processes": [],
    "cover_all_monitors": True,
    "sheep_style": "auto",
    "colors": {
        "bg": "#000000",
        "fg": "#ffb000",
        "dim": "#7a5200",
        "warn": "#ff5555",
    },
}


# --------------------------------------------------------------------------- #
# diagnostics
# --------------------------------------------------------------------------- #

def log_error(message: str) -> None:
    """Record a problem in mirror.log: under pythonw.exe there is no stderr."""
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with ERROR_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def install_error_hooks() -> None:
    def hook(exc_type, exc, tb):
        log_error("".join(traceback.format_exception(exc_type, exc, tb)).rstrip())

    sys.excepthook = hook


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #

def load_config() -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    try:
        # utf-8-sig: Notepad saves UTF-8 with a BOM and json.loads chokes on it,
        # which would silently discard the whole file
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return cfg
    except Exception as exc:
        log_error(f"config.json is not readable ({exc}); using the defaults")
        return cfg
    if not isinstance(raw, dict):
        log_error("config.json does not hold an object; using the defaults")
        return cfg
    colors = raw.get("colors")
    for key, value in raw.items():
        if key != "colors":
            cfg[key] = value
    if isinstance(colors, dict):
        cfg["colors"].update(colors)
    return cfg


def num(value, fallback: float, minimum: float | None = None) -> float:
    """Coerce to a number, tolerating nonsense in the config file."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    if result != result:  # NaN
        return float(fallback)
    if minimum is not None and result < minimum:
        return float(fallback)
    return result


def resolve_log_dir(cfg: dict) -> Path:
    raw = str(cfg.get("log_dir") or DEFAULTS["log_dir"])
    path = Path(raw)
    if path.is_absolute():
        return path
    # a relative path hangs off the folder the user opens, not off this one;
    # normalise it so a "../" in the config does not reach the status panel
    return Path(os.path.normpath(BASE_DIR / path))


def question_text(cfg: dict) -> str:
    """Shown exactly as written in the config - no forced upper case."""
    text = str(cfg.get("question") or "").strip()
    return text or DEFAULTS["question"]


def pause_key(cfg: dict) -> str:
    """Which key opens the pause row while the right Shift is held."""
    raw = str(cfg.get("pause_key") or DEFAULTS["pause_key"]).strip().lower()
    if raw in PAUSE_KEYS:
        return raw
    log_error(
        f"pause_key {raw!r} is not one of the keys on the right of the keyboard "
        f"({' '.join(PAUSE_KEYS)}); using {DEFAULTS['pause_key']}"
    )
    return DEFAULTS["pause_key"]


def sheep_label(cfg: dict) -> str:
    style = str(cfg.get("sheep_style", "auto")).lower()
    # emoji and auto come to the same thing: Tk draws the sheep just fine
    return SHEEP_ASCII if style == "ascii" else SHEEP_EMOJI


def parse_args(argv=None) -> dict:
    """--now  -> ask straight away;  --interval N -> minutes, 0.5 allowed."""
    argv = list(sys.argv[1:] if argv is None else argv)
    args = {"now": False, "interval": None}
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--now":
            args["now"] = True
        elif item == "--interval" and index + 1 < len(argv):
            index += 1
            try:
                args["interval"] = float(argv[index])
            except ValueError:
                log_error(f"--interval given a non numeric value: {argv[index]!r}")
        elif item.startswith("--interval="):
            try:
                args["interval"] = float(item.split("=", 1)[1])
            except ValueError:
                log_error(f"--interval given a non numeric value: {item!r}")
        index += 1
    return args


# --------------------------------------------------------------------------- #
# single instance and pid file
# --------------------------------------------------------------------------- #

_lock_socket: socket.socket | None = None


def acquire_single_instance() -> bool:
    """True when we are the only copy around."""
    global _lock_socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", LOCK_PORT))
        sock.listen(1)
    except OSError:
        sock.close()
        return False
    _lock_socket = sock
    atexit.register(sock.close)
    return True


def is_running() -> bool:
    """Whether another copy holds the lock. Safe to call from any process."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", LOCK_PORT))
        return False
    except OSError:
        return True
    finally:
        sock.close()


def write_pid_file() -> None:
    try:
        PID_PATH.write_text(str(os.getpid()), encoding="ascii")
    except OSError as exc:
        log_error(f"cannot write mirror.pid ({exc})")
        return
    atexit.register(_remove_pid_file)


def _remove_pid_file() -> None:
    try:
        PID_PATH.unlink(missing_ok=True)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Windows checks
# --------------------------------------------------------------------------- #

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PATH = 260

QUNS_BUSY = 2
QUNS_RUNNING_D3D_FULL_SCREEN = 3
QUNS_PRESENTATION_MODE = 4


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_wchar * MAX_PATH),
    ]


def running_process_names() -> set[str]:
    """Lower-cased names of the running executables, via Toolhelp32."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    kernel32.Process32FirstW.restype = wt.BOOL
    kernel32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wt.BOOL
    kernel32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.CloseHandle.argtypes = [wt.HANDLE]

    names: set[str] = set()
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == INVALID_HANDLE_VALUE:
        return names
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            names.add(entry.szExeFile.lower())
            found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return names


def blocking_process(cfg: dict) -> str | None:
    """First executable from 'always_defer_processes' that is currently running."""
    wanted = cfg.get("always_defer_processes") or []
    if not isinstance(wanted, (list, tuple)):
        return None
    wanted = {str(name).strip().lower() for name in wanted if str(name).strip()}
    if not wanted:
        return None
    try:
        running = running_process_names()
    except Exception as exc:
        log_error(f"could not enumerate processes ({exc})")
        return None
    for name in wanted:
        if name in running:
            return name
    return None


def user_notification_state() -> int | None:
    """SHQueryUserNotificationState: what Windows uses to mute notifications."""
    try:
        state = ctypes.c_int()
        hresult = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state))
        if hresult != 0:
            return None
        return state.value
    except Exception as exc:
        log_error(f"SHQueryUserNotificationState failed ({exc})")
        return None


def defer_reason(cfg: dict) -> str | None:
    """Why the question should wait, or None when it is fine to ask."""
    blocked_by = blocking_process(cfg)
    if blocked_by:
        return f"running: {blocked_by}"

    mode = str(cfg.get("on_fullscreen_app", "defer")).lower()
    if mode == "show":
        return None
    state = user_notification_state()
    if state is None:
        return None
    if mode == "defer_presentation":
        respected = {QUNS_PRESENTATION_MODE}
    else:
        respected = {QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE}
    if state in respected:
        return f"user state {state}"
    return None


# --------------------------------------------------------------------------- #
# the daily journal
# --------------------------------------------------------------------------- #

def save_answer(text: str, cfg: dict) -> Path:
    """Append the answer to today's file. Raises OSError when it cannot."""
    log_dir = resolve_log_dir(cfg)
    log_dir.mkdir(parents=True, exist_ok=True)
    today = date.today()
    path = log_dir / f"{today.isoformat()}.md"

    lines = [line.rstrip() for line in text.strip().splitlines()]
    entry = [f"- **{datetime.now():%H:%M}** — {lines[0]}"]
    # two spaces of indent keep the following lines inside the same list item
    entry.extend(f"  {line}" if line else "" for line in lines[1:])

    new_file = not path.exists()
    with path.open("a", encoding="utf-8") as handle:
        if new_file:
            handle.write(f"# {today.isoformat()}\n\n")
        handle.write("\n".join(entry) + "\n")
    return path


def read_today(cfg: dict) -> tuple[int, str, str]:
    """(number of answers, time of the last one, text of the last one)."""
    path = resolve_log_dir(cfg) / f"{date.today().isoformat()}.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0, "", ""
    entries = [line for line in lines if line.startswith("- **")]
    if not entries:
        return 0, "", ""
    last = entries[-1]
    try:
        stamp = last.split("**")[1]
        text = last.split("—", 1)[1].strip()
    except IndexError:
        stamp, text = "", last
    return len(entries), stamp, text


# --------------------------------------------------------------------------- #
# timer
# --------------------------------------------------------------------------- #

class Scheduler:
    """Wall-clock timer, so sleep and hibernation cannot knock it out of step."""

    def __init__(self, args: dict):
        self.args = args
        self.cfg = load_config()
        self.last_defer_reason: str | None = None
        self.next_due = time.time()
        if not (args.get("now") or self.cfg.get("ask_on_start")):
            self.next_due += self.interval_minutes * 60
        atexit.register(self._clear_state)
        self._publish("waiting")

    @property
    def interval_minutes(self) -> float:
        if self.args.get("interval") is not None:
            return num(self.args["interval"], 15, minimum=0.05)
        return num(self.cfg.get("interval_minutes"), 15, minimum=0.05)

    # -- state published for status.py ------------------------------------- #

    def _publish(self, state: str, reason: str | None = None) -> None:
        payload = {
            "state": state,
            "next_due": self.next_due,
            "interval_minutes": self.interval_minutes,
            "pid": os.getpid(),
            "defer_reason": reason,
            "updated": time.time(),
        }
        try:
            STATE_PATH.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass

    def _clear_state(self) -> None:
        try:
            STATE_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    def mark_asking(self) -> None:
        self._publish("asking")

    # -- scheduling --------------------------------------------------------- #

    def postpone(self, minutes, state: str = "waiting", reason: str | None = None) -> None:
        self.next_due = time.time() + num(minutes, 15, minimum=0.05) * 60
        self._publish(state, reason)

    def schedule_next(self) -> None:
        self.postpone(self.interval_minutes)

    def check(self) -> str:
        """'wait' or 'ask'. Rereads the config and handles postponing itself."""
        if time.time() < self.next_due:
            return "wait"
        self.cfg = load_config()
        reason = defer_reason(self.cfg)
        if reason:
            if reason != self.last_defer_reason:
                log_error(f"question postponed ({reason})")
                self.last_defer_reason = reason
            self.postpone(
                num(self.cfg.get("defer_retry_minutes"), 5, minimum=0.05),
                state="deferred", reason=reason,
            )
            return "wait"
        self.last_defer_reason = None
        return "ask"


def read_state() -> dict | None:
    """The running instance's state, or None when nothing is running.

    The file is cross-checked against the single-instance lock, so one left
    behind by a crash reads as stopped rather than as a stale truth.
    """
    if not is_running():
        return None
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None
