import time
from board import Board, Stats, copy, is_valid_placement, is_valid_board
def solve(board: Board, node_limit: int = 5_000_000, **_):
    b = copy(board)
    stats = Stats(method="Plain backtracking")
    t0 = time.perf_counter()
    if not is_valid_board(b):
        stats.time_s = time.perf_counter() - t0
        return None, stats
    empties = [(r, c) for r in range(9) for c in range(9) if b[r][c] == 0]
    def rec(i: int) -> bool:
        if i == len(empties):
            return True
        r, c = empties[i]
        for v in range(1, 10):
            if is_valid_placement(b, r, c, v):
                b[r][c] = v
                stats.nodes += 1
                if stats.nodes > node_limit:
                    b[r][c] = 0
                    return False
                if rec(i + 1):
                    return True
                b[r][c] = 0
                stats.backtracks += 1
        return False
    ok = rec(0)
    stats.solved = ok
    stats.time_s = time.perf_counter() - t0
    return (b if ok else None), stats