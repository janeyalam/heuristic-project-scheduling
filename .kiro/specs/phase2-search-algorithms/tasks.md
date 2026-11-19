# Implementation Plan: Phase 2 Search Algorithms

## Overview

The design uses Python, matching Phase 1 (`scheduling_model.py`, `data_validation.py`). The plan builds the shared helper and heuristics first, then the four algorithm modules on top of the generic search loop, then CSV I/O and the comparison script. Tests are written with stdlib `unittest` in a single `test_search.py` and are optional sub-tasks. Property tests use `random.Random(SEED)` generators (fixed seed, at least 100 cases) and carry the tag `# Feature: phase2-search-algorithms, Property N: <title>`. No change to `scheduling_model.py` is planned (Requirement 1.7 is not triggered).

## Tasks

- [x] 1. Shared helper and heuristics
  - [x] 1.1 Create `search_common.py`
    - Implement `SearchTimeout`, `make_result` (seven required keys plus `error` and `transitions`), `check_input` (wraps `validate_tasks`, tags capacity, empty set, cycle, unknown dependency, over-capacity task), `reconstruct_schedule`, `check_schedule`, `find_violations`
    - Implement `best_first_search(algorithm, tasks, capacity, *, priority, reopen, timeout_seconds, max_expansions)` with `best_g`, `parent`, heapq frontier with insertion counter (deque for BFS), stale-pop skipping, goal test on pop via `is_goal`, a single `initial_state()` call, one `successors` call per counted expansion, `time.perf_counter` timing, and statuses "solved", "no solution", "timeout", "invalid input"
    - On validator failure return `schedule_valid=False`, `makespan=None`, empty schedule, `error` from `find_violations`, status "no solution"
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7, 2.8, 2.9, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.9, 9.1, 9.6, 9.7, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 1.2 Create `heuristics.py`
    - Implement `zero_heuristic`, `longest_remaining` (Greedy default), `critical_path_remaining`, `workload_remaining`, `combined_heuristic` as `h(state, tasks, capacity) -> int`, with per-run precomputed `chain_after` cache
    - _Requirements: 6.3, 6.4, 7.2, 7.5, 11.2_

  - [x]* 1.3 Write successor-generation tests (new file `test_search.py`)
    - Create `test_search.py` with the seeded `random_dataset` generator and helper assertions
    - Example: baseline with T01 completed yields exactly 6 successors
    - Example: handcrafted instance where delaying a ready task beats a forced-start model
    - **Property 1: Successor generation is complete, unique and never idle**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**

  - [x]* 1.4 Write property test for transition well-formedness
    - **Property 2: Every transition is well formed**
    - **Validates: Requirements 3.1, 3.2, 3.4, 3.5, 3.6**

  - [x]* 1.5 Write property test for the Greedy default heuristic
    - **Property 13: Greedy default heuristic matches its definition**
    - **Validates: Requirements 6.3, 6.4**

  - [x]* 1.6 Write property test for heuristic admissibility
    - **Property 10: Project heuristics are admissible**
    - **Validates: Requirements 7.5, 6.4**

  - [x]* 1.7 Write property test for the schedule validator
    - **Property 7: The validator rejects corrupted schedules**
    - **Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6**

  - [x]* 1.8 Write unit tests for helper behavior
    - Patched `validate_schedule` raising a non-`ValueError` gives `schedule_valid=False` with "validation could not be completed" (9.7)
    - Tiny timeout with a patched clock returns "timeout" with empty schedule (10.2)
    - Spies confirm one `initial_state` call, goal decisions only via `is_goal`, and no `open(` in the four algorithm modules (2.1 to 2.4)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 9.7, 10.2_

