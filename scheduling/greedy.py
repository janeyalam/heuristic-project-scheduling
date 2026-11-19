"""Phase 2: Greedy best-first search.

Greedy explores the state with the smallest heuristic value h(n) first. It
ignores the cost so far (g). Ties go to the state added to the frontier first,
so runs are repeatable. A state seen once is never added again, so Greedy is
not guaranteed to find the shortest schedule.
"""
from scheduling.heuristics import longest_remaining
from scheduling.search_common import best_first_search


def greedy_search(tasks, capacity, heuristic=None, timeout_seconds=None, max_expansions=None):
    """Run Greedy best-first search and return the standard result dict.

    heuristic       function h(state, tasks, capacity) -> int. Default: longest_remaining.
    timeout_seconds stop with status 'timeout' after this many seconds (None = no limit).
    """
    h = longest_remaining if heuristic is None else heuristic

    def priority(state, g, cache):
        return (h(state, tasks, capacity),)

    return best_first_search('Greedy', tasks, capacity, priority=priority,
                             reopen=False, timeout_seconds=timeout_seconds, max_expansions=max_expansions)
