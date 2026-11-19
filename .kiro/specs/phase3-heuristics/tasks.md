# Implementation Plan: Phase 3 Heuristics

## Overview
Phase 3 specification: the Phase 3 section of `Technical_Requirements.md`. The heuristics H0 to H3 and the heuristic argument on Greedy and A* already exist, so these tasks cover only the gaps: two search-engine additions, the heuristic tests, the experiment data, the comparison runner and results file, and the analysis. Python standard library only, `unittest`, seeded generators. Tests are required tasks in this plan, because section 7 of the specification makes them acceptance criteria. Every number in the results file and the analysis must come from a real run.

## Tasks
- [x] 1. Search-engine additions
  - [x] 1.1 Add `states_generated` to every search result
    - Add the field to `make_result` in `search_common.py` (default 0) and count `len(successors(...))` at each counted expansion in `best_first_search`
    - Update the Phase 2 result-shape test in `test_search.py` so it expects the new key, and keep all existing tests passing
    - _Requirements: 1.1, 1.5_
  - [x] 1.2 Expose `max_expansions` and add the `state_limit` status
    - Add `max_expansions=None` to `bfs_search`, `ucs_search`, `greedy_search` and `astar_search` and pass it to `best_first_search`
    - On reaching the limit return status `state_limit`, empty schedule, `makespan=None`, `schedule_valid=False`; update every place that lists the allowed statuses, including the Phase 2 result-shape test
    - Add a unit test per algorithm with a tiny limit, and one test that a limit stop is never reported as solved
    - _Requirements: 1.2, 1.3, 1.4, 1.5_

- [x] 2. Heuristic tests (new file `test_heuristics.py`)
  - [x] 2.1 Create `test_heuristics.py` with goal-state and baseline-value tests
    - HT-01: H0, H1, H2 and H3 return 0 at a completed goal state
    - HT-02: SS baseline Day 0 with 2 workers gives H0=0, H1=4, H2=9, workload=8, H3=9
    - HT-03: a running task with 1 day left (originally 4) counts as 1 in H1, H2 and the workload bound
    - _Requirements: 2.1, 2.2, 2.3_
  - [x] 2.2 Add chain, independent-task and one-worker tests
    - HT-04: a single dependency chain gives a critical-path bound equal to the sum of the remaining durations
    - HT-05: several independent tasks give a workload bound that reflects the worker capacity
    - HT-06: with one worker the workload bound equals all remaining worker-days
    - _Requirements: 2.4_
  - [x] 2.3 Add non-mutation and non-negativity tests
    - HT-07: invalid input (cycle, bad duration, over capacity) is rejected by validation before any heuristic runs
    - HT-08: for every legal transition from reachable states, all heuristics are non-negative integers and leave tasks, state and capacity unchanged (compare before and after)
    - _Requirements: 2.5, 2.6_
  - [x] 2.4 Add the full admissibility check on the SS baseline
    - HT-09: enumerate every reachable state of the SS six-task, 2-worker instance, compute the exact remaining cost with UCS from that state, and assert `0 <= h(state) <= cost_to_goal` for every heuristic
    - Repeat for the 1-worker and 3-worker baselines if the state count stays small
    - _Requirements: 2.7_
  - [x] 2.5 Add A*/Greedy agreement and repeatability tests
    - HT-10: A* with H0, H1, H2 and H3 matches the UCS makespan on the four SS scenarios (11, 15, 9, 12)
    - Greedy runs with each heuristic on the same model, returns a valid schedule, and never reports a makespan below the optimum
    - HT-11: repeating a fixed run gives the same makespan and the same state counts
    - _Requirements: 2.8_

- [x] 3. Experiment data and scenarios
  - [x] 3.1 Create the seeded instance generator `heuristic_data.py`
    - Generate instances of 8 to 12 tasks with different dependency structures (for example wide, deep, mixed), a fixed seed per instance, and every instance valid under `validate_tasks`
    - Write four-column CSV files to `heuristic_test_data/` and a `NOTES.md` listing each file, its seed, task count and generation rules; running the generator twice gives identical files
    - Add tests: every generated file loads through `load_tasks`, sizes are 8 to 12, and output is repeatable
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 3.2 Draft `Heuristic_Scenarios.md` for SS review
    - List the baseline, one-worker, three-worker and T05 = 3 days scenarios with their expected optimal makespans (15, 11, 9, 12), changing one factor at a time
    - Mark the file as a draft awaiting SS review, and note that worker qualifications are out of scope
    - _Requirements: 3.5_