- [x] 2. Algorithm modules
  - [x] 2.1 Create `bfs.py` with `bfs_search(tasks, capacity, timeout_seconds=None)`
    - FIFO frontier, skip any already-seen state, report makespan and transition count without claiming optimality
    - _Requirements: 2.5, 4.1, 4.2, 4.3, 4.4, 4.6_

  - [x] 2.2 Create `ucs.py` with `ucs_search(tasks, capacity, timeout_seconds=None)`
    - Priority is g(n); re-push on strictly lower g; discard stale pops
    - _Requirements: 2.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.7_

  - [x] 2.3 Create `greedy.py` with `greedy_search(tasks, capacity, heuristic=None, timeout_seconds=None)`
    - Priority is h(n) only, deterministic tie-break by insertion order, default `longest_remaining`, skip seen states
    - _Requirements: 2.5, 2.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.8_

  - [x] 2.4 Create `astar.py` with `astar_search(tasks, capacity, heuristic=None, timeout_seconds=None)`
    - Priority `(g + h, h)` then insertion order, default `zero_heuristic`, re-open on strictly lower g, discard on greater or equal g
    - _Requirements: 2.5, 2.6, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.9_

  - [x]* 2.5 Write property test for invalid input rejection
    - **Property 3: Invalid input is rejected without searching**
    - **Validates: Requirements 2.7, 2.8, 2.9, 10.3, 11.8**

  - [x]* 2.6 Write property test for result shape
    - **Property 4: Results always have the required shape**
    - **Validates: Requirements 8.7, 8.9, 10.1, 10.4, 10.5, 10.6**

  - [x]* 2.7 Write property test for schedule consistency
    - **Property 5: Reconstructed schedules are internally consistent**
    - **Validates: Requirements 3.3, 8.1, 8.2, 8.3, 8.4, 8.8**

  - [x]* 2.8 Write property test for schedule validity
    - **Property 6: Every returned schedule satisfies dependencies and capacity**
    - **Validates: Requirements 9.1, 9.8, 11.6, 14.6**

  - [x]* 2.9 Write property test for UCS optimality against brute force
    - **Property 8: UCS finds the true minimum makespan**
    - **Validates: Requirements 5.5**

  - [x]* 2.10 Write property test for A* versus UCS
    - **Property 9: A\* with an admissible heuristic matches UCS**
    - **Validates: Requirements 7.5, 14.3, 11.2**

  - [x]* 2.11 Write property test for BFS minimal transitions
    - **Property 11: BFS minimises the number of transitions**
    - **Validates: Requirements 4.3**

  - [x]* 2.12 Write property test for makespan ordering
    - **Property 12: Makespan ordering across algorithms**
    - **Validates: Requirements 4.5, 6.7, 12.8, 14.4, 14.5**

  - [x]* 2.13 Write property test for determinism
    - **Property 14: Searches are deterministic**
    - **Validates: Requirements 6.2, 14.7**

  - [x]* 2.14 Write property test for the counting rule
    - **Property 15: One counting rule for states explored**
    - **Validates: Requirements 8.5**

  - [x]* 2.15 Write property test for no repeated expansion in BFS and Greedy
    - **Property 16: BFS and Greedy never expand a state twice**
    - **Validates: Requirements 4.2, 6.5**

  - [x]* 2.16 Write property test for chain datasets
    - **Property 17: Chain datasets run strictly in sequence**
    - **Validates: Requirements 11.7**

  - [x]* 2.17 Write scenario unit tests
    - UCS and A* (all admissible heuristics): baseline 2 workers = 11, 1 worker = 15, 3 workers = 9, T05 duration 3 = 12
    - BFS valid and >= 11, Greedy >= 11, all `schedule_valid` true on baseline
    - Over-capacity task gives "invalid input" with no search started; patched `successors` returning `()` gives "no solution" for all four
    - Tie-break order tests for Greedy and A*; seeded property generation (100+ datasets, validated by `validate_tasks` first) with failure messages showing dataset, algorithm and property
    - _Requirements: 4.5, 5.6, 6.2, 6.7, 7.1, 7.7, 7.8, 9.8, 11.1, 11.2, 11.3, 11.4, 11.5, 11.8, 11.9, 11.10, 11.11, 14.1, 14.2, 14.8_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. CSV I/O and comparison output
  - [x] 4.1 Create `results_io.py`
    - `COLUMNS`, `ResultsCsvError`, `write_results_csv` (UTF-8, `\n`, temp file in destination directory then `os.replace`, true/false booleans, empty makespan for None)
    - `read_results_csv` (header check first, per-row check with 1-based row number, no partial results, values parsed back to int, float, bool, None)
    - _Requirements: 12.2, 12.5, 12.9, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [x] 4.2 Create `comparison.py` and generate `comparison.csv`
    - Scenarios: baseline_2w, baseline_1w, baseline_3w, baseline_t05_3days, independent_tasks, dependency_chain; tasks loaded only via `load_tasks`
    - Run bfs, ucs, greedy, astar per scenario with measured values; catch per-run exceptions into a row with status "error", empty makespan, `schedule_valid` false, and continue
    - Verify UCS makespan is <= every other solved row, and fail clearly otherwise
    - Write via `write_results_csv` (`--output` argument, default `comparison.csv`), then run the script to produce `comparison.csv` with 24 data rows
    - _Requirements: 2.1, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9_

  - [x]* 4.3 Write property test for CSV round trip
    - **Property 18: Results CSV round trip**
    - **Validates: Requirements 13.1, 13.2, 13.3**

  - [x]* 4.4 Write unit tests for CSV errors
    - Missing header column, missing value in row 3, unwritable destination, nonexistent source; existing file untouched on failure
    - _Requirements: 12.9, 13.4, 13.5, 13.6_

  - [x]* 4.5 Write comparison output tests
    - Run `comparison.main` into a temp directory; check column order, 24 data rows, non-placeholder measured values, UCS minimal per scenario, and failed-row handling
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8_

- [x] 5. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- All test sub-tasks write to `test_search.py`, so they are placed in separate waves
- Property tests validate universal correctness properties; unit tests validate specific examples and edge cases
- Wall-clock bounds in Requirements 9.1 and 10.2 are covered by coarse smoke checks only

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3", "2.4", "4.1"] },
    { "id": 2, "tasks": ["4.2"] },
    { "id": 3, "tasks": ["1.3"] },
    { "id": 4, "tasks": ["1.4"] },
    { "id": 5, "tasks": ["1.5"] },
    { "id": 6, "tasks": ["1.6"] },
    { "id": 7, "tasks": ["1.7"] },
    { "id": 8, "tasks": ["1.8"] },
    { "id": 9, "tasks": ["2.5"] },
    { "id": 10, "tasks": ["2.6"] },
    { "id": 11, "tasks": ["2.7"] },
    { "id": 12, "tasks": ["2.8"] },
    { "id": 13, "tasks": ["2.9"] },
    { "id": 14, "tasks": ["2.10"] },
    { "id": 15, "tasks": ["2.11"] },
    { "id": 16, "tasks": ["2.12"] },
    { "id": 17, "tasks": ["2.13"] },
    { "id": 18, "tasks": ["2.14"] },
    { "id": 19, "tasks": ["2.15"] },
    { "id": 20, "tasks": ["2.16"] },
    { "id": 21, "tasks": ["2.17"] },
    { "id": 22, "tasks": ["4.3"] },
    { "id": 23, "tasks": ["4.4"] },
    { "id": 24, "tasks": ["4.5"] }
  ]
}
```
