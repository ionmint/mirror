"""Mirror - guided install and configuration.

Not usually run by hand: install.bat, configure.bat, start.bat, stop.bat and
uninstall.bat call it for you.

    py setup.py               full guided install
    py setup.py --configure   just the configuration questions
    py setup.py --start       start it
    py setup.py --stop        stop the running one
    py setup.py --summary     print the current state and exit
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
BASE_DIR = SRC_DIR.parent          # the folder the user opens
sys.path.insert(0, str(SRC_DIR))

import mirror_core as core  # noqa: E402  (after sys.path)

SCRIPT = "mirror_gui.py"
STARTUP_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"
SHORTCUT = STARTUP_DIR / "Mirror.lnk"

DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000


# --------------------------------------------------------------------------- #
# questions
# --------------------------------------------------------------------------- #

def _read(prompt: str) -> str:
    try:
        # ﻿: input coming from a file or a pipe can carry a BOM
        return input(prompt).strip().strip("﻿")
    except (EOFError, KeyboardInterrupt):
        print("\n   Interrupted, nothing was changed.\n")
        raise SystemExit(1)


def ask(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default != "" else ""
    while True:
        answer = _read(f"   {question}{suffix}: ")
        if answer:
            return answer
        if default != "":
            return default


def ask_yes_no(question: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        answer = _read(f"   {question} [{hint}]: ").lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("      Please answer Y or N.")


def ask_number(question: str, default, minimum: float = 0, whole: bool = True):
    while True:
        answer = ask(question, str(default)).replace(",", ".")
        try:
            value = float(answer)
        except ValueError:
            print("      That is not a number.")
            continue
        if value < minimum:
            print(f"      The minimum is {minimum:g}.")
            continue
        return int(value) if whole else value


# --------------------------------------------------------------------------- #
# environment
# --------------------------------------------------------------------------- #

def has_tkinter() -> bool:
    try:
        import tkinter  # noqa: F401
        return True
    except Exception:
        return False


def explain_missing_tkinter() -> None:
    print("   ! tkinter is missing: Mirror has no way to draw its window.")
    print("     It ships with Python: reinstall it from python.org leaving the")
    print('     "tcl/tk and IDLE" option ticked.')


def pythonw() -> Path:
    """The interpreter without a console window, next to the current one."""
    executable = Path(sys.executable)
    candidate = executable.with_name("pythonw.exe")
    return candidate if candidate.exists() else executable


def writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".mirror_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def read_raw_config() -> dict:
    try:
        data = json.loads(core.CONFIG_PATH.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        print("   ! config.json could not be read: writing a fresh one.")
        return {}


def write_config(cfg: dict) -> None:
    # keep the order of the defaults, so the file stays readable across rewrites
    ordered = {key: cfg[key] for key in core.DEFAULTS if key in cfg}
    ordered.update({k: v for k, v in cfg.items() if k not in ordered})
    core.CONFIG_PATH.write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# autostart
# --------------------------------------------------------------------------- #

def install_autostart() -> bool:
    command = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:MIRROR_LNK);"
        "$s.TargetPath=$env:MIRROR_TARGET;"
        "$s.Arguments=$env:MIRROR_ARGS;"
        "$s.WorkingDirectory=$env:MIRROR_DIR;"
        "$s.Description='Mirror';"
        "$s.Save()"
    )
    environment = dict(
        os.environ,
        MIRROR_LNK=str(SHORTCUT),
        MIRROR_TARGET=str(pythonw()),
        MIRROR_ARGS=f'"{SRC_DIR / SCRIPT}"',
        MIRROR_DIR=str(BASE_DIR),
    )
    try:
        STARTUP_DIR.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            env=environment, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0 or not SHORTCUT.exists():
            print(f"   ! could not create the shortcut: {result.stderr.strip()}")
            return False
        return True
    except Exception as error:
        print(f"   ! could not create the shortcut: {error}")
        return False


def remove_autostart() -> bool:
    try:
        if SHORTCUT.exists():
            SHORTCUT.unlink()
        return True
    except OSError as error:
        print(f"   ! could not remove the shortcut: {error}")
        return False


# --------------------------------------------------------------------------- #
# start / stop
# --------------------------------------------------------------------------- #

def start(quiet: bool = False) -> int:
    if core.is_running():
        if not quiet:
            print("   Mirror is already running.")
        return 0
    if not has_tkinter():
        explain_missing_tkinter()
        return 1
    cfg = core.load_config()
    try:
        subprocess.Popen(
            [str(pythonw()), str(SRC_DIR / SCRIPT)],
            cwd=str(BASE_DIR),
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
            close_fds=True,
        )
    except Exception as error:
        print(f"   ! could not start it: {error}")
        return 1
    minutes = core.num(cfg.get("interval_minutes"), 15, minimum=0.05)
    print(f"   Started. First question in {minutes:g} minutes.")
    return 0


def stop() -> int:
    pid = None
    try:
        pid = int(core.PID_PATH.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        pass

    if pid is None:
        if core.is_running():
            print("   It is running but mirror.pid is missing.")
            print("   Close it from Task Manager: look for pythonw.exe.")
            return 1
        print("   Mirror is not running.")
        return 0

    result = subprocess.run(
        ["taskkill", "/f", "/pid", str(pid)], capture_output=True, text=True
    )
    for leftover in (core.PID_PATH, core.STATE_PATH):
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass
    if result.returncode == 0:
        print("   Mirror stopped.")
    else:
        print("   It was not running any more: cleaned up the leftover files.")
    print("   It will come back at your next sign-in, or right away with start.bat.")
    return 0


# --------------------------------------------------------------------------- #
# screens
# --------------------------------------------------------------------------- #

def header(title: str) -> None:
    print()
    print("   ┌" + "─" * 56 + "┐")
    print("   │ " + title.ljust(55) + "│")
    print("   └" + "─" * 56 + "┘")
    print()


def summary(cfg: dict) -> None:
    folder = core.resolve_log_dir(cfg)
    lines = [
        ("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
        ("tkinter", "available" if has_tkinter() else "MISSING"),
        ("Question", core.question_text(cfg)),
        ("Asks every", f"{core.num(cfg.get('interval_minutes'), 15, 0.05):g} minutes"),
        ("Minimum length", str(int(core.num(cfg.get("min_chars"), 30, 0)))),
        ("Journal folder", str(folder)),
        ("Folder writable", "yes" if writable(folder) else "NO"),
        ("Autostart", "on" if SHORTCUT.exists() else "off"),
        ("Running now", "yes" if core.is_running() else "no"),
    ]
    for label, value in lines:
        print(f"   {label.ljust(20)} {value}")
    print()


def configure(raw: dict) -> dict:
    values = {**core.DEFAULTS, **raw}
    cfg = dict(raw)

    question = ask("Question to ask", str(values.get("question", core.DEFAULTS["question"])))
    interval = ask_number(
        "Ask every how many minutes",
        int(core.num(values.get("interval_minutes"), 15, 0.05)), minimum=1,
    )
    minimum = ask_number(
        "Minimum characters for an answer (0 = no minimum)",
        int(core.num(values.get("min_chars"), 30, 0)), minimum=0,
    )
    folder = ask(
        "Folder for the journal files (enter = inside this one)",
        str(values.get("log_dir", core.DEFAULTS["log_dir"])),
    )
    current_games = values.get("always_defer_processes") or []
    print()
    print("   Games during which the question must not show up.")
    print("   Executable names separated by commas, for example:")
    print("      eldenring.exe, cs2.exe")
    games = ask(
        "Games (enter to keep what is there)",
        ", ".join(current_games) if current_games else "none",
    )

    cfg["question"] = question
    cfg["interval_minutes"] = interval
    cfg["min_chars"] = minimum
    cfg["log_dir"] = folder
    cfg["always_defer_processes"] = (
        [] if games.strip().lower() in ("none", "no", "-", "") else
        [piece.strip() for piece in games.split(",") if piece.strip()]
    )
    for key, fallback in core.DEFAULTS.items():
        cfg.setdefault(key, fallback)
    write_config(cfg)
    print()
    print(f"   Saved to {core.CONFIG_PATH.name}.")
    return cfg


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main() -> int:
    arguments = sys.argv[1:]

    if "--start" in arguments:
        return start()
    if "--stop" in arguments:
        return stop()
    if "--uninstall" in arguments:
        if remove_autostart():
            print("   Autostart removed.")
            print("   A running copy keeps going until stop.bat or a restart.")
        return 0
    if "--summary" in arguments:
        header("Mirror - summary")
        summary(core.load_config())
        return 0

    config_only = "--configure" in arguments
    header("Mirror - configuration" if config_only else "Mirror - install")

    if not config_only:
        print(f"   Python {sys.version.split()[0]}")
        print(f"   Program folder: {BASE_DIR}")
        print()

    if not has_tkinter():
        explain_missing_tkinter()
        print()
        return 1

    cfg = configure(read_raw_config())
    print()

    if not writable(core.resolve_log_dir(cfg)):
        print(f"   ! cannot write to {core.resolve_log_dir(cfg)}")
        print("     pick another folder by running configure.bat again.")
        print()

    already = SHORTCUT.exists()
    question = (
        "Keep starting Mirror at every sign-in?" if already
        else "Start Mirror automatically at every sign-in?"
    )
    if ask_yes_no(question, default=True):
        if install_autostart():
            print("   Autostart is on.")
    else:
        remove_autostart()
        print("   Autostart is off: start it yourself with start.bat.")
    print()

    summary(cfg)

    if core.is_running():
        print("   Mirror is already running with the previous settings.")
        if ask_yes_no("Restart it now so the changes take effect?", default=True):
            stop()
            start(quiet=True)
    elif ask_yes_no("Start it now?", default=not config_only):
        start()
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
