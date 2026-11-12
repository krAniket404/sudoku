"""
algorithms.py  -  AI algorithms for solving Sudoku
==================================================
Every algorithm takes a puzzle (list of 81 ints, 0 = empty) and a Ctx object
that counts explored states, enforces the time limit and records animation frames.

Families implemented
  * Uninformed search ........ DFS (naive backtracking), BFS
  * Informed search .......... Greedy Best-First, A*
  * CSP techniques ........... Backtracking+MRV, Forward Checking,
                               AC-3 / MAC (arc consistency), Constraint Propagation
  * Local / stochastic ....... Hill Climbing (random restart), Simulated Annealing,
                               Genetic Algorithm
"""
import heapq
import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from itertools import combinations

# ----------------------------------------------------------------------------
# Static structure of the Sudoku constraint graph
# ----------------------------------------------------------------------------
FULL = 0x1FF                                   # domain {1..9} as a 9-bit mask
BIT2VAL = {1 << k: k + 1 for k in range(9)}
POP = [bin(i).count("1") for i in range(512)]  # popcount table

ROW_CELLS = [[r * 9 + c for c in range(9)] for r in range(9)]
COL_CELLS = [[r * 9 + c for r in range(9)] for c in range(9)]
BOX_CELLS = [[(br * 3 + r) * 9 + bc * 3 + c for r in range(3) for c in range(3)]
             for br in range(3) for bc in range(3)]
UNITS = ROW_CELLS + COL_CELLS + BOX_CELLS
UNITS_OF = [[u for u in UNITS if i in u] for i in range(81)]
PEERS = [sorted({c for u in UNITS_OF[i] for c in u} - {i}) for i in range(81)]


def bits(mask):
    """Iterate over the values (1..9) contained in a domain bit-mask."""
    while mask:
        b = mask & -mask
        yield BIT2VAL[b]
        mask ^= b


def cand_mask(grid, i):
    """Values still legal for cell i given the current grid."""
    m = 0
    for p in PEERS[i]:
        v = grid[p]
        if v:
            m |= 1 << (v - 1)
    return FULL & ~m


def givens_consistent(grid):
    for u in UNITS:
        vals = [grid[c] for c in u if grid[c]]
        if len(vals) != len(set(vals)):
            return False
    return True


def is_solved(grid):
    return all(grid) and givens_consistent(grid)


# ----------------------------------------------------------------------------
# Context: counters, time limit, animation recording
# ----------------------------------------------------------------------------
class SolverTimeout(Exception):
    pass


class Ctx:
    def __init__(self, timeout=10.0, stop=None, record=False, cap=3000):
        self.t0 = time.perf_counter()
        self.timeout = timeout
        self.stop = stop
        self.record = record
        self.cap = cap
        self.nodes = 0          # explored states / iterations / generations
        self.backtracks = 0     # dead ends (or rejected moves for local search)
        self.ops = 0            # algorithm specific: arc revisions, eliminations, restarts
        self.frames = []
        self._count = 0
        self._stride = 1

    def tick(self):
        self.nodes += 1
        if (self.nodes & 63) == 0:
            self.check()

    def check(self):
        if self.stop is not None and self.stop.is_set():
            raise SolverTimeout("stopped")
        if time.perf_counter() - self.t0 > self.timeout:
            raise SolverTimeout("timeout")

    def frame(self, cells):
        """Record a board snapshot (adaptive down-sampling keeps memory bounded)."""
        if not self.record:
            return
        self._count += 1
        if self._count % self._stride:
            return
        self.frames.append(bytes(cells))
        if len(self.frames) >= self.cap:
            self.frames = self.frames[::2]
            self._stride *= 2


# ----------------------------------------------------------------------------
# 1. DFS  -  naive backtracking (first empty cell, values 1..9)
# ----------------------------------------------------------------------------
def alg_dfs(grid, ctx):
    g = list(grid)

    def rec():
        ctx.tick()
        try:
            i = g.index(0)
        except ValueError:
            return True
        for v in bits(cand_mask(g, i)):
            g[i] = v
            ctx.frame(g)
            if rec():
                return True
        g[i] = 0
        ctx.backtracks += 1
        ctx.frame(g)
        return False

    return g if rec() else None


