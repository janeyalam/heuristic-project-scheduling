"""Phase 2 tests for the search algorithms (standard library unittest only).

Run with:
    python -m unittest -v tests.test_search

This first group checks successor generation (Requirement 1):
    - baseline example (T01 done -> exactly 6 successors)
    - a handcrafted instance where delaying a ready task beats a forced-start model
    - Property 1 on seeded random datasets
"""
import contextlib
import inspect
import io
import itertools
import os
import random
import tempfile
import unittest
from functools import lru_cache
from itertools import combinations
from unittest import mock

from scheduling import astar
from scheduling import bfs
from experiments import comparison
from scheduling import greedy
from scheduling import search_common
from scheduling import ucs
from scheduling.astar import astar_search
from scheduling.bfs import bfs_search
from scheduling.greedy import greedy_search
from scheduling.data_validation import Task, combined_lower_bound, load_tasks, validate_tasks
from scheduling.heuristics import (
    combined_heuristic, critical_path_remaining, longest_remaining,
    workload_remaining, zero_heuristic,
)
from scheduling.results_io import (
    ALLOWED_STATUSES, COLUMNS, ResultsCsvError, read_results_csv, write_results_csv,
)
from scheduling.search_common import check_schedule, find_violations
from scheduling.ucs import ucs_search
from scheduling.scheduling_model import (
    State, initial_state, is_goal, ready_tasks, successors, validate_state,
    workers_in_use,
)

TASKS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'tasks.csv')
SEED = 7375
CASES = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def random_dataset(rng, max_tasks=6, max_duration=4):
    """Return (tasks, capacity) for a random valid dataset, checked by validate_tasks.

    Dependencies only point to earlier IDs, so there are no cycles.
    Every task needs at most `capacity` workers.
    """
    while True:
        capacity = rng.randint(1, 3)
        count = rng.randint(1, max_tasks)
        ids = [f'T{i + 1:02d}' for i in range(count)]
        tasks = {}
        for index, task_id in enumerate(ids):
            deps = tuple(d for d in ids[:index] if rng.random() < 0.35)
            tasks[task_id] = Task(
                task_id,
                rng.randint(1, max_duration),
                deps,
                rng.randint(1, capacity),
            )
        try:
            validate_tasks(tasks, capacity)
        except ValueError:
            continue
        return tasks, capacity


def reachable_states(tasks, capacity, rng, limit=25):
    """Collect up to `limit` states reached by random walks from the initial state."""
    seen = {initial_state()}
    for _ in range(6):
        state = initial_state()
        while not is_goal(state, tasks):
            options = successors(state, tasks, capacity)
            if not options:
                break
            state = rng.choice(options).state
            seen.add(state)
            if len(seen) >= limit:
                return sorted(seen, key=repr)
    return sorted(seen, key=repr)


def expected_start_sets(state, tasks, capacity):
    """Independent re-computation: every non-empty fitting subset of ready tasks,
    plus the wait-only group () when something is running."""
    ready = ready_tasks(state, tasks)
    free = capacity - workers_in_use(state, tasks)
    expected = set()
    for size in range(1, len(ready) + 1):
        for group in combinations(ready, size):
            if sum(tasks[t].workers_required for t in group) <= free:
                expected.add(tuple(sorted(group)))
    if state.running:
        expected.add(())
    return expected


def assert_successors_complete(test, state, tasks, capacity, label):
    """Property 1 check for one state."""
    result = successors(state, tasks, capacity)
    actual = [s.action.started for s in result]
    expected = expected_start_sets(state, tasks, capacity)
    msg = f'{label}: state={state}'
    test.assertEqual(len(actual), len(set(actual)), msg=f'duplicate successors; {msg}')
    test.assertEqual(set(actual), expected, msg=msg)
    wait_only = [s for s in result if s.action.started == ()]
    test.assertEqual(len(wait_only), 1 if state.running else 0, msg=f'wait-only count; {msg}')
    if not state.running and not ready_tasks(state, tasks):
        test.assertEqual(result, (), msg=f'expected no successors; {msg}')
    for s in result:
        test.assertGreaterEqual(s.cost, 1, msg=f'idle transition; {msg}')


def best_makespan(tasks, capacity, forced_start):
    """Exhaustive minimum makespan over the Phase 1 model.

    With forced_start=True only transitions that start a maximal set are allowed
    (no ready task that still fits may be left waiting). That models a scheduler
    that never delays a startable task.
    """
    @lru_cache(maxsize=None)
    def solve(state):
        if is_goal(state, tasks):
            return 0
        best = None
        free = capacity - workers_in_use(state, tasks)
        ready = ready_tasks(state, tasks)
        for succ in successors(state, tasks, capacity):
            if forced_start:
                used = sum(tasks[t].workers_required for t in succ.action.started)
                left = [t for t in ready
                        if t not in succ.action.started and tasks[t].workers_required <= free - used]
                if left:
                    continue
            rest = solve(succ.state)
            if rest is None:
                continue
            total = succ.cost + rest
            if best is None or total < best:
                best = total
        return best

    return solve(initial_state())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class SuccessorTests(unittest.TestCase):
    """Requirement 1: successor generation allows delaying tasks."""

    def test_baseline_t01_completed_yields_six_successors(self):
        tasks = load_tasks(TASKS_PATH, 2)
        state = State(frozenset({'T01'}), ())
        result = successors(state, tasks, 2)
        self.assertEqual(len(result), 6, msg=f'got {[s.action.started for s in result]}')
        self.assertEqual(
            {s.action.started for s in result},
            {('T02',), ('T03',), ('T04',), ('T02', 'T03'), ('T02', 'T04'), ('T03', 'T04')},
        )

    def test_initial_state_has_single_successor_and_no_wait_only(self):
        tasks = load_tasks(TASKS_PATH, 2)
        result = successors(initial_state(), tasks, 2)
        self.assertEqual([s.action.started for s in result], [('T01',)])

    def test_delaying_a_ready_task_beats_forced_start(self):
        """Handcrafted instance (2 workers): delaying gives 9 days, forced start gives 10."""
        tasks = {
            'T01': Task('T01', 1, (), 1),
            'T02': Task('T02', 2, (), 1),
            'T03': Task('T03', 1, ('T01',), 2),
            'T04': Task('T04', 3, ('T01', 'T03'), 1),
            'T05': Task('T05', 4, ('T01', 'T02', 'T03', 'T04'), 2),
        }
        validate_tasks(tasks, 2)
        with_delay = best_makespan(tasks, 2, forced_start=False)
        forced = best_makespan(tasks, 2, forced_start=True)
        self.assertEqual(with_delay, 9)
        self.assertEqual(forced, 10)
        self.assertLessEqual(with_delay, forced - 1)

    def test_wait_only_successor_advances_to_next_completion(self):
        tasks = load_tasks(TASKS_PATH, 2)
        state = State(frozenset({'T01'}), (('T02', 4),))
        wait = [s for s in successors(state, tasks, 2) if s.action.started == ()]
        self.assertEqual(len(wait), 1)
        self.assertEqual(wait[0].cost, 4)
        self.assertEqual(wait[0].action.finished, ('T02',))

    def test_no_successors_when_everything_is_finished(self):
        tasks = load_tasks(TASKS_PATH, 2)
        state = State(frozenset(tasks), ())
        self.assertEqual(successors(state, tasks, 2), ())

    # Feature: phase2-search-algorithms, Property 1: Successor generation is complete, unique and never idle
    def test_property_1_successor_generation_complete_unique_never_idle(self):
        """**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            for state in reachable_states(tasks, capacity, rng):
                label = f'case={case} capacity={capacity} tasks={list(tasks.values())}'
                assert_successors_complete(self, state, tasks, capacity, label)
                checked += 1
        self.assertGreaterEqual(checked, CASES)


class TransitionTests(unittest.TestCase):
    """Requirement 3: every transition is well formed."""

    # Feature: phase2-search-algorithms, Property 2: Every transition is well formed
    def test_property_2_every_transition_is_well_formed(self):
        """**Validates: Requirements 3.1, 3.2, 3.4, 3.5, 3.6**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            for state in reachable_states(tasks, capacity, rng):
                label = f'case={case} capacity={capacity} tasks={list(tasks.values())} state={state}'
                for succ in successors(state, tasks, capacity):
                    try:
                        validate_state(succ.state, tasks, capacity)
                    except ValueError as exc:
                        self.fail(f'successor state invalid ({exc}); {label} action={succ.action}')
                    self.assertIsInstance(succ.cost, int, msg=label)
                    self.assertGreaterEqual(succ.cost, 1, msg=label)
                    self.assertEqual(succ.cost, succ.action.elapsed_days, msg=label)
                    checked += 1
        self.assertGreaterEqual(checked, CASES)


