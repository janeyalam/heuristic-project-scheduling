"""Phase 2: Uniform-Cost Search (UCS).

The frontier is ordered by g(n), the elapsed working days from the start.
A state found again by a strictly cheaper route is pushed again, and stale
frontier entries (g above the best known g) are discarded when popped. The
goal is tested when a state is popped, so the first goal popped has the
minimum makespan.

The shared loop in search_common.best_first_search does the work; UCS only
supplies the priority and turns re-opening on. No files are read here.
"""
from scheduling.search_common import best_first_search


def ucs_search(tasks, capacity, timeout_seconds=None, max_expansions=None):
    """Run UCS on the task dict and worker capacity. Return a Search_Result dict.

    Example: the baseline tasks.csv with capacity 2 gives status 'solved'
    and makespan 11.
    """
    return best_first_search(
        'UCS', tasks, capacity,
        priority=lambda state, g, cache: (g,),
        reopen=True,
        timeout_seconds=timeout_seconds,
        max_expansions=max_expansions,
    )
