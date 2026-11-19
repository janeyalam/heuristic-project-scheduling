"""Demo: run BFS, UCS, Greedy and A* on a task file and print the results.

Usage:
    python -m experiments.demo [--tasks tasks.csv] [--workers 2]
"""
import argparse
import os
import sys

from scheduling.astar import astar_search
from scheduling.bfs import bfs_search
from scheduling.data_validation import DataValidationError, load_tasks
from scheduling.greedy import greedy_search
from scheduling.ucs import ucs_search

ALGORITHMS = (
    ('bfs', bfs_search),
    ('ucs', ucs_search),
    ('greedy', greedy_search),
    ('astar', astar_search),
)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compare the four search algorithms')
    parser.add_argument('--tasks', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'tasks.csv'))
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args(argv)

    try:
        tasks = load_tasks(args.tasks, args.workers)
    except (DataValidationError, OSError) as exc:
        print(f'error: cannot load tasks: {exc}', file=sys.stderr)
        return 1

    print(f'Tasks: {args.tasks}   Workers: {args.workers}\n')
    
    print(f'{"algorithm":<10}{"status":<10}{"makespan":>9}{"states":>9}{"valid":>8}')
    
    results = {}
    for name, search in ALGORITHMS:
        result = search(tasks, args.workers)
        results[name] = result
        print(f'{name:<10}{result["status"]:<10}{str(result["makespan"]):>9}'
              f'{result["states_explored"]:>9}{str(result["schedule_valid"]):>8}')

    best = results['ucs']
    if best['status'] == 'solved':
        print('\nOptimal schedule (UCS):')
        print(f'{"task":<6}{"start":>6}{"finish":>8}')
        for entry in sorted(best['schedule'], key=lambda e: (e['start_time'], e['task_id'])):
            print(f'{entry["task_id"]:<6}{entry["start_time"]:>6}{entry["finish_time"]:>8}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
