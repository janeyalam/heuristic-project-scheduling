"""Phase 1: the scheduling model (states and the moves between them).

There is no search in this file. Phase 2 will import initial_state(),
successors() and is_goal().

A state only remembers which tasks are done and which are running (with
days left). It does not remember the current day. The search adds up the
days itself. Each move jumps time forward to the next task that finishes.
"""
import argparse
import csv
import os
from dataclasses import dataclass

# combinations(['A', 'B', 'C'], 2) gives ('A', 'B'), ('A', 'C'), ('B', 'C')
from itertools import combinations

from scheduling.data_validation import Task, combined_lower_bound, load_tasks


# The classes below are frozen (they cannot change after they are created).
# That way the search can safely store them in sets and dicts.
@dataclass(frozen=True)
class State:
    """A snapshot of the project at one moment: what is done and what is running.

    Example: T01 is done, T02 has 1 day left, T03 has 2 days left:
        State(completed=frozenset({'T01'}), running=(('T02', 1), ('T03', 2)))
    The current day is not stored here. The search keeps track of that.
    """
    completed: frozenset  # task ids that are finished
    running: tuple  # pairs of (task_id, remaining days)


@dataclass(frozen=True)
class Action:
    """What happened in one step: which tasks we started, which finished, and how many days passed.

    Example: Action(started=('T02', 'T03'), finished=('T03',), elapsed_days=3)
    means we started T02 and T03, and 3 days later T03 finished.
    """
    started: tuple
    finished: tuple
    elapsed_days: int


@dataclass(frozen=True)
class Successor:
    """One possible next step: the new state, the action that got us there, and its cost in days.

    Example: after starting T01 from the beginning, the cost is 2 (T01 takes 2 days).
    """
    state: State
    action: Action
    cost: int  # days that passed in this step (always at least 1)


def initial_state():
    """The starting point: nothing done, nothing running.

    Example: initial_state() -> State(completed=frozenset(), running=())
    """
    return State(frozenset(), ())


def is_goal(state, tasks):
    """True when every task is finished and nothing is still running.

    Examples (with the 6 tasks T01 to T06):
        completed = all six, running = ()          -> True
        completed = T01 to T05, running = (T06, 1) -> False (T06 is not done)
    """
    if len(state.running) > 0:
        return False
    return state.completed == frozenset(tasks)


def validate_state(state, tasks, capacity):
    """Make sure a state is possible. Raises ValueError if it is not.

    Things it rejects:
      - a task ID that is not in the project
      - the same task running twice, or running and done at the same time
      - remaining days that are below 1 or above the task's full duration
        (example: T02 with 5 days left, but T02 only takes 4)
      - more workers busy than we have
      - a started task whose prerequisites are not finished
        (example: T05 running while T04 is not done)
    """
    for task_id in state.completed:
        if task_id not in tasks:
            raise ValueError('Unknown completed task ID.')
    running_ids = []
    for task_id, days_left in state.running:
        running_ids.append(task_id)
    if len(set(running_ids)) != len(running_ids):
        raise ValueError('Duplicate running task.')
    for task_id in running_ids:
        if task_id not in tasks or task_id in state.completed:
            raise ValueError('Unknown or already completed running task.')
    for task_id, days_left in state.running:
        if days_left < 1 or days_left > tasks[task_id].duration:
            raise ValueError('Invalid remaining duration.')
    if workers_in_use(state, tasks) > capacity:
        raise ValueError('Too many workers occupied.')
    # Every task that has started needs all its prerequisites finished.
    started = set(state.completed)
    for task_id in running_ids:
        started.add(task_id)
    for task_id in sorted(started):
        for dep in tasks[task_id].dependencies:
            if dep not in state.completed:
                raise ValueError(f'Unfinished predecessor of {task_id}.')


def workers_in_use(state, tasks):
    """Count the workers that are busy right now.

    Example: T02 and T03 are running and each needs 1 worker -> 2.
    """
    total = 0
    for task_id, days_left in state.running:
        total += tasks[task_id].workers_required
    return total