# ----------------------------------------------------------------------------
# 2. BFS  -  level-by-level expansion of partial assignments
# ----------------------------------------------------------------------------
def alg_bfs(grid, ctx, max_frontier=400_000):
    q = deque([tuple(grid)])
    while q:
        s = q.popleft()
        ctx.tick()
        try:
            i = s.index(0)
        except ValueError:
            return list(s)
        ctx.frame(s)
        m = cand_mask(s, i)
        if m == 0:
            ctx.backtracks += 1
            continue
        for v in bits(m):
            q.append(s[:i] + (v,) + s[i + 1:])
        if len(q) > max_frontier:
            raise SolverTimeout("memory limit")
    return None


# ----------------------------------------------------------------------------
# 3. Backtracking + MRV (Minimum Remaining Values) heuristic
# ----------------------------------------------------------------------------
def alg_mrv(grid, ctx):
    g = list(grid)

    def rec():
        ctx.tick()
        best, bm, bc = -1, 0, 10
        for i in range(81):
            if g[i] == 0:
                m = cand_mask(g, i)
                c = POP[m]
                if c < bc:
                    best, bm, bc = i, m, c
                    if c <= 1:
                        break
        if best < 0:
            return True
        for v in bits(bm):
            g[best] = v
            ctx.frame(g)
            if rec():
                return True
        g[best] = 0
        ctx.backtracks += 1
        ctx.frame(g)
        return False

    return g if rec() else None


# ----------------------------------------------------------------------------
# Domain helpers shared by FC / MAC / CP (bit-mask domains)
# ----------------------------------------------------------------------------
def _view(d):
    return [BIT2VAL.get(x, 0) for x in d]


def _solution_from(d):
    return [BIT2VAL[x] for x in d]


def _fc_assign(d, i, v):
    """Assign v to cell i and prune it from peers' domains (forward checking)."""
    nd = d[:]
    bit = 1 << (v - 1)
    nd[i] = bit
    for p in PEERS[i]:
        if nd[p] & bit:
            nd[p] &= ~bit
            if nd[p] == 0:
                return None
    return nd


# ----------------------------------------------------------------------------
# 4. Forward Checking + MRV
# ----------------------------------------------------------------------------
def alg_fc(grid, ctx):
    d = [FULL] * 81
    asg = 0
    for i, v in enumerate(grid):
        if v:
            d = _fc_assign(d, i, v)
            if d is None:
                return None
            asg |= 1 << i

    def rec(d, asg):
        ctx.tick()
        ctx.frame(_view(d) if ctx.record else None)
        best, bc = -1, 10
        for i in range(81):
            if not (asg >> i) & 1:
                c = POP[d[i]]
                if c < bc:
                    best, bc = i, c
        if best < 0:
            return d
        for v in bits(d[best]):
            nd = _fc_assign(d, best, v)
            if nd is not None:
                r = rec(nd, asg | (1 << best))
                if r:
                    return r
        ctx.backtracks += 1
        return None

    r = rec(d, asg)
    return _solution_from(r) if r else None


# ----------------------------------------------------------------------------
# 5. AC-3 + Backtracking (MAC = Maintaining Arc Consistency)
# ----------------------------------------------------------------------------
def _ac3(d, queue, ctx):
    """AC-3 for the binary constraints  X_i != X_j  on bit-mask domains."""
    while queue:
        xi, xj = queue.popleft()
        ctx.ops += 1
        dj = d[xj]
        di = d[xi]
        # a value of xi has no support in xj only if xj's domain is exactly that value
        if dj & (dj - 1) == 0 and di & dj:
            d[xi] = di & ~dj
            if d[xi] == 0:
                return False
            for xk in PEERS[xi]:
                if xk != xj:
                    queue.append((xk, xi))
    return True


def alg_mac(grid, ctx):
    d = [FULL] * 81
    for i, v in enumerate(grid):
        if v:
            d[i] = 1 << (v - 1)
    q = deque((i, p) for i in range(81) for p in PEERS[i])
    if not _ac3(d, q, ctx):
        return None

    def rec(d):
        ctx.tick()
        ctx.frame(_view(d) if ctx.record else None)
        best, bc = -1, 10
        for i in range(81):
            c = POP[d[i]]
            if 1 < c < bc:
                best, bc = i, c
        if best < 0:
            return d
        for v in bits(d[best]):
            nd = d[:]
            nd[best] = 1 << (v - 1)
            if _ac3(nd, deque((p, best) for p in PEERS[best]), ctx):
                r = rec(nd)
                if r:
                    return r
        ctx.backtracks += 1
        return None

    r = rec(d)
    return _solution_from(r) if r else None


