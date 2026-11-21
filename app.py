import csv
import math
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText

import algorithms as A
import puzzles as P
from game import Game

# ---------------------------------------------------------------- theme  (parchment & ink)
BG, PANEL, CARD, FG = "#ece0c6", "#f5ecd9", "#e1d1ae", "#3a2a1a"
MUTED, ACCENT, GREEN, RED, AMBER = "#8a7459", "#7b2d26", "#4f7040", "#a8322a", "#b5832a"
INK = "#2b4c7e"                                   # blue fountain-pen ink for the player's digits
PAPER = "#f6eddb"
BOARD_BG, BOX_ALT, SEL, PEER, SAME = "#f8f0dd", "#efe3c6", "#d8b878", "#efe2c3", "#e6cf97"
WRONG_BG, HINT_BG = "#ebbdb0", "#f2db9a"
LINE_THIN, LINE_THICK = "#c4b290", "#3a2a1a"
HOVER, DISABLED_BG, DISABLED_FG = "#d3bf93", "#e8dcc0", "#b4a381"
FONT = "Georgia"            # text (resolved at start-up)
FONT_NUM = "Times New Roman"   # numerals: lining figures, so 0 never looks like an o
PALETTE = ["#7b2d26", "#2f5d62", "#b5832a", "#5b7553", "#8a5a83", "#c0703a",
           "#3d5a80", "#9c4a4a", "#6b705c", "#a68a64", "#4b3f72"]
KEYS = list(A.ALGORITHMS)
COLOR_OF = {k: PALETTE[i % len(PALETTE)] for i, k in enumerate(KEYS)}


def fmt_time(s):
    s = int(s)
    return f"{s // 60:02d}:{s % 60:02d}"


