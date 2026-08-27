"""Mirror - the invisible process and the question screen (tkinter).

Runs invisibly under pythonw.exe; every X minutes it builds the full screen
question and tears it down again as soon as you answer or hit pause.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import tkinter as tk
from tkinter import font as tkfont

import mirror_core as core

MAX_INPUT_LINES = 12
FONT_CANDIDATES = ("Cascadia Mono", "Consolas", "Lucida Console", "Courier New")


# --------------------------------------------------------------------------- #
# Windows helpers
# --------------------------------------------------------------------------- #

def enable_dpi_awareness() -> None:
    """Call before creating the root: lines monitor coordinates up with Tk's."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per monitor aware
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def monitor_rects() -> list[tuple[int, int, int, int]]:
    """[(x, y, width, height), ...]; the primary monitor sits at (0, 0)."""
    rects: list[tuple[int, int, int, int]] = []
    try:
        callback_type = ctypes.WINFUNCTYPE(
            wt.BOOL, wt.HANDLE, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM
        )

        def callback(_monitor, _hdc, rect_ptr, _data):
            rect = rect_ptr.contents
            rects.append(
                (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
            )
            return True

        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, callback_type(callback), 0
        )
    except Exception as exc:
        core.log_error(f"could not enumerate monitors ({exc})")
    return [r for r in rects if r[2] > 0 and r[3] > 0]


