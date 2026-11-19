"""Validate the exact four-column CSV described in the Phase 1 requirements.

Usage:
    python -m scheduling.data_validation data/tasks.csv --workers 2

Python standard library only. Data is fictional; no workplace data is needed.
"""
import argparse
import csv
import math
import os
from dataclasses import dataclass

REQUIRED_COLUMNS = ('task_id', 'duration', 'depends_on', 'workers_required')


class DataValidationError(ValueError):
    """The error we raise when the task file breaks a rule.

    Example: a task that depends on a task that is not in the file.
    """


# Frozen means a Task cannot be changed after it is loaded (tasks should not change).
@dataclass(frozen=True)
class Task:
    """One row of tasks.csv, stored as a Python object.

    Example: the row  T02,4,T01,1  becomes
    Task(task_id='T02', duration=4, dependencies=('T01',), workers_required=1)
    """
    task_id: str
    duration: int
    dependencies: tuple
    workers_required: int


def is_valid_task_id(text):
    """True when the text is exactly 'T' plus two digits 0-9.

    Examples:
        is_valid_task_id('T01')  -> True
        is_valid_task_id('T1')   -> False (needs two digits)
        is_valid_task_id('T001') -> False (too many digits)
        is_valid_task_id('t01')  -> False (capital T only)
        is_valid_task_id('T0a')  -> False (digits only)
    """
    if type(text) is not str or len(text) != 3:
        return False
    if text[0] != 'T':
        return False
    # Only plain 0-9 count as digits.
    if text[1] not in '0123456789' or text[2] not in '0123456789':
        return False
    return True


def positive_int(raw, label, line):
    """Turn a CSV cell into a whole number that is 1 or more.

    Examples:
        positive_int('4', 'duration', 3)    -> 4
        positive_int(' 2 ', 'duration', 3)  -> 2   (spaces are ignored)
        positive_int('0', 'duration', 3)    -> error (must be at least 1)
        positive_int('2.5', 'duration', 3)  -> error (not a whole number)
        positive_int('-1', 'duration', 3)   -> error (negative)
    'label' and 'line' are only used to build a helpful error message.
    """
    value = str(raw).strip()
    # Only plain 0-9 count as digits. An empty string is not a number.
    valid = len(value) > 0
    for ch in value:
        if ch not in '0123456789':
            valid = False
    if not valid or int(value) < 1:
        raise DataValidationError(f'Line {line}: {label} must be a positive integer; got "{raw}".')
    return int(value)


def parse_dependencies(raw, line):
    """Read the depends_on cell and return the task IDs it lists.

    Examples:
        parse_dependencies('None', 5)           -> ()
        parse_dependencies('', 5)               -> ()   (empty means no prerequisites)
        parse_dependencies('T01', 5)            -> ('T01',)
        parse_dependencies('T02, T03, T04', 5)  -> ('T02', 'T03', 'T04')
        parse_dependencies('T02|T03', 5)        -> ('T02', 'T03')   (| also works)
        parse_dependencies('T02, T02', 5)       -> error (listed twice)
        parse_dependencies('task2', 5)          -> error (not a valid ID like T02)
    """
    text = str(raw or '').strip()
    if text == '' or text.lower() == 'none':
        return ()
    # Also accept | for interoperability with the team's earlier prototype.
    pieces = text.replace('|', ',').split(',')
    parts = []
    for piece in pieces:
        parts.append(piece.strip())
    for part in parts:
        if not is_valid_task_id(part):
            raise DataValidationError(f'Line {line}: invalid dependency list "{text}".')
    if len(parts) != len(set(parts)):
        raise DataValidationError(f'Line {line}: duplicated prerequisite in "{text}".')
    return tuple(parts)


