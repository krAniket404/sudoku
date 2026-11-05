from dataclasses import dataclass
Board = list[list[int]] 
@dataclass
class Stats:
    method: str = ""
    solved: bool = False
    nodes: int = 0          # number of assignments tried
    backtracks: int = 0     # number of undone assignments
    time_s: float = 0.0
    extra: str = ""         # e.g. AC-3 revisions, restarts, iterations

def parse(s: str) -> Board:
    """81-char string ('.' or '0' = empty) -> Board."""
    s = s.strip().replace(".", "0")
    assert len(s) == 81
    return [[int(s[r * 9 + c]) for c in range(9)] for r in range(9)]

def to_string(b: Board) -> str:
    return "".join(str(v) for row in b for v in row)

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
    """No duplicates among filled cells (empties allowed)."""
    for r in range(9):
        for c in range(9):
            v = b[r][c]
            if v and any(b[pr][pc] == v for pr, pc in PEERS[(r, c)]):
                return False
    return True

def is_complete(b: Board) -> bool:
    return all(v != 0 for row in b for v in row) and is_valid_board(b)