# ---------------------------------------------------------------- board widget
class Board(tk.Canvas):
    """9x9 canvas used by both the Play tab and the AI tab."""

    def __init__(self, master, size=456, on_select=None, rule_conflicts=False):
        super().__init__(master, width=size, height=size, bg=BOARD_BG, highlightthickness=0, cursor="hand2")
        self.size, self.margin = size, 6
        self.cell = (size - 2 * self.margin) / 9
        self.givens, self.cells = [0] * 81, [0] * 81
        self.notes = None
        self.sel, self.hint = None, None
        self.wrong = set()
        self.solved = False
        self.same = True
        self.rule_conflicts = rule_conflicts
        self.on_select = on_select
        self.bind("<Button-1>", self._click)
        self.render()

    def set_size(self, size):
        self.size = size
        self.cell = (size - 2 * self.margin) / 9
        self.config(width=size, height=size)
        self.render()

    def _click(self, e):
        c = int((e.x - self.margin) // self.cell)
        r = int((e.y - self.margin) // self.cell)
        if 0 <= r < 9 and 0 <= c < 9:
            self.sel = r * 9 + c
            self.render()
            if self.on_select:
                self.on_select(self.sel)

    def move(self, dr, dc):
        r, c = divmod(self.sel if self.sel is not None else 40, 9)
        self.sel = ((r + dr) % 9) * 9 + (c + dc) % 9
        self.render()
        if self.on_select:
            self.on_select(self.sel)

    def conflicts(self):
        bad = set()
        for i, v in enumerate(self.cells):
            if v:
                for p in A.PEERS[i]:
                    if self.cells[p] == v:
                        bad.add(i)
                        break
        return bad

    def render(self):
        self.delete("all")
        m, s = self.margin, self.cell

        def rect(i, fill, outline="", w=1):
            r, c = divmod(i, 9)
            self.create_rectangle(m + c * s + 1, m + r * s + 1, m + (c + 1) * s - 1, m + (r + 1) * s - 1,
                                  fill=fill, outline=outline, width=w)

        for b in range(9):
            br, bc = divmod(b, 3)
            if (br + bc) % 2 == 0:
                self.create_rectangle(m + bc * 3 * s, m + br * 3 * s, m + (bc + 1) * 3 * s,
                                      m + (br + 1) * 3 * s, fill=BOX_ALT, outline="")
        if self.sel is not None:
            selv = self.cells[self.sel]
            for p in A.PEERS[self.sel]:
                rect(p, PEER)
            if self.same and selv:
                for i, v in enumerate(self.cells):
                    if v == selv:
                        rect(i, SAME)
            rect(self.sel, SEL)
        for i in self.wrong:
            rect(i, WRONG_BG)
        if self.hint is not None:
            rect(self.hint, HINT_BG, AMBER, 2)
        for k in range(10):
            thick = k % 3 == 0
            col, w = (LINE_THICK, 3) if thick else (LINE_THIN, 1)
            self.create_line(m, m + k * s, m + 9 * s, m + k * s, fill=col, width=w)
            self.create_line(m + k * s, m, m + k * s, m + 9 * s, fill=col, width=w)
        bad = self.conflicts() if self.rule_conflicts else set()
        for i, v in enumerate(self.cells):
            r, c = divmod(i, 9)
            if v:
                if i in self.wrong or i in bad:
                    color = RED
                elif self.givens[i]:
                    color = FG
                elif self.solved:
                    color = GREEN
                else:
                    color = INK
                weight = "bold" if self.givens[i] else "normal"
                self.create_text(m + (c + .5) * s, m + (r + .5) * s, text=str(v), fill=color,
                                 font=(FONT_NUM, max(12, int(s * 0.46)), weight))
            elif self.notes is not None and self.notes[i]:
                for d in self.notes[i]:
                    x = m + c * s + ((d - 1) % 3 + .5) * s / 3
                    y = m + r * s + ((d - 1) // 3 + .5) * s / 3
                    self.create_text(x, y, text=str(d), fill=MUTED, font=(FONT_NUM, max(6, int(s * 0.16))))


# ---------------------------------------------------------------- number pad button
class PadButton(tk.Frame):
    """Big digit on top, small grey italic 'n left' underneath - clearly not part of the digit."""

    def __init__(self, master, digit, command):
        super().__init__(master, bg=CARD, cursor="hand2")
        self.command, self.enabled = command, True
        self.num = tk.Label(self, text=str(digit), bg=CARD, fg=FG, font=(FONT_NUM, 18, "bold"))
        self.num.pack(pady=(5, 0))
        self.cnt = tk.Label(self, text="", bg=CARD, fg=MUTED, font=(FONT, 8, "italic"))
        self.cnt.pack(pady=(0, 5))
        for w in (self, self.num, self.cnt):
            w.bind("<Button-1>", lambda e: self.command() if self.enabled else None)
            w.bind("<Enter>", lambda e: self._paint(HOVER) if self.enabled else None)
            w.bind("<Leave>", lambda e: self._paint(CARD if self.enabled else DISABLED_BG))

    def _paint(self, bg):
        for w in (self, self.num, self.cnt):
            w.config(bg=bg)

    def update_count(self, remaining, enabled):
        self.enabled = enabled
        self.num.config(fg=FG if enabled else DISABLED_FG)
        self.cnt.config(text=f"{remaining} left" if remaining > 0 else "all placed",
                        fg=MUTED if enabled else DISABLED_FG)
        self._paint(CARD if enabled else DISABLED_BG)


# ---------------------------------------------------------------- sidebar navigation
class SideNav(tk.Frame):
    """Vertical menu on the left; shows one page at a time."""

    def __init__(self, master):
        super().__init__(master, bg=CARD, width=190)
        self.pack_propagate(False)
        tk.Label(self, text="Sudoku", bg=CARD, fg=ACCENT, font=(FONT, 26, "bold italic")).pack(
            anchor="w", padx=22, pady=(26, 28))
        self.rows, self.current = [], -1

    def add(self, frame, text):
        row = tk.Frame(self, bg=CARD, cursor="hand2")
        row.pack(fill="x")
        bar = tk.Frame(row, bg=CARD, width=4)
        bar.pack(side="left", fill="y")
        lab = tk.Label(row, text=text, bg=CARD, fg=FG, font=(FONT, 14, "italic"), anchor="w", padx=18, pady=11)
        lab.pack(side="left", fill="x", expand=True)
        i = len(self.rows)
        self.rows.append((frame, row, bar, lab))
        for w in (row, lab):
            w.bind("<Button-1>", lambda e, i=i: self.select(i))
            w.bind("<Enter>", lambda e, i=i: self._hover(i, True))
            w.bind("<Leave>", lambda e, i=i: self._hover(i, False))

    def _hover(self, i, on):
        if i != self.current:
            _, row, _, lab = self.rows[i]
            row.config(bg=HOVER if on else CARD)
            lab.config(bg=HOVER if on else CARD)

    def select(self, which):
        i = which if isinstance(which, int) else next(k for k, r in enumerate(self.rows) if r[0] is which)
        if i == self.current:
            return
        for k, (frame, row, bar, lab) in enumerate(self.rows):
            sel = k == i
            if sel:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
            row.config(bg=BG if sel else CARD)
            lab.config(bg=BG if sel else CARD, fg=ACCENT if sel else FG,
                       font=(FONT, 14, "bold italic" if sel else "italic"))
            bar.config(bg=ACCENT if sel else CARD)
        self.current = i

    def index(self, what="current"):
        return self.current


RIGHT_W, WRAP = 380, 336            # width of the slim control panel on the right


# ---------------------------------------------------------------- charts
def bar_chart(canvas, title, data, log=False, fmt="{:.3g}"):
    """data = [(label, value, colour)] - horizontal bars."""
    canvas.delete("all")
    w = canvas.winfo_width()
    if w < 100:
        w = int(canvas["width"])
    canvas.create_text(10, 12, text=title, fill=FG, anchor="w", font=(FONT, 10, "bold"))
    if not data:
        canvas.create_text(w / 2, 150, text="Run a benchmark to see results", fill=MUTED, font=(FONT, 10))
        return
    vals = [max(v, 1e-9) for _, v, _ in data]
    hi, lo = max(vals), min(vals) / 3
    left, right, top = 108, 58, 30
    row_h = min(24, (int(canvas["height"]) - top - 6) / len(data))
    for n, (lab, v, col) in enumerate(data):
        y = top + n * row_h
        if log and hi > lo:
            frac = (math.log(max(v, 1e-9)) - math.log(lo)) / (math.log(hi) - math.log(lo))
        else:
            frac = v / hi if hi else 0
        frac = max(frac, 0.02) if v > 0 else 0
        x1 = left + frac * (w - left - right)
        canvas.create_text(left - 6, y + row_h / 2, text=lab, fill=MUTED, anchor="e", font=(FONT, 8))
        canvas.create_rectangle(left, y + 3, x1, y + row_h - 3, fill=col, outline="")
        canvas.create_text(x1 + 5, y + row_h / 2, text=fmt.format(v), fill=FG, anchor="w", font=(FONT, 8))


FORMULATION = """\
PROBLEM: SUDOKU AS AN AI PROBLEM
================================
Real-world relevance: Sudoku is a canonical Constraint Satisfaction Problem (CSP). The same
formulation drives timetable scheduling, exam planning, frequency assignment and resource allocation.

APPLICATION STRUCTURE
  PLAY tab      : a human solves the puzzle (pencil notes, undo/redo, hints, mistake counter, timer).
                  The hint engine uses the same logic as the AI: naked singles and hidden singles.
  AI SOLVER tab : the computer solves a puzzle with a chosen algorithm; the search is animated.
  BENCHMARK tab : all algorithms are compared on time, explored states, backtracks and success.
  When a player finishes a puzzle, the AI's time on the same puzzle is shown for comparison.

STATE
  A 9x9 grid; each cell holds a digit 1-9 or is empty.
  Initial state : the puzzle with its given clues.
  Goal state    : all 81 cells filled and every row, column and 3x3 box contains 1-9 exactly once.

STATE SPACE & ACTIONS
  Search view : action = place a legal digit in an empty cell (path cost 1 per placement, depth = #empty cells).
  CSP view    : 81 variables, domain {1..9}, 810 binary 'not-equal' constraints (cell vs its 20 peers).
  Local-search view : every 3x3 box already contains 1-9; action = swap two non-given cells in one box.

CONSTRAINTS
  All-different over each of the 9 rows, 9 columns and 9 boxes. Given clues are fixed.

EVALUATION / HEURISTICS
  MRV (Minimum Remaining Values) : branch on the cell with the fewest legal digits (fail-first).
  Constraint tightness           : h = sum over empty cells of (|domain| - 1)  (Greedy Best-First).
  A*  : g = accumulated branching cost, h = number of empty cells (admissible).
  Conflict cost (local search)   : number of missing digits over all rows and columns; 0 = solved.

ALGORITHMS IMPLEMENTED (9)
  Uninformed : DFS (naive backtracking), BFS
  Informed   : Greedy Best-First, A*
  CSP        : Backtracking + MRV, AC-3 / MAC, Constraint Propagation (naked/hidden singles)
  Local      : Hill Climbing with restarts, Simulated Annealing

PERFORMANCE MEASURES
  Execution time, explored states (nodes / iterations / generations), backtracks (dead ends, or rejected
  moves for local search), solved vs timeout, algorithm-specific operations (arc revisions, eliminations,
  restarts, fitness evaluations).

EXPECTED FINDINGS
  * Inference-based CSP methods (MAC, Constraint Propagation) explore orders of magnitude fewer states.
  * Plain DFS is fast on easy grids but explodes on adversarial ones; BFS runs out of memory.
  * Informed search is strong when the heuristic keeps the branching factor low.
  * Stochastic local search is incomplete: fine on easy puzzles, unreliable on hard ones,
    and can never prove that a puzzle has no solution.

LIMITATIONS
  * Pure-Python timings; absolute numbers depend on the machine.
  * Local search is probabilistic, so its results vary between runs.
  * BFS/A*/Greedy store full states, so memory is capped (reported as 'memory limit').
  * Only classic 9x9 Sudoku is handled; no variants (killer, diagonal, 16x16).
  * The Play tab requires puzzles with a unique solution (generated puzzles always have one).
"""

HELP = "Keyboard: 1-9 to write, Backspace to erase, arrow keys to move, N for notes, H for a hint, Ctrl+Z / Ctrl+Y to undo and redo."


# ---------------------------------------------------------------- application
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        global FONT, FONT_NUM
        have = set(tkfont.families(self))
        FONT = next((f for f in ("Georgia", "Palatino Linotype", "DejaVu Serif") if f in have), "Times")
        FONT_NUM = next((f for f in ("Palatino Linotype", "Book Antiqua", "Times New Roman", "Liberation Serif",
                                     "DejaVu Serif") if f in have), "Times")
        self.title("Sudoku")
        self.minsize(1000, 620)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()      # fit the window to this screen
        w, h = min(1360, int(sw * 0.92)), min(860, int(sh * 0.86))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
        self.configure(bg=BG)
        self._style()

        self.game = None
        self.notes_mode = False
        self.pending_hint = None
        self.show_check = False
        self.ai_puzzle = P.parse(P.PUZZLES["Medium"])
        self.q = queue.Queue()
        self.stop_ev = threading.Event()
        self.busy = False
        self.frames, self.idx, self.playing, self.result = [], 0, False, None
        self.bench_rows = []

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        self.nav = SideNav(body)
        self.nav.pack(side="left", fill="y")
        tk.Frame(body, bg=LINE_THIN, width=1).pack(side="left", fill="y")
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self.nb = self.nav                      # .select() / .index() are used all over the app
        self.tab_play, self.tab_ai, self.tab_bench, self.tab_form = (tk.Frame(self.content, bg=BG) for _ in range(4))
        for frame, label in [(self.tab_play, "Play"), (self.tab_ai, "AI Solver"),
                             (self.tab_bench, "Benchmark"), (self.tab_form, "Formulation")]:
            self.nav.add(frame, label)
        self._build_play()
        self._build_ai()
        self._build_bench()
        self._build_form()
        self.new_game("Medium")
        self.ai_load(self.ai_puzzle)
        self.nav.select(0)
        self.bind("<Key>", self._key)
        self.after(60, self._poll)
        self.after(500, self._clock)

    # ================================================================ styling
    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=BG, foreground=FG, fieldbackground=CARD, font=(FONT, 10))
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background=PANEL)
        st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Card.TLabel", background=PANEL, foreground=FG)
        st.configure("Muted.TLabel", background=PANEL, foreground=MUTED, font=(FONT, 9))
        st.configure("H.TLabel", background=PANEL, foreground=ACCENT, font=(FONT, 12, "italic"))
        st.configure("Header.TLabel", background=BG, foreground=ACCENT, font=(FONT, 24, "bold italic"))
        st.configure("Sub.TLabel", background=BG, foreground=MUTED, font=(FONT, 11, "italic"))
        st.configure("Stat.TLabel", background=PANEL, foreground=FG, font=(FONT_NUM, 14, "bold"))
        st.configure("Big.TLabel", background=PANEL, foreground=FG, font=(FONT_NUM, 16, "bold"))
        st.configure("Title.TLabel", background=PANEL, foreground=FG, font=(FONT, 20, "italic"))
        st.configure("Msg.TLabel", background=BG, foreground=FG, font=(FONT, 10), padding=10)
        st.configure("TButton", background=CARD, foreground=FG, padding=(10, 7), borderwidth=0, focuscolor=CARD)
        st.map("TButton", background=[("active", HOVER), ("disabled", DISABLED_BG)],
               foreground=[("disabled", DISABLED_FG)])
        st.configure("Accent.TButton", background=ACCENT, foreground=PAPER, font=(FONT, 10, "bold"), focuscolor=ACCENT)
        st.map("Accent.TButton", background=[("active", "#964038"), ("disabled", "#cfb0a8")])
        st.configure("Amber.TButton", background=AMBER, foreground=FG, font=(FONT, 10, "bold"))
        st.map("Amber.TButton", background=[("active", "#d1a24a")])
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", background=BG, foreground=MUTED, padding=(18, 9), font=(FONT, 11, "italic"))
        st.map("TNotebook.Tab", background=[("selected", BG)], foreground=[("selected", ACCENT)])
        st.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=FG, arrowcolor=FG)
        st.map("TCombobox", fieldbackground=[("readonly", CARD)], foreground=[("readonly", FG)])
        st.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=24, borderwidth=0)
        st.configure("Treeview.Heading", background=CARD, foreground=ACCENT, font=(FONT, 9, "bold"))
        st.map("Treeview", background=[("selected", HOVER)])
        st.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=CARD, borderwidth=0)
        st.configure("Horizontal.TScale", background=PANEL, troughcolor=CARD)
        st.configure("TSpinbox", fieldbackground=CARD, foreground=FG, arrowcolor=FG)
        st.configure("TCheckbutton", background=PANEL, foreground=FG, indicatorbackground=PAPER,
                     indicatorforeground=ACCENT, focuscolor=PANEL)
        st.map("TCheckbutton", indicatorbackground=[("selected", PAPER)], indicatorforeground=[("selected", ACCENT)])
        st.configure("TCombobox", arrowsize=14, padding=4, selectbackground=CARD, selectforeground=FG)
        st.map("TCheckbutton", background=[("active", PANEL)])
        self.option_add("*TCombobox*Font", (FONT, 10))
        self.option_add("*TCombobox*Listbox.font", (FONT, 10))
        self.option_add("*TCombobox*Listbox.background", CARD)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", PAPER)

    def _fit(self, board, area, col):
        """Make the board as big as the free space allows (column holds board + widgets below it)."""
        w, h = area.winfo_width(), area.winfo_height()
        if w < 60 or h < 60:
            return
        other = sum(c.winfo_reqheight() for c in col.winfo_children() if c is not board)
        size = int(max(340, min(w - 24, h - other - 28)))
        if abs(size - board.size) >= 4:
            col.place_configure(width=size)
            board.set_size(size)
            for c in col.winfo_children():
                if isinstance(c, ttk.Label):
                    c.config(wraplength=size - 4)

    # ================================================================ PLAY TAB
    def _build_play(self):
        t = self.tab_play
        right = tk.Frame(t, bg=PANEL, width=RIGHT_W)
        right.pack(side="right", fill="y", padx=(0, 16), pady=16)
        right.pack_propagate(False)
        left = tk.Frame(t, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(16, 8), pady=(16, 0))
        col = tk.Frame(left, bg=BG)
        col.place(relx=0.5, y=0, anchor="n", width=456)

        self.pboard = Board(col, size=456, on_select=lambda i: self._play_select())
        self.pboard.pack()
        pad = tk.Frame(col, bg=BG)
        pad.pack(fill="x", pady=(8, 0))
        self.pad_btns = {}
        for d in range(1, 10):
            b = PadButton(pad, d, lambda d=d: self.play_digit(d))
            b.grid(row=0, column=d - 1, padx=2, sticky="ew")
            pad.columnconfigure(d - 1, weight=1)
            self.pad_btns[d] = b
        acts = tk.Frame(col, bg=BG)
        acts.pack(fill="x", pady=(6, 0))
        for text, cmd in [("Undo", self.play_undo), ("Redo", self.play_redo), ("Erase", self.play_erase)]:
            ttk.Button(acts, text=text, command=cmd).pack(side="left", padx=(0, 6))
        self.btn_notes = ttk.Button(acts, text="Notes: off", command=self.toggle_notes)
        self.btn_notes.pack(side="right")
        left.bind("<Configure>", lambda e: self._fit(self.pboard, left, col))

        px = dict(padx=18)
        ttk.Label(right, text="Your turn", style="Title.TLabel").pack(anchor="w", pady=(16, 0), **px)
        ttk.Label(right, text="Pick a cell and type a number. Each row, column and box needs 1 to 9.",
                  style="Muted.TLabel", wraplength=WRAP, justify="left").pack(anchor="w", pady=(0, 10), **px)

        stats = tk.Frame(right, bg=PANEL)
        stats.pack(fill="x", **px)
        self.pl = {}
        for n, (k, lab) in enumerate([("time", "Time"), ("level", "Level"), ("mist", "Mistakes"), ("hints", "Hints")]):
            f = tk.Frame(stats, bg=PANEL)
            f.grid(row=0, column=n, sticky="w", padx=(0, 18))
            ttk.Label(f, text=lab, style="Muted.TLabel").pack(anchor="w")
            v = ttk.Label(f, text="-", style="Stat.TLabel")
            v.pack(anchor="w")
            self.pl[k] = v
        self.pprog = ttk.Progressbar(right, mode="determinate", maximum=81)
        self.pprog.pack(fill="x", pady=(10, 2), **px)
        self.pprog_lbl = ttk.Label(right, text="", style="Muted.TLabel")
        self.pprog_lbl.pack(anchor="w", **px)

        box = tk.Frame(right, bg=BG, height=66)
        box.pack(fill="x", pady=(10, 0), **px)
        box.pack_propagate(False)
        self.msg = ttk.Label(box, text="", style="Msg.TLabel", wraplength=WRAP - 24, justify="left")
        self.msg.pack(fill="both", expand=True)

        ttk.Label(right, text="New game", style="H.TLabel").pack(anchor="w", pady=(14, 4), **px)
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill="x", **px)
        self.lvl_var = tk.StringVar(value="Medium")
        ttk.Combobox(row, textvariable=self.lvl_var, values=list(P.CLUES), state="readonly", width=8).pack(side="left")
        ttk.Button(row, text="New game", style="Accent.TButton",
                   command=lambda: self.new_game(self.lvl_var.get())).pack(side="left", padx=6)
        ttk.Button(row, text="Type my own", command=self.paste_play).pack(side="left")
        self.sample_var = tk.StringVar(value="Easy")
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill="x", pady=(6, 0), **px)
        ttk.Combobox(row, textvariable=self.sample_var, values=list(P.PUZZLES), state="readonly",
                     width=22).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Open sample", command=lambda: self.new_game(
            self.sample_var.get(), P.parse(P.PUZZLES[self.sample_var.get()]))).pack(side="left", padx=(6, 0))

        ttk.Label(right, text="Need a hand?", style="H.TLabel").pack(anchor="w", pady=(14, 4), **px)
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill="x", **px)
        self.btn_hint = ttk.Button(row, text="Hint", command=self.play_hint)
        self.btn_hint.pack(side="left")
        ttk.Button(row, text="Fill in notes", command=self.play_auto_notes).pack(side="left", padx=6)
        ttk.Button(row, text="Check", command=self.play_check).pack(side="left")
        self.v_mistakes = tk.BooleanVar(value=True)
        self.v_same = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Flag mistakes as I go", variable=self.v_mistakes,
                        command=self.refresh_play).pack(anchor="w", pady=(8, 0), **px)
        ttk.Checkbutton(right, text="Highlight same number", variable=self.v_same,
                        command=self.refresh_play).pack(anchor="w", pady=(2, 0), **px)

        ttk.Label(right, text="Done or stuck?", style="H.TLabel").pack(anchor="w", pady=(14, 4), **px)
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill="x", **px)
        ttk.Button(row, text="Show answer", command=self.play_reveal).pack(side="left")
        ttk.Button(row, text="Let the AI try this one  \u2192", style="Accent.TButton",
                   command=self.send_to_ai).pack(side="left", padx=6, fill="x", expand=True)
        ttk.Label(right, text=HELP, style="Muted.TLabel", wraplength=WRAP, justify="left").pack(
            anchor="w", pady=(14, 0), **px)

    # ---- game control
    def say(self, text, color=FG):
        self.msg.config(text=text, foreground=color)

    def new_game(self, level, grid=None):
        try:
            if grid is None:
                self.say("Generating a puzzle with a unique solution ...", MUTED)
                self.update_idletasks()
                grid = P.generate(level)
            g = Game(grid, level)
        except ValueError as e:
            messagebox.showerror("Cannot start game", str(e))
            return
        self.game = g
        g.start()
        self.notes_mode = False
        self.btn_notes.config(text="Notes: off", style="TButton")
        self.show_check = False
        self._clear_hint()
        self.pboard.givens = g.puzzle
        self.pboard.sel = None
        self.pboard.solved = False
        self.say(f"{level} puzzle, {sum(1 for v in g.puzzle if v)} numbers given. Good luck.", MUTED)
        self.refresh_play()

    def refresh_play(self):
        g, b = self.game, self.pboard
        if not g:
            return
        b.cells, b.givens, b.notes = g.cells, g.puzzle, g.notes
        b.same = self.v_same.get()
        b.solved = g.won
        b.wrong = g.wrong_cells() if (self.v_mistakes.get() or self.show_check) and not g.finished else set()
        b.hint = self.pending_hint.idx if self.pending_hint else None
        b.render()
        for d, btn in self.pad_btns.items():
            rem = 9 - g.count(d)
            btn.update_count(max(rem, 0), rem > 0 and not g.finished)
        self.pl["level"].config(text=g.level if len(g.level) < 12 else "Custom")
        self.pl["mist"].config(text=str(g.mistakes), foreground=RED if g.mistakes else FG)
        self.pl["hints"].config(text=str(g.hints))
        self.pprog["value"] = g.filled()
        self.pprog_lbl.config(text=f"{g.filled()} / 81 cells filled")
        self.pl["time"].config(text=fmt_time(g.elapsed))

    def _clock(self):
        if self.game and not self.game.finished:
            self.pl["time"].config(text=fmt_time(self.game.elapsed))
        self.after(500, self._clock)

    def _play_select(self):
        self._clear_hint()
        self.refresh_play()

    def _clear_hint(self):
        self.pending_hint = None
        self.pboard.hint = None
        self.btn_hint.config(text="Hint", style="TButton")

    def _need_cell(self):
        i = self.pboard.sel
        if i is None:
            self.say("Select a cell on the board first.", AMBER)
            return None
        if self.game.is_given(i):
            self.say("That cell is part of the puzzle - it cannot be changed.", AMBER)
            return None
        return i

    def _after_move(self):
        self.show_check = False
        self._clear_hint()
        self.refresh_play()
        if self.game.won:
            self._on_win()

    def play_digit(self, d):
        if self.game.finished:
            return
        i = self._need_cell()
        if i is None:
            return
        if self.notes_mode:
            self.game.toggle_note(i, d)
        else:
            before = self.game.mistakes
            self.game.place(i, d)
            if self.game.mistakes > before and self.v_mistakes.get():
                self.say(f"{d} doesn't go there.", RED)
            elif not self.game.finished:
                self.say("", FG)
        self._after_move()

    def play_erase(self):
        i = self._need_cell()
        if i is not None:
            self.game.erase(i)
            self._after_move()

    def play_undo(self):
        if self.game.undo():
            self._after_move()

    def play_redo(self):
        if self.game.redo():
            self._after_move()

    def toggle_notes(self):
        self.notes_mode = not self.notes_mode
        self.btn_notes.config(text="Notes: on" if self.notes_mode else "Notes: off",
                              style="Amber.TButton" if self.notes_mode else "TButton")
        self.say("Notes on: numbers now go in as small pencil marks." if self.notes_mode
                 else "Notes off: numbers go in the cell again.", MUTED)

    def play_auto_notes(self):
        self.game.auto_notes()
        self.say("Filled in every number that is still possible in each empty cell.", MUTED)
        self._after_move()

    def play_check(self):
        wrong = self.game.wrong_cells()
        self.show_check = True
        if wrong:
            self.say(f"{len(wrong)} wrong cell(s), marked in red.", RED)
        else:
            self.say("All correct so far.", GREEN)
        self.refresh_play()

    def play_hint(self):
        g = self.game
        if g.finished:
            return
        if self.pending_hint:                       # second press -> apply
            h = self.pending_hint
            g.apply_hint(h)
            self.say(f"Filled in {h.value}.", MUTED)
            self._after_move()
            return
        h = g.hint()
        if h is None:
            return
        self.pending_hint = h
        self.pboard.sel = h.idx
        self.btn_hint.config(text="Apply hint", style="Amber.TButton")
        self.say(h.text + ("" if h.kind == "mistake" else "  Press the hint button again to fill it in."), AMBER)
        self.refresh_play()

    def play_reveal(self):
        if self.game.finished:
            return
        if messagebox.askyesno("Show solution", "Show the full answer and end this game?"):
            self.game.reveal()
            self._clear_hint()
            self.say("Here is the answer. Want to see how a computer finds it? Try the button below.", MUTED)
            self.refresh_play()

    def paste_play(self):
        s = simpledialog.askstring("Enter puzzle", "81 characters (digits; 0 or . for blanks):", parent=self)
        if s:
            try:
                self.new_game("Custom", P.parse(s))
            except ValueError as e:
                messagebox.showerror("Invalid puzzle", str(e))

    def _on_win(self):
        g = self.game
        r = A.run_solver("mac", g.puzzle, timeout=5)
        txt = f"Solved in {fmt_time(g.elapsed)}  -  {g.mistakes} mistake(s), {g.hints} hint(s)."
        self.say(txt, GREEN)
        messagebox.showinfo(
            "Well done",
            f"{txt}\n\nThe computer (AC-3 + backtracking) needed {r.seconds * 1000:.2f} ms "
            f"and {r.nodes} search states for the same puzzle.\n\nThe AI Solver tab shows how it works.")

    def send_to_ai(self):
        self.ai_load(self.game.puzzle)
        self.nb.select(self.tab_ai)

    # ================================================================ AI TAB
    def _build_ai(self):
        t = self.tab_ai
        right = tk.Frame(t, bg=PANEL, width=RIGHT_W)
        right.pack(side="right", fill="y", padx=(0, 16), pady=16)
        right.pack_propagate(False)
        left = tk.Frame(t, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(16, 8), pady=(16, 0))
        col = tk.Frame(left, bg=BG)
        col.place(relx=0.5, y=0, anchor="n", width=456)
        self.board = Board(col, size=456, rule_conflicts=True)
        self.board.pack()
        self.status = ttk.Label(col, text="", foreground=MUTED, wraplength=450, justify="left")
        self.status.pack(anchor="w", pady=(8, 0))
        self.prog = ttk.Progressbar(col, mode="determinate")
        self.prog.pack(fill="x", pady=(6, 0))
        ttk.Label(col, text="You can click a cell and type to change the puzzle first.",
                  foreground=MUTED).pack(anchor="w", pady=(6, 0))
        left.bind("<Configure>", lambda e: self._fit(self.board, left, col))

        px = dict(padx=18)
        ttk.Label(right, text="Let the computer try", style="Title.TLabel").pack(anchor="w", pady=(16, 0), **px)
        ttk.Label(right, text="Choose a puzzle and a method, then watch it work through the grid.",
                  style="Muted.TLabel", wraplength=WRAP, justify="left").pack(anchor="w", pady=(0, 8), **px)

        ttk.Label(right, text="1.  Puzzle", style="H.TLabel").pack(anchor="w", **px)
        ttk.Button(right, text="Use my puzzle from Play", command=self.ai_from_play).pack(fill="x", pady=(4, 4), **px)
        self.puz_var = tk.StringVar(value="Medium")
        cb = ttk.Combobox(right, textvariable=self.puz_var, values=list(P.PUZZLES), state="readonly")
        cb.pack(fill="x", **px)
        cb.bind("<<ComboboxSelected>>", lambda e: self.ai_load(P.parse(P.PUZZLES[self.puz_var.get()])))
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill="x", pady=(6, 0), **px)
        self.ai_lvl = tk.StringVar(value="Medium")
        ttk.Combobox(row, textvariable=self.ai_lvl, values=list(P.CLUES), state="readonly", width=8).pack(side="left")
        ttk.Button(row, text="Random", command=self.ai_gen).pack(side="left", padx=6)
        ttk.Button(row, text="Type my own", command=self.ai_paste).pack(side="left")
        ttk.Button(row, text="Clear", command=lambda: self.ai_load([0] * 81)).pack(side="left", padx=6)

        ttk.Label(right, text="2.  Method", style="H.TLabel").pack(anchor="w", pady=(14, 0), **px)
        self.alg_var = tk.StringVar(value=A.ALGORITHMS["mac"]["name"])
        self.alg_cb = ttk.Combobox(right, textvariable=self.alg_var, state="readonly",
                                   values=[m["name"] for m in A.ALGORITHMS.values()])
        self.alg_cb.pack(fill="x", pady=(4, 4), **px)
        self.alg_cb.bind("<<ComboboxSelected>>", lambda e: self._alg_changed())
        box = tk.Frame(right, bg=BG, height=104)
        box.pack(fill="x", **px)
        box.pack_propagate(False)
        self.alg_desc = ttk.Label(box, text="", style="Msg.TLabel", wraplength=WRAP - 24, justify="left")
        self.alg_desc.pack(fill="both", expand=True)

        ttk.Label(right, text="3.  Go", style="H.TLabel").pack(anchor="w", pady=(14, 4), **px)
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill="x", **px)
        ttk.Label(row, text="Speed", style="Card.TLabel").pack(side="left")
        self.speed = tk.IntVar(value=60)
        ttk.Scale(row, from_=1, to=100, variable=self.speed).pack(side="left", fill="x", expand=True, padx=10)
        ttk.Label(row, text="Limit (s)", style="Card.TLabel").pack(side="left")
        self.tl_var = tk.StringVar(value="20")
        ttk.Spinbox(row, from_=1, to=300, textvariable=self.tl_var, width=4).pack(side="left", padx=(6, 0))
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill="x", pady=8, **px)
        self.btn_solve = ttk.Button(row, text="Solve it", style="Accent.TButton", command=self.solve)
        self.btn_solve.pack(side="left")
        self.btn_skip = ttk.Button(row, text="Skip ahead", command=self.skip, state="disabled")
        self.btn_skip.pack(side="left", padx=6)
        self.btn_stop = ttk.Button(row, text="Stop", command=self.stop, state="disabled")
        self.btn_stop.pack(side="left")
        ttk.Button(row, text="Reset", command=lambda: self.ai_load(self.ai_puzzle)).pack(side="left", padx=6)
        ttk.Button(right, text="Compare all methods  \u2192", command=self.go_bench).pack(fill="x", **px)

        ttk.Label(right, text="Last run", style="H.TLabel").pack(anchor="w", pady=(14, 4), **px)
        grid = tk.Frame(right, bg=PANEL)
        grid.pack(fill="x", **px)
        self.stat = {}
        for n, (k, lab) in enumerate([("status", "Status"), ("time", "Time"), ("nodes", "States explored"),
                                      ("back", "Backtracks"), ("ops", "Extra operations"),
                                      ("frames", "Frames")]):
            f = tk.Frame(grid, bg=PANEL)
            f.grid(row=n // 2, column=n % 2, sticky="w", padx=(0, 24), pady=(0, 4))
            ttk.Label(f, text=lab, style="Muted.TLabel").pack(anchor="w")
            v = ttk.Label(f, text="-", style="Stat.TLabel")
            v.pack(anchor="w")
            self.stat[k] = v
        ttk.Label(right, text="Black = given, blue = what the algorithm is trying, green = solved, red = clash.",
                  style="Muted.TLabel", wraplength=WRAP, justify="left").pack(anchor="w", pady=(8, 0), **px)
        self._alg_changed()

    def _key_of_name(self, name):
        return next(k for k, m in A.ALGORITHMS.items() if m["name"] == name)

    def _alg_changed(self):
        m = A.ALGORITHMS[self._key_of_name(self.alg_var.get())]
        self.alg_desc.config(text=f"[{m['cat']}]  {m['desc']}")

    def ai_load(self, grid):
        if self.busy:
            return
        self.playing = False
        self.ai_puzzle = list(grid)
        self.board.givens = list(grid)
        self.board.cells = list(grid)
        self.board.solved = False
        self.board.render()
        self.result, self.frames = None, []
        self.prog["value"] = 0
        self.btn_skip.config(state="disabled")
        n = sum(1 for v in grid if v)
        self.status.config(text=f"Puzzle loaded ({n} numbers given). Pick a method and press Solve it.")

    def ai_from_play(self):
        if self.game:
            self.ai_load(self.game.puzzle)

    def ai_paste(self):
        s = simpledialog.askstring("Enter puzzle", "81 characters (digits; 0 or . for blanks):", parent=self)
        if s:
            try:
                self.ai_load(P.parse(s))
                self.puz_var.set("")
            except ValueError as e:
                messagebox.showerror("Invalid puzzle", str(e))

    def ai_gen(self):
        if self.busy:
            return
        self.status.config(text="Generating a puzzle ...")
        self.update_idletasks()
        self.ai_load(P.generate(self.ai_lvl.get()))
        self.puz_var.set("")

    def _ai_key(self, e):
        b = self.board
        if e.keysym in ("Up", "Down", "Left", "Right"):
            b.move({"Up": -1, "Down": 1}.get(e.keysym, 0), {"Left": -1, "Right": 1}.get(e.keysym, 0))
            return
        if b.sel is None or self.playing:
            return
        if (e.char and e.char in "0123456789") or e.keysym in ("BackSpace", "Delete"):
            v = int(e.char) if e.char and e.char.isdigit() else 0
            i = b.sel
            self.ai_puzzle[i] = v
            b.givens[i] = v
            b.cells[i] = v
            b.solved = False
            b.render()

    # ---- running the algorithm
    def _set_busy(self, flag):
        self.busy = flag
        self.btn_solve.config(state="disabled" if flag else "normal")
        self.btn_stop.config(state="normal" if flag else "disabled")

    def solve(self):
        if self.busy:
            return
        if not any(self.ai_puzzle):
            messagebox.showinfo("Empty board", "Load or type a puzzle first.")
            return
        try:
            timeout = float(self.tl_var.get())
        except ValueError:
            timeout = 20.0
        key = self._key_of_name(self.alg_var.get())
        self.playing = False
        self.board.cells = list(self.ai_puzzle)
        self.board.givens = list(self.ai_puzzle)
        self.board.solved = False
        self.board.render()
        self.stop_ev.clear()
        self._set_busy(True)
        self.btn_skip.config(state="disabled")
        self.status.config(text=f"Running {A.ALGORITHMS[key]['name']} ...")
        self.prog.config(mode="indeterminate")
        self.prog.start(12)
        grid = list(self.ai_puzzle)

        def work():
            self.q.put(("solved", A.run_solver(key, grid, timeout, self.stop_ev, record=True)))

        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        self.stop_ev.set()
        self.playing = False
        if not self.busy:
            self.skip()

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "solved":
                    self._finished(payload)
                elif kind == "bench_row":
                    self._bench_row(*payload)
                elif kind == "bench_done":
                    self._bench_done()
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def _finished(self, r):
        self.prog.stop()
        self.prog.config(mode="determinate", value=0)
        self._set_busy(False)
        self.result = r
        self.stat["status"].config(text=r.status.upper(), foreground=GREEN if r.solved else RED)
        self.stat["time"].config(text=f"{r.seconds:.4f} s")
        self.stat["nodes"].config(text=f"{r.nodes:,}")
        self.stat["back"].config(text=f"{r.backtracks:,}")
        self.stat["ops"].config(text=f"{r.ops:,}")
        self.stat["frames"].config(text=f"{len(r.frames):,}")
        self.frames = r.frames
        self.idx = 0
        self.btn_skip.config(state="normal")
        if not self.frames:
            self._show_final()
            return
        self.playing = True
        self.status.config(text=f"{r.name}: {r.status}.  Replaying its search...")
        self._tick()

    def _tick(self):
        if not self.playing:
            return
        sp = int(self.speed.get())
        if sp <= 40:
            delay, step = int(1000 / sp), 1
        else:
            delay, step = 20, sp - 38
        self.idx = min(self.idx + step, len(self.frames) - 1)
        self.board.cells = list(self.frames[self.idx])
        self.prog["value"] = 100 * self.idx / max(1, len(self.frames) - 1)
        if self.idx >= len(self.frames) - 1:
            self.playing = False
            self._show_final()
            return
        self.board.render()
        self.after(delay, self._tick)

    def _show_final(self):
        r = self.result
        if r and r.solved:
            self.board.cells = list(r.solution)
            self.board.solved = True
            self.status.config(text=f"{r.name} solved the puzzle in {r.seconds:.4f}s "
                                    f"({r.nodes:,} states explored).")
        elif r:
            self.status.config(text=f"{r.name}: {r.status} - no solution found.")
        self.prog["value"] = 100
        self.board.render()

    def skip(self):
        self.playing = False
        if self.result:
            self._show_final()

    def go_bench(self):
        self.nb.select(self.tab_bench)
        self.lb_p.selection_clear(0, "end")
        self.lb_p.select_set("end")

    # ================================================================ BENCHMARK TAB
    def _build_bench(self):
        t = self.tab_bench
        left = ttk.Frame(t, style="Card.TFrame")
        left.pack(side="left", fill="y", padx=14, pady=14)
        ttk.Label(left, text="PUZZLES", style="H.TLabel").pack(anchor="w", padx=14, pady=(14, 4))
        self.lb_p = tk.Listbox(left, selectmode="multiple", exportselection=False, height=7, bg=CARD, fg=FG,
                               selectbackground=ACCENT, selectforeground=PAPER, highlightthickness=0,
                               borderwidth=0, activestyle="none", font=(FONT, 10))
        for n in P.PUZZLES:
            self.lb_p.insert("end", n)
        self.lb_p.insert("end", "Puzzle in AI Solver tab")
        self.lb_p.pack(fill="x", padx=14)
        self.lb_p.select_set(0, 4)
        ttk.Label(left, text="ALGORITHMS", style="H.TLabel").pack(anchor="w", padx=14, pady=(14, 4))
        self.lb_a = tk.Listbox(left, selectmode="multiple", exportselection=False, height=11, bg=CARD, fg=FG,
                               selectbackground=ACCENT, selectforeground=PAPER, highlightthickness=0,
                               borderwidth=0, activestyle="none", font=(FONT, 10), width=30)
        for k in KEYS:
            self.lb_a.insert("end", A.ALGORITHMS[k]["name"])
        self.lb_a.pack(fill="x", padx=14)
        self.lb_a.select_set(0, "end")
        row = ttk.Frame(left, style="Card.TFrame")
        row.pack(fill="x", padx=14, pady=10)
        ttk.Label(row, text="Time limit per run (s)", style="Card.TLabel").pack(side="left")
        self.btl = tk.StringVar(value="5")
        ttk.Spinbox(row, from_=1, to=120, textvariable=self.btl, width=5).pack(side="left", padx=8)
        self.btn_run = ttk.Button(left, text="Run benchmark", style="Accent.TButton", command=self.run_bench)
        self.btn_run.pack(fill="x", padx=14, pady=(4, 4))
        self.btn_bstop = ttk.Button(left, text="Stop", command=lambda: self.stop_ev.set(), state="disabled")
        self.btn_bstop.pack(fill="x", padx=14)
        ttk.Button(left, text="Export CSV", command=self.export_csv).pack(fill="x", padx=14, pady=4)
        self.bprog = ttk.Progressbar(left, mode="determinate")
        self.bprog.pack(fill="x", padx=14, pady=(8, 14))

        right = ttk.Frame(t)
        right.pack(side="left", fill="both", expand=True, padx=(0, 14), pady=14)
        cols = ("puzzle", "algo", "status", "time", "nodes", "back", "ops")
        heads = ("Puzzle", "Algorithm", "Status", "Time (s)", "States", "Backtracks", "Extra ops")
        widths = (150, 220, 100, 80, 90, 90, 90)
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=11)
        for c, h, w in zip(cols, heads, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c in ("puzzle", "algo", "status") else "e")
        self.tree.tag_configure("ok", foreground=GREEN)
        self.tree.tag_configure("fail", foreground=RED)
        self.tree.pack(fill="x")
        charts = ttk.Frame(right)
        charts.pack(fill="both", expand=True, pady=(10, 0))
        self.ch = []
        for i in range(3):
            c = tk.Canvas(charts, bg=PANEL, highlightthickness=0, width=330, height=300)
            c.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 8, 0))
            c.bind("<Configure>", lambda e: self._draw_charts())
            self.ch.append(c)
        self._draw_charts()

    def run_bench(self):
        if self.busy:
            return
        ps = [self.lb_p.get(i) for i in self.lb_p.curselection()]
        al = [KEYS[i] for i in self.lb_a.curselection()]
        if not ps or not al:
            messagebox.showinfo("Benchmark", "Select at least one puzzle and one algorithm.")
            return
        try:
            timeout = float(self.btl.get())
        except ValueError:
            timeout = 5.0
        jobs = []
        for p in ps:
            if p == "Puzzle in AI Solver tab":
                grid = list(self.ai_puzzle)
                if not any(grid):
                    messagebox.showinfo("Benchmark", "The AI Solver board is empty.")
                    return
            else:
                grid = P.parse(P.PUZZLES[p])
            for k in al:
                jobs.append((p, k, grid))
        self.tree.delete(*self.tree.get_children())
        self.bench_rows = []
        self.stop_ev.clear()
        self._set_busy(True)
        self.btn_run.config(state="disabled")
        self.btn_bstop.config(state="normal")
        self.bprog.config(maximum=len(jobs), value=0)

        def work():
            for p, k, g in jobs:
                if self.stop_ev.is_set():
                    break
                r = A.run_solver(k, g, timeout, self.stop_ev)
                self.q.put(("bench_row", (p, r, timeout)))
            self.q.put(("bench_done", None))

        threading.Thread(target=work, daemon=True).start()

    def _bench_row(self, p, r, timeout):
        if r.status == "stopped":
            return
        self.bench_rows.append((p, r.key, r.name, r.status, r.seconds, r.nodes, r.backtracks, r.ops, r.solved, timeout))
        self.tree.insert("", "end", values=(p, r.name, r.status, f"{r.seconds:.4f}", f"{r.nodes:,}",
                                            f"{r.backtracks:,}", f"{r.ops:,}"),
                         tags=("ok" if r.solved else "fail",))
        self.tree.yview_moveto(1)
        self.bprog["value"] += 1
        self._draw_charts()

    def _bench_done(self):
        self._set_busy(False)
        self.btn_run.config(state="normal")
        self.btn_bstop.config(state="disabled")
        self._draw_charts()

    def _draw_charts(self):
        agg = {}
        for p, k, name, st, secs, nodes, back, ops, solved, tmo in self.bench_rows:
            a = agg.setdefault(k, dict(t=0.0, n=0, s=0))
            a["t"] += secs if solved else tmo
            a["n"] += nodes
            a["s"] += 1 if solved else 0
        order = [k for k in KEYS if k in agg]

        def short(k):
            return A.ALGORITHMS[k]["name"].replace(" (naive backtracking)", "").replace(" (restarts)", "")[:18]

        bar_chart(self.ch[0], "Total time (s, log) - timeouts count in full",
                  [(short(k), agg[k]["t"], COLOR_OF[k]) for k in order], log=True, fmt="{:.3f}")
        bar_chart(self.ch[1], "Total explored states (log)",
                  [(short(k), max(agg[k]["n"], 1), COLOR_OF[k]) for k in order], log=True, fmt="{:,.0f}")
        bar_chart(self.ch[2], "Puzzles solved",
                  [(short(k), agg[k]["s"], COLOR_OF[k]) for k in order], log=False, fmt="{:.0f}")

    def export_csv(self):
        if not self.bench_rows:
            messagebox.showinfo("Export", "Run a benchmark first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="sudoku_results.csv")
        if path:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["puzzle", "algorithm", "status", "seconds", "states", "backtracks", "ops"])
                for p, k, name, st, secs, nodes, back, ops, solved, tmo in self.bench_rows:
                    w.writerow([p, name, st, f"{secs:.5f}", nodes, back, ops])

    # ================================================================ FORMULATION TAB
    def _build_form(self):
        box = ScrolledText(self.tab_form, bg=PANEL, fg=FG, insertbackground=FG, relief="flat",
                           font=("Courier New", 10), padx=18, pady=14, wrap="word", borderwidth=0)
        box.insert("1.0", FORMULATION)
        box.config(state="disabled")
        box.pack(fill="both", expand=True, padx=14, pady=14)

    # ================================================================ keyboard
    def _key(self, e):
        w = self.focus_get()
        if isinstance(w, (ttk.Spinbox, ttk.Entry, tk.Entry, tk.Text)):
            return
        tab = self.nb.index("current")
        if tab == 1 and not self.busy:
            self._ai_key(e)
        elif tab == 0 and self.game:
            self._play_key(e)

    def _play_key(self, e):
        b = self.pboard
        if e.keysym in ("Up", "Down", "Left", "Right"):
            b.move({"Up": -1, "Down": 1}.get(e.keysym, 0), {"Left": -1, "Right": 1}.get(e.keysym, 0))
            return
        if e.state & 0x4 and e.keysym.lower() in ("z", "y"):
            self.play_undo() if e.keysym.lower() == "z" else self.play_redo()
        elif e.char and e.char in "123456789":
            self.play_digit(int(e.char))
        elif e.keysym in ("0", "BackSpace", "Delete", "KP_0"):
            self.play_erase()
        elif e.keysym.lower() == "n":
            self.toggle_notes()
        elif e.keysym.lower() == "h":
            self.play_hint()


if __name__ == "__main__":
    App().mainloop()