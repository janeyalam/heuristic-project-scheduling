"""Phase 2: heuristic functions for Greedy and A*.

Every heuristic has the form h(state, tasks, capacity) -> int. It estimates
the working days still needed to finish the project from a state. All of them
return a whole number that is 0 or more, and 0 at a goal state. All of them
are admissible: they never guess more days than are really needed.

Some heuristics need "the longest chain of work that comes after a task".
That depends only on the tasks, so it is worked out once per task set and
remembered (see chain_after_for()).
"""
from scheduling.data_validation import longest_after

# Remembers the chain_after answer for the last task set we were asked about.
# We keep the tasks object itself so a recycled id() can never give a wrong match.
_chain_cache = {'tasks': None, 'chain_after': None}


def build_chain_after(tasks):
    """For every task, the longest chain of work that must come strictly after it.

    Example (baseline tasks): T01 -> 7 days (T02 4 + T05 2 + T06 1).
    A task nothing waits on (T06) has 0.
    """
    followers = {task_id: [] for task_id in tasks}
    for task_id, task in tasks.items():
        for dep in task.dependencies:
            followers[dep].append(task_id)
    memo = {}
    chain_after = {}
    for task_id in tasks:
        chain_after[task_id] = longest_after(task_id, tasks, followers, memo)
    return chain_after


def chain_after_for(tasks):
    """Give the chain_after table for this task set, building it only once per run."""
    if _chain_cache['tasks'] is not tasks:
        _chain_cache['chain_after'] = build_chain_after(tasks)
        _chain_cache['tasks'] = tasks
    return _chain_cache['chain_after']


def not_started_ids(state, tasks):
    """Task ids that are neither finished nor running."""
    busy = set(state.completed)
    for task_id, days_left in state.running:
        busy.add(task_id)
    result = []
    for task_id in tasks:
        if task_id not in busy:
            result.append(task_id)
    return result


def zero_heuristic(state, tasks, capacity):
    """Always 0. With A* this makes it behave like UCS.

    Example: zero_heuristic(any state, tasks, 2) -> 0
    """
    return 0


def longest_remaining(state, tasks, capacity):
    """Days left on the single longest unfinished task (the Greedy default).

    Looks at the remaining days of running tasks and the full duration of
    tasks not started yet. It is 0 when there is nothing left.
    Examples (baseline tasks):
        initial state                        -> 4 (T02 is the longest)
        T02 running with 1 day left, rest not started -> 3 (T03 and T04 take 3)
        goal state                           -> 0
    """
    longest = 0
    for task_id, days_left in state.running:
        if days_left > longest:
            longest = days_left
    for task_id in not_started_ids(state, tasks):
        if tasks[task_id].duration > longest:
            longest = tasks[task_id].duration
    return longest


def critical_path_remaining(state, tasks, capacity):
    """Longest chain of work still ahead, counting what is left of running tasks.

    For a running task it is the days left plus the chain after it. For a
    task not started it is the full duration plus the chain after it. The
    biggest of these is returned (0 when nothing is left).
    Example (baseline tasks): initial state -> 9 (T01 2 + T02 4 + T05 2 + T06 1)
    """
    chain_after = chain_after_for(tasks)
    best = 0
    for task_id, days_left in state.running:
        total = days_left + chain_after[task_id]
        if total > best:
            best = total
    for task_id in not_started_ids(state, tasks):
        total = tasks[task_id].duration + chain_after[task_id]
        if total > best:
            best = total
    return best


def workload_remaining(state, tasks, capacity):
    """Worker-days still to do, divided by the workers we have, rounded up.

    Example: 15 worker-days of work left and 2 workers -> 8 (baseline start).
    """
    work = 0
    for task_id, days_left in state.running:
        work += days_left * tasks[task_id].workers_required
    for task_id in not_started_ids(state, tasks):
        work += tasks[task_id].duration * tasks[task_id].workers_required
    # Ceiling division with whole numbers only.
    return (work + capacity - 1) // capacity


def combined_heuristic(state, tasks, capacity):
    """The bigger of critical_path_remaining and workload_remaining.

    Both are admissible, so their maximum is admissible too.
    """
    path = critical_path_remaining(state, tasks, capacity)
    load = workload_remaining(state, tasks, capacity)
    if load > path:
        return load
    return path
