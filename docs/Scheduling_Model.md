# Phase 1 Scheduling Model (aligned with the requirements)

**Course:** CS-7375 · AI-Based Intelligent Project Scheduling and Resource Optimization  
**Owner:** Model  
**Source of truth:** `Project_Requirements.md`  
**Input dataset:** `tasks.csv` (6 tasks: T01–T06)

## 1. Goal and boundary

Develop a deterministic **Resource-Constrained Project Scheduling Problem (RCPSP)** state model. The model must describe which tasks can start, keep track of work in progress, advance simulated time, and recognize project completion.

This is **Phase 1 only**. BFS, Uniform-Cost Search, Greedy Best-First Search, A*, and machine learning are not implemented in `scheduling_model.py`; they will consume its states and successors in later phases.

## 2. Requirements taken from Project_Requirements.md

- Six tasks (T01–T06) with fixed, positive, integer working-day durations.
- Two interchangeable workers in the baseline (test with 1 and 3 as sensitivity experiments).
- Each task requires one worker and runs without interruption until completion.
- A task may start when **all** predecessors have finished and sufficient workers are free.
- A worker released at time `t` may start another eligible task at `t`.
- Finish every task exactly once, obey dependencies and worker capacity, minimize overall makespan.
- The original reference schedule finishes on **day 11** using two workers.

The **suggested future skill restrictions** are not part of this initial model. Adding individually qualified workers will require changes to the state and resource representation.

## 3. Canonical input format

`tasks.csv` exactly matches the four specified columns:

```csv
task_id,duration,depends_on,workers_required
T01,2,None,1
T02,4,T01,1
T03,3,T01,1
T04,3,T01,1
T05,2,"T02, T03, T04",1
T06,1,T05,1
```

The string `None` means no prerequisites. A comma-separated dependency list must be quoted in CSV. `data_validation.py` also accepts `T02|T03|T04` for interoperability, but the distributed dataset follows the notation in the requirements.

The *task descriptions and completion conditions* remain in the requirements document. The four-column CSV contains only the algorithmic fields the requirements specify.

## 4. Scheduling vocabulary

| Term | Meaning | Example |
|---|---|---|
| **Task** | An activity with duration, worker need and prerequisites | T02 needs 4 days after T01 |
| **State** | Completed tasks and currently running tasks with remaining duration | completed={T01}, running={(T02,4),(T03,3)} |
| **Ready task** | Not begun and all predecessors completed | T02, T03, T04 become ready after T01 |
| **Action** | Choose a feasible subset of ready tasks to start | Start T02 and T03 |
| **Transition** | Start selected tasks, then advance to the next completion | T03 finishes after 3 days; T02 has 1 day left |
| **Transition cost** | How many whole days the transition advances | 3 days |
| **Goal** | Every task complete, none running | Completed={T01...T06} |

### State definition

```python
@dataclass(frozen=True)
class State:
    completed: frozenset[str]
    running: tuple[tuple[str, int], ...]  # (task_id, remaining_days)
```

Completed tasks and running tasks are **not** allowed to overlap. Running task IDs are unique. Resource demand of running tasks must never exceed worker capacity.

The state deliberately does not store the current elapsed day: future options depend on remaining tasks and remaining durations. Search algorithms will accumulate elapsed time as their path cost `g(n)`. This lets two equivalent states be compared independently of the calendar time at which they were reached.

Worker IDs are not stored in state because **the requirements say workers are interchangeable**. Once a schedule is chosen, worker labels can be assigned to non-overlapping intervals for display.

## 5. State transitions

1. Find all not-yet-started tasks whose predecessors are complete.
2. Enumerate feasible groups of those tasks within current worker capacity.
3. Allow a deliberate wait action (start no new tasks) *only if other tasks are already running*.
4. Add the selected tasks to the running set with their full durations.
5. Advance simulated time by the smallest remaining duration of any running task.
6. Mark all tasks finishing at that moment complete; subtract elapsed time from other running tasks.
7. Return the new state, action information, and the elapsed-day transition cost.

Why allow waiting? To enumerate the full state space rather than assuming that immediately starting every eligible task is always best.

### Example: after T01 completes

- Completed = `{T01}`; Running = `{}`; Time = day 2.
- Ready = `T02`, `T03`, `T04`; capacity = 2 workers.
- Feasible start actions are the 3 single-task sets and 3 two-task sets.
- Action `start(T02, T03)` runs for three days until T03 finishes.
- At day 5, completed `{T01,T03}`, running `{(T02,1)}`, and one worker becomes available.
- The next action may start T04 while T02 continues.

## 6. Phase 1 Python API

| Function | Responsibility |
|---|---|
| `load_tasks()` | Parse the four-column CSV; validate structure |
| `validate_tasks()` | Reject duplicate/missing prerequisite IDs, cycles, invalid durations and excessive worker needs |
| `initial_state()` | Return a state before any work starts |
| `ready_tasks()` | List tasks whose dependencies have all finished |
| `workers_in_use()` | Compute current resource demand |
| `legal_start_sets()` | Generate all possible action groups under capacity |
| `advance()` | Execute one legal decision and advance to the next completion event |
| `successors()` | Return all valid one-step successors with transition costs |
| `is_goal()` | Detect when all tasks are complete |
| `validate_schedule()` | Check a full schedule against precedence, duration and capacity rules |

## 7. Reference results and lower bounds

The reference schedule in the requirements is a **feasible 11-day schedule**. It is also optimal:

- T01 must take 2 days first.
- T02, T03, and T04 require 4, 3, and 3 days on two workers. At least 6 days are needed (one worker must handle at least two of those tasks sequentially).
- T05 and T06 then require 2 + 1 days.
- Thus any feasible schedule takes at least 2 + 6 + 2 + 1 = **11 days**.
- The reference schedule meets this lower bound, proving optimality.

`data_validation.py` prints three lower bounds:

- Longest precedence path = **9 days**.
- Total worker workload = **ceil(15 / 2) = 8 days**.
- Parallel-split bound = **11 days**. This is the argument above: T01, then the best split of T02, T03 and T04 over two workers, then T05 and T06.
- Combined lower bound = the largest of the three = **11 days**, which equals the reference schedule, so the schedule is optimal.

The first two bounds alone stop at 9, below the real optimum of 11. This will matter in Phase 3 when designing A* heuristics: a simple estimate can be safe but too low to guide the search well.

## 8. Hand-offs and tests

- **Requirements owner:** Confirm this six-task example stays the agreed starting point.
- **Dataset:** Use the exact same `tasks.csv` columns and `None`/quoted-comma dependency convention.
- **Model:** Check state representation, transitions, cost calculation, goal detection; then integrate algorithms in Phase 2.
- **Testing:** Validate the reference schedule and test invalid conditions (premature starts, resource overload, bad dependencies).

Run:

```bash
python -m scheduling.data_validation data/tasks.csv --workers 2
python -m scheduling.scheduling_model data/tasks.csv --workers 2
python -m unittest -v tests.test_phase1
```

On Windows use `python` (or `py`). On macOS and Linux use `python3` instead of `python`.

Phase 1 is complete when the reference trace reaches all six tasks at day 11, input validation catches bad cases, and the transition functions are ready for all four later search algorithms.
