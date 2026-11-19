"""Phase 3 tests for the heuristic functions (standard library unittest only).

Run with:
    python -m unittest -v tests.test_heuristics

This group checks goal-state and baseline values (Requirements 2.1, 2.2, 2.3).
"""
import copy
import os
import unittest

from scheduling.data_validation import DataValidationError, Task, load_tasks, validate_tasks
from scheduling.search_common import check_input
from scheduling.heuristics import (
    combined_heuristic, critical_path_remaining, longest_remaining,
    workload_remaining, zero_heuristic,
)
from scheduling.astar import astar_search
from experiments import heuristic_summary
from scheduling.heuristic_io import write_heuristic_csv
from experiments.heuristic_summary import summary_markdown
from scheduling.greedy import greedy_search
from scheduling.ucs import ucs_search
from scheduling.scheduling_model import State, initial_state, is_goal, successors

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS_CSV = os.path.join(ROOT, 'data', 'tasks.csv')
CAPACITY = 2


class GoalAndBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = load_tasks(TASKS_CSV, CAPACITY)

    def test_ht01_all_heuristics_zero_at_goal(self):
        """HT-01: H0, H1, H2, H3 return 0 at a completed goal state."""
        goal = State(frozenset(self.tasks), ())
        for h in (zero_heuristic, longest_remaining, critical_path_remaining,
                  combined_heuristic):
            with self.subTest(heuristic=h.__name__):
                self.assertEqual(h(goal, self.tasks, CAPACITY), 0)

    def test_ht02_baseline_day0_values(self):
        """HT-02: baseline Day 0, 2 workers -> H0=0, H1=4, H2=9, workload=8, H3=9."""
        s = initial_state()
        self.assertEqual(zero_heuristic(s, self.tasks, CAPACITY), 0)
        self.assertEqual(longest_remaining(s, self.tasks, CAPACITY), 4)
        self.assertEqual(critical_path_remaining(s, self.tasks, CAPACITY), 9)
        self.assertEqual(workload_remaining(s, self.tasks, CAPACITY), 8)
        self.assertEqual(combined_heuristic(s, self.tasks, CAPACITY), 9)

    def test_ht03_running_task_counts_remaining_days(self):
        """HT-03: a running task with 1 day left (of 4) counts as 1, not 4."""
        self.assertEqual(self.tasks['T02'].duration, 4)
        # Only T02 is left, with 1 day remaining.
        only_t02 = {'T02': Task('T02', 4, (), 1)}
        s = State(frozenset(), (('T02', 1),))
        self.assertEqual(longest_remaining(s, only_t02, CAPACITY), 1)
        self.assertEqual(critical_path_remaining(s, only_t02, CAPACITY), 1)
        self.assertEqual(workload_remaining(s, only_t02, CAPACITY), 1)

        # Full baseline: T01, T03, T04 done, T02 has 1 day left.
        s = State(frozenset({'T01', 'T03', 'T04'}), (('T02', 1),))
        self.assertEqual(longest_remaining(s, self.tasks, CAPACITY), 2)       # T05
        self.assertEqual(critical_path_remaining(s, self.tasks, CAPACITY), 4)  # 1 + 2 + 1
        self.assertEqual(workload_remaining(s, self.tasks, CAPACITY), 2)       # (1+2+1)/2


