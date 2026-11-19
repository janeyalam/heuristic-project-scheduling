"""Phase 2: Breadth-First Search over the scheduling state space.

BFS takes states in the order they were added (first in, first out) and never
adds a state that has already been seen. It reports the makespan and the number
of transitions of the schedule it finds. It does not claim the makespan is
optimal: BFS minimises transitions, not days.

Python standard library only. This module never opens files.
"""
from scheduling import search_common as _common


def _fifo_priority(*_):
    """Same priority for every state, so the insertion order alone decides."""
    return ()


def bfs_search(tasks, capacity, timeout_seconds=None, max_expansions=None):
    """Run BFS and return the shared Search_Result dict (algorithm 'BFS').

    tasks           dict of task_id -> Task (from data_validation.load_tasks)
    capacity        number of workers available
    timeout_seconds stop with status 'timeout' after this many seconds (None = no limit)

    'makespan' is the length of the schedule found and 'transitions' is the
    number of actions on the path. The makespan is not guaranteed to be minimal.
    """
    return _common.best_first_search('BFS', tasks, capacity, priority=_fifo_priority,
                                     reopen=False, timeout_seconds=timeout_seconds, max_expansions=max_expansions)