# ----------------------------------------------------------------------------
# 6. Constraint Propagation (naked + hidden singles) + search
# ----------------------------------------------------------------------------
def alg_cp(grid, ctx):
    def assign(d, i, v):
        other = d[i] & ~(1 << (v - 1))
        for dv in bits(other):
            if not eliminate(d, i, dv):
                return False
        return True

    def eliminate(d, i, v):
        bit = 1 << (v - 1)
        if not d[i] & bit:
            return True
        ctx.ops += 1
        d[i] &= ~bit
        if d[i] == 0:
            return False
        if d[i] & (d[i] - 1) == 0:                       # naked single
            v2 = BIT2VAL[d[i]]
            for p in PEERS[i]:
                if not eliminate(d, p, v2):
                    return False
        for u in UNITS_OF[i]:                            # hidden single
            places = [c for c in u if d[c] & bit]
            if not places:
                return False
            if len(places) == 1 and not assign(d, places[0], v):
                return False
        return True

    d = [FULL] * 81
    for i, v in enumerate(grid):
        if v and not assign(d, i, v):
            return None

    def rec(d):
        ctx.tick()
        ctx.frame(_view(d) if ctx.record else None)
        best, bc = -1, 10
        for i in range(81):
            c = POP[d[i]]
            if 1 < c < bc:
                best, bc = i, c
        if best < 0:
            return d
        for v in bits(d[best]):
            nd = d[:]
            if assign(nd, best, v):
                r = rec(nd)
                if r:
                    return r
        ctx.backtracks += 1
        return None

    r = rec(d)
    return _solution_from(r) if r else None


# ----------------------------------------------------------------------------
# 7 & 8. Greedy Best-First and A*
#   state  = partial assignment; action = fill the MRV cell with a legal value
#   Greedy : h(n) = tightness = sum over empty cells of (|domain|-1)
#   A*     : f(n) = g(n) + h(n),  g = sum of branching costs (filling a cell that
#            has k legal digits costs k, forced moves cost 1), h = cells still empty
#            (admissible: every remaining cell costs at least 1). Ties -> tightness.
#   Dead-end states (a cell with an empty domain) are pruned on generation.
# ----------------------------------------------------------------------------
def _evaluate(s):
    empt = tight = 0
    best, bm, bc = -1, 0, 10
    for i in range(81):
        if s[i] == 0:
            m = cand_mask(s, i)
            c = POP[m]
            if c == 0:
                return None
            empt += 1
            tight += c - 1
            if c < bc:
                best, bm, bc = i, m, c
    return empt, tight, best, bm


def _best_first(grid, ctx, astar, max_heap=500_000):
    start = tuple(grid)
    ev = _evaluate(start)
    if ev is None:
        return None
    cnt = 0
    heap = [((0, 0, 0), cnt, start, 0, ev)]
    while heap:
        _, _, s, g, ev = heapq.heappop(heap)
        ctx.tick()
        ctx.frame(s)
        empt, tight, cell, mask = ev
        if empt == 0:
            return list(s)
        for v in bits(mask):
            ns = s[:cell] + (v,) + s[cell + 1:]
            nev = _evaluate(ns)
            if nev is None:
                ctx.backtracks += 1
                continue
            cnt += 1
            ng = g + (POP[mask] if astar else 1)   # A*: a guess among k digits costs k
            prio = (ng + nev[0], nev[1], cnt) if astar else (nev[1], nev[0], cnt)
            heapq.heappush(heap, (prio, cnt, ns, ng, nev))
        if len(heap) > max_heap:
            raise SolverTimeout("memory limit")
    return None


def alg_greedy(grid, ctx):
    return _best_first(grid, ctx, astar=False)


def alg_astar(grid, ctx):
    return _best_first(grid, ctx, astar=True)


# ----------------------------------------------------------------------------
# Local search representation: every 3x3 box always holds digits 1..9 exactly once
# (givens fixed). Cost = number of missing digits over all rows and columns.
# A move swaps two non-fixed cells inside one box.
# ----------------------------------------------------------------------------
def _init_boxes(grid, rnd):
    g = list(grid)
    free_by_box = []
    for b in range(9):
        cells = BOX_CELLS[b]
        present = {g[c] for c in cells if g[c]}
        missing = [v for v in range(1, 10) if v not in present]
        rnd.shuffle(missing)
        free = [c for c in cells if g[c] == 0]
        for c, v in zip(free, missing):
            g[c] = v
        free_by_box.append(free)
    return g, free_by_box


def _row_cost(g, r):
    return 9 - len(set(g[r * 9:r * 9 + 9]))


def _col_cost(g, c):
    return 9 - len(set(g[c::9]))


def _total_cost(g):
    return sum(_row_cost(g, k) + _col_cost(g, k) for k in range(9))


