"""Phase 2: the helper code shared by BFS, UCS, Greedy and A*.

The four algorithms only differ in how they pick the next state from the
frontier (the list of states waiting to be explored). Everything else lives
here: checking the input, the search loop, counting, timing, building the
schedule and checking it.

Python standard library only. The search never reads files. It gets the tasks
from data_validation.load_tasks() and the moves from scheduling_model.
"""
import heapq
import time
from collections import deque

from scheduling.data_validation import DataValidationError, validate_tasks
from scheduling.scheduling_model import initial_state, is_goal, successors, validate_schedule

STATUS_SOLVED = 'solved'
STATUS_NO_SOLUTION = 'no solution'
STATUS_TIMEOUT = 'timeout'
STATUS_STATE_LIMIT = 'state_limit'
STATUS_INVALID_INPUT = 'invalid input'


class SearchLimit(Exception):
    """Raised when a search stops because its expansion limit was reached."""


class SearchTimeout(Exception):
    """Raised when a search stops because its time or expansion limit was reached.

    best_first_search() catches it and returns a "timeout" result, so callers
    normally never see it.
    """


def make_result(algorithm, status, makespan=None, schedule=None, states_explored=0,
                execution_time_ms=0.0, schedule_valid=False, error=None, transitions=None,
                states_generated=0):
    """Build the result dict that every search returns.

    The seven required keys are always there. 'error', 'transitions' and
    'states_generated' (successors produced by counted expansions) are extra keys. Example for a failed run:
        make_result('BFS', 'invalid input', error='empty task set')
    gives makespan None, schedule [] and schedule_valid False.
    """
    if schedule is None:
        schedule = []
    return {
        'algorithm': algorithm,
        'makespan': makespan,
        'schedule': schedule,
        'states_explored': states_explored,
        'states_generated': states_generated,
        'execution_time_ms': execution_time_ms,
        'schedule_valid': schedule_valid,
        'status': status,
        'error': error,
        'transitions': transitions,
    }


def check_input(tasks, capacity):
    """Check the tasks and worker capacity. Return None if fine, else a short error text.

    The text starts with the kind of problem. Examples:
        capacity 0                 -> 'invalid worker capacity: ...'
        no tasks                   -> 'empty task set: ...'
        T02 <-> T03                -> 'dependency cycle: ...'
        T02 needs T09 (missing)    -> 'unknown dependency: ...'
        T05 needs 3, capacity 2    -> 'task T05 needs 3 workers, capacity is 2'
    """
    try:
        validate_tasks(tasks, capacity)
    except DataValidationError as exc:
        text = str(exc)
        if 'capacity must be' in text:
            return f'invalid worker capacity: {text}'
        if 'cannot be empty' in text:
            return f'empty task set: {text}'
        if 'cycle' in text:
            return f'dependency cycle: {text}'
        if 'missing dependency' in text:
            return f'unknown dependency: {text}'
        if 'workers, capacity is' in text:
            return f'task {text}'
        return f'invalid input: {text}'
    except (TypeError, AttributeError, KeyError) as exc:
        return f'invalid input: {type(exc).__name__}: {exc}'
    return None


def reconstruct_schedule(actions):
    """Turn the list of Actions along the path into a schedule with start and finish days.

    A running clock t starts at 0. A task in action.started begins at t. A task
    in action.finished ends at t + elapsed_days. Then t moves forward.
    Example: [Action(('T01',), ('T01',), 2)] -> T01 from day 0 to day 2.
    Returns entries sorted by (start_time, task_id).
    """
    clock = 0
    starts = {}
    entries = []
    for action in actions:
        for task_id in action.started:
            starts[task_id] = clock
        clock += action.elapsed_days
        for task_id in action.finished:
            entries.append({
                'task_id': task_id,
                'start_time': starts[task_id],
                'finish_time': clock,
            })
    entries.sort(key=lambda e: (e['start_time'], e['task_id']))
    return entries


def _to_rows(entries):
    """Convert schedule entries into the rows that validate_schedule() expects."""
    rows = []
    for entry in entries:
        rows.append({
            'task_id': entry.get('task_id'),
            'start_day': entry.get('start_time'),
            'finish_day': entry.get('finish_time'),
        })
    return rows


def check_schedule(entries, tasks, capacity):
    """Check a schedule with the Phase 1 validator. Return (is_valid, error_text).

    Examples:
        good schedule              -> (True, None)
        T02 starts before T01 ends -> (False, 'T02: starts before T01 finishes.')
        validator crashes          -> (False, 'validation could not be completed: ...')
    """
    try:
        validate_schedule(_to_rows(entries), tasks, capacity)
    except ValueError as exc:
        return False, str(exc)
    except Exception as exc:  # the validator itself failed; never report success
        return False, f'validation could not be completed: {type(exc).__name__}: {exc}'
    return True, None


