# SB's data_validation_SB.py vs our data_validation.py

## Summary answer

**Partly aligned. Not drop-in safe.** SB's file has the same core idea (read tasks.csv, validate, compute lower bounds) and the same column names. It works with `scheduling_model.py` without crashing. But it fails `test_phase1.py` at import, accepts several inputs our rules reject, and reports a **combined lower bound of 9 days for tasks.csv instead of the required 11**. The requirements say the minimum is 11 days, so SB's bound contradicts them.

Nothing in the project was modified. The test copy lived in `%TEMP%\sbcmp` and has been deleted. Python 3.14.3, `__pycache__` cleared first.

## 1. Side-by-side API

| Item | Ours (`data_validation.py`) | SB's (`data_validation_SB.py`) |
|---|---|---|
| Task class | frozen dataclass `Task(task_id, duration, dependencies: tuple, workers_required)` | Same four fields, same frozen dataclass (typed `Tuple[str, ...]`) |
| Error class | `DataValidationError(ValueError)` | **None.** Raises plain `ValueError` and `FileNotFoundError` |
| `load_tasks` | `load_tasks(path, worker_capacity=2)` returns dict in file order | `load_tasks(path, worker_capacity)` (no default) returns dict in file order. Same Task values for tasks.csv |
| Validation function | `validate_tasks(tasks, cap)` | none (validation is inside `load_tasks`) |
| Bounds | `lower_bounds` returns `(9, 8)`, `group_split_bound` returns 11, `combined_lower_bound` returns 11 | `critical_path_lower_bound`, `capacity_lower_bound`, `combined_lower_bound` (max of those two only) |
| Helpers | `is_valid_task_id`, `positive_int`, `parse_dependencies`, `check_for_cycle`, `earliest_finish`, `place_jobs`, `_best_split`, `longest_after` | `_parse_dependencies`, plus `generate_dataset` (extra) |
| Constant | `REQUIRED_COLUMNS` | none (a local set) |
| CLI | `python data_validation.py tasks.csv --workers 2` | `csv_file`, `--worker`/`--workers` (default 2), plus `--generate N`, `--seed` |

## 2. Drop-in test (temp folder only)

- `python -m unittest -v test_phase1`: **ERROR**. `ImportError: cannot import name 'DataValidationError' from 'data_validation'`. The whole test module fails to load, so 0 tests run.
- `python scheduling_model.py tasks.csv --workers 2`: **runs**. It prints the reference schedule, "VALID reference schedule: 11 working days", then `Lower bound 9 < schedule length 11; optimality is not proven.` This is wrong. 11 is optimal, and our version proves it. The cause is SB's combined bound (9).
- Only `Task`, `load_tasks` and `combined_lower_bound` are used by `scheduling_model.py`, and those exist in SB's file. Missing for tests: `DataValidationError`, `group_split_bound`, `lower_bounds`, `validate_tasks`.

## 3. CLI comparison on tasks.csv (both exit 0)

Ours:
```
VALID: 6 tasks, 2 workers, all dependencies valid and acyclic.
Lower bounds: critical path 9 days; worker workload 8 days.
Parallel-split lower bound: 11 days ...
Combined lower bound: 11 days. ...
```
SB's:
```
Validation Successful: 6 task(s) loaded from 'tasks.csv'.
Worker Capacity      : 2
Critical Path Bound  : 9 day(s)
Capacity Lower Bound : 8 day(s)
Combined Lower Bound : 9 day(s)
Loaded Tasks: ... (one line per task)
```
Differences: wording, SB lists each task (nice), but SB's combined bound is 9 not 11. Errors: ours prints `INVALID INPUT: ...` to stderr and exits 1 (via `parser.exit`). SB prints `[Validation Error] ...` to stderr and exits 1. Both exit 1, different text.

## 4. Behavior table (both modules imported by file path)

