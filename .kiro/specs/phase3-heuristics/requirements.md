# Requirements Document
## Introduction
Phase 3 adds a systematic heuristic comparison on top of the Phase 2 search engine. The source specification is the Phase 3 section of `Technical_Requirements.md` (the former `Phase3_Requirements.md`, now in `backup_docs/`). This document records only the gaps, so finished work is not redone.
Review of the existing code found:
- The heuristics H0 to H3 already exist in `heuristics.py` as `zero_heuristic`, `longest_remaining`, `critical_path_remaining`, `workload_remaining` and `combined_heuristic`. At Day 0 of the baseline with two workers they return 0, 4, 9, 8 and 9, as the specification expects. The specification's names (`h_zero`, ...) differ, and the specification allows signatures to follow the Phase 2 code, so nothing is renamed.
- `greedy_search(tasks, capacity, heuristic=None, timeout_seconds=None)` and `astar_search(...)` already accept a heuristic function. A* already reopens a state found by a strictly cheaper route. Every solved schedule already passes the schedule validator.
- `best_first_search` has a `max_expansions` argument that the four searches do not expose, and no `state_limit` status exists. There is no `states_generated` count.
- `test_search.py` already checks admissibility on random reachable states, A* against UCS for all five heuristics on the four SS scenarios, invalid-input rejection and repeatability. It does not check the full SS baseline against exact UCS cost-to-go, partly finished running work as a named case, or non-mutation.
- `comparison.py` runs A* with its default heuristic, which is zero, so A* behaves like UCS there. A probe on the baseline with two workers showed A* exploring 15 states with H0 and 6 with H2 or H3, all finding 11 days. This is a lead, not a result, and the runner must produce the measured numbers.
Deliverables in scope: the two search-engine additions, `test_heuristics.py`, `heuristic_data.py` with `heuristic_test_data/`, `Heuristic_Scenarios.md` (draft for SS), `heuristic_io.py`, `heuristic_comparison.py`, `heuristic_results.csv`, `Heuristic_Analysis.md` and the documentation updates. Out of scope: machine-learning heuristics, worker skills and Phase 4.
## Glossary
- **Search_Engine**: The four search modules `bfs.py`, `ucs.py`, `greedy.py`, `astar.py` and the shared module `search_common.py`.
- **Heuristic**: A function `h(state, tasks, capacity)` that returns a whole number of estimated remaining working days.
- **H0, H1, H2, H3**: The zero heuristic, the longest remaining task, the remaining critical path, and the larger of the critical path and the workload bound, as defined in the Phase 3 section of `Technical_Requirements.md`.
- **Admissible_Heuristic**: A Heuristic whose value never exceeds the true minimum remaining working days.
- **Search_Result**: The dictionary returned by every search, with keys including `algorithm`, `makespan`, `schedule`, `states_explored`, `execution_time_ms`, `schedule_valid` and `status`.
- **Status_Value**: A string in the `status` key of a Search_Result.
- **States_Expanded**: The number of states removed from the frontier and expanded, excluding stale entries. This is the existing `states_explored`.
- **States_Generated**: The number of successor transitions produced during expansion.
- **Optimum**: The makespan returned by UCS on the same instance.
- **Optimality_Gap**: 100 times (makespan minus Optimum) divided by Optimum, in percent.
- **Baseline_Dataset**: The six-task dataset in `tasks.csv`.
- **SS_Scenarios**: The four baseline scenarios: two workers (optimum 11), one worker (15), three workers (9) and T05 at 3 days with two workers (12).
- **Synthetic_Instances**: Seeded generated task sets of 8 to 12 tasks written to `heuristic_test_data/`.
- **Comparison_Runner**: The script `heuristic_comparison.py`.
- **Results_File**: `heuristic_results.csv`.
- **Test_Suite**: The `unittest` tests in `test_search.py` and `test_heuristics.py`.
## Requirements
### Requirement 1: Search-effort metrics
**User Story:** As a researcher, I want every search to report how many states it generated and to stop cleanly at a state limit, so that heuristics can be compared fairly and incomplete runs are never mistaken for results.
#### Acceptance Criteria
1. THE Search_Engine SHALL include a `states_generated` key in every Search_Result, equal to the total number of successors returned by the model across all counted expansions.
2. WHEN a search is given `max_expansions` and the limit is reached before a goal is found, THE Search_Engine SHALL return Status_Value "state_limit", an empty schedule, a makespan of None and `schedule_valid` false.
3. THE bfs_search, ucs_search, greedy_search and astar_search functions SHALL each accept `max_expansions` with a default of None, meaning no limit.
4. THE Search_Engine SHALL NOT report a run that stopped on a limit or a timeout as solved or optimal.
5. THE Test_Suite SHALL verify the criteria above for all four algorithms, and all existing Phase 2 tests SHALL continue to pass.
### Requirement 2: Heuristic tests
**User Story:** As a tester, I want a dedicated heuristic test file that covers every correctness case in the Phase 3 specification, so that admissibility and goal behavior are verified against exact costs.
#### Acceptance Criteria
1. THE Test_Suite SHALL verify that H0, H1, H2 and H3 return 0 at a completed goal state.
2. THE Test_Suite SHALL verify that for the Baseline_Dataset with two workers at Day 0, H0 is 0, H1 is 4, the critical-path bound is 9, the workload bound is 8 and H3 is 9.
3. THE Test_Suite SHALL verify that a running task with 1 day left, originally 4 days, is counted as 1 day by H1, H2 and the workload bound.
4. THE Test_Suite SHALL verify that for a single dependency chain the critical-path bound equals the sum of the remaining durations, that for independent tasks the workload bound reflects the worker capacity, and that with one worker the workload bound equals all remaining worker-days.
5. THE Test_Suite SHALL verify that invalid input is rejected by validation before any heuristic is evaluated.
6. THE Test_Suite SHALL verify that for every legal transition from reachable states, every heuristic returns a non-negative integer and leaves the tasks, the state and the capacity unchanged.
7. THE Test_Suite SHALL verify that for every reachable state of the SS baseline with two workers, each heuristic satisfies 0 <= h(state) <= the exact remaining cost computed by UCS from that state.
8. THE Test_Suite SHALL verify that A* with H0, H1, H2 and H3 returns the UCS makespan on each of the SS_Scenarios, that Greedy with each heuristic returns a valid schedule with a makespan no lower than the Optimum, and that repeating a fixed run gives the same makespan and the same state counts.
### Requirement 3: Experiment data and scenarios
**User Story:** As a researcher, I want repeatable synthetic instances and documented business scenarios, so that the comparison covers more than the six-task baseline.
#### Acceptance Criteria
1. THE heuristic_data module SHALL generate Synthetic_Instances of 8 to 12 tasks with differing dependency structures, one fixed seed per instance, each passing `validate_tasks`.
2. THE heuristic_data module SHALL write each instance as a four-column CSV file into `heuristic_test_data/` together with a `NOTES.md` that lists each file, its seed, its task count and the generation rules.
3. WHEN the generator runs twice, THE heuristic_data module SHALL produce identical files.
4. THE Test_Suite SHALL verify that every generated file loads through `load_tasks`, that the sizes are within 8 to 12, and that the output is repeatable.
5. THE Heuristic_Scenarios document SHALL list the SS_Scenarios with their optimal makespans, change one factor at a time, state that worker qualifications are out of scope, and be marked as a draft awaiting SS review.
### Requirement 4: Fair comparison runner
**User Story:** As a researcher, I want one script that runs every method on the same instances under the same limits, so that differences come from the heuristic and not from the setup.
#### Acceptance Criteria
1. THE Comparison_Runner SHALL run UCS, A* with H0, H1, H2 and H3, and Greedy with H1 and H3 on each instance of the SS_Scenarios and the Synthetic_Instances.
2. THE Comparison_Runner SHALL load every task set only through `load_tasks` and SHALL use one shared timeout and one shared `max_expansions` for all methods.
3. THE Comparison_Runner SHALL time each run 5 times and report the median runtime, with the heuristic computation time included in the measured time, and SHALL take state counts from the first run.
4. THE Comparison_Runner SHALL pass every returned schedule through the schedule validator and record the result in `solution_valid`.
5. IF a run raises an exception, THEN THE Comparison_Runner SHALL record a row with status "error", empty makespan and gap, and `solution_valid` false, and SHALL continue with the remaining runs.
6. IF an A* run with an admissible heuristic returns a makespan different from the Optimum on the same instance, THEN THE Comparison_Runner SHALL exit with code 1 and SHALL write no results file.
7. THE Comparison_Runner SHALL validate the `--output` path before running anything and SHALL NOT pass any value to a shell.
### Requirement 5: Results file
**User Story:** As a researcher, I want a validated results file with real measurements only, so that the analysis can be reproduced and trusted.
#### Acceptance Criteria
1. THE Results_File SHALL have the columns `scenario_id,seed,task_count,worker_capacity,algorithm,heuristic,search_status,makespan_days,states_expanded,states_generated,runtime_ms,solution_valid,optimality_gap_pct`, in that order.
2. THE heuristic_io module SHALL write the Results_File through a temporary file and an atomic replace, so that a failed write leaves any existing file unchanged.
3. THE heuristic_io reader SHALL check the header and every value, and SHALL name the row and the column of any error.
4. WHEN a run did not finish with status "solved", THE Results_File SHALL hold an empty `makespan_days` and an empty `optimality_gap_pct` for that row.
5. THE Results_File SHALL contain only values measured by actual runs.
6. THE Test_Suite SHALL verify a write-then-read round trip, the error cases for a missing column, an unknown status and a negative count, and that the runner writes to a temporary folder in its tests and not over the project's Results_File.
### Requirement 6: Summary and analysis
**User Story:** As a project member, I want a summary table and a written analysis based on the measurements, so that the research questions are answered honestly.
#### Acceptance Criteria
1. THE summary script SHALL produce a markdown table from the Results_File using only the standard library, showing the median States_Expanded and the median runtime per method for each scenario group, and the Optimality_Gap for Greedy.
2. THE Heuristic_Analysis document SHALL answer the research questions listed under "Research questions" in the Phase 3 section of `Technical_Requirements.md` using only numbers present in the Results_File.
3. THE Heuristic_Analysis document SHALL state its limits, report any unexpected result, and SHALL NOT promise a speedup.
4. WHERE figures are produced, THE project SHALL add any plotting dependency only after the user approves it, with an exact pinned version checked for known vulnerabilities.
### Requirement 7: Documentation and status
**User Story:** As a new project member, I want the project documents to describe the Phase 3 files and their real status, so that I can run and review them.
#### Acceptance Criteria
1. THE README, Technical_Requirements, Project_Structure and Implementation_Plan documents SHALL describe the Phase 3 files and the commands to run them.
2. THE Implementation_Plan Phase 3 checklist SHALL be ticked only for items that are done, and the SS review and the JC figures SHALL stay unticked unless they happened.