class ChainIndependentOneWorkerTests(unittest.TestCase):
    """Requirement 2.4: chain, independent-task and one-worker cases."""

    def test_ht04_single_chain_critical_path_is_sum_of_durations(self):
        """HT-04: A(2) -> B(3) -> C(4) gives critical path 9 = sum of durations."""
        tasks = {
            'A': Task('A', 2, (), 1),
            'B': Task('B', 3, ('A',), 1),
            'C': Task('C', 4, ('B',), 1),
        }
        s = initial_state()
        self.assertEqual(critical_path_remaining(s, tasks, 2), 9)
        self.assertEqual(combined_heuristic(s, tasks, 2), 9)
        # After A finishes, only B and C remain: 3 + 4.
        s = State(frozenset({'A'}), ())
        self.assertEqual(critical_path_remaining(s, tasks, 2), 7)

    def test_ht05_independent_tasks_workload_reflects_capacity(self):
        """HT-05: four independent 2-day, 1-worker tasks = 8 worker-days."""
        tasks = {t: Task(t, 2, (), 1) for t in ('A', 'B', 'C', 'D')}
        s = initial_state()
        self.assertEqual(workload_remaining(s, tasks, 2), 4)   # 8 / 2
        self.assertEqual(workload_remaining(s, tasks, 4), 2)   # 8 / 4
        self.assertEqual(workload_remaining(s, tasks, 3), 3)   # ceil(8 / 3)
        # Critical path is only 2, so the workload bound is the larger one.
        self.assertEqual(critical_path_remaining(s, tasks, 2), 2)
        self.assertEqual(combined_heuristic(s, tasks, 2), 4)

    def test_ht06_one_worker_workload_equals_all_worker_days(self):
        """HT-06: with one worker the workload bound is all remaining worker-days."""
        tasks = {
            'A': Task('A', 2, (), 1),
            'B': Task('B', 3, ('A',), 1),
            'C': Task('C', 4, (), 1),
        }
        s = initial_state()
        self.assertEqual(workload_remaining(s, tasks, 1), 9)
        # A running with 1 day left, B and C not started: 1 + 3 + 4.
        s = State(frozenset(), (('A', 1),))
        self.assertEqual(workload_remaining(s, tasks, 1), 8)


ALL_HEURISTICS = (zero_heuristic, longest_remaining, critical_path_remaining,
                  workload_remaining, combined_heuristic)


class InputRejectionTests(unittest.TestCase):
    """HT-07 (Requirement 2.5): bad input is rejected by validation first."""

    def test_ht07_invalid_input_rejected_by_validation(self):
        cycle = {
            'T01': Task('T01', 1, ('T02',), 1),
            'T02': Task('T02', 1, ('T01',), 1),
        }
        bad_duration = {'T01': Task('T01', 0, (), 1)}
        over_capacity = {'T01': Task('T01', 1, (), 3)}
        cases = {
            'cycle': (cycle, 2, 'dependency cycle'),
            'bad duration': (bad_duration, 2, 'invalid input'),
            'over capacity': (over_capacity, 2, 'needs 3 workers, capacity is 2'),
        }
        for name, (tasks, cap, expected) in cases.items():
            with self.subTest(case=name):
                self.assertIsNotNone(check_input(tasks, cap))
                self.assertIn(expected, check_input(tasks, cap))
                with self.assertRaises(DataValidationError):
                    validate_tasks(tasks, cap)


class NonMutationNonNegativityTests(unittest.TestCase):
    """HT-08 (Requirement 2.6): non-negative ints, and no input is changed."""

    @classmethod
    def setUpClass(cls):
        cls.tasks = load_tasks(TASKS_CSV, CAPACITY)

    def _reachable_states(self):
        start = initial_state()
        seen = {start}
        stack = [start]
        while stack:
            state = stack.pop()
            for succ in successors(state, self.tasks, CAPACITY):
                if succ.state not in seen:
                    seen.add(succ.state)
                    stack.append(succ.state)
        return seen

    def test_ht08_non_negative_ints_and_no_mutation(self):
        states = self._reachable_states()
        self.assertGreater(len(states), 1)
        checked = 0
        for state in states:
            for succ in successors(state, self.tasks, CAPACITY):
                for target in (state, succ.state):
                    for h in ALL_HEURISTICS:
                        tasks_before = copy.deepcopy(self.tasks)
                        state_before = copy.deepcopy(target)
                        cap_before = CAPACITY
                        value = h(target, self.tasks, CAPACITY)
                        with self.subTest(heuristic=h.__name__, state=target):
                            self.assertIs(type(value), int)
                            self.assertGreaterEqual(value, 0)
                            self.assertEqual(self.tasks, tasks_before)
                            self.assertEqual(target, state_before)
                            self.assertEqual(CAPACITY, cap_before)
                        checked += 1
        self.assertGreater(checked, 0)


