"""Phase 2: run BFS, UCS, Greedy and A* on six scenarios and write comparison.csv.

Usage:
    python -m experiments.comparison [--output comparison.csv]

Every number in the output comes from a real run. Tasks are read only through
load_tasks (data_validation.py). Small and modified datasets are written to a
temporary folder as CSV files, loaded, and then removed.

Python standard library only.
"""
import argparse
import csv
import os
import sys
import tempfile

from scheduling.astar import astar_search
from scheduling.bfs import bfs_search
from scheduling.data_validation import DataValidationError, load_tasks
from scheduling.greedy import greedy_search
from scheduling.results_io import ResultsCsvError, write_results_csv
from scheduling.ucs import ucs_search

HEADER = ('task_id', 'duration', 'depends_on', 'workers_required')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_FILE = os.path.join(BASE_DIR, 'data', 'tasks.csv')

ALGORITHMS = (
    ('bfs', bfs_search),
    ('ucs', ucs_search),
    ('greedy', greedy_search),
    ('astar', astar_search),
)

# Small built-in datasets: (task_id, duration, depends_on, workers_required).
INDEPENDENT_ROWS = (
    ('T01', 3, 'None', 1),
    ('T02', 2, 'None', 1),
    ('T03', 4, 'None', 1),
    ('T04', 1, 'None', 1),
)
CHAIN_ROWS = (
    ('T01', 2, 'None', 1),
    ('T02', 3, 'T01', 1),
    ('T03', 1, 'T02', 1),
    ('T04', 2, 'T03', 1),
)


def _write_task_csv(path, rows):
    """Write task rows to a CSV file that load_tasks can read."""
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(HEADER)
        writer.writerows(rows)


def _baseline_rows_with_t05(duration):
    """Read tasks.csv rows as text and set T05's duration."""
    with open(BASELINE_FILE, 'r', encoding='utf-8-sig', newline='') as handle:
        rows = [list(row) for row in csv.reader(handle)][1:]
    for row in rows:
        if row and row[0].strip() == 'T05':
            row[1] = str(duration)
    return rows


def build_scenarios(temp_dir):
    """Return a list of (name, csv_path, worker_capacity) for the six scenarios."""
    t05_path = os.path.join(temp_dir, 'baseline_t05_3days.csv')
    _write_task_csv(t05_path, _baseline_rows_with_t05(3))
    independent_path = os.path.join(temp_dir, 'independent_tasks.csv')
    _write_task_csv(independent_path, INDEPENDENT_ROWS)
    chain_path = os.path.join(temp_dir, 'dependency_chain.csv')
    _write_task_csv(chain_path, CHAIN_ROWS)
    return [
        ('baseline_2w', BASELINE_FILE, 2),
        ('baseline_1w', BASELINE_FILE, 1),
        ('baseline_3w', BASELINE_FILE, 3),
        ('baseline_t05_3days', t05_path, 2),
        ('independent_tasks', independent_path, 2),
        ('dependency_chain', chain_path, 2),
    ]


def _error_row(scenario, algorithm):
    """A row for a run that raised an exception."""
    return {
        'scenario': scenario,
        'algorithm': algorithm,
        'makespan': None,
        'states_explored': 0,
        'execution_time_ms': 0.0,
        'schedule_valid': False,
        'status': 'error',
    }


def _result_row(scenario, algorithm, result):
    """Copy the seven CSV fields out of a Search_Result."""
    solved = result['status'] == 'solved'
    return {
        'scenario': scenario,
        'algorithm': algorithm,
        'makespan': result['makespan'] if solved else None,
        'states_explored': result['states_explored'],
        'execution_time_ms': result['execution_time_ms'],
        'schedule_valid': bool(result['schedule_valid']) if solved else False,
        'status': result['status'],
    }


def run_scenarios(scenarios):
    """Run every algorithm on every scenario. A failing run becomes an 'error' row."""
    rows = []
    for name, path, capacity in scenarios:
        try:
            tasks = load_tasks(path, capacity)
        except (DataValidationError, OSError) as exc:
            print(f'error: scenario {name}: cannot load tasks: {exc}', file=sys.stderr)
            for algorithm, _ in ALGORITHMS:
                rows.append(_error_row(name, algorithm))
            continue
        for algorithm, search in ALGORITHMS:
            try:
                rows.append(_result_row(name, algorithm, search(tasks, capacity)))
            except Exception as exc:  # one failed run must not stop the others
                print(f'error: {name}/{algorithm} failed: {type(exc).__name__}: {exc}',
                      file=sys.stderr)
                rows.append(_error_row(name, algorithm))
    return rows


def check_ucs_minimal(rows):
    """Raise ValueError unless UCS is <= every other solved row in each scenario."""
    ucs = {}
    for row in rows:
        if row['algorithm'] == 'ucs' and row['status'] == 'solved':
            ucs[row['scenario']] = row['makespan']
    for row in rows:
        if row['status'] != 'solved' or row['algorithm'] == 'ucs':
            continue
        best = ucs.get(row['scenario'])
        if best is not None and best > row['makespan']:
            raise ValueError(
                f"UCS makespan {best} is larger than {row['algorithm']} makespan "
                f"{row['makespan']} in scenario {row['scenario']}")


def validate_output_path(path):
    """Reject empty paths, NUL characters and non-existent destination folders."""
    if not path or '\x00' in path:
        raise ValueError('output path must be a non-empty path without NUL characters')
    if os.path.isdir(path):
        raise ValueError(f'output path is a directory: {path}')
    folder = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(folder):
        raise ValueError(f'output folder does not exist: {folder}')


def main(argv=None):
    """Build scenarios, run all algorithms, check UCS, write the CSV. Returns an exit code."""
    parser = argparse.ArgumentParser(description='Compare BFS, UCS, Greedy and A*')
    parser.add_argument('--output', default=os.path.join(BASE_DIR, 'results', 'comparison.csv'))
    args = parser.parse_args(argv)
    try:
        validate_output_path(args.output)
    except ValueError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix='comparison_') as temp_dir:
        scenarios = build_scenarios(temp_dir)
        rows = run_scenarios(scenarios)

    try:
        check_ucs_minimal(rows)
    except ValueError as exc:
        print(f'error: UCS check failed: {exc}', file=sys.stderr)
        return 1
    try:
        write_results_csv(args.output, rows)
    except ResultsCsvError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    print(f'Wrote {len(rows)} rows to {args.output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
