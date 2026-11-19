"""Tests for the Phase 1 requirements and model.

Run from the project folder:
    python -m unittest -v tests.test_phase1
"""
import csv
import tempfile
import unittest
from pathlib import Path

from scheduling.data_validation import (
    DataValidationError, Task, combined_lower_bound, group_split_bound,
    load_tasks, lower_bounds, validate_tasks,
)
from scheduling.scheduling_model import (
    advance, initial_state, is_goal, legal_start_sets, ready_tasks,
    read_reference_schedule, successors, validate_schedule,
)

ROOT = Path(__file__).resolve().parent.parent
TASKS_PATH = ROOT / 'data' / 'tasks.csv'
SCHEDULE_PATH = ROOT / 'data' / 'reference_schedule.csv'


def copy_task(task, duration=None, dependencies=None, workers_required=None):
    """Make a new Task like the old one, but change the fields we pass in."""
    new_duration = task.duration
    if duration is not None:
        new_duration = duration
    new_dependencies = task.dependencies
    if dependencies is not None:
        new_dependencies = dependencies
    new_workers = task.workers_required
    if workers_required is not None:
        new_workers = workers_required
    return Task(
        task_id=task.task_id,
        duration=new_duration,
        dependencies=new_dependencies,
        workers_required=new_workers,
    )


def make_rows(items):
    """Turn (task_id, start, finish) tuples into schedule rows (no worker_id)."""
    rows = []
    for task_id, start, finish in items:
        rows.append({'task_id': task_id, 'start_day': start, 'finish_day': finish})
    return rows