class AdmissibilityTests(unittest.TestCase):
    """HT-09 (Requirement 2.7): 0 <= h(state) <= exact cost-to-goal, every state."""

    @staticmethod
    def _cost_to_goal_table(tasks, capacity):
        """Exact remaining cost from every reachable state.

        Every move spends at least 1 day and never revisits a state, so the
        state graph has no cycles and a memoized recursion is exact.
        """
        memo = {}

        def cost(state):
            if state in memo:
                return memo[state]
            if is_goal(state, tasks):
                memo[state] = 0
                return 0
            best = None
            for succ in successors(state, tasks, capacity):
                total = succ.cost + cost(succ.state)
                if best is None or total < best:
                    best = total
            memo[state] = best
            return best

        cost(initial_state())
        return memo

    def _check_capacity(self, capacity):
        tasks = load_tasks(TASKS_CSV, capacity)
        table = self._cost_to_goal_table(tasks, capacity)
        self.assertGreater(len(table), 1)
        for state, true_cost in table.items():
            self.assertIsNotNone(true_cost)
            for h in ALL_HEURISTICS:
                value = h(state, tasks, capacity)
                with self.subTest(workers=capacity, heuristic=h.__name__, state=state):
                    self.assertGreaterEqual(value, 0)
                    self.assertLessEqual(value, true_cost)
        return table

    def test_ht09_admissible_on_two_worker_baseline(self):
        table = self._check_capacity(2)
        self.assertEqual(table[initial_state()], 11)

    def test_ht09_admissible_on_one_worker_baseline(self):
        self._check_capacity(1)

    def test_ht09_admissible_on_three_worker_baseline(self):
        self._check_capacity(3)


def _ss_scenarios():
    """The four SS scenarios as (name, tasks, capacity, optimal makespan)."""
    base2 = load_tasks(TASKS_CSV, 2)
    t05 = base2['T05']
    t05_three = dict(base2)
    t05_three['T05'] = Task('T05', 3, t05.dependencies, t05.workers_required)
    return [
        ('2 workers', base2, 2, 11),
        ('1 worker', load_tasks(TASKS_CSV, 1), 1, 15),
        ('3 workers', load_tasks(TASKS_CSV, 3), 3, 9),
        ('T05=3 days, 2 workers', t05_three, 2, 12),
    ]


AGREEMENT_HEURISTICS = (zero_heuristic, longest_remaining,
                        critical_path_remaining, combined_heuristic)


class AgreementAndRepeatabilityTests(unittest.TestCase):
    """HT-10 and HT-11 (Requirement 2.8)."""

    @classmethod
    def setUpClass(cls):
        cls.scenarios = _ss_scenarios()

    def test_ht10_astar_matches_ucs_on_ss_scenarios(self):
        for name, tasks, cap, expected in self.scenarios:
            ucs = ucs_search(tasks, cap)
            self.assertEqual(ucs['makespan'], expected, name)
            for h in AGREEMENT_HEURISTICS:
                with self.subTest(scenario=name, heuristic=h.__name__):
                    res = astar_search(tasks, cap, heuristic=h)
                    self.assertEqual(res['status'], 'solved')
                    self.assertTrue(res['schedule_valid'])
                    self.assertEqual(res['makespan'], ucs['makespan'])

    def test_ht10_greedy_valid_and_never_below_optimum(self):
        for name, tasks, cap, expected in self.scenarios:
            for h in AGREEMENT_HEURISTICS:
                with self.subTest(scenario=name, heuristic=h.__name__):
                    res = greedy_search(tasks, cap, heuristic=h)
                    self.assertEqual(res['status'], 'solved')
                    self.assertTrue(res['schedule_valid'])
                    self.assertGreaterEqual(res['makespan'], expected)

    def test_ht11_repeated_runs_give_same_results(self):
        runs = (
            ('UCS', lambda t, c: ucs_search(t, c)),
            ('A* H3', lambda t, c: astar_search(t, c, heuristic=combined_heuristic)),
            ('Greedy H1', lambda t, c: greedy_search(t, c, heuristic=longest_remaining)),
        )
        for name, tasks, cap, _ in self.scenarios:
            for label, run in runs:
                with self.subTest(scenario=name, method=label):
                    first = run(tasks, cap)
                    for _ in range(2):
                        again = run(tasks, cap)
                        for key in ('makespan', 'states_explored', 'states_generated'):
                            self.assertEqual(again[key], first[key])