def ready_tasks(state, tasks):
    """List the tasks that could start now: not started yet, and all prerequisites done.

    This ignores free workers. It only looks at prerequisites.
    Examples:
        at the start (nothing done)  -> ('T01',)
        T01 done                     -> ('T02', 'T03', 'T04')
        T01 done, T02 running        -> ('T03', 'T04')
        T01, T02, T03 done           -> ('T04',)   (T05 still needs T04)
    """
    started = set(state.completed)
    for task_id, days_left in state.running:
        started.add(task_id)
    ready = []
    for task_id, task in tasks.items():
        if task_id in started:
            continue
        all_done = True
        for dep in task.dependencies:
            if dep not in state.completed:
                all_done = False
        if all_done:
            ready.append(task_id)
    return tuple(sorted(ready))


def legal_start_sets(state, tasks, capacity):
    """List every group of tasks we are allowed to start right now.

    A group is allowed when all its tasks are ready and the free workers are
    enough for all of them together. An empty group means "start nothing and
    wait for a running task to finish". That is only allowed when something
    is already running, because otherwise time could never move forward.
    Examples (2 workers):
        at the start                 -> (('T01',),)
        T01 done, nothing running    -> 6 choices: T02, T03, T04, and
                                        the pairs (T02,T03), (T02,T04), (T03,T04)
        T01 done, T02 running        -> (), ('T03',), ('T04',)
                                        (only 1 free worker, so no pairs)
        everything finished          -> ()
    """
    validate_state(state, tasks, capacity)
    if is_goal(state, tasks):
        return ()
    ready = ready_tasks(state, tasks)
    free_workers = capacity - workers_in_use(state, tasks)
    result = []
    for size in range(len(ready) + 1):
        for group in combinations(ready, size):
            if size == 0 and len(state.running) == 0:
                continue  # waiting with nothing running would never move time
            needed = 0
            for task_id in group:
                needed += tasks[task_id].workers_required
            if needed <= free_workers:
                result.append(group)
    return tuple(result)


def advance(state, started, tasks, capacity):
    """Start the chosen tasks, then jump forward to the moment the next task finishes.

    Time moves by the smallest "days left" among everything running. Tasks
    that reach zero are marked done. The others keep their remaining days.
    Raises ValueError if the chosen group is not one of the legal choices.
    Examples:
        Start T01 at the beginning:
            T01 has 2 days, so we jump 2 days. T01 is done. Cost = 2.
        T01 done, start T02 (4 days) and T03 (3 days):
            smallest is 3, so we jump 3 days. T03 is done and T02 has
            1 day left. Cost = 3.
        Start ('T05',) while T04 is not done -> ValueError
    """
    validate_state(state, tasks, capacity)
    chosen = tuple(sorted(started))
    if len(set(chosen)) != len(chosen):
        raise ValueError(f'Illegal scheduling action: {chosen}')
    if chosen not in legal_start_sets(state, tasks, capacity):
        raise ValueError(f'Illegal scheduling action: {chosen}')

    # Everything running after the new tasks start.
    running = list(state.running)
    for task_id in chosen:
        running.append((task_id, tasks[task_id].duration))

    # Find the smallest number of days left. That is how far time jumps.
    days_passed = running[0][1]
    for task_id, days_left in running:
        if days_left < days_passed:
            days_passed = days_left

    finished = []
    still_running = []
    for task_id, days_left in running:
        if days_left == days_passed:
            finished.append(task_id)
        else:
            still_running.append((task_id, days_left - days_passed))
    finished = tuple(sorted(finished))

    completed = set(state.completed)
    for task_id in finished:
        completed.add(task_id)
    next_state = State(frozenset(completed), tuple(sorted(still_running)))
    validate_state(next_state, tasks, capacity)
    return Successor(next_state, Action(chosen, finished, days_passed), days_passed)