def check_for_cycle(node, tasks, color, path):
    """Walk down from one task through its prerequisites and raise if we go in a circle.

    This function calls itself, once for each prerequisite.
    color 1 = "on the path I am walking now", color 2 = "fully checked, fine".
    'path' is the list of tasks on the current walk (used to print the cycle).
    If we reach a task that is already color 1, we walked in a circle.
    Example: T02 needs T03 and T03 needs T02. Walking T02 -> T03 -> T02
    hits T02 again while it is still color 1, so we report the cycle.
    """
    if color.get(node) == 2:
        return
    if color.get(node) == 1:
        cycle = path[path.index(node):] + [node]
        raise DataValidationError('Dependency cycle: ' + ' -> '.join(cycle))
    color[node] = 1
    path.append(node)
    for dep in tasks[node].dependencies:
        check_for_cycle(dep, tasks, color, path)
    path.pop()
    color[node] = 2


def validate_tasks(tasks, worker_capacity):
    """Check that the whole set of tasks makes sense. Returns nothing if all is fine.

    It stops with an error if it finds any of these:
      - worker_capacity is not a whole number of 1 or more
      - there are no tasks
      - a task ID, duration or workers_required is bad
      - a task needs more workers than we have
        (example: T05 needs 3 workers but capacity is 2)
      - a task depends on itself, or on a task that does not exist
        (example: T02 depends on T09 and there is no T09)
      - tasks depend on each other in a circle
        (example: T02 -> T03 -> T02, so neither could ever start)
    """
    if type(worker_capacity) is not int or worker_capacity < 1:
        raise DataValidationError('Worker capacity must be a positive integer.')
    if not tasks:
        raise DataValidationError('Project cannot be empty.')
    for task_id, task in tasks.items():
        if not is_valid_task_id(task_id) or task_id != task.task_id:
            raise DataValidationError(f'Invalid or mismatched task ID "{task_id}".')
        if type(task.duration) is not int or task.duration < 1:
            raise DataValidationError(f'{task_id}: duration must be positive.')
        if type(task.workers_required) is not int or task.workers_required < 1:
            raise DataValidationError(f'{task_id}: workers_required must be positive.')
        if task.workers_required > worker_capacity:
            raise DataValidationError(f'{task_id}: needs {task.workers_required} workers, capacity is {worker_capacity}.')
        if len(task.dependencies) != len(set(task.dependencies)):
            raise DataValidationError(f'{task_id}: repeated dependencies.')
        for dep in task.dependencies:
            if dep == task_id:
                raise DataValidationError(f'{task_id}: self-dependency.')
            if dep not in tasks:
                raise DataValidationError(f'{task_id}: missing dependency {dep}.')

    # Circle check: start a walk from every task.
    color = {}
    path = []
    for task_id in tasks:
        check_for_cycle(task_id, tasks, color, path)


