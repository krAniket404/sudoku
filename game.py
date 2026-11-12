"""
game.py - rules and state of the *human* Sudoku game (no GUI code here).
Features: pencil notes, undo/redo, mistake counter, logical hints, auto-notes, solution check.
"""
import time
from dataclasses import dataclass

import algorithms as A
import puzzles as P


@dataclass
class Hint:
    idx: int
    value: int
    kind: str
    text: str


def name(i):
    return f"R{i // 9 + 1}C{i % 9 + 1}"


def unit_name(u):
    return ("row %d" % (u + 1)) if u < 9 else ("column %d" % (u - 8)) if u < 18 else ("box %d" % (u - 17))


class Game:
    def __init__(self, puzzle, level="Custom"):
        self.puzzle = list(puzzle)
        if not A.givens_consistent(self.puzzle):
            raise ValueError("The givens already break a Sudoku rule.")
        if P.count_solutions(self.puzzle, 2) != 1:
            raise ValueError("This puzzle must have exactly one solution to be playable.")
        self.solution = A.run_solver("cp", self.puzzle, timeout=10).solution
        self.level = level
        self.cells = list(self.puzzle)
        self.notes = [set() for _ in range(81)]
        self.undo_stack, self.redo_stack = [], []
        self.mistakes = 0
        self.hints = 0
        self.finished = False
        self.won = False
        self._acc = 0.0
        self._t0 = None

    # ---------------------------------------------------------------- timer
    def start(self):
        if self._t0 is None and not self.finished:
            self._t0 = time.time()

    def pause(self):
        if self._t0 is not None:
            self._acc += time.time() - self._t0
            self._t0 = None

    @property
    def elapsed(self):
        return self._acc + (time.time() - self._t0 if self._t0 is not None else 0.0)

    # ---------------------------------------------------------------- helpers
    def is_given(self, i):
        return self.puzzle[i] != 0

    def count(self, d):
        return sum(1 for v in self.cells if v == d)

    def filled(self):
        return sum(1 for v in self.cells if v)

    def wrong_cells(self):
        return {i for i, v in enumerate(self.cells) if v and v != self.solution[i]}

    def _snapshot(self, changes, j):
        if j not in changes:
            changes[j] = (self.cells[j], frozenset(self.notes[j]))

    def _push(self, changes):
        if changes:
            self.undo_stack.append(changes)
            self.redo_stack.clear()

    def _check_done(self):
        if self.cells == self.solution:
            self.finished = self.won = True
            self.pause()

    # ---------------------------------------------------------------- moves
    def place(self, i, v):
        """Put digit v (0 = clear) in cell i. Returns True if something changed."""
        if self.finished or self.is_given(i) or self.cells[i] == v:
            return False
        ch = {}
        self._snapshot(ch, i)
        self.cells[i] = v
        self.notes[i] = set()
        if v:
            if v != self.solution[i]:
                self.mistakes += 1
            for p in A.PEERS[i]:                      # auto-remove matching pencil marks
                if v in self.notes[p]:
                    self._snapshot(ch, p)
                    self.notes[p].discard(v)
        self._push(ch)
        self._check_done()
        return True

    def toggle_note(self, i, v):
        if self.finished or self.is_given(i) or self.cells[i]:
            return False
        ch = {}
        self._snapshot(ch, i)
        self.notes[i] ^= {v}
        self._push(ch)
        return True

    def erase(self, i):
        if self.finished or self.is_given(i):
            return False
        if self.cells[i]:
            return self.place(i, 0)
        if self.notes[i]:
            ch = {}
            self._snapshot(ch, i)
            self.notes[i] = set()
            self._push(ch)
            return True
        return False

    def auto_notes(self):
        if self.finished:
            return
        ch = {}
        for i in range(81):
            if not self.cells[i]:
                new = set(A.bits(A.cand_mask(self.cells, i)))
                if new != self.notes[i]:
                    self._snapshot(ch, i)
                    self.notes[i] = new
        self._push(ch)

    def _swap_state(self, changes):
        inverse = {}
        for j, (val, notes) in changes.items():
            inverse[j] = (self.cells[j], frozenset(self.notes[j]))
            self.cells[j], self.notes[j] = val, set(notes)
        return inverse

    def undo(self):
        if self.finished or not self.undo_stack:
            return False
        self.redo_stack.append(self._swap_state(self.undo_stack.pop()))
        return True

    def redo(self):
        if self.finished or not self.redo_stack:
            return False
        self.undo_stack.append(self._swap_state(self.redo_stack.pop()))
        self._check_done()
        return True

    def reveal(self):
        self.cells = list(self.solution)
        self.notes = [set() for _ in range(81)]
        self.finished, self.won = True, False
        self.pause()

    # ---------------------------------------------------------------- hints
    def hint(self):
        wrong = sorted(self.wrong_cells())
        if wrong:
            i = wrong[0]
            return Hint(i, self.solution[i], "mistake",
                        f"{name(i)} holds a wrong digit. Press the hint button again to correct it.")
        masks = {i: A.cand_mask(self.cells, i) for i in range(81) if not self.cells[i]}
        for i, m in masks.items():                    # naked single
            if A.POP[m] == 1:
                v = A.BIT2VAL[m]
                return Hint(i, v, "naked",
                            f"Naked single: {name(i)} can only be {v} - every other digit already appears "
                            f"in its row, column or box.")
        for u, cells in enumerate(A.UNITS):           # hidden single
            for d in range(1, 10):
                if any(self.cells[c] == d for c in cells):
                    continue
                spots = [c for c in cells if c in masks and masks[c] >> (d - 1) & 1]
                if len(spots) == 1:
                    return Hint(spots[0], d, "hidden",
                                f"Hidden single: in {unit_name(u)}, the digit {d} fits in only one cell: "
                                f"{name(spots[0])}.")
        if masks:
            i = min(masks, key=lambda k: A.POP[masks[k]])
            cand = "".join(map(str, A.bits(masks[i])))
            return Hint(i, self.solution[i], "reveal",
                        f"No simple single exists. {name(i)} is the tightest cell (candidates {cand}); "
                        f"the hint reveals its value.")
        return None

    def apply_hint(self, h):
        self.hints += 1
        self.place(h.idx, h.value)
