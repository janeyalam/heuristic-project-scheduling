"""Phase 2: write and read the comparison results CSV.

One row per search run, with seven columns (see COLUMNS). Writing and then
reading gives back the same values, and writing those values again gives a
file with exactly the same bytes.

Python standard library only. Every problem is reported as a ResultsCsvError
with a short message. No stack trace text is put in the message.
"""
import csv
import math
import os
import tempfile

COLUMNS = ('scenario', 'algorithm', 'makespan', 'states_explored',
           'execution_time_ms', 'schedule_valid', 'status')

# The four search statuses plus 'error' for a run that raised (comparison.py).
ALLOWED_STATUSES = ('solved', 'no solution', 'timeout', 'state_limit', 'invalid input', 'error')


class ResultsCsvError(Exception):
    """Raised when a results CSV cannot be written, read or understood."""


def _is_int(value):
    """True for a real int (a bool does not count)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _format_row(row, number):
    """Check one result dict and return its seven CSV text values.

    number is the 1-based row number used in error messages. Extra keys in the
    dict (schedule, error, ...) are ignored because only the seven columns are
    written. Bad values are rejected, not fixed.
    """
    if not isinstance(row, dict):
        raise ResultsCsvError(f'row {number}: expected a dict')
    for column in COLUMNS:
        if column not in row:
            raise ResultsCsvError(f'row {number}: missing column {column}')

    for column in ('scenario', 'algorithm'):
        if not isinstance(row[column], str):
            raise ResultsCsvError(f'row {number}: {column} must be text')
        if row[column] == '':
            raise ResultsCsvError(f'row {number}: {column} must not be empty')

    makespan = row['makespan']
    if makespan is None:
        makespan_text = ''
    elif _is_int(makespan) and makespan >= 0:
        makespan_text = str(makespan)
    else:
        raise ResultsCsvError(f'row {number}: makespan must be a non-negative whole number or None')

    states = row['states_explored']
    if not (_is_int(states) and states >= 0):
        raise ResultsCsvError(f'row {number}: states_explored must be a non-negative whole number')

    millis = row['execution_time_ms']
    if isinstance(millis, bool) or not isinstance(millis, (int, float)):
        raise ResultsCsvError(f'row {number}: execution_time_ms must be a number')
    millis = float(millis)
    if not math.isfinite(millis) or millis < 0:
        raise ResultsCsvError(f'row {number}: execution_time_ms must be a finite number >= 0')

    valid = row['schedule_valid']
    if not isinstance(valid, bool):
        raise ResultsCsvError(f'row {number}: schedule_valid must be True or False')

    status = row['status']
    if status not in ALLOWED_STATUSES:
        raise ResultsCsvError(f'row {number}: unknown status {status!r}')

    return [row['scenario'], row['algorithm'], makespan_text, str(states),
            repr(millis), 'true' if valid else 'false', status]


def write_results_csv(path, rows):
    """Write the rows to path as UTF-8 CSV with \\n line endings.

    rows is a list of result dicts (keys as in COLUMNS; extra keys are ignored).
    Everything is checked first. The text goes to a temp file in the same folder
    and is moved over path with os.replace, so a failure never leaves a partial
    file and never touches an existing one. Raises ResultsCsvError naming the
    path and the reason.
    """
    try:
        target = os.fspath(path)
    except TypeError:
        raise ResultsCsvError('cannot write results: path must be a string or path') from None
    if not isinstance(target, str) or target == '':
        raise ResultsCsvError('cannot write results: path must be a non-empty string')
    if isinstance(rows, (str, bytes, dict)):
        raise ResultsCsvError(f'cannot write {target}: rows must be a list of dicts')

    try:
        values = [_format_row(row, number) for number, row in enumerate(rows, start=1)]
    except TypeError:
        raise ResultsCsvError(f'cannot write {target}: rows must be a list of dicts') from None
    except ResultsCsvError as exc:
        raise ResultsCsvError(f'cannot write {target}: {exc}') from None

    folder = os.path.dirname(os.path.abspath(target))
    temp_name = None
    try:
        handle, temp_name = tempfile.mkstemp(prefix='.results_', suffix='.tmp', dir=folder)
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
        raise ResultsCsvError(f'cannot write {target}: {reason}') from None
    finally:
        if temp_name is not None:
            try:
                os.remove(temp_name)
            except OSError:
                pass


def _parse_row(record, number):
    """Turn one CSV record (list of text) into a result dict, or raise ResultsCsvError."""
    if len(record) < len(COLUMNS):
        raise ResultsCsvError(
            f'row {number}: missing column {COLUMNS[len(record)]}')
    if len(record) > len(COLUMNS):
        raise ResultsCsvError(f'row {number}: unexpected extra value')

    scenario, algorithm, makespan, states, millis, valid, status = record
    for column, text in (('scenario', scenario), ('algorithm', algorithm),
                         ('states_explored', states), ('execution_time_ms', millis),
                         ('schedule_valid', valid), ('status', status)):
        if text == '':
            raise ResultsCsvError(f'row {number}: missing column {column}')

    try:
        makespan_value = None if makespan == '' else int(makespan)
        states_value = int(states)
        millis_value = float(millis)
    except ValueError:
        raise ResultsCsvError(f'row {number}: a number could not be read') from None
    if (makespan_value is not None and makespan_value < 0) or states_value < 0 \
            or not math.isfinite(millis_value) or millis_value < 0:
        raise ResultsCsvError(f'row {number}: numbers must not be negative')

    if valid not in ('true', 'false'):
        raise ResultsCsvError(f'row {number}: schedule_valid must be true or false')
    if status not in ALLOWED_STATUSES:
        raise ResultsCsvError(f'row {number}: unknown status {status!r}')

    return {
        'scenario': scenario,
        'algorithm': algorithm,
        'makespan': makespan_value,
        'states_explored': states_value,
        'execution_time_ms': millis_value,
        'schedule_valid': valid == 'true',
        'status': status,
    }


def read_results_csv(path):
    """Read a results CSV and return a list of result dicts in file order.

    Values come back as int, float, bool and None, so writing them again gives
    the same bytes. A missing header column is reported by name; a short row is
    reported with the column name and its 1-based data row number. On any error
    nothing is returned. Raises ResultsCsvError.
    """
    try:
        source = os.fspath(path)
    except TypeError:
        raise ResultsCsvError('cannot read results: path must be a string or path') from None
    if not isinstance(source, str) or source == '':
        raise ResultsCsvError('cannot read results: path must be a non-empty string')

    records = []
    try:
        with open(source, 'r', encoding='utf-8', newline='') as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            if header is None:
                raise ResultsCsvError(f'{source}: header is missing column {COLUMNS[0]}')
            for column in COLUMNS:
                if column not in header:
                    raise ResultsCsvError(f'{source}: header is missing column {column}')
            if tuple(header) != COLUMNS:
                raise ResultsCsvError(f'{source}: header columns must be exactly {", ".join(COLUMNS)}')
            for number, record in enumerate(reader, start=1):
                try:
                    records.append(_parse_row(record, number))
                except ResultsCsvError as exc:
                    raise ResultsCsvError(f'{source}: {exc}') from None
    except ResultsCsvError:
        raise
    except OSError as exc:
        reason = exc.strerror or str(exc)
        raise ResultsCsvError(f'cannot read {source}: {reason}') from None
    except (UnicodeError, csv.Error) as exc:
        raise ResultsCsvError(f'cannot read {source}: {exc}') from None
    return records
