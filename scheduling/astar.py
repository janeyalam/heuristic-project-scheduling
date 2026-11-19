"""Phase 2: A* search.

A* explores the state with the smallest f = g + h first, where g is the days
spent so far and h is a heuristic estimate of the days still needed. Ties are
broken by the smaller h, then by the order states were added to the frontier.
A state found again by a strictly cheaper route is re-opened; a route that is
equal or more expensive is dropped. With an admissible heuristic the makespan
is optimal. The default heuristic is zero_heuristic, which makes A* act like UCS.
"""
from scheduling.heuristics import zero_heuristic
from scheduling.search_common import best_first_search


def astar_search(tasks, capacity, heuristic=None, timeout_seconds=None, max_expansions=None):
    """Run A* and return the standard result dict (algorithm 'A*').

    heuristic is a function h(state, tasks, capacity) -> int; None means
    zero_heuristic. Example (baseline tasks, 2 workers): makespan 11.
    """
    if heuristic is None:
        heuristic = zero_heuristic

    def priority(state, g, cache):
        h = heuristic(state, tasks, capacity)
        return (g + h, h)

    return best_first_search('A*', tasks, capacity, priority=priority, reopen=True,
                             timeout_seconds=timeout_seconds, max_expansions=max_expansions)