| case | ours | SB's | aligned? |
|---|---|---|---|
| tasks.csv | ACCEPT | ACCEPT | yes |
| old 5-column header (with task_name) | REJECT | ACCEPT | **NO** |
| wrong column order | REJECT | ACCEPT | **NO** |
| extra column | REJECT | ACCEPT | **NO** |
| unquoted `T02, T03` row | REJECT | REJECT | yes (SB's rejection is by accident, see below) |
| `T02\|T03\|T04` deps | ACCEPT | REJECT (unknown task `T02\|T03\|T04`) | **NO** |
| deps `None` / `none` / empty | ACCEPT | ACCEPT | yes |
| duplicate id | REJECT | REJECT | yes |
| bad ids T1, t01, T001, A, TASK_01 | REJECT | ACCEPT (all five) | **NO** |
| duration 0, -1, 2.5 | REJECT | REJECT | yes |
| duration ` 3 ` | ACCEPT | ACCEPT | yes |
| duration `+3` | REJECT | ACCEPT | **NO** |
| duration Arabic-Indic digit `٣` | REJECT | ACCEPT | **NO** |
| id with non-ASCII digits `T١٢` | REJECT | ACCEPT | **NO** |
| workers_required 0; 3 with capacity 2 | REJECT | REJECT | yes |
| self dependency | REJECT | REJECT | yes |
| missing dependency | REJECT | REJECT | yes |
| 2-task and 3-task cycles | REJECT | REJECT | yes |
| empty file; header only | REJECT | REJECT | yes |
| missing file | REJECT `DataValidationError` (is a ValueError) | `FileNotFoundError` (not a ValueError) | **NO** (type) |
| BOM, CRLF, blank line in middle | ACCEPT | ACCEPT | yes |
| capacity 0, 2.0 | REJECT | REJECT | yes |
| capacity `True` | REJECT | ACCEPT (bool is an int) | **NO** (minor) |
| capacity 1, 3 | ACCEPT | ACCEPT | yes |

Why the unquoted row is rejected by SB: `csv.DictReader` puts the extra cells under a `None` key, and SB's `int(...)` on the shifted cell fails. It is not an explicit "malformed row" check. Error type for every SB rejection is plain `ValueError`, so the "aligned" column compares accept/reject only.

## 5. Lower bounds

| Case | Ours combined | SB combined | Expected |
|---|---|---|---|
| tasks.csv, cap 1 | 15 | 15 | 15 |
| tasks.csv, cap 2 | 11 | **9** (cp 9, capacity 8) | 11 |
| tasks.csv, cap 3 | 9 | 9 | 9 |
| T05 = 3 days, cap 2 | 12 | **10** | 12 |

SB only takes `max(critical path, workload)`. It has no equivalent of our `group_split_bound` (T02, T03, T04 share two workers, so one worker needs at least 6 days). That step is the explanation the requirements give for 11. Capacity 1 and 3 match only because there one of the two simple bounds happens to be tight.

## 6. Style, bugs, security

Beginner readability (our style avoids typing, comprehensions, regex, nested functions):
- `from typing import Dict, List, Tuple` and annotations like `Dict[str, List[str]]`.
- `str | Path` in signatures needs Python 3.10+. Fails on older Python.
- List and dict comprehensions, set comprehension, generator expression with `max(..., default=0)`, `raise ... from exc`, f-string `!r`, `deque` and Kahn's algorithm, `rng.sample`, `sorted(set)`.
- `except Exception` in `main` (catch-all). Our rule is specific errors only.
- `generate_dataset` and `--generate`/`--seed` use `random`. Not asked for in the requirements.
- Docstrings are short and have no examples, unlike ours.

Bugs and surprises:
1. Combined bound is wrong for this project (9, not 11). This is the main defect.
2. Task id format is never checked. `T1`, `t01`, `TASK_01` pass.
3. Header only needs the four names to be present. Extra columns, reordered columns, and the old five-column header all pass.
4. `|` dependency separator not supported (our rule and the old prototype support it).
5. `int()` accepts `+3`, underscores (`1_0`), and non-ASCII digits.
6. Dependency ids are not format-checked. A bad one only shows up as "unknown task".
7. `--generate` writes (and overwrites without asking) the path given as `csv_file`. Running it by mistake on tasks.csv would replace the data file. Also the generated file uses `"T02, T03"` unquoted-looking text via `csv.DictWriter`, which does quote it, so that part is fine.
8. Missing file raises `FileNotFoundError`, not a validation error, so a caller catching `ValueError` misses it.
9. Capacity `True` is accepted.

Security: no `eval`/`exec`, no network calls, standard library only. File handling uses a `with` block. The only path concern is the `--generate` overwrite above, which is a local command-line tool and low risk.

## 7. Verdict and recommendation

**Partly aligned.**

Differences that matter (fix before using SB's file):
1. Fails `test_phase1.py` at import (no `DataValidationError`, `group_split_bound`, `lower_bounds`, `validate_tasks`).
2. Combined lower bound 9 instead of 11 (and 10 instead of 12 when T05 = 3). Makes `scheduling_model.py` print "optimality is not proven", which contradicts the requirements.
3. Accepts bad ids, wrong or extra columns, the old five-column header, and `+3`/non-ASCII digits.
4. Rejects `|` dependencies.
5. Missing file raises a non-ValueError exception.

Differences that do not matter: CLI wording and extra task listing, `--worker` alias, `[Validation Error]` vs `INVALID INPUT`, docstring style, typing and comprehensions (matter only for the beginner-style goal), `generate_dataset`.

Options:
- **(a) Keep ours (recommended).** It passes the tests, gives 11, and matches the requirements and beginner style. Tell SB: "Your file works for loading tasks.csv, but the combined bound gives 9 and the requirements say 11. Our `data_validation.py` is the shared one."
- **(b) Adopt SB's.** Would need: `DataValidationError(ValueError)`, the three missing functions, a group-split bound, strict header, `T` plus two ASCII digit id check, ASCII-digit integer parsing, `|` support, missing-file error wrapped, plus removal of typing, `str | Path` and comprehensions. That is effectively rewriting it into ours.
- **(c) Merge.** Optionally ask SB to propose `generate_dataset` and the per-task listing in the CLI output as a separate small addition, written in the beginner style. Not needed for Phase 1.