class GeneratedInstanceTests(unittest.TestCase):
    def test_generated_files_load_and_sizes(self):
        """Every generated file loads through load_tasks and has 8 to 12 tasks."""
        import tempfile
        from experiments import heuristic_data
        with tempfile.TemporaryDirectory() as tmp:
            paths = heuristic_data.generate_all(tmp)
            self.assertEqual(len(paths), len(heuristic_data.INSTANCES))
            self.assertTrue(os.path.isfile(os.path.join(tmp, 'NOTES.md')))
            for path in paths:
                with self.subTest(file=os.path.basename(path)):
                    tasks = load_tasks(path, CAPACITY)
                    self.assertTrue(8 <= len(tasks) <= 12)

    def test_generator_is_repeatable(self):
        """Two runs write byte-identical files."""
        import tempfile
        from experiments import heuristic_data
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            heuristic_data.generate_all(a)
            heuristic_data.generate_all(b)
            self.assertEqual(sorted(os.listdir(a)), sorted(os.listdir(b)))
            for name in os.listdir(a):
                with open(os.path.join(a, name), 'rb') as fa, open(os.path.join(b, name), 'rb') as fb:
                    self.assertEqual(fa.read(), fb.read(), name)


class HeuristicCsvTests(unittest.TestCase):
    """Requirements 5.1, 5.2, 5.3, 5.6: results CSV writer and reader."""

    @staticmethod
    def _random_rows(seed, count):
        import random
        from scheduling import results_io
        rng = random.Random(seed)
        rows = []
        for i in range(count):
            status = rng.choice(results_io.ALLOWED_STATUSES)
            solved = status == 'solved'
            rows.append({
                'scenario_id': f'S{i}',
                'seed': rng.choice([None, rng.randint(0, 10**6)]),
                'task_count': rng.randint(0, 12),
                'worker_capacity': rng.randint(1, 4),
                'algorithm': rng.choice(['UCS', 'A*', 'Greedy']),
                'heuristic': rng.choice(['none', 'H1', 'H3']),
                'search_status': status,
                'makespan_days': rng.randint(1, 40) if solved else None,
                'states_expanded': rng.randint(0, 10**5),
                'states_generated': rng.randint(0, 10**5),
                'runtime_ms': rng.choice([0, rng.random() * 100]),
                'solution_valid': rng.choice([True, False]),
                'optimality_gap_pct': rng.choice([None, rng.random() * 50]) if solved else None,
            })
        return rows

    def _good_row(self):
        return self._random_rows(1, 1)[0] | {
            'search_status': 'solved', 'makespan_days': 11, 'optimality_gap_pct': 0.0}

    def test_round_trip_is_exact_and_bytes_repeat(self):
        import tempfile
        from scheduling import heuristic_io
        rows = self._random_rows(7, 40)
        with tempfile.TemporaryDirectory() as tmp:
            first = os.path.join(tmp, 'a.csv')
            second = os.path.join(tmp, 'b.csv')
            heuristic_io.write_heuristic_csv(first, rows)
            with open(first, encoding='utf-8', newline='') as f:
                self.assertEqual(f.readline().rstrip('\n'), ','.join(heuristic_io.COLUMNS))
            back = heuristic_io.read_heuristic_csv(first)
            self.assertEqual(back, rows)
            heuristic_io.write_heuristic_csv(second, back)
            with open(first, 'rb') as fa, open(second, 'rb') as fb:
                self.assertEqual(fa.read(), fb.read())
            self.assertEqual(os.listdir(tmp).count('a.csv'), 1)
            self.assertEqual(len(os.listdir(tmp)), 2)

    def test_failed_write_keeps_existing_file_and_no_temp(self):
        import tempfile
        from scheduling import heuristic_io
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'r.csv')
            heuristic_io.write_heuristic_csv(path, [self._good_row()])
            with open(path, 'rb') as f:
                before = f.read()
            bad = self._good_row()
            bad['states_expanded'] = -1
            with self.assertRaises(heuristic_io.HeuristicCsvError):
                heuristic_io.write_heuristic_csv(path, [bad])
            with open(path, 'rb') as f:
                self.assertEqual(f.read(), before)
            self.assertEqual(os.listdir(tmp), ['r.csv'])

    def test_reader_names_missing_column(self):
        import tempfile
        from scheduling import heuristic_io
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'r.csv')
            cols = [c for c in heuristic_io.COLUMNS if c != 'runtime_ms']
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(','.join(cols) + '\n')
            with self.assertRaises(heuristic_io.HeuristicCsvError) as ctx:
                heuristic_io.read_heuristic_csv(path)
            self.assertIn('runtime_ms', str(ctx.exception))

    def _edit_and_read(self, column, text):
        import tempfile
        from scheduling import heuristic_io
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'r.csv')
            heuristic_io.write_heuristic_csv(path, [self._good_row(), self._good_row()])
            with open(path, encoding='utf-8', newline='') as f:
                lines = f.read().split('\n')
            cells = lines[2].split(',')
            cells[heuristic_io.COLUMNS.index(column)] = text
            lines[2] = ','.join(cells)
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write('\n'.join(lines))
            heuristic_io.read_heuristic_csv(path)

    def test_reader_rejects_bad_status_with_row_and_column(self):
        from scheduling import heuristic_io
        with self.assertRaises(heuristic_io.HeuristicCsvError) as ctx:
            self._edit_and_read('search_status', 'maybe')
        self.assertIn('row 2', str(ctx.exception))
        self.assertIn('search_status', str(ctx.exception))

    def test_reader_rejects_negative_counts(self):
        from scheduling import heuristic_io
        for column in ('task_count', 'worker_capacity', 'states_expanded', 'states_generated'):
            with self.subTest(column=column):
                with self.assertRaises(heuristic_io.HeuristicCsvError) as ctx:
                    self._edit_and_read(column, '-1')
                self.assertIn('row 2', str(ctx.exception))
                self.assertIn(column, str(ctx.exception))

    def test_writer_rejects_value_on_unsolved_row(self):
        import tempfile
        from scheduling import heuristic_io
        row = self._good_row()
        row['search_status'] = 'timeout'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(heuristic_io.HeuristicCsvError) as ctx:
                heuristic_io.write_heuristic_csv(os.path.join(tmp, 'r.csv'), [row])
            self.assertIn('makespan_days', str(ctx.exception))
            self.assertEqual(os.listdir(tmp), [])