def successors(state, tasks, capacity):
    """Give every state we can reach in one step from this state.

    It runs advance() once for each legal group of tasks to start.
    Example: with T01 done and nothing running, there are 6 legal groups,
    so this returns 6 successors. A search algorithm uses this to explore.
    """
    result = []
    for group in legal_start_sets(state, tasks, capacity):
        result.append(advance(state, group, tasks, capacity))
    return tuple(result)


def validate_schedule(rows, tasks, capacity):
    """Check a finished schedule. Return the total days if it is valid, else raise ValueError.

    Each row needs task_id, start_day and finish_day. worker_id is optional
    (like 1, 2 or W1). The checks are:
      - every task appears exactly once
      - finish - start equals the task's duration, and start is not negative
      - a task starts only after all its prerequisites have finished
      - at any moment, the workers needed do not exceed capacity
      - if worker_id is given, it is from 1 to capacity, and one worker is
        not given two tasks at the same time
    A task may start on the same day another one finishes (finish 2, start 2 is fine).
    Examples:
        The reference schedule (T01 0-2, T02 2-6, T03 2-5, T04 5-8,
        T05 8-10, T06 10-11) -> returns 11
        T02 starting on day 1 while T01 runs until day 2 -> error (starts before T01 finishes)
        T02, T03 and T04 all running on day 2 with capacity 2 -> error (demand 3)
        worker_id 3 with capacity 2 -> error
    """
    if len(rows) != len(tasks):
        raise ValueError(f'Expected {len(tasks)} schedule rows; got {len(rows)}.')
    times = {}      # task_id -> (start, finish)
    worker_of = {}  # task_id -> worker number as text
    for row in rows:
        missing = []
        for column in ('task_id', 'start_day', 'finish_day'):
            if row.get(column) is None:
                missing.append(column)
        if len(missing) > 0:
            raise ValueError(f'Malformed schedule row {dict(row)}: missing {", ".join(missing)}.')
        task_id = str(row['task_id']).strip()
        if task_id not in tasks or task_id in times:
            raise ValueError(f'Unknown or duplicate schedule task {task_id}.')
        try:
            start = int(row['start_day'])
            finish = int(row['finish_day'])
        except (TypeError, ValueError):
            raise ValueError(f'{task_id}: start and finish must be integers.')
        if start < 0 or finish - start != tasks[task_id].duration:
            raise ValueError(f'{task_id}: invalid timing or duration.')
        times[task_id] = (start, finish)
        if row.get('worker_id') is not None:
            worker_of[task_id] = _parse_worker_id(task_id, row['worker_id'], capacity)

    for task_id, task in tasks.items():
        for dep in task.dependencies:
            if times[dep][1] > times[task_id][0]:
                raise ValueError(f'{task_id}: starts before {dep} finishes.')

    # Demand only changes on a start or finish day, so check those days.
    day_set = set()
    for start, finish in times.values():
        day_set.add(start)
        day_set.add(finish)
    days = sorted(day_set)
    for day in days[:-1]:
        running = []
        for task_id, (start, finish) in times.items():
            if start <= day < finish:
                running.append(task_id)
        demand = 0
        for task_id in running:
            demand += tasks[task_id].workers_required
        if demand > capacity:
            raise ValueError(f'Worker demand {demand} exceeds {capacity} at day {day}.')
        busy_workers = set()
        for task_id in running:
            if task_id not in worker_of:
                continue
            if worker_of[task_id] in busy_workers:
                raise ValueError(f'Worker assigned to overlapping tasks at day {day}.')
            busy_workers.add(worker_of[task_id])

    last_day = 0
    for start, finish in times.values():
        if finish > last_day:
            last_day = finish
    return last_day