def _swap_delta(g, a, b):
    """Apply swap(a,b) in place and return the change in cost."""
    ra, ca = divmod(a, 9)
    rb, cb = divmod(b, 9)
    rows, cols = {ra, rb}, {ca, cb}
    before = sum(_row_cost(g, r) for r in rows) + sum(_col_cost(g, c) for c in cols)
    g[a], g[b] = g[b], g[a]
    after = sum(_row_cost(g, r) for r in rows) + sum(_col_cost(g, c) for c in cols)
    return after - before


# ----------------------------------------------------------------------------
# 9. Hill climbing (steepest descent in a random box, sideways moves, random restarts)
# ----------------------------------------------------------------------------
def alg_hill(grid, ctx):
    rnd = random.Random()
    while True:
        g, free = _init_boxes(grid, rnd)
        boxes = [f for f in free if len(f) >= 2]
        if not boxes:
            return g if _total_cost(g) == 0 else None
        cost = _total_cost(g)
        stall = 0
        while cost > 0 and stall < 300:
            ctx.tick()
            f = rnd.choice(boxes)
            best, bd = None, 99
            for a, b in combinations(f, 2):
                dlt = _swap_delta(g, a, b)
                g[a], g[b] = g[b], g[a]            # undo
                if dlt < bd or (dlt == bd and rnd.random() < 0.5):
                    best, bd = (a, b), dlt
            if bd < 0:
                g[best[0]], g[best[1]] = g[best[1]], g[best[0]]
                cost += bd
                stall = 0
            elif bd == 0:
                g[best[0]], g[best[1]] = g[best[1]], g[best[0]]
                stall += 1
            else:
                ctx.backtracks += 1
                stall += 1
            if ctx.nodes % 10 == 0:
                ctx.frame(g)
        if cost == 0:
            return g
        ctx.ops += 1                                # restart
        ctx.frame(g)


# ----------------------------------------------------------------------------
# 10. Simulated annealing (geometric cooling with reheating and restarts)
# ----------------------------------------------------------------------------
def alg_sa(grid, ctx):
    rnd = random.Random()
    T0, alpha, Tmin = 0.45, 0.99995, 0.05
    while True:
        g, free = _init_boxes(grid, rnd)
        boxes = [f for f in free if len(f) >= 2]
        if not boxes:
            return g if _total_cost(g) == 0 else None
        cost = _total_cost(g)
        for _cycle in range(4):
            T = T0
            while T > Tmin:
                if cost == 0:
                    return g
                ctx.tick()
                f = rnd.choice(boxes)
                a, b = rnd.sample(f, 2)
                dlt = _swap_delta(g, a, b)
                if dlt <= 0 or rnd.random() < math.exp(-dlt / T):
                    cost += dlt
                else:
                    g[a], g[b] = g[b], g[a]
                    ctx.backtracks += 1
                T *= alpha
                if ctx.nodes % 40 == 0:
                    ctx.frame(g)
        ctx.ops += 1                                # restart
        ctx.frame(g)