class RunnerTests(unittest.TestCase):
    """Requirements 4.5, 4.6, 5.6: heuristic_comparison.main and run_instance.

    Output goes only to a temp folder. build_instances is patched to return
    small instances and `methods` is a reduced tuple, so the tests stay fast.
    """

    PROJECT_RESULTS = os.path.join(ROOT, 'results', 'heuristic_results.csv')

    @staticmethod
    def _snapshot(path):
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            data = f.read()
        return data, os.stat(path).st_mtime_ns

    def setUp(self):
        import tempfile
        from unittest import mock
        from experiments import heuristic_comparison
        self.hc = heuristic_comparison
        self.before = self._snapshot(self.PROJECT_RESULTS)
        self.addCleanup(lambda: self.assertEqual(
            self._snapshot(self.PROJECT_RESULTS), self.before))
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.out = os.path.join(self.tmp, 'out.csv')
        self.instances = [
            {'scenario_id': 'small_a', 'seed': None, 'capacity': 2,
             'tasks': load_tasks(TASKS_CSV, 2)},
            {'scenario_id': 'small_b', 'seed': 5, 'capacity': 1,
             'tasks': load_tasks(TASKS_CSV, 1)},
        ]
        patcher = mock.patch.object(
            heuristic_comparison, 'build_instances', return_value=self.instances)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.methods = (
            ('ucs', 'none', self.hc._ucs),
            ('astar', 'H3', self.hc._astar(combined_heuristic)),
            ('greedy', 'H1', self.hc._greedy(longest_remaining)),
        )

    def _main(self, argv, methods=None):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = self.hc.main(argv, self.methods if methods is None else methods)
        return code

    def test_columns_and_row_count(self):
        from scheduling import heuristic_io
        code = self._main(['--output', self.out, '--timeout', '5'])
        self.assertEqual(code, 0)
        self.assertEqual(len(heuristic_io.COLUMNS), 13)
        with open(self.out, encoding='utf-8', newline='') as f:
            self.assertEqual(f.readline().rstrip('\n').split(','), list(heuristic_io.COLUMNS))
        rows = heuristic_io.read_heuristic_csv(self.out)
        self.assertEqual(len(rows), len(self.instances) * len(self.methods))
        for row in rows:
            self.assertEqual(len(row), 13)
            self.assertEqual(row['search_status'], 'solved')
            self.assertTrue(row['solution_valid'])
        ucs_rows = [r for r in rows if r['algorithm'] == 'ucs']
        self.assertEqual([r['makespan_days'] for r in ucs_rows], [11, 15])

    def test_failing_method_becomes_error_row(self):
        from scheduling import heuristic_io

        def boom(tasks, capacity, timeout, limit):
            raise RuntimeError('boom')

        methods = (self.methods[0], ('astar', 'H1', boom), self.methods[2])
        code = self._main(['--output', self.out, '--timeout', '5'], methods)
        self.assertEqual(code, 0)
        rows = heuristic_io.read_heuristic_csv(self.out)
        self.assertEqual(len(rows), len(self.instances) * 3)
        errors = [r for r in rows if r['search_status'] == 'error']
        self.assertEqual(len(errors), len(self.instances))
        for row in errors:
            self.assertEqual(row['heuristic'], 'H1')
            self.assertIsNone(row['makespan_days'])
            self.assertIsNone(row['optimality_gap_pct'])
            self.assertFalse(row['solution_valid'])
        others = [r for r in rows if r['search_status'] != 'error']
        self.assertEqual(len(others), len(self.instances) * 2)
        self.assertTrue(all(r['search_status'] == 'solved' for r in others))

    def test_state_limit_is_recorded_as_incomplete(self):
        from scheduling import heuristic_io
        code = self._main(['--output', self.out, '--timeout', '5',
                           '--max-expansions', '1'])
        self.assertEqual(code, 0)
        rows = heuristic_io.read_heuristic_csv(self.out)
        self.assertEqual(len(rows), len(self.instances) * len(self.methods))
        for row in rows:
            self.assertEqual(row['search_status'], 'state_limit')
            self.assertIsNone(row['makespan_days'])
            self.assertIsNone(row['optimality_gap_pct'])
            self.assertFalse(row['solution_valid'])
            self.assertLessEqual(row['states_expanded'], 1)

    def test_astar_mismatch_exits_1_and_writes_nothing(self):
        def wrong(tasks, capacity, timeout, limit):
            result = ucs_search(tasks, capacity)
            result = dict(result)
            result['makespan'] = result['makespan'] + 3
            return result

        methods = (self.methods[0], ('astar', 'H3', wrong))
        code = self._main(['--output', self.out, '--timeout', '5'], methods)
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(self.out))
        self.assertEqual(os.listdir(self.tmp), [])
        with self.assertRaises(self.hc.OptimalityError):
            self.hc.run_instance(self.instances[0], methods, timeout=5, repeats=1)

    def test_bad_output_paths_exit_2_and_write_nothing(self):
        subdir = os.path.join(self.tmp, 'folder.csv')
        os.mkdir(subdir)
        cases = {
            'directory': subdir,
            'missing parent': os.path.join(self.tmp, 'nope', 'out.csv'),
            'not csv': os.path.join(self.tmp, 'out.txt'),
            'empty': '',
        }
        for name, path in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self._main(['--output', path]), 2)
                self.assertFalse(os.path.exists(path) and os.path.isfile(path))
        self.assertEqual(os.listdir(self.tmp), ['folder.csv'])
        self.assertEqual(os.listdir(subdir), [])
        with self.assertRaises(ValueError):
            self.hc.validate_output_path('')