def _parse_worker_id(task_id, value, capacity):
    """Turn a worker_id like '2' or 'W2' into the text '2'. Raise ValueError if not 1..capacity."""
    text = str(value).strip()
    digits = text
    if text[:1] == 'W' or text[:1] == 'w':
        digits = text[1:]
    # Only plain 0-9 count as digits. An empty string is not a number.
    valid = len(digits) > 0
    for ch in digits:
        if ch not in '0123456789':
            valid = False
    if valid:
        number = int(digits)
        if 1 <= number <= capacity:
            return str(number)
    raise ValueError(f'{task_id}: worker_id {text} must be an integer from 1 to {capacity}.')


def read_reference_schedule(path):
    """Read a schedule CSV into a list of rows (one dict per row).

    The file must have the columns task_id, start_day and finish_day.
    worker_id may also be there. Values are returned as the raw text from
    the file; validate_schedule() does the number checks.
    Example row: {'task_id': 'T02', 'worker_id': '1', 'start_day': '2', 'finish_day': '6'}
    Raises ValueError if a required column is missing from the header.
    """
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        if fields is None:
            fields = []
        absent = []
        for column in ('task_id', 'start_day', 'finish_day'):
            if column not in fields:
                absent.append(column)
        if len(absent) > 0:
            raise ValueError(f'Reference schedule is missing column(s): {", ".join(absent)}.')
        rows = []
        for r in reader:
            rows.append({
                'task_id': r.get('task_id'),
                'worker_id': r.get('worker_id'),
                'start_day': r.get('start_day'),
                'finish_day': r.get('finish_day'),
            })
    return rows


def trace_reference_schedule(tasks, capacity):
    """Replay reference_schedule.csv step by step and print each step.

    First it validates the schedule. Then, starting from the empty state, it
    starts the tasks listed for each day and calls advance() until the goal
    is reached. Example of the output lines:
        Day  2: started=('T01',), finished=('T01',), running=(), completed=['T01']
    At the end it prints the total days (11) and compares it with the lower
    bound. Equal means no faster schedule exists.
    """
    schedule_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'reference_schedule.csv')
    rows = read_reference_schedule(schedule_file)
    makespan = validate_schedule(rows, tasks, capacity)
    state = initial_state()
    elapsed = 0
    print('State transitions for the reference schedule:')
    while not is_goal(state, tasks):
        starts = []
        for row in rows:
            if int(row['start_day']) == elapsed:
                starts.append(str(row['task_id']))
        starts = tuple(sorted(starts))
        step = advance(state, starts, tasks, capacity)
        elapsed += step.cost
        state = step.state
        day_text = str(elapsed).rjust(2)
        print(f'Day {day_text}: started={step.action.started}, finished={step.action.finished}, '
              f'running={state.running}, completed={sorted(state.completed)}')
    if elapsed != makespan:
        raise ValueError(f'Replay took {elapsed} days but the schedule says {makespan}.')
    print(f'VALID reference schedule: {makespan} working days')
    bound = combined_lower_bound(tasks, capacity)
    if makespan == bound:
        print(f'Lower bound {bound} equals the schedule length, so it is optimal.')
    else:
        print(f'Lower bound {bound} < schedule length {makespan}; optimality is not proven.')


def main():
    """Command line entry point. Loads the tasks and prints the starting situation.

    Example:
        python -m scheduling.scheduling_model data/tasks.csv --workers 2
    It prints the initial state, the tasks ready at the start, and the legal
    choices at the start. With the 6 baseline tasks and 2 workers it also
    replays the reference schedule.
    """
    parser = argparse.ArgumentParser(description='Demonstrate the Phase 1 model on the project tasks')
    parser.add_argument('csv_file', nargs='?',
                        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'tasks.csv'))
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    tasks = load_tasks(args.csv_file, args.workers)
    print('Initial state:', initial_state())
    print('Initially ready:', ready_tasks(initial_state(), tasks))
    print('Initial legal choices:', legal_start_sets(initial_state(), tasks, args.workers))
    baseline_ids = {'T01', 'T02', 'T03', 'T04', 'T05', 'T06'}
    if args.workers == 2 and set(tasks) == baseline_ids:
        trace_reference_schedule(tasks, args.workers)


if __name__ == '__main__':
    main()