class GreedyHeuristicTests(unittest.TestCase):
    """Requirements 6.3, 6.4: the Greedy default heuristic is longest_remaining."""

    def test_baseline_examples(self):
        tasks = load_tasks(TASKS_PATH, 2)
        self.assertEqual(longest_remaining(initial_state(), tasks, 2), 4)
        self.assertEqual(longest_remaining(State(frozenset(tasks), ()), tasks, 2), 0)

    def test_greedy_default_heuristic_is_longest_remaining(self):
        import inspect
        from scheduling import greedy
        source = inspect.getsource(greedy)
        self.assertIn('longest_remaining', source)

    # Feature: phase2-search-algorithms, Property 13: Greedy default heuristic matches its definition
    def test_property_13_greedy_default_heuristic_matches_definition(self):
        """**Validates: Requirements 6.3, 6.4**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            for state in reachable_states(tasks, capacity, rng):
                busy = set(state.completed) | {t for t, _ in state.running}
                values = [days for _, days in state.running]
                values += [tasks[t].duration for t in tasks if t not in busy]
                expected = max(values) if values else 0
                actual = longest_remaining(state, tasks, capacity)
                msg = (f'case={case} capacity={capacity} tasks={list(tasks.values())} '
                       f'state={state} expected={expected} actual={actual}')
                self.assertEqual(actual, expected, msg=msg)
                if not values:
                    self.assertEqual(actual, 0, msg=msg)
                checked += 1
        self.assertGreaterEqual(checked, CASES)


def true_remaining_cost(state, tasks, capacity):
    """Exact minimum days to finish from `state` (exhaustive search over successors)."""
    @lru_cache(maxsize=None)
    def solve(current):
        if is_goal(current, tasks):
            return 0
        best = None
        for succ in successors(current, tasks, capacity):
            rest = solve(succ.state)
            if rest is None:
                continue
            total = succ.cost + rest
            if best is None or total < best:
                best = total
        return best

    return solve(state)


class HeuristicAdmissibilityTests(unittest.TestCase):
    """Requirements 7.5, 6.4: no project heuristic overestimates the true remaining days."""

    HEURISTICS = (zero_heuristic, longest_remaining, critical_path_remaining,
                  workload_remaining, combined_heuristic)

    def test_baseline_initial_state_estimates(self):
        tasks = load_tasks(TASKS_PATH, 2)
        self.assertEqual(critical_path_remaining(initial_state(), tasks, 2), 9)
        for h in self.HEURISTICS:
            self.assertLessEqual(h(initial_state(), tasks, 2), 11, msg=h.__name__)

    # Feature: phase2-search-algorithms, Property 10: Project heuristics are admissible
    def test_property_10_project_heuristics_are_admissible(self):
        """**Validates: Requirements 7.5, 6.4**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            for state in reachable_states(tasks, capacity, rng):
                actual = true_remaining_cost(state, tasks, capacity)
                self.assertIsNotNone(actual, msg=f'dead end; case={case} state={state}')
                for h in self.HEURISTICS:
                    value = h(state, tasks, capacity)
                    msg = (f'case={case} capacity={capacity} tasks={list(tasks.values())} '
                           f'state={state} heuristic={h.__name__} h={value} true={actual}')
                    self.assertIsInstance(value, int, msg=msg)
                    self.assertGreaterEqual(value, 0, msg=msg)
                    self.assertLessEqual(value, actual, msg=msg)
                    if is_goal(state, tasks):
                        self.assertEqual(value, 0, msg=msg)
                checked += 1
        self.assertGreaterEqual(checked, CASES)


def corrupt_schedule(kind, entries, tasks, capacity, rng):
    """Return (corrupted entries, expected violation type, text that must appear in the message),
    or None when this dataset has no way to apply the corruption."""
    entries = [dict(e) for e in entries]
    by_id = {e['task_id']: e for e in entries}
    if kind == 'missing':
        victim = rng.choice(entries)
        entries.remove(victim)
        return entries, 'missing', victim['task_id']
    if kind == 'duplicate':
        victim = rng.choice(entries)
        entries.append(dict(victim))
        return entries, 'duplicate', victim['task_id']
    if kind == 'unknown':
        entries.append({'task_id': 'T99', 'start_time': 0, 'finish_time': 1})
        return entries, 'unknown', 'T99'
    if kind == 'duration':
        victim = rng.choice(entries)
        victim['finish_time'] += rng.randint(1, 2)
        return entries, 'duration', victim['task_id']
    if kind == 'dependency':
        pairs = [(t, d) for t, task in tasks.items() for d in task.dependencies]
        if not pairs:
            return None
        task_id, dep = rng.choice(pairs)
        entry = by_id[task_id]
        length = entry['finish_time'] - entry['start_time']
        entry['start_time'] = by_id[dep]['finish_time'] - 1
        entry['finish_time'] = entry['start_time'] + length
        return entries, 'dependency', task_id
    if kind == 'capacity':
        pairs = [(a, b) for a in tasks for b in tasks if a != b
                 and tasks[a].workers_required + tasks[b].workers_required > capacity]
        if not pairs:
            return None
        a, b = rng.choice(pairs)
        length = by_id[b]['finish_time'] - by_id[b]['start_time']
        by_id[b]['start_time'] = by_id[a]['start_time']
        by_id[b]['finish_time'] = by_id[b]['start_time'] + length
        return entries, 'capacity', f"day {by_id[a]['start_time']}"
    raise AssertionError(f'unknown corruption kind {kind}')


class ValidatorTests(unittest.TestCase):
    """Requirements 9.2 to 9.6: the schedule validator rejects corrupted schedules."""

    KINDS = ('missing', 'duplicate', 'unknown', 'duration', 'dependency', 'capacity')

    def test_baseline_valid_schedule_has_no_violations(self):
        tasks = load_tasks(TASKS_PATH, 2)
        entries = ucs_search(tasks, 2)['schedule']
        self.assertEqual(find_violations(entries, tasks, 2), [])
        self.assertEqual(check_schedule(entries, tasks, 2), (True, None))

    # Feature: phase2-search-algorithms, Property 7: The validator rejects corrupted schedules
    def test_property_7_validator_rejects_corrupted_schedules(self):
        """**Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6**"""
        rng = random.Random(SEED)
        applied = dict.fromkeys(self.KINDS, 0)
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            entries = ucs_search(tasks, capacity)['schedule']
            base = f'case={case} capacity={capacity} tasks={list(tasks.values())}'
            self.assertEqual(find_violations(entries, tasks, capacity), [], msg=f'valid base; {base}')
            self.assertEqual(check_schedule(entries, tasks, capacity), (True, None), msg=base)
            for kind in self.KINDS:
                corrupted = corrupt_schedule(kind, entries, tasks, capacity, rng)
                if corrupted is None:
                    continue
                bad, vtype, mention = corrupted
                applied[kind] += 1
                msg = f'{base} corruption={kind} schedule={bad}'
                problems = find_violations(bad, tasks, capacity)
                matching = [p for p in problems if p.startswith(vtype + ':') and mention in p]
                self.assertTrue(matching, msg=f'no {vtype} violation naming {mention}; got {problems}; {msg}')
                valid, text = check_schedule(bad, tasks, capacity)
                self.assertFalse(valid, msg=msg)
                self.assertTrue(text, msg=msg)
        for kind, count in applied.items():
            self.assertGreater(count, 0, msg=f'corruption {kind} was never applied')


