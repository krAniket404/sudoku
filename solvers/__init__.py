from .backtracking import solve as backtracking
from .csp import (solve_fc, solve_fc_mrv, solve_fc_mrv_lcv,
                  solve_ac3_fc_mrv, solve_mac)
from .local_search import solve_hc, solve_sa

SOLVERS = {
    'Plain backtracking': backtracking,
    'Forward checking': solve_fc,
    'FC + MRV + degree': solve_fc_mrv,
    'FC + MRV + LCV': solve_fc_mrv_lcv,
    'AC-3 preprocessing + FC + MRV': solve_ac3_fc_mrv,
    'MAC (AC-3 maintained) + MRV': solve_mac,
    'Hill climbing + restarts': solve_hc,
    'Simulated annealing': solve_sa,
}

# local search is incomplete: it can never prove a puzzle unsolvable
INCOMPLETE = {'Hill climbing + restarts', 'Simulated annealing'}