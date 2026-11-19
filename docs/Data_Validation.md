# Understanding data_validation.py

This is a guide to `data_validation.py` for the team. It explains what the file does, how each part works, and how to run it.

## 1. What the file does

`data_validation.py` has two jobs:

1. **Check `tasks.csv`.** It reads the file and makes sure every row follows the rules in `Project_Requirements.md`: the right columns, valid task IDs, positive numbers, real prerequisites and no circles. If anything is wrong, it stops and says which line and why.
2. **Work out lower bounds.** A lower bound is a number of days the project **cannot** beat, whatever plan you pick. For our data the bound is **11 days**. The reference schedule also takes 11 days, which proves it is the best possible.

`scheduling_model.py` and `test_phase1.py` both import from this file, so it has to stay in the same package (`scheduling/`) as them.

| Other file | What it uses from here |
|---|---|
| `scheduling_model.py` | `load_tasks`, `Task`, `combined_lower_bound` |
| `test_phase1.py` | `load_tasks`, `Task`, `DataValidationError`, `validate_tasks`, `lower_bounds`, `group_split_bound`, `combined_lower_bound` |

The file uses only the Python standard library, so there is nothing to install.

## 2. How to run it

From the project root folder:

```bash
python -m scheduling.data_validation data/tasks.csv --workers 2
```

(On Windows use `python` or `py`. On macOS and Linux use `python3`.)

Output for our `tasks.csv`:

```
VALID: 6 tasks, 2 workers, all dependencies valid and acyclic.
Lower bounds: critical path 9 days; worker workload 8 days.
Parallel-split lower bound: 11 days (shared-prerequisite tasks split across workers).
Combined lower bound: 11 days. A schedule of exactly this length is optimal; otherwise optimality is not proven.
```

- `tasks.csv` is the file to check. If you leave it out, the script uses `data/tasks.csv` anyway.
- `--workers` is the number of workers. If you leave it out, it uses 2.

If the file breaks a rule, the script prints `INVALID INPUT: <reason>` and exits with code 1. See section 6 for examples.

## 3. The input file it expects

`tasks.csv` must have **exactly** these four columns, in this order:

```csv
task_id,duration,depends_on,workers_required
T01,2,None,1
T02,4,T01,1
T03,3,T01,1
T04,3,T01,1
T05,2,"T02, T03, T04",1
T06,1,T05,1
```

| Column | Rule | Good | Bad |
|---|---|---|---|
| `task_id` | `T` plus exactly two digits, used only once | `T01` | `T1`, `t01`, `T001`, `A` |
| `duration` | Whole number, 1 or more (working days) | `4`, ` 4 ` | `0`, `-1`, `2.5`, `+3` |
| `depends_on` | `None`, empty, or task IDs separated by commas (in quotes) or `\|` | `None`, `T01`, `"T02, T03"`, `T02\|T03` | `T02, T03` without quotes, `T02, T02`, `task2` |
| `workers_required` | Whole number from 1 up to the number of workers | `1` | `0`, `3` with 2 workers |

A list like `T02, T03, T04` needs quotes, because the commas would otherwise split it into extra columns. In that case the script reports `malformed CSV`.

## 4. The building blocks

### `REQUIRED_COLUMNS`
The four column names, in order. `load_tasks` compares the file's header against this.

### `DataValidationError`
The error the file raises when the data breaks a rule. It is a kind of `ValueError`, so code that catches `ValueError` also catches it.

### `Task`
One row of `tasks.csv`, stored as a Python object:

```python
Task(task_id='T02', duration=4, dependencies=('T01',), workers_required=1)
```

It is a *frozen* dataclass, which means it can't be changed after it's created. Tasks should stay the same once they're loaded.

## 5. The functions, one by one

### Checking one cell

| Function | What it does | Example |
|---|---|---|
| `is_valid_task_id(text)` | True if the text is `T` plus two digits 0-9 | `'T01'` gives True, `'T1'` gives False |
| `positive_int(raw, label, line)` | Turns a cell into a whole number of 1 or more, otherwise raises an error | `' 2 '` gives 2, `'0'` is an error |
| `parse_dependencies(raw, line)` | Turns the `depends_on` cell into a tuple of IDs | `'T02, T03, T04'` gives `('T02', 'T03', 'T04')`, `'None'` gives `()` |

`label` and `line` are only used to write a helpful error message, such as `Line 2: duration must be a positive integer; got "0".`

### Reading and checking the whole file

**`load_tasks(path, worker_capacity=2)`** is the main function other files call. Step by step:

1. Check that the file exists.
2. Check that the header is exactly `task_id,duration,depends_on,workers_required`.
3. For each row:
   - stop if the row has too many or too few cells (usually missing quotes)
   - check the task ID and that it isn't a duplicate
   - turn the cells into a `Task` using the three helpers above
4. Run `validate_tasks` on the full set.
5. Return a dictionary of tasks keyed by ID, in file order.

```python
tasks = load_tasks('data/tasks.csv', 2)
tasks['T02'].duration       # 4
tasks['T05'].dependencies   # ('T02', 'T03', 'T04')
```

**`validate_tasks(tasks, worker_capacity)`** checks rules that need the whole set of tasks, not just one row:

- The worker count is a whole number, 1 or more.
- There is at least one task.
- Every ID, duration and worker count is valid.
- No task needs more workers than we have.
- No task lists the same prerequisite twice, depends on itself, or depends on a task that doesn't exist.
- There are no circles (see `check_for_cycle`).

