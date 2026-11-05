from .backtracking import solve as backtracking
from .csp import solve_fc, solve_fc_mrv, solve_ac3_mrv
from .local_search import solve_sa

SOLVERS = { "Plain backtracking": backtracking, "Forward checking": solve_fc, "FC + MRV": solve_fc_mrv, "AC-3 + MRV (MAC)": solve_ac3_mrv, "Simulated annealing": solve_sa, }