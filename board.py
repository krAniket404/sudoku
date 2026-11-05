# board.py
import time
from dataclasses import dataclass

Board = list[list[int]]   # needs Python 3.10+

class SearchLimit(Exception):
    # raised inside a solver when node_limit or timeout_s is hit
    pass

@dataclass
class Stats:
    method: str = ''
    status: str = ''        # solved | unsolvable | invalid | limit
    nodes: int = 0          # value assignments made by the search
    decisions: int = 0      # nodes where the cell had more than one candidate
    backtracks: int = 0     # assignments undone
    revisions: int = 0      # AC-3 revise() calls that removed a value
    iterations: int = 0     # local search moves
    restarts: int = 0       # local search restarts
    time_s: float = 0.0
    extra: str = ''         # free text for the report

    @property
    def solved(self) -> bool:
        return self.status == 'solved'

def check_limits(stats, t0, node_limit, timeout_s):
    # call once per node; the clock is read every 256 nodes to stay cheap
    if node_limit is not None and stats.nodes > node_limit:
        raise SearchLimit
    if timeout_s is not None and stats.nodes % 256 == 0:
        if time.perf_counter() - t0 > timeout_s:
            raise SearchLimit

def parse(s: str) -> Board:
    # 81-char string ('.' or '0' = empty) -> Board
    s = s.strip().replace('.', '0')
    if len(s) != 81 or not s.isdigit():
        raise ValueError('puzzle must be 81 characters: digits 0-9 or .')
    return [[int(s[r * 9 + c]) for c in range(9)] for r in range(9)]

def to_string(b: Board) -> str:
    return ''.join(str(v) for row in b for v in row)

def copy(b: Board) -> Board:
    return [row[:] for row in b]

def box_index(r: int, c: int) -> int:
    return (r // 3) * 3 + c // 3

# Precomputed once: PEERS[(r, c)] -> set of the 20 peer cells
PEERS = {}
for r in range(9):
    for c in range(9):
        p = set()
        for i in range(9):
            p.add((r, i))
            p.add((i, c))
        br, bc = 3 * (r // 3), 3 * (c // 3)
        for i in range(br, br + 3):
            for j in range(bc, bc + 3):
                p.add((i, j))
        p.discard((r, c))
        PEERS[(r, c)] = p

def is_valid_placement(b: Board, r: int, c: int, v: int) -> bool:
    return all(b[pr][pc] != v for pr, pc in PEERS[(r, c)])

def is_valid_board(b: Board) -> bool:
    # no duplicates among filled cells (empties allowed)
    for r in range(9):
        for c in range(9):
            v = b[r][c]
            if v and any(b[pr][pc] == v for pr, pc in PEERS[(r, c)]):
                return False
    return True

def is_complete(b: Board) -> bool:
    return all(v != 0 for row in b for v in row) and is_valid_board(b)