def find_violations(entries, tasks, capacity):
    """List every problem in a schedule (validate_schedule only reports the first).

    Each text names the type and the task or day. Types: missing, duplicate,
    unknown, duration, dependency, capacity. An empty list means no problems.
    Example: ['dependency: T02 starts at day 1 before T01 finishes at day 2']
    """
    problems = []
    times = {}
    tried = set()  # tasks that appeared with malformed times (already reported)
    for entry in entries:
        task_id = entry.get('task_id')
        start = entry.get('start_time')
        finish = entry.get('finish_time')
        if task_id not in tasks:
            problems.append(f'unknown: task {task_id} is not in the project')
            continue
        if task_id in times:
            problems.append(f'duplicate: task {task_id} appears more than once')
            continue
        tried.add(task_id)
        if type(start) is not int or type(finish) is not int:
            problems.append(f'duration: {task_id} has non-integer times')
            continue
        times[task_id] = (start, finish)
        if start < 0 or finish - start != tasks[task_id].duration:
            problems.append(f'duration: {task_id} runs {start} to {finish}, '
                            f'expected {tasks[task_id].duration} days from a non-negative start')
    for task_id in tasks:
        if task_id not in times and task_id not in tried:
            problems.append(f'missing: task {task_id} is not scheduled')
    for task_id, task in tasks.items():
        if task_id not in times:
            continue
        for dep in task.dependencies:
            if dep in times and times[dep][1] > times[task_id][0]:
                problems.append(f'dependency: {task_id} starts at day {times[task_id][0]} '
                                f'before {dep} finishes at day {times[dep][1]}')
    days = set()
    for start, finish in times.values():
        days.add(start)
        days.add(finish)
    for day in sorted(days):
        demand = 0
        for task_id, (start, finish) in times.items():
            if start <= day < finish:
                demand += tasks[task_id].workers_required
        if demand > capacity:
            problems.append(f'capacity: worker demand {demand} exceeds {capacity} at day {day}')
    return problems


def _path_actions(parent, state):
    """Walk the parent links from a state back to the start. Return the Actions in order."""
    actions = []
    while state in parent:
        state, action = parent[state]
        actions.append(action)
    actions.reverse()
    return actions


def best_first_search(algorithm, tasks, capacity, *, priority, reopen,
                      timeout_seconds=None, max_expansions=None):
    """The one search loop used by all four algorithms.

    algorithm       name put in the result ('BFS', 'UCS', 'Greedy', 'A*')
    priority        function (state, g, cache) -> tuple. Smaller tuples are explored
                    first; ties go to the state added to the frontier first. Pass
                    None for a plain first-in first-out queue (BFS). 'cache' is a
                    dict the function may use to remember work for this run.
    reopen          True: a state found again by a strictly cheaper route is added
                    again (UCS, A*). False: a state seen once is never added again
                    (BFS, Greedy).
    timeout_seconds stop with status 'timeout' after this many seconds (None = no limit)
    max_expansions  stop with status 'state_limit' after this many expansions (None = no limit)

    A state counts as explored once when it is taken from the frontier, is not
    a stale leftover, is not the goal, and its successors are generated.
    The goal is tested when a state is taken out, not when it is generated.
    """
    error = check_input(tasks, capacity)
    if error is not None:
        return make_result(algorithm, STATUS_INVALID_INPUT, error=error)

    cache = {}
    best_g = {}
    parent = {}
    counter = 0
    explored = 0
    generated = 0

    start = time.perf_counter()
    root = initial_state()
    best_g[root] = 0
    if priority is None:
        frontier = deque([(0, root)])
    else:
        frontier = [(priority(root, 0, cache), counter, 0, root)]
    counter += 1

    def elapsed_ms():
        return (time.perf_counter() - start) * 1000.0

    try:
        while frontier:
            if timeout_seconds is not None and time.perf_counter() - start >= timeout_seconds:
                raise SearchTimeout('time limit reached')
            if max_expansions is not None and explored >= max_expansions:
                raise SearchLimit('expansion limit reached')
            if priority is None:
                g, state = frontier.popleft()
            else:
                _, _, g, state = heapq.heappop(frontier)
            if g > best_g[state]:
                continue  # stale entry: a cheaper route to this state was found later
            if is_goal(state, tasks):
                actions = _path_actions(parent, state)
                schedule = reconstruct_schedule(actions)
                valid, message = check_schedule(schedule, tasks, capacity)
                if not valid:
                    problems = find_violations(schedule, tasks, capacity)
                    text = '; '.join(problems) if problems else message
                    return make_result(algorithm, STATUS_NO_SOLUTION, states_explored=explored, states_generated=generated,
                                       execution_time_ms=elapsed_ms(), error=text)
                return make_result(algorithm, STATUS_SOLVED, makespan=g, schedule=schedule,
                                   states_explored=explored, states_generated=generated, execution_time_ms=elapsed_ms(),
                                   schedule_valid=True, transitions=len(actions))
            explored += 1
            steps = list(successors(state, tasks, capacity))
            generated += len(steps)
            for step in steps:
                new_g = g + step.cost
                known = step.state in best_g
                if known and (not reopen or new_g >= best_g[step.state]):
                    continue
                best_g[step.state] = new_g
                parent[step.state] = (state, step.action)
                if priority is None:
                    frontier.append((new_g, step.state))
                else:
                    heapq.heappush(frontier, (priority(step.state, new_g, cache), counter,
                                              new_g, step.state))
                counter += 1
    except SearchLimit as exc:
        return make_result(algorithm, STATUS_STATE_LIMIT, states_explored=explored, states_generated=generated,
                           execution_time_ms=elapsed_ms(), error=str(exc))
    except SearchTimeout as exc:
        return make_result(algorithm, STATUS_TIMEOUT, states_explored=explored, states_generated=generated,
                           execution_time_ms=elapsed_ms(), error=str(exc))
    return make_result(algorithm, STATUS_NO_SOLUTION, states_explored=explored, states_generated=generated,
                       execution_time_ms=elapsed_ms())
