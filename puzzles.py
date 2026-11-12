"""puzzles.py - sample puzzles and a random puzzle generator (unique solutions)."""
import random
from algorithms import PEERS, FULL, POP, bits

PUZZLES = {
    "Easy":                 "003020600900305001001806400008102900700000008006708200002609500800203009005010300",
    "Medium":               "000000907000420180000705026100904000050000040000507009920108000034059000507000000",
    "Hard (Norvig)":        "400000805030000000000700000020000060000080400000010000000603070500200000104000000",
    "Very hard":            "000000010400000000020000000000050407008000300001090000300400200050100000000806000",
    "World's hardest (Inkala)": "800000000003600000070090200050007000000045700000100030001000068008500010090000400",
}


def parse(text):
    s = [c for c in text if c.isdigit() or c in ".-_"]
    if len(s) != 81:
        raise ValueError("A Sudoku needs exactly 81 cells (found %d)." % len(s))
    return [int(c) if c.isdigit() else 0 for c in s]


def to_string(grid):
    return "".join(str(v) if v else "." for v in grid)


def count_solutions(grid, limit=2):
    """Fast MRV backtracking counter used for uniqueness checks."""
    g = list(grid)
    n = [0]

    def mask(i):
        m = 0
        for p in PEERS[i]:
            if g[p]:
                m |= 1 << (g[p] - 1)
        return FULL & ~m

    def rec():
        best, bm, bc = -1, 0, 10
        for i in range(81):
            if g[i] == 0:
                m = mask(i)
                c = POP[m]
                if c < bc:
                    best, bm, bc = i, m, c
                    if c == 0:
                        return
        if best < 0:
            n[0] += 1
            return
        for v in bits(bm):
            g[best] = v
            rec()
            if n[0] >= limit:
                return
        g[best] = 0

    rec()
    return n[0]


def _random_full(rng):
    g = [0] * 81

    def rec():
        best, bm, bc = -1, 0, 10
        for i in range(81):
            if g[i] == 0:
                m = FULL
                for p in PEERS[i]:
                    if g[p]:
                        m &= ~(1 << (g[p] - 1))
                c = POP[m]
                if c < bc:
                    best, bm, bc = i, m, c
        if best < 0:
            return True
        vals = list(bits(bm))
        rng.shuffle(vals)
        for v in vals:
            g[best] = v
            if rec():
                return True
        g[best] = 0
        return False

    rec()
    return g


CLUES = {"Easy": 40, "Medium": 32, "Hard": 27, "Expert": 24}


def generate(level="Medium", seed=None):
    """Random puzzle with a unique solution; fewer clues = harder."""
    rng = random.Random(seed)
    target = CLUES.get(level, 32)
    g = _random_full(rng)
    cells = list(range(81))
    rng.shuffle(cells)
    clues = 81
    for i in cells:
        if clues <= target:
            break
        keep = g[i]
        g[i] = 0
        if count_solutions(g, 2) != 1:
            g[i] = keep
        else:
            clues -= 1
    return g