def load_tasks(path, worker_capacity=2):
    """Read tasks.csv, check every row, and return the tasks keyed by ID.

    Example:
        tasks = load_tasks('tasks.csv', 2)
        tasks['T02'].duration      -> 4
        tasks['T05'].dependencies  -> ('T02', 'T03', 'T04')

    It stops with an error if:
      - the file is missing
      - the header is not exactly task_id,duration,depends_on,workers_required
      - a row has the wrong number of cells (often a missing quote around
        a list like "T02, T03, T04")
      - a task ID is bad or used twice
    After every row is read, validate_tasks runs the checks on the full set.
    """
    filename = str(path)
    if not os.path.isfile(filename):
        raise DataValidationError(f'Dataset not found: {filename}')
    tasks = {}
    with open(filename, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or tuple(reader.fieldnames) != REQUIRED_COLUMNS:
            raise DataValidationError('Expected CSV columns, in order: ' + ','.join(REQUIRED_COLUMNS))
        line = 1
        for row in reader:
            line += 1
            # A None key means extra cells; a None value means missing cells.
            bad_row = None in row
            for value in row.values():
                if value is None:
                    bad_row = True
            if bad_row:
                raise DataValidationError(f'Line {line}: malformed CSV (check quotes and commas).')
            task_id = row['task_id'].strip()
            if not is_valid_task_id(task_id):
                raise DataValidationError(f'Line {line}: invalid task ID "{task_id}".')
            if task_id in tasks:
                raise DataValidationError(f'Line {line}: duplicate task {task_id}.')
            tasks[task_id] = Task(
                task_id=task_id,
                duration=positive_int(row['duration'], 'duration', line),
                dependencies=parse_dependencies(row['depends_on'], line),
                workers_required=positive_int(row['workers_required'], 'workers_required', line)
            )
    validate_tasks(tasks, worker_capacity)
    return tasks


def earliest_finish(task_id, tasks, memo):
    """Earliest day a task can be done: its own duration plus its slowest prerequisite.

    This function calls itself for each prerequisite.
    'memo' remembers answers we already worked out, so we do not repeat them.
    Example: T02 takes 4 and needs T01 (2 days) -> 6.
    """
    if task_id not in memo:
        slowest = 0
        for dep in tasks[task_id].dependencies:
            finish = earliest_finish(dep, tasks, memo)
            if finish > slowest:
                slowest = finish
        memo[task_id] = tasks[task_id].duration + slowest
    return memo[task_id]


def lower_bounds(tasks, worker_capacity):
    """Return two simple answers to "the project cannot finish faster than this".

    1. Critical path: the longest chain of tasks that must run one after
       another. For our data: T01 (2) + T02 (4) + T05 (2) + T06 (1) = 9 days.
    2. Workload: all the work added up, divided by the number of workers,
       rounded up. For our data: 15 worker-days / 2 workers = 7.5, so 8 days.
    Returns (9, 8) for tasks.csv. The real answer can be higher than both.
    """
    validate_tasks(tasks, worker_capacity)
    memo = {}
    critical_path = 0
    total_work = 0
    for task_id, task in tasks.items():
        finish = earliest_finish(task_id, tasks, memo)
        if finish > critical_path:
            critical_path = finish
        total_work += task.duration * task.workers_required
    workload = math.ceil(total_work / worker_capacity)
    return critical_path, workload


def place_jobs(jobs, index, loads, best):
    """Try to give job number 'index' to each worker in turn. Return the best finish time found.

    This function calls itself for the next job. 'loads' is how much work each
    worker has so far, and 'best' is the shortest finish time found so far.
    Two shortcuts keep it fast, and neither can skip the best answer:
      - skip a worker if this job would not beat 'best' (it can only get worse)
      - skip a worker whose load equals one we already tried (same result)
    """
    if index == len(jobs):
        busiest = max(loads)
        if busiest < best:
            return busiest
        return best
    tried = []
    for k in range(len(loads)):
        if loads[k] in tried or loads[k] + jobs[index] >= best:
            continue
        tried.append(loads[k])
        loads[k] += jobs[index]
        best = place_jobs(jobs, index + 1, loads, best)
        loads[k] -= jobs[index]
    return best


def _best_split(durations, parts):
    """Find the shortest time to finish a set of jobs that can run in any order.

    'durations' are the job lengths and 'parts' is how many workers share them.
    It tries the ways to hand out the jobs and keeps the best one.
    Examples:
        _best_split([4, 3, 3], 2)  -> 6   (one worker does 3 + 3 = 6, the other does 4)
        _best_split([4, 3, 3], 3)  -> 4   (each job gets its own worker)
        _best_split([5], 2)        -> 5   (one job cannot be split)
    """
    # Biggest jobs first, so bad choices show up early and get skipped.
    jobs = sorted(durations, reverse=True)
    loads = [0] * parts
    return place_jobs(jobs, 0, loads, sum(jobs))


def longest_after(task_id, tasks, followers, memo):
    """Longest chain of work that comes strictly after a task.

    This function calls itself for each task that waits on this one.
    Example with our data: after T05 there is only T06 (1 day) -> 1.
    """
    if task_id not in memo:
        longest = 0
        for follower in followers[task_id]:
            chain = tasks[follower].duration + longest_after(follower, tasks, followers, memo)
            if chain > longest:
                longest = chain
        memo[task_id] = longest
    return memo[task_id]


def group_split_bound(tasks, worker_capacity):
    """A third "cannot finish faster than this" number, using tasks that wait on the same thing.

    Tasks with the same prerequisites cannot start until those prerequisites
    are done. After that they have to share the workers. The bound adds up:
      head  = when the shared prerequisites are done
      split = the best possible time to share the group between the workers
      tail  = the shortest work still left after one of the group finishes
    Example with our data: T02, T03 and T04 all wait only for T01.
      head  = 2          (T01 takes 2 days)
      split = 6          (jobs of 4, 3, 3 on 2 workers: 3 + 3 on one, 4 on the other)
      tail  = 3          (T05 takes 2, then T06 takes 1)
      bound = 2 + 6 + 3 = 11 days
    That matches the reference schedule, so 11 days is the best possible.
    Groups where some task needs more than 1 worker (or more than 12 tasks)
    use a looser but still safe split number. Returns 0 if no group has 2+ tasks.
    """
    validate_tasks(tasks, worker_capacity)
    finish_memo = {}
    after_memo = {}

    # followers[t] = the tasks that list t as a prerequisite.
    followers = {}
    for t in tasks:
        followers[t] = []
    for t, task in tasks.items():
        for dep in task.dependencies:
            followers[dep].append(t)

    # Group tasks that have exactly the same prerequisites.
    # A frozenset is a set that can be used as a dict key (a normal set cannot).
    groups = {}
    for t, task in tasks.items():
        key = frozenset(task.dependencies)
        if key not in groups:
            groups[key] = []
        groups[key].append(t)

    best = 0
    for deps, members in groups.items():
        if len(members) < 2:
            continue
        head = 0
        for d in deps:
            finish = earliest_finish(d, tasks, finish_memo)
            if finish > head:
                head = finish

        jobs = []
        total_work = 0
        all_single = True
        shortest_tail = None
        for t in members:
            jobs.append(tasks[t].duration)
            total_work += tasks[t].duration * tasks[t].workers_required
            if tasks[t].workers_required != 1:
                all_single = False
            tail = longest_after(t, tasks, followers, after_memo)
            if shortest_tail is None or tail < shortest_tail:
                shortest_tail = tail

        # Safe split number: no faster than the longest job or the shared workload.
        split = max(max(jobs), math.ceil(total_work / worker_capacity))
        if all_single and len(members) <= 12:
            split = max(split, _best_split(jobs, worker_capacity))

        bound = head + split + shortest_tail
        if bound > best:
            best = bound
    return best


def combined_lower_bound(tasks, worker_capacity):
    """Take the biggest of the three bounds, since all three are true at once.

    Example: critical path 9, workload 8, group split 11 -> returns 11.
    If a real schedule also takes 11 days, nothing faster is possible.
    """
    path, workload = lower_bounds(tasks, worker_capacity)
    return max(path, workload, group_split_bound(tasks, worker_capacity))


def main():
    """Command line entry point. Loads the file, checks it, prints the result.

    Example:
        python -m scheduling.data_validation data/tasks.csv --workers 2
    Prints "VALID: ..." and the lower bounds when the file is fine.
    On a problem it prints "INVALID INPUT: <reason>" and exits with code 1.
    """
    parser = argparse.ArgumentParser(description='Validate scheduling requirements CSV')
    parser.add_argument('csv_file', nargs='?',
                        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'tasks.csv'))
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    try:
        tasks = load_tasks(args.csv_file, args.workers)
        path, workload = lower_bounds(tasks, args.workers)
    except DataValidationError as exc:
        parser.exit(1, f'INVALID INPUT: {exc}\n')
    print(f'VALID: {len(tasks)} tasks, {args.workers} workers, all dependencies valid and acyclic.')
    print(f'Lower bounds: critical path {path} days; worker workload {workload} days.')
    split = group_split_bound(tasks, args.workers)
    print(f'Parallel-split lower bound: {split} days (shared-prerequisite tasks split across workers).')
    print(f'Combined lower bound: {max(path, workload, split)} days. '
          'A schedule of exactly this length is optimal; otherwise optimality is not proven.')


if __name__ == '__main__':
    main()