def force_foreground(hwnd: int) -> None:
    """Work around the Windows foreground lock, which otherwise denies focus."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.GetForegroundWindow.restype = wt.HWND
        current = user32.GetForegroundWindow()
        if not current or current == hwnd:
            user32.SetForegroundWindow(hwnd)
            return
        other_thread = user32.GetWindowThreadProcessId(current, None)
        my_thread = kernel32.GetCurrentThreadId()
        attached = False
        if other_thread and other_thread != my_thread:
            attached = bool(user32.AttachThreadInput(other_thread, my_thread, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
        if attached:
            user32.AttachThreadInput(other_thread, my_thread, False)
    except Exception as exc:
        core.log_error(f"could not bring the window to the front ({exc})")


def toplevel_hwnd(window: tk.Misc) -> int:
    try:
        user32 = ctypes.windll.user32
        user32.GetAncestor.restype = wt.HWND
        user32.GetAncestor.argtypes = [wt.HWND, ctypes.c_uint]
        return user32.GetAncestor(window.winfo_id(), 2)  # GA_ROOT
    except Exception:
        return 0


# --------------------------------------------------------------------------- #
# the question screen
# --------------------------------------------------------------------------- #

class PromptWindow:
    def __init__(self, root: tk.Tk, cfg: dict, on_close):
        self.root = root
        self.cfg = cfg
        self.on_close = on_close
        self.closed = False
        self.pause_open = False
        self._lines = 0

        colors = cfg["colors"]
        self.bg = colors["bg"]
        self.fg = colors["fg"]
        self.dim = colors["dim"]
        self.warn = colors["warn"]
        self.min_chars = int(core.num(cfg.get("min_chars"), 30, minimum=0))

        rects = monitor_rects()
        if not rects:
            rects = [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]
        primary = next((r for r in rects if r[0] == 0 and r[1] == 0), rects[0])

        # the blank screens go up first, so the question keeps the top of the pile
        self.blanks: list[tk.Toplevel] = []
        if cfg.get("cover_all_monitors", True):
            for rect in rects:
                if rect == primary:
                    continue
                self.blanks.append(self._make_blank(rect))

        self.window = tk.Toplevel(root)
        self.window.title("Mirror")
        self.window.configure(bg=self.bg)
        self.window.geometry(f"{primary[2]}x{primary[3]}+{primary[0]}+{primary[1]}")
        self.window.attributes("-fullscreen", True)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)
        self.window.bind("<Escape>", lambda _event: "break")
        for sequence in ("<Control-Alt-Shift-KeyPress-Q>", "<Control-Alt-Shift-KeyPress-q>"):
            self.window.bind(sequence, self._on_abort)

        self._build(primary[2], primary[3])

        self.window.lift()
        self.window.grab_set()
        self.window.focus_force()
        self.text.focus_set()
        self.window.after(60, lambda: force_foreground(toplevel_hwnd(self.window)))

    # -- building ----------------------------------------------------------- #

    def _make_blank(self, rect) -> tk.Toplevel:
        blank = tk.Toplevel(self.root)
        blank.overrideredirect(True)
        blank.configure(bg=self.bg)
        blank.geometry(f"{rect[2]}x{rect[3]}+{rect[0]}+{rect[1]}")
        blank.attributes("-topmost", True)
        return blank

    def _pick_font_family(self) -> str:
        available = set(tkfont.families(self.root))
        for family in FONT_CANDIDATES:
            if family in available:
                return family
        return "Courier"

    def _build(self, screen_w: int, screen_h: int) -> None:
        family = self._pick_font_family()
        scale = max(1.0, min(1.6, screen_h / 1080))
        self.f_title = tkfont.Font(family=family, size=int(20 * scale), weight="bold")
        self.f_body = tkfont.Font(family=family, size=int(13 * scale))
        self.f_small = tkfont.Font(family=family, size=int(10 * scale))

        pad = int(26 * scale)
        box_w = max(420, int(screen_w * core.num(self.cfg.get("width_fraction"), 0.3333, 0.05)))

        container = tk.Frame(
            self.window,
            bg=self.bg,
            highlightbackground=self.dim,
            highlightcolor=self.dim,
            highlightthickness=1,
        )
        container.place(relx=0.5, rely=0.5, anchor="center", width=box_w)

        legend = tk.Label(self.window, text=" mirror ", bg=self.bg, fg=self.dim, font=self.f_small)
        legend.place(in_=container, x=int(18 * scale), y=0, anchor="w")

        inner = tk.Frame(container, bg=self.bg)
        inner.pack(fill="both", expand=True, padx=pad, pady=pad)
        inner_w = box_w - 2 * pad - 2

        tk.Label(
            inner, text=f"> {core.question_text(self.cfg)}", bg=self.bg, fg=self.fg,
            font=self.f_title, anchor="w", justify="left", wraplength=inner_w,
        ).pack(fill="x")

        rule_chars = max(4, inner_w // max(1, self.f_small.measure("─")))
        tk.Label(
            inner, text="─" * rule_chars, bg=self.bg, fg=self.dim,
            font=self.f_small, anchor="w",
        ).pack(fill="x", pady=(int(6 * scale), int(14 * scale)))

        row = tk.Frame(inner, bg=self.bg)
        row.pack(fill="x")
        tk.Label(row, text=">", bg=self.bg, fg=self.dim, font=self.f_body).pack(
            side="left", anchor="n"
        )
        self.text = tk.Text(
            row, width=1, height=1, wrap="word", bg=self.bg, fg=self.fg,
            insertbackground=self.fg, blockcursor=True, relief="flat", bd=0,
            highlightthickness=0, font=self.f_body, undo=True, spacing3=int(2 * scale),
            selectbackground=self.fg, selectforeground=self.bg,
            inactiveselectbackground=self.dim,
        )
        self.text.pack(side="left", fill="x", expand=True, padx=(int(8 * scale), 0))
        self.text.bind("<KeyRelease>", self._on_change)
        self.text.bind("<<Paste>>", lambda _e: self.text.after(1, self._on_change))
        self.text.bind("<Return>", self._on_return)
        self.text.bind("<KP_Enter>", self._on_return)
        self.text.bind("<Shift-Return>", self._on_newline)

        self.underline = tk.Frame(inner, bg=self.dim, height=1)
        self.underline.pack(fill="x", pady=(int(6 * scale), int(4 * scale)))

        self.counter = tk.Label(
            inner, text="", bg=self.bg, fg=self.dim, font=self.f_small, anchor="e"
        )
        self.counter.pack(fill="x")

        self.error = tk.Label(
            inner, text="", bg=self.bg, fg=self.warn, font=self.f_small,
            anchor="w", wraplength=inner_w, justify="left",
        )

        bottom = tk.Frame(inner, bg=self.bg)
        bottom.pack(fill="x", pady=(int(16 * scale), 0))
        bottom.grid_columnconfigure(0, weight=1, uniform="edge")
        bottom.grid_columnconfigure(2, weight=1, uniform="edge")

        self.send_button = self._make_button(bottom, "[ SEND ]", self._submit, self.f_body)
        self.send_button.grid(row=0, column=1)

        self.sheep_button = self._make_button(
            bottom, f"[ {core.sheep_label(self.cfg)} ]", self._toggle_pause, self.f_small,
            color=self.dim,
        )
        self.sheep_button.grid(row=0, column=2, sticky="e")

        self.pause_row = tk.Frame(inner, bg=self.bg)
        tk.Label(
            self.pause_row, text="pause for", bg=self.bg, fg=self.dim, font=self.f_small
        ).pack(side="left")
        self.pause_entry = tk.Entry(
            self.pause_row, width=5, justify="center", bg=self.bg, fg=self.fg,
            insertbackground=self.fg, relief="flat", bd=0, font=self.f_small,
            highlightbackground=self.dim, highlightcolor=self.fg, highlightthickness=1,
            selectbackground=self.fg, selectforeground=self.bg,
        )
        self.pause_entry.insert(
            0, str(int(core.num(self.cfg.get("default_pause_minutes"), 60, minimum=1)))
        )
        self.pause_entry.pack(side="left", padx=int(8 * scale))
        self.pause_entry.bind("<Return>", lambda _e: (self._pause(), "break")[1])
        tk.Label(
            self.pause_row, text="minutes", bg=self.bg, fg=self.dim, font=self.f_small
        ).pack(side="left")
        self._make_button(
            self.pause_row, "[ PAUSE ]", self._pause, self.f_small
        ).pack(side="left", padx=(int(14 * scale), 0))

        self._on_change()

    def _make_button(self, parent, label, command, font, color=None) -> tk.Button:
        return tk.Button(
            parent, text=label, command=command, font=font,
            bg=self.bg, fg=color or self.fg, activebackground=self.bg,
            activeforeground=self.fg, disabledforeground=self.dim,
            relief="flat", bd=0, highlightthickness=0, padx=6, pady=2, cursor="hand2",
        )

    # -- behaviour ---------------------------------------------------------- #

    def _content(self) -> str:
        return self.text.get("1.0", "end-1c").strip()

    def _display_lines(self) -> int:
        try:
            # without this the count uses the previous layout: the box would grow
            # one keystroke late, and not at all when text is pasted in
            self.text.update_idletasks()
            counted = self.text.count("1.0", "end-1c", "displaylines")
        except tk.TclError:
            return 1
        if isinstance(counted, tuple):
            counted = counted[0] if counted else 0
        # count returns the steps between lines, so there is always one more line
        return max(1, int(counted or 0) + 1)

    def _on_change(self, _event=None) -> None:
        lines = min(self._display_lines(), MAX_INPUT_LINES)
        if lines != self._lines:
            self._lines = lines
            self.text.configure(height=lines)

        length = len(self._content())
        if self.min_chars:
            reached = length >= self.min_chars
            self.counter.configure(
                text=str(length) if reached else f"{length} / {self.min_chars}",
                fg=self.fg if reached else self.dim,
            )
        else:
            self.counter.configure(text=str(length) if length else "")
        self.send_button.configure(
            state="normal" if length >= max(1, self.min_chars) else "disabled"
        )

    def _on_return(self, _event):
        self._submit()
        return "break"

    def _on_newline(self, _event):
        self.text.insert("insert", "\n")
        self._on_change()
        return "break"

    def _show_error(self, message: str) -> None:
        self.error.configure(text=message)
        self.error.pack(fill="x", pady=(8, 0))

    def _submit(self) -> None:
        content = self._content()
        if len(content) < max(1, self.min_chars):
            self.window.bell()
            return
        try:
            core.save_answer(content, self.cfg)
        except Exception as exc:
            core.log_error(f"could not save the answer: {exc!r}")
            self._show_error(
                f"Cannot write to the journal file: {exc}\n"
                "Your answer is still here: close the file if you have it open and try again."
            )
            return
        self._close("answer", 0)

    def _toggle_pause(self) -> None:
        """The sheep stays put and works as a switch, both ways."""
        if self.pause_open:
            self.pause_row.pack_forget()
            self.sheep_button.configure(fg=self.dim)
            self.pause_open = False
            self.text.focus_set()
        else:
            self.pause_row.pack(fill="x", pady=(10, 0))
            self.sheep_button.configure(fg=self.fg)
            self.pause_open = True
            self.pause_entry.focus_set()
            self.pause_entry.select_range(0, "end")
        # the box is anchored to the centre: without an explicit repaint the area
        # it frees up keeps showing the old drawing
        self.window.update_idletasks()
        self.window.update()

    def _pause(self) -> None:
        try:
            minutes = float(self.pause_entry.get().strip().replace(",", "."))
        except ValueError:
            minutes = 0
        if minutes <= 0:
            self.window.bell()
            return
        self._close("pause", minutes)

    def _on_abort(self, _event=None):
        core.log_error("screen closed with Ctrl+Alt+Shift+Q (nothing saved)")
        self._close("abort", 0)
        return "break"

    def _close(self, action: str, minutes: float) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.window.grab_release()
        except tk.TclError:
            pass
        for blank in self.blanks:
            try:
                blank.destroy()
            except tk.TclError:
                pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        self.on_close(action, minutes)


# --------------------------------------------------------------------------- #
# application
# --------------------------------------------------------------------------- #

class App:
    def __init__(self, root: tk.Tk, args: dict):
        self.root = root
        self.scheduler = core.Scheduler(args)
        self.prompt: PromptWindow | None = None
        root.report_callback_exception = self._on_callback_error
        self._tick()

    def _on_callback_error(self, exc_type, exc, tb) -> None:
        import traceback
        core.log_error("".join(traceback.format_exception(exc_type, exc, tb)).rstrip())

    def _tick(self) -> None:
        try:
            if self.prompt is None and self.scheduler.check() == "ask":
                self.scheduler.mark_asking()
                self.prompt = PromptWindow(self.root, self.scheduler.cfg, self._on_prompt_closed)
        except Exception as exc:
            core.log_error(f"tick: {exc!r}")
            self.prompt = None
            self.scheduler.schedule_next()
        self.root.after(core.TICK_SECONDS * 1000, self._tick)

    def _on_prompt_closed(self, action: str, minutes: float) -> None:
        self.prompt = None
        if action == "pause":
            self.scheduler.postpone(minutes, state="paused")
        else:
            self.scheduler.schedule_next()


def main() -> int:
    core.install_error_hooks()
    args = core.parse_args()
    if not core.acquire_single_instance():
        return 0
    core.write_pid_file()
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    App(root, args)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
