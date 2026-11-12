# Sudoku

A Sudoku game you can play yourself, and also a place where you can watch a computer solve it using different AI methods.

Sudoku is a good example of a problem that AI can solve, so we built a game around it and compared how well different AI algorithms do.

---

## What you need

- Python 3.8 or newer
- Nothing else. There is nothing to install with pip.

The window is built with `tkinter`, which comes with Python on Windows and Mac. On Linux you may need to install it once:

```
sudo apt install python3-tk
```

---

## How to run it

Put all the files in the same folder, open a terminal in that folder, and type:

```
python app.py
```

(On some computers it is `python3 app.py`.)

---

## The files

| File | What it does |
|---|---|
| `app.py` | The window. Run this one. |
| `game.py` | The rules of the game you play: notes, undo, hints, mistakes. |
| `algorithms.py` | All the AI algorithms that solve Sudoku. |
| `puzzles.py` | Some ready-made puzzles, and a maker for new random ones. |
| `benchmark.py` | Optional. Tests every algorithm on every puzzle in the terminal. |

Keep all the files together. `app.py` needs the other three to work.

---

## What is in the app

There are four pages. You pick them from the menu on the left.

### 1. Play

This is where you solve the Sudoku yourself.

- Click a cell, then type a number from 1 to 9, or click the number buttons under the board.
- The small text under each number button tells you how many of that number are still left to place.
- Turn on **Notes** to write small pencil marks instead of real numbers.
- **Undo** and **Redo** take back or bring back your moves.
- **Hint** shows you a cell you can fill in and explains why. Press it again to fill the cell in.
- **Fill in notes** writes all the possible numbers into every empty cell for you.
- **Check** marks any wrong cells in red.
- You can also choose a difficulty (Easy, Medium, Hard, Expert) and start a new game, open a sample puzzle, or type in your own.
- When you finish, the app tells you your time, your mistakes, and how fast the computer solved the same puzzle.

Keyboard shortcuts: `1-9` to write a number, `Backspace` to erase, arrow keys to move, `N` for notes, `H` for a hint, `Ctrl+Z` to undo and `Ctrl+Y` to redo.

### 2. AI Solver

Here the computer does the solving, and you watch.

1. Pick a puzzle. You can use the one from the Play page, a sample, a random one, or type your own.
2. Pick a method (one of the AI algorithms).
3. Press **Solve it**.

The board shows the algorithm trying numbers and backing up when it gets stuck. You can change the speed, skip to the end, or stop it. When it finishes, you see how long it took and how many states it explored.

### 3. Benchmark

This page compares the algorithms with each other. Choose some puzzles and some methods, press **Run benchmark**, and you get a table and three charts (time, states explored, and how many puzzles were solved). You can save the results as a CSV file.

### 4. Formulation

The written explanation of the problem, for the project report: the start state, the goal, the actions, the rules, and the limits.

---

## The AI algorithms

There are 11 of them, in four groups.

**Simple search**
- **DFS (depth-first search):** Fill in the first empty cell, go deeper, and back up when stuck. No tricks.
- **BFS (breadth-first search):** Try all the options level by level. It uses a lot of memory and runs out quickly on harder puzzles.

**Smarter search**
- **Greedy best-first:** Always continues with the board that looks most promising.
- **A\*:** Like greedy, but it also counts how much work has been done so far.

**Constraint solving (the best group for Sudoku)**
- **Backtracking + MRV:** Always fill the cell that has the fewest possible numbers first.
- **Forward checking:** When a number is placed, remove it right away from all the cells that see it.
- **AC-3 (MAC):** Keeps cleaning up impossible numbers before and during the search.
- **Constraint propagation:** Uses the same two tricks a human uses (a cell with only one option, and a number that fits in only one place), then searches only if needed.

**Guessing methods**
- **Hill climbing:** Fill the board randomly, then keep swapping numbers to reduce mistakes.
- **Simulated annealing:** Like hill climbing, but sometimes accepts a worse move so it does not get stuck.
- **Genetic algorithm:** Keeps a group of random boards and "breeds" the best ones together.

---

## What we found

- The constraint methods (AC-3 and constraint propagation) are the fastest by far, and explore very few states.
- Plain DFS is fine on easy puzzles but can be very slow on tricky ones.
- BFS often runs out of memory.
- The guessing methods (hill climbing, annealing, genetic) work on easy puzzles but often fail on hard ones. They are also random, so the result changes each time.

Run `python benchmark.py` or use the Benchmark page to see the real numbers on your own computer.

---

## Limits

- It is written in plain Python, so the times depend on how fast your computer is.
- The guessing methods are random, so they can give different results each run.
- BFS, greedy and A\* keep many boards in memory, so we stop them at a limit.
- Only normal 9x9 Sudoku is supported.
- The Play page only accepts puzzles that have exactly one solution. Puzzles made by the app always do.

---

## Something not working?

- **"No module named tkinter"**: install it with `sudo apt install python3-tk` (Linux). On Windows or Mac, reinstall Python from python.org.
- **Window looks cut off**: make the window a bit bigger or maximize it. The board resizes by itself.
- **An algorithm says "timeout"**: it did not finish in the time limit. That is normal for the slower methods on hard puzzles. You can raise the limit on the AI Solver page.
