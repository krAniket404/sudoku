# solvers/backtracking.py
import time
from board import (Board, Stats, SearchLimit, check_limits, copy,
                   is_valid_placement, is_valid_board)

def solve(board, node_limit=None, timeout_s=None, seed=None, **_):
    b = copy(board)
    stats = Stats(method='Plain backtracking')
    t0 = time.perf_counter()
    if not is_valid_board(b):
        stats.status = 'invalid'
        stats.time_s = time.perf_counter() - t0
        return None, stats
    empties = [(r, c) for r in range(9) for c in range(9) if b[r][c] == 0]

    def rec(i):
        if i == len(empties):
            return True
        r, c = empties[i]
        for v in range(1, 10):
            if is_valid_placement(b, r, c, v):
                b[r][c] = v
                stats.nodes += 1
                check_limits(stats, t0, node_limit, timeout_s)
                if rec(i + 1):
                    return True
                b[r][c] = 0
                stats.backtracks += 1
        return False

    try:
        ok = rec(0)
        stats.status = 'solved' if ok else 'unsolvable'
    except SearchLimit:
        ok = False
        stats.status = 'limit'
    stats.time_s = time.perf_counter() - t0
    return (b if ok else None), stats