# ----------------------------------------------------------------------------
# 11. Genetic algorithm (box-wise crossover, swap mutation, elitism)
# ----------------------------------------------------------------------------
def alg_ga(grid, ctx, pop_size=120):
    rnd = random.Random()
    _, free = _init_boxes(grid, rnd)
    boxes = [(b, f) for b, f in enumerate(free) if len(f) >= 2]

    def new_ind():
        g, _ = _init_boxes(grid, rnd)
        return g

    def mutate(g):
        for _ in range(rnd.choice((1, 1, 2, 3))):
            if not boxes:
                return
            _, f = rnd.choice(boxes)
            a, b = rnd.sample(f, 2)
            g[a], g[b] = g[b], g[a]

    pop = [new_ind() for _ in range(pop_size)]
    best_seen, stagnant = 999, 0
    while True:
        ctx.tick()
        scored = sorted(((_total_cost(g), g) for g in pop), key=lambda t: t[0])
        ctx.ops += len(pop)
        if scored[0][0] == 0:
            return scored[0][1]
        if ctx.nodes % 4 == 0:
            ctx.frame(scored[0][1])
        if scored[0][0] < best_seen:
            best_seen, stagnant = scored[0][0], 0
        else:
            stagnant += 1
        elites = [g for _, g in scored[:pop_size // 10]]
        if stagnant > 120:                           # diversify
            pop = elites + [new_ind() for _ in range(pop_size - len(elites))]
            best_seen, stagnant = 999, 0
            ctx.backtracks += 1
            continue
        pool = [g for _, g in scored[:pop_size // 2]]
        nxt = [g[:] for g in elites]
        while len(nxt) < pop_size:
            p1, p2 = rnd.choice(pool), rnd.choice(pool)
            child = p1[:]
            for cells in BOX_CELLS:
                if rnd.random() < 0.5:
                    for c in cells:
                        child[c] = p2[c]
            if rnd.random() < 0.8:
                mutate(child)
            # memetic step: cheap local improvement (accept non-worsening swaps)
            for _ in range(12):
                if not boxes:
                    break
                _, f = rnd.choice(boxes)
                a, b = rnd.sample(f, 2)
                if _swap_delta(child, a, b) > 0:
                    child[a], child[b] = child[b], child[a]
            nxt.append(child)
        pop = nxt


# ----------------------------------------------------------------------------
# Registry + runner
# ----------------------------------------------------------------------------
ALGORITHMS = {
    "dfs":    dict(name="DFS (naive backtracking)", cat="Uninformed search", func=alg_dfs,
                   desc="Depth-first search: fills the first empty cell with each legal digit in turn and backtracks on dead ends. No heuristics."),
    "bfs":    dict(name="BFS", cat="Uninformed search", func=alg_bfs,
                   desc="Breadth-first search over partial assignments (queue). Complete but its frontier explodes, so it hits the memory limit on harder puzzles."),
    "mrv":    dict(name="Backtracking + MRV", cat="CSP", func=alg_mrv,
                   desc="Backtracking CSP search that always branches on the cell with the Minimum Remaining Values (fail-first heuristic)."),
    "fc":     dict(name="Forward Checking + MRV", cat="CSP", func=alg_fc,
                   desc="Each assignment immediately prunes the digit from the domains of the 20 peers; backtracks as soon as a domain becomes empty."),
    "mac":    dict(name="AC-3 + Backtracking (MAC)", cat="CSP", func=alg_mac,
                   desc="Maintains arc consistency: AC-3 runs on the binary 'not-equal' constraints before search and after every assignment."),
    "cp":     dict(name="Constraint Propagation + Search", cat="CSP", func=alg_cp,
                   desc="Naked-single and hidden-single inference (human-style rules) applied recursively, with MRV search only when stuck."),
    "greedy": dict(name="Greedy Best-First", cat="Informed search", func=alg_greedy,
                   desc="Priority queue ordered by h(n) = constraint tightness (sum of domain sizes minus one). Expands the most constrained state first."),
    "astar":  dict(name="A* Search", cat="Informed search", func=alg_astar,
                   desc="f(n) = g(n) + h(n): g = accumulated branching cost (a cell with k legal digits costs k), h = cells still empty (admissible). Prefers paths of forced moves."),
    "hill":   dict(name="Hill Climbing (restarts)", cat="Local search", func=alg_hill,
                   desc="Boxes are pre-filled with 1-9; swaps inside a box that reduce row/column conflicts are accepted, with sideways moves and random restarts."),
    "sa":     dict(name="Simulated Annealing", cat="Local search", func=alg_sa,
                   desc="Same swap neighbourhood as hill climbing but worse moves are accepted with probability exp(-dE/T); geometric cooling with restarts."),
    "ga":     dict(name="Genetic Algorithm", cat="Local search", func=alg_ga,
                   desc="Memetic GA: population of box-valid boards; box-wise crossover, swap mutation, local improvement, elitism and diversification. Fitness = conflicts."),
}


@dataclass
class Result:
    key: str
    name: str
    solved: bool
    solution: list
    seconds: float
    nodes: int
    backtracks: int
    ops: int
    status: str
    frames: list = field(default_factory=list)


def run_solver(key, grid, timeout=10.0, stop=None, record=False):
    meta = ALGORITHMS[key]
    ctx = Ctx(timeout, stop, record)
    sol, status = None, "no solution"
    if not givens_consistent(grid):
        return Result(key, meta["name"], False, None, 0.0, 0, 0, 0, "invalid puzzle")
    t0 = time.perf_counter()
    ctx.t0 = t0
    try:
        sol = meta["func"](list(grid), ctx)
        if sol is not None:
            if is_solved(sol):
                status = "solved"
            else:
                sol, status = None, "invalid result"
    except SolverTimeout as e:
        status = str(e)
    except RecursionError:
        status = "recursion limit"
    secs = time.perf_counter() - t0
    if record and sol:
        ctx.frames.append(bytes(sol))
    return Result(key, meta["name"], sol is not None, sol, secs, ctx.nodes,
                  ctx.backtracks, ctx.ops, status, ctx.frames)
