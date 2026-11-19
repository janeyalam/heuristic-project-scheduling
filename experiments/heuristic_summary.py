"""Phase 3: print a markdown summary table from a heuristic results CSV.

Usage:
    python -m experiments.heuristic_summary heuristic_results.csv

Reads an existing results CSV with heuristic_io.read_heuristic_csv and prints a
markdown table. No search is run and the CSV is never changed.

Rows are grouped by scenario group ('baseline' for scenario ids that start with
'baseline', otherwise the text before the first '_') and by method
(algorithm/heuristic). Only solved rows count. For each group and method the
table shows the median states expanded, the median runtime in ms, and, for
Greedy only, the median and maximum optimality gap in percent. A value that
cannot be computed is shown as '-'.

Exit codes: 0 success, 2 bad path or unreadable file.
Python standard library only.
"""
import os
import statistics
import sys

from scheduling.heuristic_io import HeuristicCsvError, read_heuristic_csv

HEADER = ('group', 'method', 'solved', 'median states expanded',
          'median runtime (ms)', 'median gap (%)', 'max gap (%)')


def scenario_group(scenario_id):
    """Return 'baseline' for baseline scenarios, else the prefix before '_'."""
    if scenario_id.startswith('baseline'):
        return 'baseline'
    return scenario_id.split('_', 1)[0]


def _method(row):
    if row['heuristic'] == 'none':
        return row['algorithm']
    return f"{row['algorithm']}/{row['heuristic']}"


def _number(value, decimals):
    return '-' if value is None else f'{value:.{decimals}f}'


def summary_markdown(rows):
    """Return the summary as a markdown table (text, no trailing newline).

    rows is a list of result dicts as returned by read_heuristic_csv.
    """
    cells = {}
    for row in rows:
        if row['search_status'] != 'solved':
            continue
        key = (scenario_group(row['scenario_id']), _method(row), row['algorithm'])
        cells.setdefault(key, []).append(row)

    lines = ['| ' + ' | '.join(HEADER) + ' |',
             '|' + '|'.join([' --- '] * len(HEADER)) + '|']
    for group, method, algorithm in sorted(cells):
        group_rows = cells[(group, method, algorithm)]
        expanded = statistics.median(r['states_expanded'] for r in group_rows)
        runtime = statistics.median(r['runtime_ms'] for r in group_rows)
        median_gap = max_gap = None
        if algorithm == 'greedy':
            gaps = [r['optimality_gap_pct'] for r in group_rows
                    if r['optimality_gap_pct'] is not None]
            if gaps:
                median_gap, max_gap = statistics.median(gaps), max(gaps)
        lines.append('| ' + ' | '.join((
            group, method, str(len(group_rows)), _number(expanded, 1),
            _number(runtime, 2), _number(median_gap, 1), _number(max_gap, 1))) + ' |')
    return '\n'.join(lines)


def validate_input_path(path):
    """Reject empty paths, NUL, non-.csv names and anything that is not a file."""
    if not isinstance(path, str) or not path.strip() or '\x00' in path:
        raise ValueError('path must be a non-empty path without NUL characters')
    if not path.lower().endswith('.csv'):
        raise ValueError('path must end with .csv')
    if not os.path.isfile(path):
        raise ValueError(f'not a file: {path}')


def main(argv=None):
    """Print the summary for the CSV named in argv. Returns the exit code."""
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) != 1:
        print('usage: python -m experiments.heuristic_summary RESULTS.csv', file=sys.stderr)
        return 2
    try:
        validate_input_path(args[0])
        rows = read_heuristic_csv(args[0])
    except (ValueError, HeuristicCsvError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    print(summary_markdown(rows))
    return 0


if __name__ == '__main__':
    sys.exit(main())
