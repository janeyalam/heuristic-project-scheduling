"""Phase 3: run UCS, A* (H0-H3) and Greedy (H1, H3) on the same instances.

Usage:
    python -m experiments.heuristic_comparison [--output heuristic_results.csv]
                                   [--timeout SECONDS] [--max-expansions N]

Instances: the four SS scenarios (tasks.csv with 2, 1 and 3 workers, and T05 at
3 days with 2 workers) and the synthetic files in heuristic_test_data/ at
capacity 2. Tasks are read only through load_tasks (data_validation.py).

Every method runs under one shared timeout and one shared max_expansions. Each
run is timed 5 times; the median runtime is reported and the state counts come
from the first run. If an A* run with an admissible heuristic (H0 to H3) solves
an instance with a makespan different from UCS, nothing is written and the exit
code is 1.

Python standard library only. No value is passed to a shell.
"""
import argparse
import csv
import os
import statistics
import sys
import tempfile
import time

from scheduling.astar import astar_search
from scheduling.data_validation import DataValidationError, load_tasks
from scheduling.greedy import greedy_search
from experiments.heuristic_data import CAPACITY as SYNTHETIC_CAPACITY, INSTANCES
from scheduling.heuristic_io import COLUMNS, HeuristicCsvError, write_heuristic_csv
from scheduling.heuristics import (combined_heuristic, critical_path_remaining,
                        longest_remaining, zero_heuristic)
from scheduling.ucs import ucs_search

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_FILE = os.path.join(BASE_DIR, 'data', 'tasks.csv')
SYNTHETIC_DIR = os.path.join(BASE_DIR, 'data', 'heuristic_test_data')
DEFAULT_OUTPUT = os.path.join(BASE_DIR, 'results', 'heuristic_results.csv')

HEADER = ('task_id', 'duration', 'depends_on', 'workers_required')
REPEATS = 5

# Shared limits (module defaults; also CLI options).
DEFAULT_TIMEOUT_SECONDS = 60
MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS = 1, 3600
DEFAULT_MAX_EXPANSIONS = 200000
MIN_MAX_EXPANSIONS, MAX_MAX_EXPANSIONS = 1, 10000000

# (algorithm, heuristic label, admissible A* heuristic?, function(tasks, capacity, timeout, limit))
def _ucs(tasks, capacity, timeout, limit):
    return ucs_search(tasks, capacity, timeout_seconds=timeout, max_expansions=limit)


def _astar(heuristic):
    def run(tasks, capacity, timeout, limit):
        return astar_search(tasks, capacity, heuristic=heuristic,
                            timeout_seconds=timeout, max_expansions=limit)
    return run


def _greedy(heuristic):
    def run(tasks, capacity, timeout, limit):
        return greedy_search(tasks, capacity, heuristic=heuristic,
                             timeout_seconds=timeout, max_expansions=limit)
    return run


METHODS = (
    ('ucs', 'none', _ucs),
    ('astar', 'H0', _astar(zero_heuristic)),
    ('astar', 'H1', _astar(longest_remaining)),
    ('astar', 'H2', _astar(critical_path_remaining)),
    ('astar', 'H3', _astar(combined_heuristic)),
    ('greedy', 'H1', _greedy(longest_remaining)),
    ('greedy', 'H3', _greedy(combined_heuristic)),
)
ADMISSIBLE = frozenset(('H0', 'H1', 'H2', 'H3'))


class OptimalityError(Exception):
    """An A* run with an admissible heuristic did not match the UCS makespan."""


def _baseline_rows_with_t05(duration):
    with open(BASELINE_FILE, 'r', encoding='utf-8-sig', newline='') as handle:
        rows = [list(row) for row in csv.reader(handle)][1:]
    for row in rows:
        if row and row[0].strip() == 'T05':
            row[1] = str(duration)
    return rows


