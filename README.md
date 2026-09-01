# Mirror

Every X minutes Mirror takes over the screen and asks **"What are you doing?"**.
What you type goes into a Markdown file named after today's date: a new file each
day, every answer of that day appended to it.

It is a way to end up with a journal of where the day went, without having to
remember to write one.

## Install

**[Download the latest release](https://github.com/ionmint/mirror/releases/latest)**,
extract it anywhere, then **double click `install.bat`**. It finds Python, asks
six questions, writes `config.json`, sets up autostart and launches Mirror.

To move it to another PC: copy the folder (the `.bat` files and `src\` are enough,
the rest is recreated) and run `install.bat` there.

The only requirement is **Python 3.8 or newer**, with the tkinter that comes with
it — the standard installer from python.org includes it. If Python is missing,
`install.bat` says so and offers to open the download page — leave the *"Add
python.exe to PATH"* box ticked while installing. Nothing else: no `pip`, no
third party libraries.

If you downloaded the ZIP, Windows asks once whether you trust `install.bat`:
anything arriving from the internet carries a mark that says so. Confirm it, or
right-click the ZIP → Properties → **Unblock** before extracting and the question
never comes up.

## The six files you use

They are the six in plain sight. Everything else lives in `src\` and is not meant
to be run by hand.

| File | What it does |
|---|---|
| `install.bat` | guided install: run this first |
| `configure.bat` | asks the same questions again to change your mind |
| `status.bat` | live panel: what Mirror is doing and when it will ask next |
| `start.bat` | start it now |
| `stop.bat` | stop it |
| `uninstall.bat` | removes autostart and stops it (your journals stay) |

`config.json` can also be edited by hand (see below), but everything worth
changing is among the questions `configure.bat` asks.

## The loop, in short

```
   (nothing on screen)  ──15 min──►  QUESTION  ──answer──►  line in the journal
          ▲                             │                          │
          └─────────────────────────────┴──────────────────────────┘
                     the timer restarts and Mirror disappears
```

Mirror is always running and **invisible**: no console, no taskbar button. No
window exists until the timer runs out; the moment you answer (or pause) it
vanishes and goes back to waiting. It is not meant to be closed — pause it
instead.

Autostart is a shortcut in your Startup folder (`shell:startup` → `Mirror.lnk`).

---

## Day to day

```
 ┌ mirror ──────────────────────────────────┐
 │                                          │
 │  > What are you doing?                   │
 │  ──────────────────────────────────────  │
 │                                          │
 │  > writing the plan for the app█         │
 │  ──────────────────────────────────────  │
 │                                 28 / 30  │
 │                                          │
 │              [ SEND ]            [ 🐑 ]  │
 └──────────────────────────────────────────┘
```

| Key | What it does |
|---|---|
| **Enter** | send the answer and close the screen |
| **Shift+Enter** | new line inside the answer |
| **Ctrl+V** | paste |
| **Right Shift + -** | show the pause row, and hide it again |
| **Esc**, the **X** | do nothing: you leave by answering or pausing |
| **Ctrl+Alt+Shift+Q** | escape hatch (see below) |

The **🐑** button at the bottom right is a switch: click it and the pause row
appears, click it again and it folds away. **Right Shift + -** does the same
thing, and it is the reason the screen needs no mouse at all: the sheep was the
last control without a key of its own.

```
   pause for [ 60 ] minutes   [ PAUSE ]
```

The cursor is already in the field: type the minutes and press **Enter**, or the
PAUSE button if you would rather. The screen closes **without writing anything**
to the journal and stays away for that long. For a really long break just use a
big number (`600` is ten hours).

## The status panel

`status.bat` opens a small window that refreshes once a second until you press a
key:

```
  ┌─ mirror ─────────────────────────────────────────────┐
  │  STATUS          running                             │
  │  ──────────────────────────────────────────────────  │
  │  next question   in 07:12                            │
  │  interval        15 min                              │
  │  today's log     4 answers                           │
  │  last answer     10:30  writing the plan for the a…  │
  │  autostart       on                                  │
  │  log folder      C:\Mirror\log                       │
  └──────────────────────────────────────────────────────┘
       press any key to close · updates live
```

The status line reads `running`, `paused`, `asking now`, `holding · cs2.exe`
(waiting for a game to close) or `stopped`.

---

## The journal

One file per day, in the folder you picked during the install — `log\`, right
here, unless you said otherwise:

```
log\2026-08-26.md
log\2026-08-27.md
```

Inside:

```markdown
# 2026-08-27

- **09:15** — Writing the plan for the app.
- **09:45** — Team meeting
  then reviewing the PR
- **10:30** — Coffee, then catching up on email.
```

- The file name is decided **when you write**: an answer given at one in the
  morning lands in the new day's file, not yesterday's.
- Extra lines of a multi-line answer are indented by two spaces, so Markdown
  keeps them inside the same bullet.
- If the file is locked by an editor, the screen **stays open** with a red notice
  instead of losing what you wrote: close the file and press Enter again.

If you expect to replace this folder one day with a newer copy of Mirror, point
`log_dir` at somewhere outside it — an absolute path works — so that updating the
program can never touch your journals.

---

## What it does, feature by feature

### The box that grows
It starts one line tall and grows as you type — both when you break the line
yourself and when the text wraps on its own. Past 12 lines it stops growing and
scrolls.

### Minimum length
An answer needs at least **30 characters** (`min_chars`): below that the SEND
button is dead, the counter shows `12 / 30` in dim amber and pressing Enter only
beeps. Once you are over it the counter becomes a plain number in full amber.
With `min_chars: 0` only the "not empty" rule remains.

### The hidden pause
There is no pause field in sight, only the sheep. That is deliberate friction — a
pause button within easy reach turns into a skip button.

The way in from the keyboard is **Right Shift + -**, which the install lets you
change: `pause_key` takes any key from the right of the keyboard, so the
shortcut sits under the same hand as the right Shift itself.

`-` `,` `.`, `6` to `0`, `y u i o p h j k l n m` and `f7` to `f12`. It reads the
key by its position, not by the character printed on it, so the Italian and the
UK layout behave the same and Caps Lock changes nothing.

The **right** Shift matters. On a key from that side of the keyboard the shifted
character is one you reach for with the *left* Shift, so the shortcut stays out
of the way of writing: with the default, Right Shift + `-` opens the pause row
while left Shift + `-` still types `_` as always.

### A screen you cannot skip
`Esc`, the X and `Ctrl+C` close nothing. The only ways out are answering and
pausing.

**Escape hatch**: `Ctrl+Alt+Shift+Q` closes without saving and pushes the
question back by one interval. It is not a comfortable skip: it is deliberately
awkward to press by accident, and exists in case a bug ever leaves every screen
covered. To remove it, delete `_on_abort` from `src\mirror_gui.py`.

### Every monitor
Mirror puts the question on the primary monitor and blacks out the others, so you
cannot just carry on working on the screen next door. With
`cover_all_monitors: false` it only covers the primary one.

### Holding off during games and presentations
When the timer runs out Mirror first checks whether you are busy, and **waits**
rather than barging in. `on_fullscreen_app` sets how polite it is:

| Value | Behaviour |
|---|---|
| `defer` (default) | wait if Windows reports a full screen game, a full screen app or presentation mode |
| `show` | ask anyway, on top of everything |
| `defer_presentation` | wait only in presentation mode; ask during games |

This is the same signal Windows uses to mute notifications
(`SHQueryUserNotificationState`), so it also covers screen sharing in calls.

### The games list
One of the install questions, and it **overrides everything**, `show` included:

```json
"always_defer_processes": ["eldenring.exe", "cs2.exe"]
```

As long as one of those executables is running — even when it is not in the
foreground, even if you have gone back to the desktop — the question waits until
you have **closed** the game. Write the executable file name; case does not
matter.

Nothing is ever lost: the question retries every `defer_retry_minutes` and
arrives as soon as you are free.

### A timer that survives sleep
It does not count minutes of its own, it compares a deadline against the clock:
if the PC sleeps or hibernates, the deadline has already passed when it wakes and
the question comes straight away instead of drifting.

### One instance only
Mirror cannot be started twice: the extra copy quits quietly, so running
`start.bat` while it is up does no harm.

### Config read on the fly
`config.json` is reread **every time the timer runs out**: change the interval,
save, and it applies from the next question.

---

## config.json

The first five keys are the ones the install asks about; the rest are there if
you feel like it.

| Key | Default | What it does |
|---|---|---|
| `question` | `"What are you doing?"` | the question, shown exactly as written here |
| `interval_minutes` | `15` | how often it asks |
| `min_chars` | `30` | minimum length of an answer (`0` = no minimum) |
| `log_dir` | `"log"` | journal folder; an absolute path works too |
| `always_defer_processes` | `[]` | executables that always make it wait |
| `default_pause_minutes` | `60` | what the pause field starts at |
| `pause_key` | `"-"` | which key, held with the **right** Shift, opens the pause row. Right of the keyboard only: `- , .`, `6`–`0`, `y u i o p h j k l n m`, `f7`–`f12` |
| `ask_on_start` | `false` | `true` = ask right away instead of waiting |
| `width_fraction` | `0.3333` | box width as a share of the screen |
| `on_fullscreen_app` | `"defer"` | `defer` \| `show` \| `defer_presentation` |
| `defer_retry_minutes` | `5` | how often to retry while holding off |
| `cover_all_monitors` | `true` | `false` = cover the primary monitor only |
| `sheep_style` | `"auto"` | `auto` \| `emoji` \| `ascii` |
| `colors` | amber on black | `bg`, `fg`, `dim` (secondary text), `warn` (errors) |

A different palette — green phosphor:

```json
"colors": { "bg": "#000000", "fg": "#33ff33", "dim": "#1f7a1f", "warn": "#ff5555" }
```

There is no `config.json` in a fresh copy: `install.bat` writes it. Without one
Mirror still starts, on the defaults above. If the file has a syntax error Mirror
falls back to those defaults too, and notes it in `mirror.log`, rather than
refusing to start.

---

## What is in here

The six `.bat` files above, `config.json`, and:

| | What it is for |
|---|---|
| `src\setup.py` | the guided procedure behind the `.bat` files |
| `src\_python.bat` | finds Python; called by the others, not run by hand |
| `src\mirror_core.py` | config, journal, timer, checks |
| `src\mirror_gui.py` | the invisible process and the question screen |
| `src\status.py` | the live status panel |
| `src\console_ui.py` | terminal drawing, used by the status panel |
| `log\` | the journals, one per day |
| `mirror.pid` | process id, used by `stop.bat` |
| `mirror.log` | errors and postponements. Only appears when there is something to say |
| `.mirror_state.json` | what the running process is doing, read by `status.bat` |
| `.gitignore` | keeps your settings and your journals out of version control |

The last four appear on their own once Mirror has run.

### Command line, for testing

Handy when you do not want to wait a quarter of an hour:

```
py src\mirror_gui.py --now           ask immediately, ignoring the timer
py src\mirror_gui.py --interval 1    one minute interval (0.5 works too)
py src\setup.py --summary            print the current settings and exit
```

---

## When something looks wrong

| Symptom | Where to look |
|---|---|
| it does not start | run `py src\setup.py --summary`, then read `mirror.log`: under `pythonw.exe` there is no console to show errors |
| the question never comes | `mirror.log` again: it also records every postponement, with the reason |
| the config seems ignored | invalid JSON — `mirror.log` says so. A Notepad BOM is fine |
| the sheep is an empty box | set `"sheep_style": "ascii"` |
| `stop.bat` says it is not running | it already stopped; delete a leftover `mirror.pid` by hand |
| autostart opens nothing | the shortcut points at an old path: run `install.bat` again |
| two questions at once | cannot happen, but if it does: `stop.bat`, then `start.bat` |

## Notes for whoever maintains this

Two Windows quirks Mirror works around, written down so they do not have to be
rediscovered:

- **Notepad's BOM**: saving `config.json` as UTF-8 in Notepad puts three
  invisible bytes in front, which makes `json.loads` fail. The file is read as
  `utf-8-sig`, so any editor will do.
- **The foreground lock**: Windows stops a background process from taking the
  foreground. Mirror uses the `AttachThreadInput` dance, otherwise the screen
  would appear without keyboard focus and you would be typing into whatever is
  underneath.

One layout rule worth keeping: everything in `src\` computes its paths from
`BASE_DIR`, the folder above it — the one you are looking at. That is what keeps
`config.json`, `log\` and the runtime files out where you can reach them, instead
of buried next to the code.

---

## Licence

MIT — see `LICENSE`. Take it, change it, keep the journals to yourself.