It returns nothing when everything is fine. The tests call it directly with broken data.

**`check_for_cycle(node, tasks, color, path)`** finds circular dependencies, such as T01 needing T02 while T02 needs T01. Neither task could ever start.

It walks from a task down through its prerequisites, marking each task as it goes:
- color 1 means "on the path I'm walking now"
- color 2 means "already checked, fine"

If the walk reaches a task that is still color 1, it has gone in a circle and reports it, for example `Dependency cycle: T01 -> T02 -> T01`. The function calls itself once for each prerequisite.

### Lower bounds

All three bounds answer the same question: "what is the fastest this project could possibly finish?" Each one looks at it differently, and since all three are true, the biggest one is the most useful.

**`lower_bounds(tasks, worker_capacity)`** returns two simple bounds as a pair:

1. **Critical path:** the longest chain of tasks that must run one after another. For our data that's T01 (2) + T02 (4) + T05 (2) + T06 (1) = **9 days**. Even with unlimited workers you can't beat this.
2. **Workload:** all the work added up, divided by the workers, rounded up. That's 15 worker-days / 2 workers = 7.5, so **8 days**.

For `tasks.csv` it returns `(9, 8)`. It uses **`earliest_finish(task_id, tasks, memo)`**, which works out the earliest day each task can be done: its own duration plus its slowest prerequisite. For example, T02 = 4 + T01's 2 = 6. `memo` stores answers already worked out so they aren't repeated.

**`group_split_bound(tasks, worker_capacity)`** is the bound that gets to 11. It looks for tasks that wait on exactly the same prerequisites, because those tasks have to share the workers once they're free. For our data, T02, T03 and T04 all wait only for T01:

| Part | Meaning | Our data |
|---|---|---|
| head | When the shared prerequisites are done | T01 takes 2 days, so 2 |
| split | Best possible time to share the group between the workers | Jobs of 4, 3, 3 on 2 workers: 3 + 3 on one, 4 on the other, so 6 |
| tail | Shortest work left after one of the group finishes | T05 (2) + T06 (1) = 3 |
| **bound** | head + split + tail | **2 + 6 + 3 = 11** |

This is the same argument the requirements use to show 11 is the minimum. It uses three helpers:
- **`_best_split(durations, parts)`** finds the best split of jobs over the workers. For example, `_best_split([4, 3, 3], 2)` gives 6.
- **`place_jobs(jobs, index, loads, best)`** does the actual trying. It hands each job to each worker in turn and keeps the best result. It skips choices that can't beat the best found so far, which keeps it fast.
- **`longest_after(task_id, tasks, followers, memo)`** finds the longest chain of work after a task. After T05 that's just T06, so 1.

If a group is large (over 12 tasks) or a task in it needs more than 1 worker, the function uses a simpler split number that is less tight but still a valid lower bound.

**`combined_lower_bound(tasks, worker_capacity)`** returns the biggest of the three: max(9, 8, 11) = **11**. `scheduling_model.py` compares this with the reference schedule. If they're equal, nothing faster is possible.

| Workers | Combined lower bound | Matches requirements? |
|---|---:|---|
| 1 | 15 | Yes |
| 2 | 11 | Yes |
| 3 | 9 | Yes |
| 2, with T05 = 3 days | 12 | Yes |

### Command line

**`main()`** runs when you type `python -m scheduling.data_validation ...`. It:
- reads the arguments
- calls `load_tasks` and the bound functions
- prints the result

On a `DataValidationError` it prints `INVALID INPUT: ...` and exits with code 1.

## 6. Error messages you may see

These are real outputs from running the script on broken files:

| Problem in the file | Message |
|---|---|
| Wrong or old header | `Expected CSV columns, in order: task_id,duration,depends_on,workers_required` |
| Bad task ID (`T1`) | `Line 2: invalid task ID "T1".` |
| Duration 0 | `Line 2: duration must be a positive integer; got "0".` |
| `T01, T03` without quotes | `Line 3: malformed CSV (check quotes and commas).` |
| Prerequisite that doesn't exist | `T02: missing dependency T09.` |
| Circular dependency | `Dependency cycle: T01 -> T02 -> T01` |
| Task needs 3 workers, we have 2 | `T01: needs 3 workers, capacity is 2.` |
| Same ID twice | `Line 3: duplicate task T01.` |

Every message starts with `INVALID INPUT:` on the command line. Line numbers count the header as line 1.

## 7. Trying it yourself

In the Python shell (`python` in the project root folder):

```python
from scheduling.data_validation import *

tasks = load_tasks('data/tasks.csv', 2)
tasks['T05']                         # Task(task_id='T05', duration=2, ...)
lower_bounds(tasks, 2)               # (9, 8)
group_split_bound(tasks, 2)          # 11
combined_lower_bound(tasks, 3)       # 9
parse_dependencies('T02|T03', 1)     # ('T02', 'T03')
is_valid_task_id('T1')               # False
```

To see the error checks, copy `tasks.csv` to a new file, break one thing (for example set a duration to 0), and run `python -m scheduling.data_validation yourcopy.csv`. Don't edit the real `tasks.csv`.

The automated tests for this file are in `test_phase1.py`:

```bash
python -m unittest -v tests.test_phase1
```

All 26 tests should pass.