class HelperBehaviorTests(unittest.TestCase):
    """Unit tests for search_common behavior (Requirements 2.1 to 2.4, 9.7, 10.2)."""

    def setUp(self):
        self.tasks = {
            'T01': Task('T01', 2, (), 1),
            'T02': Task('T02', 1, ('T01',), 1),
        }
        self.capacity = 1
        self.searches = (
            ('BFS', bfs_search), ('UCS', ucs_search),
            ('Greedy', greedy_search), ('A*', astar_search),
        )

    def test_validator_crash_gives_invalid_schedule(self):
        """9.7: a non-ValueError from validate_schedule is never reported as success."""
        with mock.patch.object(search_common, 'validate_schedule',
                               side_effect=RuntimeError('boom')):
            result = ucs_search(self.tasks, self.capacity)
        self.assertFalse(result['schedule_valid'])
        self.assertIn('validation could not be completed', result['error'])
        self.assertNotEqual(result['status'], 'solved')

    def test_check_schedule_reports_validator_crash(self):
        with mock.patch.object(search_common, 'validate_schedule',
                               side_effect=KeyError('x')):
            valid, text = check_schedule([], self.tasks, self.capacity)
        self.assertFalse(valid)
        self.assertIn('validation could not be completed', text)

    def test_tiny_timeout_with_patched_clock_returns_timeout(self):
        """10.2: the clock jumps 1 second per call, so a 0.5 s limit trips at once."""
        ticks = itertools.count()
        with mock.patch.object(search_common.time, 'perf_counter',
                               side_effect=lambda: float(next(ticks))):
            for name, run in self.searches:
                result = run(self.tasks, self.capacity, timeout_seconds=0.5)
                self.assertEqual(result['status'], 'timeout', msg=name)
                self.assertEqual(result['schedule'], [], msg=name)
                self.assertIsNone(result['makespan'], msg=name)
                self.assertFalse(result['schedule_valid'], msg=name)

    def test_tiny_expansion_limit_returns_state_limit(self):
        """Phase 3 1.2: max_expansions=1 stops every algorithm before the goal."""
        for name, run in self.searches:
            result = run(self.tasks, self.capacity, max_expansions=1)
            self.assertEqual(result['status'], 'state_limit', msg=name)
            self.assertEqual(result['schedule'], [], msg=name)
            self.assertIsNone(result['makespan'], msg=name)
            self.assertFalse(result['schedule_valid'], msg=name)
            self.assertEqual(result['states_explored'], 1, msg=name)

    def test_limit_stop_is_never_solved_and_none_means_unlimited(self):
        for name, run in self.searches:
            for limit in (0, 1):
                self.assertNotEqual(run(self.tasks, self.capacity, max_expansions=limit)['status'],
                                    'solved', msg=f'{name} limit={limit}')
            self.assertEqual(run(self.tasks, self.capacity, max_expansions=None)['status'],
                             'solved', msg=name)
            self.assertEqual(run(self.tasks, self.capacity, max_expansions=100)['status'],
                             'solved', msg=name)

    def test_one_initial_state_call_and_goal_only_via_is_goal(self):
        """2.1 to 2.3: one initial_state() call per run; goal decided by is_goal()."""
        for name, run in self.searches:
            goal_answers = []

            def spy_goal(state, tasks):
                answer = is_goal(state, tasks)
                goal_answers.append(answer)
                return answer

            with mock.patch.object(search_common, 'initial_state',
                                   wraps=initial_state) as init_spy, \
                    mock.patch.object(search_common, 'is_goal', side_effect=spy_goal):
                result = run(self.tasks, self.capacity)
            self.assertEqual(init_spy.call_count, 1, msg=name)
            self.assertEqual(result['status'], 'solved', msg=name)
            self.assertTrue(goal_answers and goal_answers[-1], msg=name)
            self.assertFalse(any(goal_answers[:-1]), msg=name)

    def test_goal_is_never_inferred_when_is_goal_says_no(self):
        """2.3: if is_goal never says True, the search cannot report 'solved'."""
        for name, run in self.searches:
            with mock.patch.object(search_common, 'is_goal', return_value=False):
                result = run(self.tasks, self.capacity)
            self.assertEqual(result['status'], 'no solution', msg=name)
            self.assertFalse(result['schedule_valid'], msg=name)

    def test_algorithm_modules_never_call_open(self):
        """2.4: the four algorithm modules read no files."""
        for module in (bfs, ucs, greedy, astar):
            source = inspect.getsource(module)
            self.assertNotIn('open(', source, msg=module.__name__)

def make_invalid_input(kind, tasks, capacity, rng):
    """Break a valid dataset in one way. Return (tasks, capacity, word the error must contain)."""
    tasks = dict(tasks)
    ids = sorted(tasks)
    if kind == 'empty':
        return {}, capacity, 'empty'
    if kind == 'unknown':
        victim = tasks[rng.choice(ids)]
        tasks[victim.task_id] = Task(victim.task_id, victim.duration,
                                     victim.dependencies + ('T99',), victim.workers_required)
        return tasks, capacity, 'unknown'
    if kind == 'cycle':
        first = tasks[ids[0]]
        last = tasks[ids[-1]]
        if first.task_id == last.task_id:
            tasks[first.task_id] = Task(first.task_id, first.duration,
                                        (first.task_id,), first.workers_required)
            return tasks, capacity, 'self-dependency'
        else:
            # make the first task depend on the last; the last reaches the first
            tasks[last.task_id] = Task(last.task_id, last.duration,
                                       tuple(sorted(set(last.dependencies) | {first.task_id})),
                                       last.workers_required)
            tasks[first.task_id] = Task(first.task_id, first.duration,
                                        (last.task_id,), first.workers_required)
        return tasks, capacity, 'cycle'
    if kind == 'over_capacity':
        victim = tasks[rng.choice(ids)]
        tasks[victim.task_id] = Task(victim.task_id, victim.duration,
                                     victim.dependencies, capacity + rng.randint(1, 2))
        return tasks, capacity, victim.task_id
    if kind == 'bad_capacity':
        return tasks, rng.choice([0, -1, -5, 2.5, '2', None]), 'capacity'
    raise AssertionError(f'unknown invalid kind {kind}')
class InvalidInputTests(unittest.TestCase):
    """Requirements 2.7, 2.8, 2.9, 10.3, 11.8: bad input is rejected before any search."""
    KINDS = ('empty', 'unknown', 'cycle', 'over_capacity', 'bad_capacity')
    SEARCHES = (('BFS', bfs_search), ('UCS', ucs_search),
                ('Greedy', greedy_search), ('A*', astar_search))
    def check_rejected(self, name, run, tasks, capacity, word, label):
        with mock.patch.object(search_common, 'successors') as spy:
            result = run(tasks, capacity)
        msg = f'{label} algorithm={name} result={result}'
        spy.assert_not_called()
        self.assertEqual(result['status'], 'invalid input', msg=msg)
        self.assertEqual(result['states_explored'], 0, msg=msg)
        self.assertIsNone(result['makespan'], msg=msg)
        self.assertEqual(result['schedule'], [], msg=msg)
        self.assertIs(result['schedule_valid'], False, msg=msg)
        self.assertTrue(result['error'], msg=msg)
        self.assertIn(word, result['error'], msg=msg)
    def test_over_capacity_task_names_the_task(self):
        tasks = load_tasks(TASKS_PATH, 2)
        t05 = tasks['T05']
        tasks['T05'] = Task('T05', t05.duration, t05.dependencies, 3)
        for name, run in self.SEARCHES:
            self.check_rejected(name, run, tasks, 2, 'T05', 'baseline T05 needs 3 workers')
    # Feature: phase2-search-algorithms, Property 3: Invalid input is rejected without searching
    def test_property_3_invalid_input_rejected_without_searching(self):
        """**Validates: Requirements 2.7, 2.8, 2.9, 10.3, 11.8**"""
        rng = random.Random(SEED)
        applied = dict.fromkeys(self.KINDS, 0)
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            kind = self.KINDS[case % len(self.KINDS)]
            bad_tasks, bad_capacity, word = make_invalid_input(kind, tasks, capacity, rng)
            applied[kind] += 1
            label = f'case={case} kind={kind} capacity={bad_capacity!r} tasks={list(bad_tasks.values())}'
            for name, run in self.SEARCHES:
                self.check_rejected(name, run, bad_tasks, bad_capacity, word, label)
        for kind, count in applied.items():
            self.assertGreater(count, 0, msg=f'invalid kind {kind} was never applied')