- [x] 4. Comparison runner and results file
  - [x] 4.1 Create `heuristic_io.py` for the results CSV
    - Write and read the 13-column `heuristic_results.csv` with the exact header from the specification; atomic write via a temp file and `os.replace`; the reader checks the header and values and names the row and column of any error
    - Round-trip test with a seeded generator, plus error tests (missing column, bad status, negative counts) in `test_heuristics.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [x] 4.2 Create `heuristic_comparison.py`
    - Build the instance list (four SS scenarios plus the synthetic instances), load tasks only through `load_tasks`, and run UCS, A* with H0, H1, H2 and H3, and Greedy with H1 and H3 under one shared timeout and `max_expansions`
    - Time each run 5 times and report the median `runtime_ms` with the heuristic time inside it; take state counts from the first run; validate every schedule; compute `optimality_gap_pct` from the UCS makespan; catch a failing run into an `error` row and continue
    - Exit with code 1 and write nothing if an A* row with an admissible heuristic differs from the UCS makespan; validate the `--output` path before running
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.4_
  - [x] 4.3 Generate `heuristic_results.csv` and check it
    - Run the runner, confirm one row per instance and method, no invented values, incomplete runs have empty makespan and gap, and every A* row matches UCS
    - Report the row count and the states expanded on the SS 2-worker baseline for each method
    - _Requirements: 5.4, 5.5_
  - [x] 4.4 Add runner tests to `test_heuristics.py`
    - Write the output to a temp folder, never over the project's `heuristic_results.csv`
    - Cover: expected columns and row count, a forced exception becomes an `error` row, a limit stop is recorded as incomplete and not optimal, an A* mismatch makes the runner fail, and a bad output path exits non-zero
    - _Requirements: 4.5, 4.6, 5.6_

- [x] 5. Summary of results
  - [x] 5.1 Generate a markdown summary table from `heuristic_results.csv`
    - Use only the standard library; show median states expanded and median runtime per method for each scenario group, plus the optimality gap for Greedy
    - Add a `--summary` option to the runner or a small script, with a test on a fixed small CSV
    - _Requirements: 6.1_
  - [x] 5.2 Create comparison figures (optional)
    - Needs a dependency decision first: matplotlib is not installed or pinned in this project. Ask the user before adding it, check the version for known CVEs, pin the exact version, and source it from the approved registry
    - If approved, plot states expanded per method and scenario and save the images next to the CSV
    - _Requirements: 6.4_

- [x] 6. Analysis and documentation
  - [x] 6.1 Write `Heuristic_Analysis.md`
    - Answer the research questions under "Research questions" in the Phase 3 section of `Technical_Requirements.md` using only the measured numbers from `heuristic_results.csv`
    - Include limits (instance sizes, single machine, timing noise), any unexpected result, and when Greedy gives a faster but longer schedule; do not promise a speedup
    - _Requirements: 6.2, 6.3_
  - [x] 6.2 Update the project documents
    - Update `README.md`, `Technical_Requirements.md`, `Project_Structure.md` and `Implementation_Plan.md` for the Phase 3 files and commands
    - Tick the Phase 3 checklist items in `Implementation_Plan.md` only where the work is done; leave the SS review and JC figures unticked unless they happened
    - _Requirements: 7.1, 7.2_

- [x] 7. Checkpoint - Ensure all tests pass
  - Run `python -m unittest discover -v` and report the counts; fix only genuine failures

## Notes
- Tasks marked with `*` are optional and can be skipped
- Each task references the numbered requirements in `requirements.md` for traceability
- All tests for Phase 3 write to `test_heuristics.py`, except tasks 1.1 and 1.2, which also update `test_search.py`; test tasks are placed in separate waves
- Every number in `heuristic_results.csv` and `Heuristic_Analysis.md` must come from a real run
- Task 5.2 needs a dependency decision from the user before any work starts
## Task Dependency Graph
```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "3.2"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1"] },
    { "id": 3, "tasks": ["2.2"] },
    { "id": 4, "tasks": ["2.3"] },
    { "id": 5, "tasks": ["2.4"] },
    { "id": 6, "tasks": ["2.5"] },
    { "id": 7, "tasks": ["3.1"] },
    { "id": 8, "tasks": ["4.1"] },
    { "id": 9, "tasks": ["4.2"] },
    { "id": 10, "tasks": ["4.3"] },
    { "id": 11, "tasks": ["4.4"] },
    { "id": 12, "tasks": ["5.1"] },
    { "id": 13, "tasks": ["5.2"] },
    { "id": 14, "tasks": ["6.1"] },
    { "id": 15, "tasks": ["6.2"] }
  ]
}
```