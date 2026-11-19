"""Phase 3: write and read the heuristic results CSV.

One row per search run, with thirteen columns (see COLUMNS). Writing and then
reading gives back the same values, and writing those values again gives a
file with exactly the same bytes.

Python standard library only. Every problem is reported as a HeuristicCsvError
with a short message that names the row and the column. No stack trace text is
put in the message.
"""
import csv
import math
import os
import tempfile

from scheduling.results_io import ALLOWED_STATUSES

COLUMNS = ('scenario_id', 'seed', 'task_count', 'worker_capacity', 'algorithm',
           'heuristic', 'search_status', 'makespan_days', 'states_expanded',
           'states_generated', 'runtime_ms', 'solution_valid', 'optimality_gap_pct')

_COUNT_COLUMNS = ('task_count', 'worker_capacity', 'states_expanded', 'states_generated')


class HeuristicCsvError(Exception):
    """Raised when a heuristic results CSV cannot be written, read or understood."""


def _is_int(value):
    """True for a real int (a bool does not count)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    """True for a finite int or float (a bool does not count)."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _bad(number, column, reason):
    return HeuristicCsvError(f'row {number}, column {column}: {reason}')


def _format_row(row, number):
    """Check one result dict and return its thirteen CSV text values.

    number is the 1-based row number used in error messages. Extra keys are
    ignored. Bad values are rejected, not fixed.
    """
    if not isinstance(row, dict):
        raise HeuristicCsvError(f'row {number}: expected a dict')
    for column in COLUMNS:
        if column not in row:
            raise _bad(number, column, 'missing column')

    for column in ('scenario_id', 'algorithm', 'heuristic'):
        if not isinstance(row[column], str) or row[column] == '':
            raise _bad(number, column, 'must be non-empty text')

    seed = row['seed']
    if seed is None:
        seed_text = ''
    elif _is_int(seed):
        seed_text = str(seed)
    else:
        raise _bad(number, 'seed', 'must be a whole number or None')

    counts = {}
    for column in _COUNT_COLUMNS:
        value = row[column]
        if not (_is_int(value) and value >= 0):
            raise _bad(number, column, 'must be a non-negative whole number')
        counts[column] = str(value)

    status = row['search_status']
    if status not in ALLOWED_STATUSES:
        raise _bad(number, 'search_status', f'unknown status {status!r}')

    solved = status == 'solved'
    makespan = row['makespan_days']
    gap = row['optimality_gap_pct']
    if not solved:
        if makespan is not None:
            raise _bad(number, 'makespan_days', 'must be empty unless status is solved')
        if gap is not None:
            raise _bad(number, 'optimality_gap_pct', 'must be empty unless status is solved')
        makespan_text = gap_text = ''
    else:
        if not (_is_int(makespan) and makespan >= 0):
            raise _bad(number, 'makespan_days', 'must be a non-negative whole number')
        makespan_text = str(makespan)
        if gap is None:
            gap_text = ''
        elif _is_number(gap):
            gap_text = repr(float(gap))
        else:
            raise _bad(number, 'optimality_gap_pct', 'must be a finite number or None')

    millis = row['runtime_ms']
    if not (_is_number(millis) and millis >= 0):
        raise _bad(number, 'runtime_ms', 'must be a finite number >= 0')

    valid = row['solution_valid']
    if not isinstance(valid, bool):
        raise _bad(number, 'solution_valid', 'must be True or False')

    return [row['scenario_id'], seed_text, counts['task_count'], counts['worker_capacity'],
            row['algorithm'], row['heuristic'], status, makespan_text,
            counts['states_expanded'], counts['states_generated'], repr(float(millis)),
            'true' if valid else 'false', gap_text]