class ResultShapeTests(unittest.TestCase):
    """Requirements 8.7, 8.9, 10.1, 10.4, 10.5, 10.6: every result has the required shape."""

    REQUIRED_KEYS = ('algorithm', 'makespan', 'schedule', 'states_explored',
                     'execution_time_ms', 'schedule_valid', 'status', 'states_generated')
    STATUSES = ('solved', 'no solution', 'timeout', 'state_limit', 'invalid input')
    SEARCHES = (('BFS', bfs_search), ('UCS', ucs_search),
                ('Greedy', greedy_search), ('A*', astar_search))

    def check_shape(self, result, label):
        for key in self.REQUIRED_KEYS:
            self.assertIn(key, result, msg=f'missing key {key}; {label}')
        self.assertIn(result['status'], self.STATUSES, msg=label)
        states = result['states_explored']
        self.assertIsInstance(states, int, msg=label)
        self.assertNotIsInstance(states, bool, msg=label)
        self.assertGreaterEqual(states, 0, msg=label)
        generated = result['states_generated']
        self.assertIsInstance(generated, int, msg=label)
        self.assertNotIsInstance(generated, bool, msg=label)
        self.assertGreaterEqual(generated, 0, msg=label)
        elapsed = result['execution_time_ms']
        self.assertIsInstance(elapsed, (int, float), msg=label)
        self.assertGreaterEqual(elapsed, 0, msg=label)
        self.assertIsInstance(result['schedule_valid'], bool, msg=label)
        if result['status'] == 'solved':
            self.assertIs(result['schedule_valid'], True, msg=label)
            self.assertIsInstance(result['makespan'], (int, float), msg=label)
            self.assertGreaterEqual(result['makespan'], 0, msg=label)
            self.assertTrue(result['schedule'], msg=label)
        else:
            self.assertIsNone(result['makespan'], msg=label)
            self.assertEqual(result['schedule'], [], msg=label)
            self.assertIs(result['schedule_valid'], False, msg=label)

    def test_baseline_solved_result_shape(self):
        tasks = load_tasks(TASKS_PATH, 2)
        for name, run in self.SEARCHES:
            result = run(tasks, 2)
            self.assertEqual(result['status'], 'solved', msg=name)
            self.check_shape(result, f'baseline algorithm={name}')

    # Feature: phase2-search-algorithms, Property 4: Results always have the required shape
    def test_property_4_results_always_have_required_shape(self):
        """**Validates: Requirements 8.7, 8.9, 10.1, 10.4, 10.5, 10.6**"""
        rng = random.Random(SEED)
        kinds = InvalidInputTests.KINDS
        seen_status = set()
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            base = f'case={case} capacity={capacity} tasks={list(tasks.values())}'
            bad_kind = kinds[case % len(kinds)]
            bad_tasks, bad_capacity, _ = make_invalid_input(bad_kind, tasks, capacity, rng)
            for name, run in self.SEARCHES:
                # solved
                result = run(tasks, capacity)
                self.check_shape(result, f'{base} algorithm={name} scenario=solved')
                seen_status.add(result['status'])
                # invalid input
                result = run(bad_tasks, bad_capacity)
                self.check_shape(result, f'{base} algorithm={name} scenario=invalid:{bad_kind}')
                seen_status.add(result['status'])
                # no solution: a model that offers no successors
                with mock.patch.object(search_common, 'successors', return_value=()):
                    result = run(tasks, capacity)
                self.check_shape(result, f'{base} algorithm={name} scenario=no solution')
                seen_status.add(result['status'])
                # timeout: the clock advances 1 s per reading, limit is 0.5 s
                ticks = itertools.count()
                with mock.patch.object(search_common.time, 'perf_counter',
                                       side_effect=lambda: float(next(ticks))):
                    result = run(tasks, capacity, timeout_seconds=0.5)
                self.check_shape(result, f'{base} algorithm={name} scenario=timeout')
                seen_status.add(result['status'])
                # state_limit: stop after one expansion
                result = run(tasks, capacity, max_expansions=1)
                self.check_shape(result, f'{base} algorithm={name} scenario=state_limit')
                seen_status.add(result['status'])
        self.assertEqual(seen_status, set(self.STATUSES))


class ScheduleConsistencyTests(unittest.TestCase):
    """Requirements 3.3, 8.1 to 8.4, 8.8: a solved schedule is internally consistent."""

    SEARCHES = (('BFS', bfs_search), ('UCS', ucs_search),
                ('Greedy', greedy_search), ('A*', astar_search))

    def run_with_path(self, run, tasks, capacity):
        """Run a search and also capture the actions of the returned path."""
        captured = []
        original = search_common.reconstruct_schedule

        def spy(actions):
            captured.append(list(actions))
            return original(actions)

        with mock.patch.object(search_common, 'reconstruct_schedule', side_effect=spy):
            result = run(tasks, capacity)
        return result, (captured[-1] if captured else None)

    def check_consistent(self, result, actions, tasks, label):
        self.assertEqual(result['status'], 'solved', msg=label)
        schedule = result['schedule']
        ids = [e['task_id'] for e in schedule]
        self.assertEqual(sorted(ids), sorted(tasks), msg=f'one entry per task; {label}')
        self.assertEqual(len(ids), len(set(ids)), msg=f'duplicate entry; {label}')
        for entry in schedule:
            msg = f'entry={entry}; {label}'
            self.assertGreaterEqual(entry['start_time'], 0, msg=msg)
            self.assertEqual(entry['finish_time'] - entry['start_time'],
                             tasks[entry['task_id']].duration, msg=msg)
        self.assertEqual(result['makespan'], max(e['finish_time'] for e in schedule), msg=label)
        self.assertIsNotNone(actions, msg=f'path not captured; {label}')
        self.assertEqual(result['makespan'], sum(a.elapsed_days for a in actions), msg=label)

    def test_baseline_schedule_is_consistent(self):
        tasks = load_tasks(TASKS_PATH, 2)
        for name, run in self.SEARCHES:
            result, actions = self.run_with_path(run, tasks, 2)
            self.check_consistent(result, actions, tasks, f'baseline algorithm={name}')

    # Feature: phase2-search-algorithms, Property 5: Reconstructed schedules are internally consistent
    def test_property_5_reconstructed_schedules_are_internally_consistent(self):
        """**Validates: Requirements 3.3, 8.1, 8.2, 8.3, 8.4, 8.8**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            for name, run in self.SEARCHES:
                label = (f'case={case} algorithm={name} capacity={capacity} '
                         f'tasks={list(tasks.values())}')
                result, actions = self.run_with_path(run, tasks, capacity)
                self.check_consistent(result, actions, tasks, label)
                checked += 1
        self.assertGreaterEqual(checked, CASES)


class ScheduleValidityTests(unittest.TestCase):
    """Requirements 9.1, 9.8, 11.6, 14.6: every returned schedule is valid."""

    SEARCHES = (('BFS', bfs_search), ('UCS', ucs_search),
                ('Greedy', greedy_search), ('A*', astar_search))

    def check_valid(self, result, tasks, capacity, label):
        self.assertEqual(result['status'], 'solved', msg=label)
        schedule = result['schedule']
        by_id = {e['task_id']: e for e in schedule}
        # Dependencies: each task starts no earlier than every prerequisite finishes.
        for task_id, task in tasks.items():
            for dep in task.dependencies:
                self.assertGreaterEqual(by_id[task_id]['start_time'], by_id[dep]['finish_time'],
                                        msg=f'{task_id} starts before {dep} finishes; {label}')
        # Capacity: workers of tasks active on each day never exceed capacity.
        last_day = max(e['finish_time'] for e in schedule)
        for day in range(last_day):
            used = sum(tasks[e['task_id']].workers_required for e in schedule
                       if e['start_time'] <= day < e['finish_time'])
            self.assertLessEqual(used, capacity, msg=f'day {day} uses {used}; {label}')
        # Phase 1 validator and the result flag agree.
        self.assertEqual(find_violations(schedule, tasks, capacity), [], msg=label)
        self.assertEqual(check_schedule(schedule, tasks, capacity), (True, None), msg=label)
        self.assertIs(result['schedule_valid'], True, msg=label)

    def test_baseline_schedules_are_valid(self):
        tasks = load_tasks(TASKS_PATH, 2)
        for name, run in self.SEARCHES:
            self.check_valid(run(tasks, 2), tasks, 2, f'baseline algorithm={name}')

    # Feature: phase2-search-algorithms, Property 6: Every returned schedule satisfies dependencies and capacity
    def test_property_6_every_returned_schedule_satisfies_dependencies_and_capacity(self):
        """**Validates: Requirements 9.1, 9.8, 11.6, 14.6**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            for name, run in self.SEARCHES:
                label = (f'case={case} algorithm={name} capacity={capacity} '
                         f'tasks={list(tasks.values())}')
                self.check_valid(run(tasks, capacity), tasks, capacity, label)
                checked += 1
        self.assertGreaterEqual(checked, CASES)