class SummaryTests(unittest.TestCase):
    """Requirement 6.1: markdown summary from a results CSV."""

    @staticmethod
    def _row(scenario, algorithm, heuristic, expanded, ms, gap=None, status='solved'):
        solved = status == 'solved'
        return {'scenario_id': scenario, 'seed': None, 'task_count': 5,
                'worker_capacity': 2, 'algorithm': algorithm, 'heuristic': heuristic,
                'search_status': status, 'makespan_days': 7 if solved else None,
                'states_expanded': expanded, 'states_generated': expanded,
                'runtime_ms': ms, 'solution_valid': solved,
                'optimality_gap_pct': gap if solved else None}

    def _rows(self):
        r = self._row
        return [
            r('baseline_2w', 'astar', 'H1', 10, 1.0),
            r('baseline_1w', 'astar', 'H1', 30, 3.0),
            r('baseline_3w', 'astar', 'H1', 20, 2.0),
            r('baseline_3w', 'astar', 'H1', 999, 99.0, status='timeout'),
            r('wide_01', 'greedy', 'H3', 4, 0.5, gap=10.0),
            r('wide_02', 'greedy', 'H3', 6, 1.5, gap=0.0),
            r('wide_03', 'greedy', 'H3', 8, 2.5, gap=30.0),
            r('deep_01', 'ucs', 'none', 5, 1.25),
        ]

    def test_summary_markdown_known_medians(self):
        lines = summary_markdown(self._rows()).split('\n')
        self.assertEqual(len(lines), 5)
        self.assertTrue(lines[0].startswith('| group | method'))
        self.assertIn('| baseline | astar/H1 | 3 | 20.0 | 2.00 | - | - |', lines)
        self.assertIn('| wide | greedy/H3 | 3 | 6.0 | 1.50 | 10.0 | 30.0 |', lines)
        self.assertIn('| deep | ucs | 1 | 5.0 | 1.25 | - | - |', lines)

    def test_summary_main_reads_csv_and_rejects_bad_path(self):
        import contextlib
        import io
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'results.csv')
            write_heuristic_csv(path, self._rows())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(heuristic_summary.main([path]), 0)
            self.assertEqual(out.getvalue().strip(), summary_markdown(self._rows()))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(heuristic_summary.main([os.path.join(folder, 'no.csv')]), 2)
                self.assertEqual(heuristic_summary.main([folder]), 2)
                self.assertEqual(heuristic_summary.main([]), 2)


if __name__ == '__main__':
    unittest.main()