def _write_task_csv(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(HEADER)
        writer.writerows(rows)


def build_instances(synthetic_dir=SYNTHETIC_DIR):
    """Load all instances. Returns a list of dicts with scenario_id, seed, tasks, capacity.

    Tasks come only from load_tasks. The T05 variant is written to a temporary
    folder that is removed before returning.
    """
    instances = []
    for name, path, capacity in (('baseline_2w', BASELINE_FILE, 2),
                                 ('baseline_1w', BASELINE_FILE, 1),
                                 ('baseline_3w', BASELINE_FILE, 3)):
        instances.append({'scenario_id': name, 'seed': None, 'capacity': capacity,
                          'tasks': load_tasks(path, capacity)})
    with tempfile.TemporaryDirectory(prefix='heuristic_') as temp_dir:
        t05_path = os.path.join(temp_dir, 'baseline_t05_3days.csv')
        _write_task_csv(t05_path, _baseline_rows_with_t05(3))
        instances.append({'scenario_id': 'baseline_t05_3days', 'seed': None, 'capacity': 2,
                          'tasks': load_tasks(t05_path, 2)})
    for file_name, _shape, seed, _count in INSTANCES:
        path = os.path.join(synthetic_dir, file_name)
        instances.append({'scenario_id': os.path.splitext(file_name)[0], 'seed': seed,
                          'capacity': SYNTHETIC_CAPACITY,
                          'tasks': load_tasks(path, SYNTHETIC_CAPACITY)})
    return instances


def _error_row(instance, algorithm, heuristic):
    return {
        'scenario_id': instance['scenario_id'], 'seed': instance['seed'],
        'task_count': len(instance['tasks']), 'worker_capacity': instance['capacity'],
        'algorithm': algorithm, 'heuristic': heuristic, 'search_status': 'error',
        'makespan_days': None, 'states_expanded': 0, 'states_generated': 0,
        'runtime_ms': 0.0, 'solution_valid': False, 'optimality_gap_pct': None,
    }


def _run_method(instance, algorithm, heuristic, func, timeout, max_expansions, repeats):
    """Run one method `repeats` times. Returns a row (without gap)."""
    tasks, capacity = instance['tasks'], instance['capacity']
    times = []
    first = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = func(tasks, capacity, timeout, max_expansions)
        times.append((time.perf_counter() - start) * 1000.0)
        if first is None:
            first = result
    solved = first['status'] == 'solved'
    return {
        'scenario_id': instance['scenario_id'], 'seed': instance['seed'],
        'task_count': len(tasks), 'worker_capacity': capacity,
        'algorithm': algorithm, 'heuristic': heuristic,
        'search_status': first['status'],
        'makespan_days': first['makespan'] if solved else None,
        'states_expanded': first['states_explored'],
        'states_generated': first.get('states_generated', 0),
        'runtime_ms': statistics.median(times),
        'solution_valid': bool(first['schedule_valid']) if solved else False,
        'optimality_gap_pct': None,
    }


def run_instance(instance, methods=METHODS, timeout=DEFAULT_TIMEOUT_SECONDS,
                 max_expansions=DEFAULT_MAX_EXPANSIONS, repeats=REPEATS):
    """Run every method on one instance and return its rows (gaps filled in).

    A method that raises becomes an 'error' row and the others still run.
    Raises OptimalityError if an A* row with an admissible heuristic is solved
    with a makespan different from the UCS makespan.
    """
    rows = []
    for algorithm, heuristic, func in methods:
        try:
            rows.append(_run_method(instance, algorithm, heuristic, func,
                                    timeout, max_expansions, repeats))
        except Exception as exc:  # one failed run must not stop the others
            print(f"error: {instance['scenario_id']}/{algorithm}/{heuristic} failed: "
                  f'{type(exc).__name__}: {exc}', file=sys.stderr)
            rows.append(_error_row(instance, algorithm, heuristic))

    optimum = None
    for row in rows:
        if row['algorithm'] == 'ucs' and row['search_status'] == 'solved':
            optimum = row['makespan_days']
    if optimum is not None:
        for row in rows:
            if row['search_status'] != 'solved':
                continue
            if optimum == 0:
                row['optimality_gap_pct'] = 0.0 if row['makespan_days'] == 0 else None
            else:
                row['optimality_gap_pct'] = 100.0 * (row['makespan_days'] - optimum) / optimum
            if (row['algorithm'] == 'astar' and row['heuristic'] in ADMISSIBLE
                    and row['makespan_days'] != optimum):
                raise OptimalityError(
                    f"{instance['scenario_id']}: A*/{row['heuristic']} makespan "
                    f"{row['makespan_days']} differs from UCS makespan {optimum}")
    return rows


def run_all(instances, methods=METHODS, timeout=DEFAULT_TIMEOUT_SECONDS,
            max_expansions=DEFAULT_MAX_EXPANSIONS, repeats=REPEATS):
    """Run every method on every instance and return all rows."""
    rows = []
    for instance in instances:
        rows.extend(run_instance(instance, methods, timeout, max_expansions, repeats))
    return rows


def validate_output_path(path):
    """Reject empty paths, NUL, non-.csv names, directories and missing folders."""
    if not isinstance(path, str) or not path.strip() or '\x00' in path:
        raise ValueError('output path must be a non-empty path without NUL characters')
    if not path.lower().endswith('.csv'):
        raise ValueError('output path must end with .csv')
    if os.path.isdir(path):
        raise ValueError(f'output path is a directory: {path}')
    folder = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(folder):
        raise ValueError(f'output folder does not exist: {folder}')


def _int_range(low, high):
    def parse(text):
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f'must be a whole number, got {text!r}') from None
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(f'must be between {low} and {high}')
        return value
    return parse