class UcsOptimalityTests(unittest.TestCase):
    """Requirement 5.5: UCS returns the true minimum makespan."""

    def test_baseline_ucs_matches_brute_force(self):
        tasks = load_tasks(TASKS_PATH, 2)
        result = ucs_search(tasks, 2)
        self.assertEqual(result['makespan'], best_makespan(tasks, 2, forced_start=False))
        self.assertEqual(result['makespan'], 11)

    # Feature: phase2-search-algorithms, Property 8: UCS finds the true minimum makespan
    def test_property_8_ucs_finds_true_minimum_makespan(self):
        """**Validates: Requirements 5.5**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            label = f'case={case} capacity={capacity} tasks={list(tasks.values())}'
            expected = best_makespan(tasks, capacity, forced_start=False)
            result = ucs_search(tasks, capacity)
            self.assertEqual(result['status'], 'solved', msg=label)
            self.assertIsNotNone(expected, msg=f'brute force found no schedule; {label}')
            self.assertEqual(result['makespan'], expected,
                             msg=f'UCS={result["makespan"]} brute force={expected}; {label}')
            checked += 1
        self.assertGreaterEqual(checked, CASES)


class AstarVersusUcsTests(unittest.TestCase):
    """Requirements 7.5, 14.3, 11.2: A* with an admissible heuristic matches UCS."""

    HEURISTICS = (zero_heuristic, longest_remaining, critical_path_remaining,
                  workload_remaining, combined_heuristic)

    def test_baseline_astar_matches_ucs_for_all_heuristics(self):
        tasks = load_tasks(TASKS_PATH, 2)
        expected = ucs_search(tasks, 2)['makespan']
        self.assertEqual(expected, 11)
        for h in self.HEURISTICS:
            result = astar_search(tasks, 2, heuristic=h)
            self.assertEqual(result['makespan'], expected, msg=h.__name__)

    # Feature: phase2-search-algorithms, Property 9: A* with an admissible heuristic matches UCS
    def test_property_9_astar_with_admissible_heuristic_matches_ucs(self):
        """**Validates: Requirements 7.5, 14.3, 11.2**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            ucs_result = ucs_search(tasks, capacity)
            for h in self.HEURISTICS:
                label = (f'case={case} heuristic={h.__name__} capacity={capacity} '
                         f'tasks={list(tasks.values())}')
                result = astar_search(tasks, capacity, heuristic=h)
                self.assertEqual(result['status'], 'solved', msg=label)
                self.assertEqual(result['makespan'], ucs_result['makespan'],
                                 msg=f'A*={result["makespan"]} UCS={ucs_result["makespan"]}; {label}')
                self.assertIs(result['schedule_valid'], True, msg=label)
                checked += 1
        self.assertGreaterEqual(checked, CASES)


def min_transitions(tasks, capacity):
    """Independent layered breadth-first reference: fewest transitions to any goal state."""
    start = initial_state()
    seen = {start}
    layer = [start]
    depth = 0
    while layer:
        if any(is_goal(s, tasks) for s in layer):
            return depth
        following = []
        for state in layer:
            for succ in successors(state, tasks, capacity):
                if succ.state not in seen:
                    seen.add(succ.state)
                    following.append(succ.state)
        layer = following
        depth += 1
    return None


class BfsMinimalTransitionsTests(unittest.TestCase):
    """Requirement 4.3: BFS returns a schedule with the fewest transitions."""

    def test_baseline_bfs_matches_reference(self):
        tasks = load_tasks(TASKS_PATH, 2)
        result = bfs_search(tasks, 2)
        self.assertEqual(result['status'], 'solved')
        self.assertEqual(result['transitions'], min_transitions(tasks, 2))

    # Feature: phase2-search-algorithms, Property 11: BFS minimises the number of transitions
    def test_property_11_bfs_minimises_number_of_transitions(self):
        """**Validates: Requirements 4.3**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            label = f'case={case} capacity={capacity} tasks={list(tasks.values())}'
            expected = min_transitions(tasks, capacity)
            self.assertIsNotNone(expected, msg=f'reference found no goal; {label}')
            result = bfs_search(tasks, capacity)
            self.assertEqual(result['status'], 'solved', msg=label)
            self.assertEqual(result['transitions'], expected,
                             msg=f'BFS={result["transitions"]} reference={expected}; {label}')
            checked += 1
        self.assertGreaterEqual(checked, CASES)


class MakespanOrderingTests(unittest.TestCase):
    """Requirements 4.5, 6.7, 12.8, 14.4, 14.5: UCS is minimal, BFS and Greedy are no better."""

    def test_baseline_ordering(self):
        tasks = load_tasks(TASKS_PATH, 2)
        ucs_makespan = ucs_search(tasks, 2)['makespan']
        self.assertGreaterEqual(ucs_makespan, combined_lower_bound(tasks, 2))
        self.assertGreaterEqual(bfs_search(tasks, 2)['makespan'], ucs_makespan)
        self.assertGreaterEqual(greedy_search(tasks, 2)['makespan'], ucs_makespan)

    # Feature: phase2-search-algorithms, Property 12: Makespan ordering across algorithms
    def test_property_12_makespan_ordering_across_algorithms(self):
        """**Validates: Requirements 4.5, 6.7, 12.8, 14.4, 14.5**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            label = f'case={case} capacity={capacity} tasks={list(tasks.values())}'
            results = {
                'UCS': ucs_search(tasks, capacity),
                'BFS': bfs_search(tasks, capacity),
                'Greedy': greedy_search(tasks, capacity),
            }
            for name, result in results.items():
                self.assertEqual(result['status'], 'solved', msg=f'{name}; {label}')
            ucs_makespan = results['UCS']['makespan']
            bound = combined_lower_bound(tasks, capacity)
            self.assertGreaterEqual(ucs_makespan, bound,
                                    msg=f'UCS={ucs_makespan} bound={bound}; {label}')
            for name in ('BFS', 'Greedy'):
                self.assertGreaterEqual(results[name]['makespan'], ucs_makespan,
                                        msg=f'{name}={results[name]["makespan"]} '
                                            f'UCS={ucs_makespan}; {label}')
            checked += 1
        self.assertGreaterEqual(checked, CASES)


class DeterminismTests(unittest.TestCase):
    """Requirements 6.2, 14.7: running a search twice gives identical output."""

    SEARCHES = (('BFS', bfs_search), ('UCS', ucs_search),
                ('Greedy', greedy_search), ('A*', astar_search))

    def check_same(self, run, tasks, capacity, label):
        first = run(tasks, capacity)
        second = run(tasks, capacity)
        self.assertEqual(first['makespan'], second['makespan'], msg=f'makespan; {label}')
        self.assertEqual(first['schedule'], second['schedule'], msg=f'schedule; {label}')
        self.assertEqual(first['states_explored'], second['states_explored'],
                         msg=f'states_explored; {label}')

    def test_baseline_runs_are_repeatable(self):
        tasks = load_tasks(TASKS_PATH, 2)
        for name, run in self.SEARCHES:
            self.check_same(run, tasks, 2, f'baseline algorithm={name}')

    # Feature: phase2-search-algorithms, Property 14: Searches are deterministic
    def test_property_14_searches_are_deterministic(self):
        """**Validates: Requirements 6.2, 14.7**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            for name, run in self.SEARCHES:
                label = (f'case={case} algorithm={name} capacity={capacity} '
                         f'tasks={list(tasks.values())}')
                self.check_same(run, tasks, capacity, label)
                checked += 1
        self.assertGreaterEqual(checked, CASES)


class CountingRuleTests(unittest.TestCase):
    """Requirement 8.5: states_explored equals the number of successors() calls."""

    SEARCHES = (('BFS', bfs_search), ('UCS', ucs_search),
                ('Greedy', greedy_search), ('A*', astar_search))

    def check_count(self, run, tasks, capacity, label):
        with mock.patch.object(search_common, 'successors', wraps=successors) as spy:
            result = run(tasks, capacity)
        self.assertEqual(result['states_explored'], spy.call_count,
                         msg=f'states_explored={result["states_explored"]} '
                             f'successors calls={spy.call_count}; {label}')
        return result

    def test_baseline_count_matches_calls(self):
        tasks = load_tasks(TASKS_PATH, 2)
        for name, run in self.SEARCHES:
            result = self.check_count(run, tasks, 2, f'baseline algorithm={name}')
            self.assertGreater(result['states_explored'], 0, msg=name)

    # Feature: phase2-search-algorithms, Property 15: One counting rule for states explored
    def test_property_15_one_counting_rule_for_states_explored(self):
        """**Validates: Requirements 8.5**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            for name, run in self.SEARCHES:
                label = (f'case={case} algorithm={name} capacity={capacity} '
                         f'tasks={list(tasks.values())}')
                result = self.check_count(run, tasks, capacity, label)
                self.assertEqual(result['status'], 'solved', msg=label)
                checked += 1
        self.assertGreaterEqual(checked, CASES)


