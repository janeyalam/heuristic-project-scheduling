# Heuristic Search for Project Scheduling

CS-7375 course project: AI-based project scheduling using graph search and heuristic algorithms.

This project schedules a **six-task workforce-training onboarding pilot** (T01–T06, two workers) and compares four search algorithms: BFS, UCS, Greedy Best-First and A*. The best schedule finishes in 11 working days.

**Team:** JA (Software Engineering / Search), SB (Computer Science / AI), SS (Business Development), JC (Testing / Visualization; provisional).

## Quick start

With Python 3.10+ installed, open a terminal in this directory and run:

```bash
python -m experiments.demo                    # four algorithms side by side on tasks.csv
python -m unittest discover -v    # all tests (Phase 1, 2 and 3)
```

On Windows use `python` (or `py`). On macOS and Linux use `python3` instead of `python`. More commands are in [Start here](#start-here) and [Phase 2](#phase-2--search-algorithms).
## Files

```
docs/          Requirements, plan, model and analysis documents
data/          Input data (tasks.csv, reference_schedule.csv, heuristic_test_data/)
results/       Generated results (comparison.csv, heuristic_results.csv)
scheduling/    Library code: validation, model, search, heuristics, CSV readers/writers
experiments/   Scripts: comparisons, data generator, summary, demo
tests/         Automated tests for Phases 1 to 3
backup_docs/   Retired documents
```

Run scripts from this folder as modules, for example `python -m experiments.demo`.

| File | Owner | Use |
|---|---|---|
| `docs/Project_Requirements.md` | SS | Project requirements (source of truth) |
| `docs/Technical_Requirements.md` | Team | What the system must do, by phase (Phase 1 model, Phase 2 search, Phase 3 heuristics) |
| `docs/Implementation_Plan.md` | Team | Who builds what, order of work, and the completion checklist |
| `docs/Project_Structure.md` | Team | How the files connect and how data flows from `tasks.csv` to `comparison.csv` |
| `docs/Data_Validation.md` | Team | Details of the input validation rules |
| `data/tasks.csv` | SB handoff | SS tasks transformed into agreed four-column CSV |
| `scheduling/data_validation.py` | SB handoff | Schema, dependency, duration and resource validation |
| `docs/Scheduling_Model.md` | JA | Definitions and expected model behavior |
| `scheduling/scheduling_model.py` | JA | Phase 1 state/transition implementation (not BFS/A*) |
| `data/reference_schedule.csv` | SS/JC handoff | SS reference schedule in machine-readable form |
| `tests/test_phase1.py` | JC/JA | Phase 1 automated tests |
| `scheduling/search_common.py`, `scheduling/heuristics.py` | Shared | Shared search helpers (input checks, timeout, schedule validation) and heuristics |
| `scheduling/bfs.py`, `scheduling/ucs.py`, `scheduling/greedy.py`, `scheduling/astar.py` | JA | The four search algorithms |
| `scheduling/results_io.py`, `experiments/comparison.py` | Shared | Results CSV reader/writer and the six-scenario comparison |
| `results/comparison.csv` | JC / JA | Generated comparison results (24 rows) |
| `experiments/demo.py` | Shared | Short side-by-side demo of the four algorithms |
| `tests/test_search.py` | JC / JA | Phase 2 automated tests (unit and property tests) |
| `experiments/heuristic_data.py`, `data/heuristic_test_data/` | SB / JA | Generator and output folder for the synthetic Phase 3 instances (6 CSVs and `NOTES.md`) |
| `scheduling/heuristic_io.py` | Shared | Reader/writer for `heuristic_results.csv` (13 columns) |
| `experiments/heuristic_comparison.py` | JC / JA | Runs UCS, A* (H0 to H3) and Greedy (H1, H3) on 10 instances |
| `experiments/heuristic_summary.py` | Shared | Prints a markdown summary table from `heuristic_results.csv` |
| `tests/test_heuristics.py` | JC / JA | Phase 3 automated tests |
| `results/heuristic_results.csv` | JC / JA | Generated Phase 3 results (70 rows) |
| `docs/Heuristic_Scenarios.md` | SS | Phase 3 scenarios. **Draft, SS review pending** |
| `docs/Heuristic_Analysis.md` | All | Interpretation of `heuristic_results.csv` |

**All scenarios are synthetic. No employer data is used.**

## Start here

With Python 3.10+ installed, open a terminal in this directory and run:

```bash
python -m scheduling.data_validation data/tasks.csv --workers 2
python -m scheduling.scheduling_model data/tasks.csv --workers 2
python -m unittest -v tests.test_phase1
```

On Windows use `python` (or `py`). On macOS and Linux use `python3` instead of `python`.

The reference schedule should finish in 11 working days using two workers. Changing capacity to 1 or 3 is a sensitivity study; the supplied reference schedule has exactly two assigned workers, so the default reference tracer is shown only at capacity 2.

The CSV file has **four columns exactly as SS requested**: `task_id`, `duration`, `depends_on`, `workers_required`. Any other header is rejected by `data_validation.py`.

## Current boundaries

- State models *interchangeable worker capacity*, not individually skilled employee assignment.
- Only deterministic, integer-duration, non-preemptive activities with finish-to-start dependencies.
- `validate_schedule()` verifies feasibility but does **not** find optimal schedules.
- Phase 2 adds the four search algorithms; see the section below.

## Phase 2 — Search algorithms

Phase 2 finds schedules in the Phase 1 state model with four algorithms. The successor generator does not force every eligible task to start, so waiting is a legal choice and the optimality claims hold.

| Algorithm | File | Behavior |
|---|---|---|
| Breadth-First Search | `bfs.py` | Fewest transitions; not guaranteed to minimize days |
| Uniform-Cost Search | `ucs.py` | Minimum makespan |
| Greedy Best-First | `greedy.py` | Guided by a heuristic only; fast, not guaranteed optimal |
| A* | `astar.py` | Minimum makespan with an admissible heuristic |

Each search returns a result with `status` (`solved`, `no solution`, `timeout` or `invalid input`), `makespan`, `schedule`, `states_explored`, `execution_time_ms` and `schedule_valid`. An invalid schedule is never reported as solved.

### Run it

```bash
python -m experiments.demo                         # four algorithms side by side on tasks.csv
python -m experiments.demo --workers 1             # try 1 or 3 workers
python -m experiments.comparison --output results/comparison.csv   # six scenarios x four algorithms
python -m unittest discover -v         # all Phase 1 and Phase 2 tests
```

`comparison.py` stops with exit code 1 and writes nothing if UCS ever returns a larger makespan than another algorithm.

### Comparison analysis

Results from `comparison.csv` (makespan in days; states explored in parentheses):

| Scenario | BFS | UCS | Greedy | A* |
|---|---|---|---|---|
| baseline, 2 workers | 12 (15) | 11 (15) | 12 (5) | 11 (15) |
| baseline, 1 worker | 15 (10) | 15 (10) | 15 (6) | 15 (10) |
| baseline, 3 workers | 12 (15) | 9 (15) | 9 (5) | 9 (15) |
| baseline, T05 = 3 days | 13 (15) | 12 (15) | 13 (9) | 12 (15) |
| independent tasks | 6 (42) | 5 (37) | 5 (3) | 5 (37) |
| dependency chain | 8 (4) | 8 (4) | 8 (4) | 8 (4) |

- **UCS and A* are optimal.** They return the same makespan in every scenario, and it matches the reference values (11, 15, 9, 12 for the four baseline scenarios). `comparison.py` also checks that UCS is never beaten.
- **BFS is not optimal.** It minimizes the number of transitions, not days, so it is longer than UCS in four of six scenarios (by 1 to 3 days).
- **Greedy is fast but unreliable.** It explores the fewest states in every scenario that has choices, and it found the optimum in four of six (1 worker, 3 workers, independent tasks, dependency chain). It returned a longer schedule in the 2-worker and T05 = 3 scenarios, so its answer depends on the instance.
- **A* here is the zero-heuristic baseline.** `comparison.py` runs A* with its default heuristic, `h = 0`, which makes A* behave like UCS. That is why A* explored exactly as many states as UCS in every scenario. A better heuristic does prune: on the baseline with 2 workers, A* with the critical-path heuristic explored 6 states instead of 15 and still found 11 days. Phase 3 compares the heuristics systematically.
- **One worker or a dependency chain gives every algorithm the same makespan.** With one worker, tasks run one at a time and the worker is never idle while a task is ready, so the makespan is the sum of the durations (15 days) whatever the order. Different orders only change individual start and finish days. A strict chain allows only one order.
- **Limits of this data.** Each result is a single run on tiny instances. `execution_time_ms` is well under a few milliseconds and varies between runs, so it is not a reliable basis for ranking the algorithms. The state counts are deterministic and are the more useful comparison.

## Phase 3 — Heuristics

Phase 3 compares UCS, A* with heuristics H0 to H3 (`heuristics.py`) and Greedy with H1 and H3 on 10 instances: the four baseline scenarios and six synthetic ones. Each method runs 5 times; the median runtime is reported and the state counts come from the first run.

```bash
python -m experiments.heuristic_data                          # write data/heuristic_test_data/
python -m experiments.heuristic_comparison [--output results/heuristic_results.csv] [--timeout 60] [--max-expansions 200000]
python -m experiments.heuristic_summary results/heuristic_results.csv # markdown summary table
python -m unittest -v tests.test_heuristics             # Phase 3 tests (29)
```

`heuristic_comparison.py` exit codes: 0 success, 1 optimality mismatch (an admissible A* run differs from UCS; nothing is written), load failure or write failure, 2 bad option or output path. `--timeout` is 1 to 3600 seconds and `--max-expansions` is 1 to 10000000.

Search engine additions for Phase 3: every result has a `states_generated` key (successors produced by counted expansions), the search functions accept `max_expansions`, and a run that reaches that limit returns status `state_limit`.

Results are in `results/heuristic_results.csv` and discussed in `docs/Heuristic_Analysis.md`. `docs/Heuristic_Scenarios.md` is a draft and SS has not reviewed it. No comparison figures were made.
