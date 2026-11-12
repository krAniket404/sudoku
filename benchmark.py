"""benchmark.py - command-line comparison of all algorithms (writes results.csv)."""
import csv
import sys
import algorithms as A
import puzzles as P

TIMEOUT = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0

rows = []
print(f"{'Puzzle':26}{'Algorithm':34}{'Status':14}{'Time(s)':>9}{'Nodes':>10}{'Backtr.':>10}{'Ops':>10}")
print("-" * 113)
for pname, ptxt in P.PUZZLES.items():
    grid = P.parse(ptxt)
    for key, meta in A.ALGORITHMS.items():
        r = A.run_solver(key, grid, timeout=TIMEOUT)
        rows.append([pname, meta["name"], r.status, round(r.seconds, 4), r.nodes, r.backtracks, r.ops])
        print(f"{pname:26}{meta['name']:34}{r.status:14}{r.seconds:9.3f}{r.nodes:10}{r.backtracks:10}{r.ops:10}")
    print()

with open("results.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["puzzle", "algorithm", "status", "seconds", "nodes", "backtracks", "ops"])
    w.writerows(rows)
print("Saved results.csv")