class NoRepeatedExpansionTests(unittest.TestCase):
    """Requirements 4.2, 6.5: BFS and Greedy never expand the same state twice."""

    SEARCHES = (('BFS', bfs_search), ('Greedy', greedy_search))

    def expanded_states(self, run, tasks, capacity):
        """Run a search and return (result, list of states passed to successors())."""
        expanded = []

        def spy(state, tasks_arg, capacity_arg):
            expanded.append(state)
            return successors(state, tasks_arg, capacity_arg)

        with mock.patch.object(search_common, 'successors', side_effect=spy):
            result = run(tasks, capacity)
        return result, expanded

    def test_baseline_no_state_expanded_twice(self):
        tasks = load_tasks(TASKS_PATH, 2)
        for name, run in self.SEARCHES:
            result, expanded = self.expanded_states(run, tasks, 2)
            self.assertEqual(result['status'], 'solved', msg=name)
            self.assertEqual(len(expanded), len(set(expanded)), msg=name)

    # Feature: phase2-search-algorithms, Property 16: BFS and Greedy never expand a state twice
    def test_property_16_bfs_and_greedy_never_expand_a_state_twice(self):
        """**Validates: Requirements 4.2, 6.5**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_dataset(rng)
            for name, run in self.SEARCHES:
                label = (f'case={case} algorithm={name} capacity={capacity} '
                         f'tasks={list(tasks.values())}')
                result, expanded = self.expanded_states(run, tasks, capacity)
                self.assertEqual(result['status'], 'solved', msg=label)
                repeated = [s for s in set(expanded) if expanded.count(s) > 1]
                self.assertEqual(repeated, [], msg=f'repeated expansion {repeated}; {label}')
                self.assertEqual(result['states_explored'], len(expanded), msg=label)
                checked += 1
        self.assertGreaterEqual(checked, CASES)


def random_chain(rng, max_tasks=6, max_duration=4):
    """Return (tasks, capacity) for a single dependency chain T01 <- T02 <- ..."""
    capacity = rng.randint(1, 3)
    count = rng.randint(1, max_tasks)
    tasks = {}
    for index in range(count):
        task_id = f'T{index + 1:02d}'
        deps = (f'T{index:02d}',) if index else ()
        tasks[task_id] = Task(task_id, rng.randint(1, max_duration), deps,
                              rng.randint(1, capacity))
    validate_tasks(tasks, capacity)
    return tasks, capacity


class ChainDatasetTests(unittest.TestCase):
    """Requirement 11.7: a single dependency chain runs strictly in sequence."""

    SEARCHES = (('BFS', bfs_search), ('UCS', ucs_search),
                ('Greedy', greedy_search), ('A*', astar_search))

    def check_chain(self, result, tasks, label):
        self.assertEqual(result['status'], 'solved', msg=label)
        by_id = {e['task_id']: e for e in result['schedule']}
        self.assertEqual(sorted(by_id), sorted(tasks), msg=label)
        for task_id, task in tasks.items():
            if task.dependencies:
                self.assertEqual(by_id[task_id]['start_time'],
                                 by_id[task.dependencies[0]]['finish_time'],
                                 msg=f'{task_id} not starting when prerequisite finishes; {label}')
            else:
                self.assertEqual(by_id[task_id]['start_time'], 0, msg=label)
        self.assertEqual(result['makespan'], sum(t.duration for t in tasks.values()), msg=label)

    def test_fixed_chain(self):
        tasks = {
            'T01': Task('T01', 2, (), 1),
            'T02': Task('T02', 3, ('T01',), 2),
            'T03': Task('T03', 1, ('T02',), 1),
        }
        for name, run in self.SEARCHES:
            self.check_chain(run(tasks, 2), tasks, f'fixed chain algorithm={name}')

    # Feature: phase2-search-algorithms, Property 17: Chain datasets run strictly in sequence
    def test_property_17_chain_datasets_run_strictly_in_sequence(self):
        """**Validates: Requirements 11.7**"""
        rng = random.Random(SEED)
        checked = 0
        for case in range(CASES):
            tasks, capacity = random_chain(rng)
            for name, run in self.SEARCHES:
                label = (f'case={case} algorithm={name} capacity={capacity} '
                         f'tasks={list(tasks.values())}')
                self.check_chain(run(tasks, capacity), tasks, label)
                checked += 1
        self.assertGreaterEqual(checked, CASES)


class ScenarioTests(unittest.TestCase):
    """Task 2.17: reference makespans, failure statuses and tie-break order."""

    SEARCHES = (('BFS', bfs_search), ('UCS', ucs_search),
                ('Greedy', greedy_search), ('A*', astar_search))
    HEURISTICS = (zero_heuristic, longest_remaining, critical_path_remaining,
                  workload_remaining, combined_heuristic)

    def baseline(self, capacity, t05_duration=None):
        tasks = load_tasks(TASKS_PATH, capacity)
        if t05_duration is not None:
            t05 = tasks['T05']
            tasks['T05'] = Task('T05', t05_duration, t05.dependencies, t05.workers_required)
        validate_tasks(tasks, capacity)
        return tasks

    def check_makespans(self, tasks, capacity, expected, scenario):
        """Requirements 11.1 to 11.5: UCS and A* (every admissible heuristic) hit `expected`."""
        result = ucs_search(tasks, capacity)
        self.assertEqual(result['status'], 'solved', msg=f'{scenario} UCS')
        self.assertEqual(result['makespan'], expected, msg=f'{scenario} algorithm=UCS')
        self.assertIs(result['schedule_valid'], True, msg=f'{scenario} algorithm=UCS')
        for h in self.HEURISTICS:
            result = astar_search(tasks, capacity, heuristic=h)
            name = f'{scenario} algorithm=A* heuristic={h.__name__}'
            self.assertEqual(result['status'], 'solved', msg=name)
            self.assertEqual(result['makespan'], expected, msg=name)
            self.assertIs(result['schedule_valid'], True, msg=name)
        default = astar_search(tasks, capacity)
        self.assertEqual(default['makespan'], expected, msg=f'{scenario} A* default heuristic')

    def test_baseline_two_workers_is_11(self):
        self.check_makespans(self.baseline(2), 2, 11, 'baseline 2 workers')

    def test_baseline_one_worker_is_15(self):
        self.check_makespans(self.baseline(1), 1, 15, 'baseline 1 worker')

    def test_baseline_three_workers_is_9(self):
        self.check_makespans(self.baseline(3), 3, 9, 'baseline 3 workers')

    def test_baseline_t05_duration_3_is_12(self):
        self.check_makespans(self.baseline(2, t05_duration=3), 2, 12, 'baseline T05 duration 3')

    def test_baseline_bfs_and_greedy_valid_and_not_below_optimum(self):
        tasks = self.baseline(2)
        for name, run in self.SEARCHES:
            result = run(tasks, 2)
            self.assertEqual(result['status'], 'solved', msg=name)
            self.assertIs(result['schedule_valid'], True, msg=f'{name} schedule_valid')
            self.assertEqual(find_violations(result['schedule'], tasks, 2), [], msg=name)
            if name in ('BFS', 'Greedy'):
                self.assertGreaterEqual(result['makespan'], 11, msg=name)

    def test_independent_tasks_never_exceed_capacity(self):
        """Requirement 11.6."""
        tasks = {
            'T01': Task('T01', 2, (), 1),
            'T02': Task('T02', 3, (), 2),
            'T03': Task('T03', 1, (), 1),
            'T04': Task('T04', 2, (), 2),
        }
        validate_tasks(tasks, 2)
        checker = ScheduleValidityTests()
        for name, run in self.SEARCHES:
            checker.check_valid(run(tasks, 2), tasks, 2, f'independent tasks algorithm={name}')

    def test_over_capacity_task_is_invalid_input_and_never_searched(self):
        """Requirement 11.8."""
        tasks = self.baseline(2)
        t05 = tasks['T05']
        tasks['T05'] = Task('T05', t05.duration, t05.dependencies, 3)
        for name, run in self.SEARCHES:
            with mock.patch.object(search_common, 'successors') as spy, \
                    mock.patch.object(search_common, 'initial_state') as init_spy:
                result = run(tasks, 2)
            spy.assert_not_called()
            init_spy.assert_not_called()
            self.assertEqual(result['status'], 'invalid input', msg=name)
            self.assertEqual(result['states_explored'], 0, msg=name)
            self.assertIn('T05', result['error'], msg=name)

    def test_no_solution_when_model_offers_no_successors(self):
        """Requirement 11.9."""
        tasks = self.baseline(2)
        for name, run in self.SEARCHES:
            with mock.patch.object(search_common, 'successors', return_value=()):
                result = run(tasks, 2)
            self.assertEqual(result['status'], 'no solution', msg=name)
            self.assertEqual(result['schedule'], [], msg=name)
            self.assertIsNone(result['makespan'], msg=name)
            self.assertIs(result['schedule_valid'], False, msg=name)

    # --- tie-break order (Requirements 6.2, 7.1) --------------------------------
    def two_independent_tasks(self):
        """Capacity 1, durations 1 and 2: the first expansion has two successors."""
        tasks = {'T01': Task('T01', 1, (), 1), 'T02': Task('T02', 2, (), 1)}
        validate_tasks(tasks, 1)
        first = successors(initial_state(), tasks, 1)
        by_task = {s.action.started: s.state for s in first}
        self.assertEqual(set(by_task), {('T01',), ('T02',)})
        return tasks, by_task[('T01',)], by_task[('T02',)]

    def expansion_order(self, run, tasks, heuristic):
        expanded = []

        def spy(state, tasks_arg, capacity_arg):
            expanded.append(state)
            return successors(state, tasks_arg, capacity_arg)

        with mock.patch.object(search_common, 'successors', side_effect=spy):
            run(tasks, 1, heuristic=heuristic)
        return expanded

    def test_greedy_equal_h_expands_in_insertion_order(self):
        tasks = {'T01': Task('T01', 2, (), 1), 'T02': Task('T02', 2, (), 1)}
        validate_tasks(tasks, 1)
        first = [s.state for s in successors(initial_state(), tasks, 1)]
        expanded = self.expansion_order(greedy_search, tasks, lambda s, t, c: 0)
        self.assertEqual(expanded[0], initial_state())
        self.assertEqual(expanded[1:3], first, msg=f'expanded={expanded}')

    def test_greedy_lower_h_expands_first_regardless_of_insertion(self):
        tasks, s1, s2 = self.two_independent_tasks()
        table = {s1: 5, s2: 1}
        expanded = self.expansion_order(greedy_search, tasks, lambda s, t, c: table.get(s, 9))
        self.assertEqual(expanded[1], s2, msg=f'expanded={expanded}')

    def test_astar_tie_on_f_prefers_lower_h(self):
        tasks, s1, s2 = self.two_independent_tasks()
        table = {s1: 3, s2: 2}  # f(s1) = 1 + 3 = 4, f(s2) = 2 + 2 = 4, s2 has the lower h
        expanded = self.expansion_order(astar_search, tasks, lambda s, t, c: table.get(s, 0))
        self.assertEqual(expanded[1], s2, msg=f'expanded={expanded}')

    def test_astar_tie_on_f_and_h_uses_insertion_order(self):
        """Two independent equal-length tasks give equal g, so f and h tie."""
        tasks = {'T01': Task('T01', 2, (), 1), 'T02': Task('T02', 2, (), 1)}
        validate_tasks(tasks, 1)
        first = [s.state for s in successors(initial_state(), tasks, 1)]
        expanded = self.expansion_order(astar_search, tasks, lambda s, t, c: 0)
        self.assertEqual(expanded[1:3], first, msg=f'expanded={expanded}')

    # --- seeded generation (Requirements 14.1, 14.2, 14.8) ----------------------
    def test_seeded_generation_is_repeatable_valid_and_large_enough(self):
        def build():
            rng = random.Random(SEED)
            return [random_dataset(rng, max_tasks=8) for _ in range(CASES)]

        first, second = build(), build()
        self.assertGreaterEqual(len(first), 100)
        self.assertEqual(first, second, msg='same seed must give the same datasets')
        for index, (tasks, capacity) in enumerate(first):
            label = f'dataset {index} capacity={capacity} tasks={list(tasks.values())}'
            self.assertTrue(1 <= len(tasks) <= 8, msg=label)
            try:
                validate_tasks(tasks, capacity)
            except ValueError as exc:
                self.fail(f'generated dataset failed validation ({exc}); {label}')

    def test_failure_message_names_dataset_algorithm_and_property(self):
        """Requirement 14.8: a failing property check reports what is needed to reproduce it."""
        tasks = {'T01': Task('T01', 1, (), 1)}
        label = f'case=0 algorithm=UCS property=makespan capacity=1 tasks={list(tasks.values())}'
        with self.assertRaises(AssertionError) as caught:
            self.assertEqual(1, 2, msg=label)
        text = str(caught.exception)
        for part in ('algorithm=UCS', 'property=makespan', 'T01'):
            self.assertIn(part, text)


def random_result_rows(rng):
    """Return a list of 0 to 8 random valid result dicts for the results CSV."""
    words = ['baseline_2w', 'a b', 'x,y', 'say "hi"', 'ünï', 'line\nbreak', ' pad ', 'T01']
    rows = []
    for _ in range(rng.randint(0, 8)):
        solved = rng.random() < 0.7
        rows.append({
            'scenario': rng.choice(words),
            'algorithm': rng.choice(['BFS', 'UCS', 'Greedy', 'A*', rng.choice(words)]),
            'makespan': rng.randint(0, 50) if solved else None,
            'states_explored': rng.randint(0, 10 ** 6),
            'execution_time_ms': rng.choice([
                0, rng.randint(0, 5000), rng.random() * 1000, rng.random() * 1e-7, 1e15 * rng.random()]),
            'schedule_valid': rng.random() < 0.5,
            'status': rng.choice(ALLOWED_STATUSES),
        })
    return rows


class CsvRoundTripTests(unittest.TestCase):
    """Requirements 13.1, 13.2, 13.3: writing then reading gives the same rows and bytes."""

    # Feature: phase2-search-algorithms, Property 18: Results CSV round trip
    def test_property_18_results_csv_round_trip(self):
        """**Validates: Requirements 13.1, 13.2, 13.3**"""
        rng = random.Random(SEED + 18)
        with tempfile.TemporaryDirectory() as folder:
            first = os.path.join(folder, 'first.csv')
            second = os.path.join(folder, 'second.csv')
            for case in range(CASES):
                rows = random_result_rows(rng)
                label = f'case={case} property=csv round trip rows={rows}'
                write_results_csv(first, rows)
                back = read_results_csv(first)
                expected = [dict(row, execution_time_ms=float(row['execution_time_ms'])) for row in rows]
                self.assertEqual(expected, back, msg=label)
                for got, want in zip(back, rows):
                    self.assertIs(type(got['schedule_valid']), bool, msg=label)
                    self.assertEqual(want['makespan'] is None, got['makespan'] is None, msg=label)
                write_results_csv(second, back)
                with open(first, 'rb') as one, open(second, 'rb') as two:
                    self.assertEqual(one.read(), two.read(), msg=label)
            self.assertEqual(sorted(os.listdir(folder)), ['first.csv', 'second.csv'])


class CsvErrorTests(unittest.TestCase):
    """Requirements 12.9, 13.4, 13.5, 13.6: CSV problems raise ResultsCsvError."""

    HEADER = ','.join(COLUMNS)
    GOOD_ROW = 'baseline_2w,ucs,11,50,1.5,true,solved'

    def _write(self, folder, name, text):
        path = os.path.join(folder, name)
        with open(path, 'w', encoding='utf-8', newline='') as handle:
            handle.write(text)
        return path

    def test_missing_header_column_is_named(self):
        """Requirement 13.4"""
        with tempfile.TemporaryDirectory() as folder:
            header = ','.join(c for c in COLUMNS if c != 'states_explored')
            path = self._write(folder, 'bad.csv', header + '\n')
            with self.assertRaises(ResultsCsvError) as ctx:
                read_results_csv(path)
            self.assertIn('states_explored', str(ctx.exception))

    def test_missing_value_in_row_3_names_row_and_column(self):
        """Requirement 13.5"""
        with tempfile.TemporaryDirectory() as folder:
            text = '\n'.join([self.HEADER, self.GOOD_ROW, self.GOOD_ROW,
                              'baseline_2w,ucs,11,,1.5,true,solved']) + '\n'
            path = self._write(folder, 'bad.csv', text)
            with self.assertRaises(ResultsCsvError) as ctx:
                read_results_csv(path)
            message = str(ctx.exception)
            self.assertIn('row 3', message)
            self.assertIn('states_explored', message)

    def test_short_row_names_row_and_first_absent_column(self):
        """Requirement 13.5"""
        with tempfile.TemporaryDirectory() as folder:
            text = '\n'.join([self.HEADER, self.GOOD_ROW, self.GOOD_ROW,
                              'baseline_2w,ucs,11,50']) + '\n'
            path = self._write(folder, 'bad.csv', text)
            with self.assertRaises(ResultsCsvError) as ctx:
                read_results_csv(path)
            message = str(ctx.exception)
            self.assertIn('row 3', message)
            self.assertIn('execution_time_ms', message)

    def test_nonexistent_source_raises(self):
        """Requirement 13.4"""
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'missing.csv')
            with self.assertRaises(ResultsCsvError) as ctx:
                read_results_csv(path)
            self.assertIn('missing.csv', str(ctx.exception))

    def test_unwritable_destination_raises_and_leaves_no_files(self):
        """Requirements 12.9, 13.6"""
        row = {'scenario': 's', 'algorithm': 'ucs', 'makespan': 3, 'states_explored': 1,
               'execution_time_ms': 0.5, 'schedule_valid': True, 'status': 'solved'}
        with tempfile.TemporaryDirectory() as folder:
            missing_dir = os.path.join(folder, 'no_such_dir', 'out.csv')
            with self.assertRaises(ResultsCsvError) as ctx:
                write_results_csv(missing_dir, [row])
            self.assertIn('out.csv', str(ctx.exception))
            self.assertFalse(os.path.exists(os.path.join(folder, 'no_such_dir')))

            directory_target = os.path.join(folder, 'a_directory')
            os.mkdir(directory_target)
            with self.assertRaises(ResultsCsvError):
                write_results_csv(directory_target, [row])
            self.assertEqual(sorted(os.listdir(folder)), ['a_directory'])
            self.assertEqual(os.listdir(directory_target), [])

    def test_existing_file_untouched_when_write_fails(self):
        """Requirements 12.9, 13.6"""
        good = {'scenario': 's', 'algorithm': 'ucs', 'makespan': 3, 'states_explored': 1,
                'execution_time_ms': 0.5, 'schedule_valid': True, 'status': 'solved'}
        bad_rows = [
            dict(good, status='bogus'),
            dict(good, states_explored=-1),
            {key: value for key, value in good.items() if key != 'makespan'},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'out.csv')
            write_results_csv(path, [good])
            with open(path, 'rb') as handle:
                before = handle.read()
            for rows in bad_rows:
                with self.assertRaises(ResultsCsvError):
                    write_results_csv(path, [good, rows])
                with open(path, 'rb') as handle:
                    self.assertEqual(before, handle.read())
                self.assertEqual(os.listdir(folder), ['out.csv'])

    def test_existing_file_untouched_when_replace_fails(self):
        """Requirements 12.9, 13.6: failure after the temp file is written."""
        good = {'scenario': 's', 'algorithm': 'ucs', 'makespan': 3, 'states_explored': 1,
                'execution_time_ms': 0.5, 'schedule_valid': True, 'status': 'solved'}
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'out.csv')
            write_results_csv(path, [good])
            with open(path, 'rb') as handle:
                before = handle.read()
            with mock.patch('scheduling.results_io.os.replace', side_effect=PermissionError(13, 'denied')):
                with self.assertRaises(ResultsCsvError):
                    write_results_csv(path, [dict(good, makespan=9)])
            with open(path, 'rb') as handle:
                self.assertEqual(before, handle.read())
            self.assertEqual(os.listdir(folder), ['out.csv'])


class ComparisonOutputTests(unittest.TestCase):
    """Requirements 12.1 to 12.8: comparison.main writes a correct comparison file.

    Output always goes to a temporary directory, never to the project's comparison.csv.
    """

    SCENARIOS = ('baseline_2w', 'baseline_1w', 'baseline_3w', 'baseline_t05_3days',
                 'independent_tasks', 'dependency_chain')
    ALGORITHM_NAMES = ('bfs', 'ucs', 'greedy', 'astar')

    def _run_main(self, output, algorithms=None):
        """Run comparison.main quietly. Returns (exit code, stderr text)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            if algorithms is None:
                code = comparison.main(['--output', output])
            else:
                with mock.patch.object(comparison, 'ALGORITHMS', algorithms):
                    code = comparison.main(['--output', output])
        return code, err.getvalue()

    def test_columns_rows_and_measured_values(self):
        """Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6"""
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'out.csv')
            code, _ = self._run_main(path)
            self.assertEqual(0, code)

            with open(path, 'r', encoding='utf-8', newline='') as handle:
                lines = handle.read().splitlines()
            self.assertEqual(','.join(COLUMNS), lines[0], msg='column order')
            self.assertEqual(24, len(lines) - 1, msg='data rows')

            rows = read_results_csv(path)
            self.assertEqual(24, len(rows))
            expected_order = [(s, a) for s in self.SCENARIOS for a in self.ALGORITHM_NAMES]
            self.assertEqual(expected_order, [(r['scenario'], r['algorithm']) for r in rows])
            for row in rows:
                label = f"{row['scenario']}/{row['algorithm']}"
                self.assertEqual('solved', row['status'], msg=label)
                self.assertIs(True, row['schedule_valid'], msg=label)
                self.assertIsInstance(row['makespan'], int, msg=label)
                self.assertGreaterEqual(row['makespan'], 0, msg=label)
                # A measured run expands at least one state and takes measurable time.
                self.assertGreater(row['states_explored'], 0, msg=label)
                self.assertIsInstance(row['execution_time_ms'], float, msg=label)
                self.assertGreater(row['execution_time_ms'], 0.0, msg=label)

    def test_reference_makespans_for_ucs(self):
        """Requirements 12.4, 12.8: values come from real runs (11, 15, 9, 12)."""
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'out.csv')
            self.assertEqual(0, self._run_main(path)[0])
            ucs_rows = {r['scenario']: r['makespan']
                        for r in read_results_csv(path) if r['algorithm'] == 'ucs'}
        self.assertEqual(11, ucs_rows['baseline_2w'])
        self.assertEqual(15, ucs_rows['baseline_1w'])
        self.assertEqual(9, ucs_rows['baseline_3w'])
        self.assertEqual(12, ucs_rows['baseline_t05_3days'])
        self.assertEqual(8, ucs_rows['dependency_chain'])  # chain 2+3+1+2
        self.assertEqual(5, ucs_rows['independent_tasks'])  # 4+1 and 3+2 on two workers

    def test_ucs_is_minimal_in_every_scenario(self):
        """Requirement 12.8"""
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'out.csv')
            self.assertEqual(0, self._run_main(path)[0])
            rows = read_results_csv(path)
        for scenario in self.SCENARIOS:
            group = [r for r in rows if r['scenario'] == scenario and r['status'] == 'solved']
            ucs_makespan = next(r['makespan'] for r in group if r['algorithm'] == 'ucs')
            for row in group:
                self.assertLessEqual(ucs_makespan, row['makespan'],
                                     msg=f"{scenario}: ucs vs {row['algorithm']}")

    def test_failed_run_becomes_error_row_and_others_continue(self):
        """Requirement 12.7"""
        def broken_search(tasks, capacity):
            raise RuntimeError('boom')

        algorithms = (
            ('bfs', bfs_search),
            ('ucs', ucs_search),
            ('greedy', broken_search),
            ('astar', astar_search),
        )
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'out.csv')
            code, stderr_text = self._run_main(path, algorithms)
            self.assertEqual(0, code)
            rows = read_results_csv(path)
        self.assertEqual(24, len(rows))
        self.assertIn('boom', stderr_text)
        for row in rows:
            label = f"{row['scenario']}/{row['algorithm']}"
            if row['algorithm'] == 'greedy':
                self.assertEqual('error', row['status'], msg=label)
                self.assertIsNone(row['makespan'], msg=label)
                self.assertIs(False, row['schedule_valid'], msg=label)
            else:
                self.assertEqual('solved', row['status'], msg=label)
                self.assertIs(True, row['schedule_valid'], msg=label)

    def test_no_schedule_row_is_written_with_failure_status(self):
        """Requirement 12.7: a run with no schedule keeps its row, empty makespan, valid false."""
        def no_solution_search(tasks, capacity):
            return search_common.make_result('Greedy', 'no solution', states_explored=3,
                                             execution_time_ms=0.25)

        algorithms = (
            ('bfs', bfs_search),
            ('ucs', ucs_search),
            ('greedy', no_solution_search),
            ('astar', astar_search),
        )
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'out.csv')
            self.assertEqual(0, self._run_main(path, algorithms)[0])
            rows = read_results_csv(path)
        self.assertEqual(24, len(rows))
        greedy_rows = [r for r in rows if r['algorithm'] == 'greedy']
        self.assertEqual(6, len(greedy_rows))
        for row in greedy_rows:
            self.assertEqual('no solution', row['status'])
            self.assertIsNone(row['makespan'])
            self.assertIs(False, row['schedule_valid'])
            self.assertEqual(3, row['states_explored'])

    def test_unusable_output_path_leaves_existing_file_untouched(self):
        """Requirements 12.9, 12.5: bad destination is an error and nothing is overwritten."""
        with tempfile.TemporaryDirectory() as folder:
            existing = os.path.join(folder, 'out.csv')
            with open(existing, 'wb') as handle:
                handle.write(b'keep me\n')
            missing_folder = os.path.join(folder, 'no_such_dir', 'out.csv')
            self.assertNotEqual(0, self._run_main(missing_folder)[0])
            self.assertNotEqual(0, self._run_main(folder)[0])
            with open(existing, 'rb') as handle:
                self.assertEqual(b'keep me\n', handle.read())
            self.assertEqual(['out.csv'], os.listdir(folder))


if __name__ == '__main__':
    unittest.main()