def write_heuristic_csv(path, rows):
    """Write the rows to path as UTF-8 CSV with \\n line endings.

    rows is a list of result dicts keyed by COLUMNS. Everything is checked
    first. The text goes to a temp file in the same folder and is moved over
    path with os.replace, so a failure never leaves a partial file and never
    touches an existing one. Raises HeuristicCsvError naming the path and the
    reason.
    """
    try:
        target = os.fspath(path)
    except TypeError:
        raise HeuristicCsvError('cannot write results: path must be a string or path') from None
    if not isinstance(target, str) or target == '':
        raise HeuristicCsvError('cannot write results: path must be a non-empty string')
    if isinstance(rows, (str, bytes, dict)):
        raise HeuristicCsvError(f'cannot write {target}: rows must be a list of dicts')

    try:
        values = [_format_row(row, number) for number, row in enumerate(rows, start=1)]
    except TypeError:
        raise HeuristicCsvError(f'cannot write {target}: rows must be a list of dicts') from None
    except HeuristicCsvError as exc:
        raise HeuristicCsvError(f'cannot write {target}: {exc}') from None

    folder = os.path.dirname(os.path.abspath(target))
    temp_name = None
    try:
        handle, temp_name = tempfile.mkstemp(prefix='.heuristic_', suffix='.tmp', dir=folder)
        with os.fdopen(handle, 'w', encoding='utf-8', newline='') as out:
            writer = csv.writer(out, lineterminator='\n')
            writer.writerow(COLUMNS)
            writer.writerows(values)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp_name, target)
        temp_name = None
    except (OSError, csv.Error, UnicodeError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        raise HeuristicCsvError(f'cannot write {target}: {reason}') from None
    finally:
        if temp_name is not None:
            try:
                os.remove(temp_name)
            except OSError:
                pass


def _parse_row(record, number):
    """Turn one CSV record (list of text) into a result dict, or raise HeuristicCsvError."""
    if len(record) < len(COLUMNS):
        raise _bad(number, COLUMNS[len(record)], 'missing column')
    if len(record) > len(COLUMNS):
        raise HeuristicCsvError(f'row {number}: unexpected extra value')
    cell = dict(zip(COLUMNS, record))

    for column in ('scenario_id', 'algorithm', 'heuristic', 'search_status',
                   'runtime_ms', 'solution_valid') + _COUNT_COLUMNS:
        if cell[column] == '':
            raise _bad(number, column, 'value is empty')

    result = {'scenario_id': cell['scenario_id'], 'algorithm': cell['algorithm'],
              'heuristic': cell['heuristic']}

    if cell['seed'] == '':
        result['seed'] = None
    else:
        try:
            result['seed'] = int(cell['seed'])
        except ValueError:
            raise _bad(number, 'seed', 'must be a whole number or empty') from None

    for column in _COUNT_COLUMNS:
        try:
            value = int(cell[column])
        except ValueError:
            raise _bad(number, column, 'must be a whole number') from None
        if value < 0:
            raise _bad(number, column, 'must not be negative')
        result[column] = value

    status = cell['search_status']
    if status not in ALLOWED_STATUSES:
        raise _bad(number, 'search_status', f'unknown status {status!r}')
    result['search_status'] = status

    solved = status == 'solved'
    if not solved:
        for column in ('makespan_days', 'optimality_gap_pct'):
            if cell[column] != '':
                raise _bad(number, column, 'must be empty unless status is solved')
        result['makespan_days'] = None
        result['optimality_gap_pct'] = None
    else:
        if cell['makespan_days'] == '':
            raise _bad(number, 'makespan_days', 'value is empty')
        try:
            makespan = int(cell['makespan_days'])
        except ValueError:
            raise _bad(number, 'makespan_days', 'must be a whole number') from None
        if makespan < 0:
            raise _bad(number, 'makespan_days', 'must not be negative')
        result['makespan_days'] = makespan
        if cell['optimality_gap_pct'] == '':
            result['optimality_gap_pct'] = None
        else:
            try:
                gap = float(cell['optimality_gap_pct'])
            except ValueError:
                raise _bad(number, 'optimality_gap_pct', 'must be a number') from None
            if not math.isfinite(gap):
                raise _bad(number, 'optimality_gap_pct', 'must be a finite number')
            result['optimality_gap_pct'] = gap

    try:
        millis = float(cell['runtime_ms'])
    except ValueError:
        raise _bad(number, 'runtime_ms', 'must be a number') from None
    if not math.isfinite(millis) or millis < 0:
        raise _bad(number, 'runtime_ms', 'must be a finite number >= 0')
    result['runtime_ms'] = millis

    if cell['solution_valid'] not in ('true', 'false'):
        raise _bad(number, 'solution_valid', 'must be true or false')
    result['solution_valid'] = cell['solution_valid'] == 'true'

    return {column: result[column] for column in COLUMNS}


def read_heuristic_csv(path):
    """Read a heuristic results CSV and return a list of result dicts in file order.

    Values come back as int, float, bool and None, so writing them again gives
    the same bytes. A missing header column is reported by name; a bad value is
    reported with its 1-based data row number and column name. On any error
    nothing is returned. Raises HeuristicCsvError.
    """
    try:
        source = os.fspath(path)
    except TypeError:
        raise HeuristicCsvError('cannot read results: path must be a string or path') from None
    if not isinstance(source, str) or source == '':
        raise HeuristicCsvError('cannot read results: path must be a non-empty string')

    records = []
    try:
        with open(source, 'r', encoding='utf-8', newline='') as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            if header is None:
                raise HeuristicCsvError(f'{source}: header is missing column {COLUMNS[0]}')
            for column in COLUMNS:
                if column not in header:
                    raise HeuristicCsvError(f'{source}: header is missing column {column}')
            if tuple(header) != COLUMNS:
                raise HeuristicCsvError(
                    f'{source}: header columns must be exactly {",".join(COLUMNS)}')
            for number, record in enumerate(reader, start=1):
                try:
                    records.append(_parse_row(record, number))
                except HeuristicCsvError as exc:
                    raise HeuristicCsvError(f'{source}: {exc}') from None
    except HeuristicCsvError:
        raise
    except OSError as exc:
        reason = exc.strerror or str(exc)
        raise HeuristicCsvError(f'cannot read {source}: {reason}') from None
    except (UnicodeError, csv.Error) as exc:
        raise HeuristicCsvError(f'cannot read {source}: {exc}') from None
    return records