def format_summary(rows):
    """Return a short fixed-width summary table as text."""
    lines = [f"{'scenario':<20} {'method':<10} {'status':<11} {'makespan':>8} "
             f"{'expanded':>9} {'ms':>9} {'gap%':>7}"]
    for row in rows:
        method = row['algorithm'] if row['heuristic'] == 'none' \
            else f"{row['algorithm']}/{row['heuristic']}"
        makespan = '' if row['makespan_days'] is None else str(row['makespan_days'])
        gap = '' if row['optimality_gap_pct'] is None else f"{row['optimality_gap_pct']:.1f}"
        lines.append(f"{row['scenario_id']:<20} {method:<10} {row['search_status']:<11} "
                     f"{makespan:>8} {row['states_expanded']:>9} "
                     f"{row['runtime_ms']:>9.2f} {gap:>7}")
    return '\n'.join(lines)


def main(argv=None, methods=METHODS):
    """Run the comparison and write the CSV. Returns the exit code.

    0 success, 1 optimality mismatch or write failure, 2 bad option or path.
    `methods` may be replaced by tests (for example with a failing method).
    """
    parser = argparse.ArgumentParser(description='Compare UCS, A* and Greedy heuristics')
    parser.add_argument('--output', default=DEFAULT_OUTPUT)
    parser.add_argument('--timeout', type=_int_range(MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS),
                        default=DEFAULT_TIMEOUT_SECONDS, help='seconds per search call')
    parser.add_argument('--max-expansions',
                        type=_int_range(MIN_MAX_EXPANSIONS, MAX_MAX_EXPANSIONS),
                        default=DEFAULT_MAX_EXPANSIONS, help='expansion limit per search call')
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        validate_output_path(args.output)
    except ValueError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2

    try:
        instances = build_instances()
    except (DataValidationError, OSError) as exc:
        print(f'error: cannot load instances: {exc}', file=sys.stderr)
        return 1
    try:
        rows = run_all(instances, methods, args.timeout, args.max_expansions)
    except OptimalityError as exc:
        print(f'error: optimality check failed: {exc}', file=sys.stderr)
        return 1
    try:
        write_heuristic_csv(args.output, rows)
    except HeuristicCsvError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    print(format_summary(rows))
    print(f'Wrote {len(rows)} rows to {args.output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