class RequirementsTests(unittest.TestCase):
    def setUp(self):
        # Runs before every test. 2 workers is our normal case.
        self.tasks = load_tasks(TASKS_PATH, 2)

    # ---- Dataset and CSV checks ----

    def test_dataset_structure(self):
        """tasks.csv has the 6 expected tasks with the right durations and prerequisites."""
        self.assertEqual(list(self.tasks), ['T01', 'T02', 'T03', 'T04', 'T05', 'T06'])
        total = 0
        for task in self.tasks.values():
            total += task.duration
        self.assertEqual(total, 15)
        self.assertEqual(self.tasks['T05'].dependencies, ('T02', 'T03', 'T04'))
        self.assertEqual(self.tasks['T01'].dependencies, ())
        durations = {'T01': 2, 'T02': 4, 'T03': 3, 'T04': 3, 'T05': 2, 'T06': 1}
        deps = {
            'T01': (),
            'T02': ('T01',),
            'T03': ('T01',),
            'T04': ('T01',),
            'T05': ('T02', 'T03', 'T04'),
            'T06': ('T05',),
        }
        for tid in durations:
            self.assertEqual(self.tasks[tid].duration, durations[tid], tid)
            self.assertEqual(self.tasks[tid].dependencies, deps[tid], tid)
            self.assertEqual(self.tasks[tid].workers_required, 1, tid)

    def test_tasks_csv_header_is_exact(self):
        """The first line of tasks.csv has exactly the four required columns."""
        with TASKS_PATH.open(encoding='utf-8-sig', newline='') as f:
            header = next(csv.reader(f))
        self.assertEqual(header, ['task_id', 'duration', 'depends_on', 'workers_required'])

    # ---- Bad input checks ----

    def test_old_five_column_header_rejected(self):
        """A CSV with the old five-column header is refused."""
        # TemporaryDirectory makes a throwaway folder that is deleted automatically.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'old.csv'
            path.write_text(
                'task_id,task_name,duration_days,depends_on,workers_required\n'
                'T01,Design,2,None,1\n',
                encoding='utf-8',
            )
            # assertRaises means: the code inside must raise this error,
            # otherwise the test fails.
            with self.assertRaises(ValueError):
                load_tasks(path, 2)

    def test_unquoted_multi_prerequisite_csv_rejected(self):
        """A prerequisite list without quotes (T01, T03) makes a bad row and is refused."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.csv'
            path.write_text(
                'task_id,duration,depends_on,workers_required\n'
                'T01,1,None,1\n'
                'T02,1,T01, T03,1\n'
                'T03,1,None,1\n',
                encoding='utf-8',
            )
            with self.assertRaises(DataValidationError):
                load_tasks(path, 2)

    def test_missing_predecessor_rejected(self):
        """A task that depends on a task that does not exist is refused."""
        tasks = dict(self.tasks)  # a copy, so the original stays the same
        tasks['T05'] = copy_task(tasks['T05'], dependencies=('ZZ',))
        with self.assertRaises(DataValidationError):
            validate_tasks(tasks, 2)

    def test_cycle_rejected(self):
        """Tasks that depend on each other in a circle are refused."""
        tasks = dict(self.tasks)
        tasks['T01'] = copy_task(tasks['T01'], dependencies=('T06',))
        with self.assertRaises(DataValidationError):
            validate_tasks(tasks, 2)

    def test_overcapacity_task_rejected(self):
        """A task that needs more workers than we have is refused."""
        tasks = dict(self.tasks)
        tasks['T02'] = copy_task(tasks['T02'], workers_required=3)
        with self.assertRaises(DataValidationError):
            validate_tasks(tasks, 2)

    def test_bad_duration_rejected(self):
        """A task with duration 0 is refused."""
        tasks = dict(self.tasks)
        tasks['T02'] = copy_task(tasks['T02'], duration=0)
        with self.assertRaises(DataValidationError):
            validate_tasks(tasks, 2)

    def test_malformed_schedule_row_rejected(self):
        """A schedule row with a missing or non-number start_day is refused."""
        rows = read_reference_schedule(SCHEDULE_PATH)
        del rows[0]['start_day']
        with self.assertRaises(ValueError):
            validate_schedule(rows, self.tasks, 2)

        rows = read_reference_schedule(SCHEDULE_PATH)
        rows[0]['start_day'] = 'abc'
        with self.assertRaises(ValueError):
            validate_schedule(rows, self.tasks, 2)

    def test_worker_id_out_of_range_rejected(self):
        """Worker 3 is refused when we only have 2 workers."""
        rows = read_reference_schedule(SCHEDULE_PATH)
        for row in rows:
            if row['task_id'] == 'T03':
                row['worker_id'] = '3'
        with self.assertRaises(ValueError):
            validate_schedule(rows, self.tasks, 2)

    def test_invalid_schedule_dependency(self):
        """T05 starting at day 7, before T04 is done, is refused."""
        rows = read_reference_schedule(SCHEDULE_PATH)
        for row in rows:
            if row['task_id'] == 'T05':
                row['start_day'] = 7
                row['finish_day'] = 9
        with self.assertRaises(ValueError):
            validate_schedule(rows, self.tasks, 2)

    def test_invalid_schedule_worker_overlap(self):
        """One worker given two tasks at the same time is refused."""
        rows = read_reference_schedule(SCHEDULE_PATH)
        for row in rows:
            if row['task_id'] == 'T03':
                row['worker_id'] = '1'
        with self.assertRaises(ValueError):
            validate_schedule(rows, self.tasks, 2)

    # ---- Model checks (state and advance) ----

    def test_initial_state_and_ready_tasks(self):
        """At the start only T01 is ready and the project is not finished."""
        state = initial_state()
        self.assertEqual(ready_tasks(state, self.tasks), ('T01',))
        self.assertFalse(is_goal(state, self.tasks))

    def test_start_and_advance_t01(self):
        """Starting T01 jumps 2 days, T01 is done, and T02, T03, T04 become ready."""
        step = advance(initial_state(), ('T01',), self.tasks, 2)
        self.assertEqual(step.cost, 2)
        self.assertEqual(step.state.completed, frozenset({'T01'}))
        self.assertEqual(ready_tasks(step.state, self.tasks), ('T02', 'T03', 'T04'))

    def test_legal_start_groups_at_day_2(self):
        """After T01, there are 6 choices (3 single, 3 pairs) and never all 3 together."""
        state = advance(initial_state(), ('T01',), self.tasks, 2).state
        choices = legal_start_sets(state, self.tasks, 2)
        self.assertEqual(len(choices), 6)  # 3 singles + 3 pairs
        self.assertIn(('T02', 'T03'), choices)
        self.assertNotIn(('T02', 'T03', 'T04'), choices)

    def test_invalid_t05_start_before_prerequisites(self):
        """Starting T05 at the beginning is refused."""
        with self.assertRaises(ValueError):
            advance(initial_state(), ('T05',), self.tasks, 2)

    def test_no_more_than_two_workers(self):
        """Starting T02, T03 and T04 together with 2 workers is refused."""
        state = advance(initial_state(), ('T01',), self.tasks, 2).state
        with self.assertRaises(ValueError):
            advance(state, ('T02', 'T03', 'T04'), self.tasks, 2)

    def test_worker_finishing_at_t_can_start_next_task_at_t(self):
        """A worker who finishes on day 2 can start the next task on day 2."""
        tasks = {
            'T01': Task('T01', 2, (), 1),
            'T02': Task('T02', 4, ('T01',), 1),
        }
        rows = [
            {'task_id': 'T01', 'worker_id': 'W1', 'start_day': 0, 'finish_day': 2},
            {'task_id': 'T02', 'worker_id': 'W1', 'start_day': 2, 'finish_day': 6},
        ]
        self.assertEqual(validate_schedule(rows, tasks, 1), 6)
        # Model: after T01 completes at day 2 the single worker is free again.
        step = advance(initial_state(), ('T01',), tasks, 1)
        self.assertEqual(step.cost, 2)
        self.assertEqual(step.state.running, ())
        self.assertIn(('T02',), legal_start_sets(step.state, tasks, 1))
        self.assertEqual(advance(step.state, ('T02',), tasks, 1).cost, 4)

    def test_successors_outputs_have_positive_cost(self):
        """From the start there is one next step and it costs 2 days."""
        options = successors(initial_state(), self.tasks, 2)
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0].cost, 2)

    def test_reference_actions_match_model_and_reach_goal(self):
        """Replaying the reference schedule with advance() reaches the goal in 11 days."""
        schedule = read_reference_schedule(SCHEDULE_PATH)
        state = initial_state()
        time = 0
        while not is_goal(state, self.tasks):
            # Collect the tasks that start on this day.
            starts = []
            for row in schedule:
                if int(row['start_day']) == time:
                    starts.append(row['task_id'])
            starts = tuple(sorted(starts))
            step = advance(state, starts, self.tasks, 2)
            time += step.cost
            state = step.state
        self.assertEqual(time, 11)
        self.assertEqual(state.completed, frozenset(self.tasks))

    # ---- Schedule checks ----

    def test_reference_schedule_is_valid_and_11_days(self):
        """reference_schedule.csv is a valid schedule and takes 11 days."""
        schedule = read_reference_schedule(SCHEDULE_PATH)
        self.assertEqual(validate_schedule(schedule, self.tasks, 2), 11)

    # ---- Staffing and sensitivity cases ----

    def test_1_worker_reference_is_15_days(self):
        """With 1 worker, doing the tasks one by one takes 15 days."""
        tasks = load_tasks(TASKS_PATH, 1)
        rows = make_rows([
            ('T01', 0, 2),
            ('T02', 2, 6),
            ('T03', 6, 9),
            ('T04', 9, 12),
            ('T05', 12, 14),
            ('T06', 14, 15),
        ])
        self.assertEqual(validate_schedule(rows, tasks, 1), 15)

    def test_3_worker_reference_is_9_days(self):
        """With 3 workers, T02, T03 and T04 run together and it takes 9 days."""
        tasks = load_tasks(TASKS_PATH, 3)
        rows = make_rows([
            ('T01', 0, 2),
            ('T02', 2, 6),
            ('T03', 2, 5),
            ('T04', 2, 5),
            ('T05', 6, 8),
            ('T06', 8, 9),
        ])
        self.assertEqual(validate_schedule(rows, tasks, 3), 9)
        # The same rows need 3 workers at day 2, so 2 workers must be refused.
        with self.assertRaises(ValueError):
            validate_schedule(rows, self.tasks, 2)

    def test_rehearsal_3_day_schedule_is_12_days(self):
        """If T05 takes 3 days instead of 2, the schedule takes 12 days."""
        tasks = dict(self.tasks)
        tasks['T05'] = copy_task(tasks['T05'], duration=3)
        rows = read_reference_schedule(SCHEDULE_PATH)
        for row in rows:
            if row['task_id'] == 'T05':
                row['finish_day'] = 11
            if row['task_id'] == 'T06':
                row['start_day'] = 11
                row['finish_day'] = 12
        self.assertEqual(validate_schedule(rows, tasks, 2), 12)

    # ---- Lower bounds ----

    def test_precedence_and_worker_bounds_are_lower_than_optimum(self):
        """Critical path is 9 and workload is 8, both below the real answer of 11."""
        self.assertEqual(lower_bounds(self.tasks, 2), (9, 8))

    def test_group_split_lower_bound(self):
        """The group split bound is 11 for 2 workers and stays safe for other cases."""
        self.assertEqual(group_split_bound(self.tasks, 2), 11)
        self.assertEqual(combined_lower_bound(self.tasks, 2), 11)
        self.assertEqual(lower_bounds(self.tasks, 2), (9, 8))  # API unchanged
        one = combined_lower_bound(load_tasks(TASKS_PATH, 1), 1)
        three = combined_lower_bound(load_tasks(TASKS_PATH, 3), 3)
        self.assertLessEqual(one, 15)
        self.assertLessEqual(three, 9)
        longer = dict(self.tasks)
        longer['T05'] = copy_task(longer['T05'], duration=3)
        self.assertLessEqual(combined_lower_bound(longer, 2), 12)


if __name__ == '__main__':
    unittest.main(verbosity=2)
