# Requirements Document

## Introduction

Phase 2 (JA's scope: P2.1 to P2.4, plus JA's share of P2.7) adds four AI search algorithms, Breadth-First Search (BFS), Uniform-Cost Search (UCS), Greedy Best-First Search and A*, on top of the Phase 1 scheduling model in `scheduling_model.py`. All four algorithms solve the same resource-constrained scheduling problem (baseline: six tasks T01 to T06 in `tasks.csv`, two interchangeable workers, optimal makespan 11 working days) using the same initial state, goal test and transition rules. Only the search strategy differs.

Review of the existing Phase 1 code found:

- `successors(state, tasks, capacity)` already enumerates every subset of ready tasks that fits in the free workers (via `legal_start_sets`). It does not force all eligible tasks to start, so delaying a task is already possible. The only forbidden choice is "start nothing" when nothing is running, because time could not advance.
- Because a delayed task can start at any later completion event, restricting starts to completion events does not remove any optimal schedule. This must be confirmed by tests, not assumed.
- A `State` stores only `completed` and `running`, not the current day. Search code must accumulate elapsed days itself.
- Start and finish times are not stored. They must be reconstructed from the sequence of `Action` objects.
- `validate_schedule(rows, tasks, capacity)` already checks a schedule and returns the makespan. `load_tasks` and `validate_tasks` already reject a task that needs more workers than capacity.

Deliverables in scope: `bfs.py`, `ucs.py`, `greedy.py`, `astar.py`, a shared helper module for common search behavior, `test_search.py` and `comparison.csv`. Out of scope: P2.5 shared datasets (SB), P2.6 scenarios (SS) and Phase 3 heuristics.

## Glossary

- **Search_Engine**: The collection of the four search algorithm modules and their shared helper module.
- **Scheduling_Model**: The Phase 1 module `scheduling_model.py`, exposing `initial_state`, `successors`, `is_goal`, `validate_schedule` and related functions.
- **Data_Validator**: The Phase 1 module `data_validation.py`, exposing `load_tasks` and `validate_tasks`.
- **BFS**: The Breadth-First Search module `bfs.py`.
- **UCS**: The Uniform-Cost Search module `ucs.py`.
- **Greedy_Search**: The Greedy Best-First Search module `greedy.py`.
- **AStar_Search**: The A* Search module `astar.py`.
- **Search_Helper**: The shared module that holds the result structure, schedule reconstruction, timing and state counting used by all four algorithms.
- **State**: A Phase 1 `State` holding the set of completed tasks and the running tasks with remaining days.
- **Successor**: A Phase 1 `Successor` holding the next State, the `Action` taken and the cost in elapsed working days.
- **Transition**: One move from a State to a Successor.
- **Makespan**: The total number of working days from project start until the last task finishes.
- **g(n)**: The cumulative elapsed working days from the initial State to a State n.
- **h(n)**: The estimated remaining working days from a State n to a goal State.
- **Heuristic**: A function that computes h(n) for a State.
- **Admissible_Heuristic**: A Heuristic whose h(n) never exceeds the true minimum remaining working days.
- **Expanded_State**: A State removed from the frontier and for which successors are generated.
- **Search_Result**: The common dictionary returned by every algorithm, with keys `algorithm`, `makespan`, `schedule`, `states_explored`, `execution_time_ms`, `schedule_valid` and `status`.
- **Status_Value**: One of the strings "solved", "no solution", "timeout" or "invalid input", stored in the `status` key of a Search_Result.
- **Schedule_Entry**: One element of the `schedule` list, with `task_id`, `start_time` and `finish_time` in working days.
- **Schedule_Validator**: The component that checks a schedule against dependencies, worker capacity and durations, using `validate_schedule` from the Scheduling_Model.
- **Baseline_Dataset**: The six-task dataset in `tasks.csv` with two workers.
- **Search_Timeout**: A configured limit on search wall-clock time or Expanded_State count.
- **Comparison_Report**: The file `comparison.csv` listing algorithm metrics per scenario.
- **Test_Suite**: The file `test_search.py`, run with `python -m unittest`.

## Requirements

### Requirement 1: Successor generation allows delaying tasks

**User Story:** As a scheduler developer, I want the successor generator to allow delaying eligible tasks, so that the search space contains every schedule needed for a valid optimality claim.

#### Acceptance Criteria

1. WHEN the Scheduling_Model generates Successors for a State with at least one running task, THE Scheduling_Model SHALL include exactly one Successor that starts no new task and advances time to the next working day on which at least one running task completes.
2. WHEN the Scheduling_Model generates Successors for a State with at least 1 free worker and at least 1 ready task, THE Scheduling_Model SHALL include exactly one Successor for every non-empty subset of ready tasks whose combined worker requirement is less than or equal to the number of free workers, with no duplicate Successors.
3. IF a State has no running task and at least one ready task, THEN THE Scheduling_Model SHALL omit the "start nothing" Successor, so that every Transition advances time by at least 1 working day.
4. IF a State has no running task and no ready task, THEN THE Scheduling_Model SHALL return zero Successors.
5. THE Test_Suite SHALL verify that, for the Baseline_Dataset with two workers, a State with T01 completed and no running task yields exactly 6 Successors.
6. THE Test_Suite SHALL verify that an exhaustive search over the Scheduling_Model finds a delayed-start schedule that a forced-start model would miss, using a small instance in which delaying a ready task yields a Makespan strictly lower (by at least 1 working day) than the best Makespan obtainable when every startable task is started immediately.
7. IF verification shows that the Scheduling_Model cannot represent a required delay, THEN THE Scheduling_Model SHALL be modified so that the delayed schedule is reachable, and THE Test_Suite SHALL include at least 1 test that fails before the modification and passes after it.

### Requirement 2: Common search interface and input handling

**User Story:** As a scheduler developer, I want all four algorithms to share one interface and one set of inputs, so that comparisons across algorithms are fair.

#### Acceptance Criteria

1. WHEN any algorithm in the Search_Engine begins a run, THE Search_Engine SHALL load tasks only through the Data_Validator `load_tasks` function, with zero direct reads of the task data file by the algorithm modules (TR-01).
2. WHEN any algorithm in the Search_Engine begins a run, THE Search_Engine SHALL start the search from the State returned by exactly one call to the Scheduling_Model `initial_state` function (TR-02).
3. WHEN the Search_Engine evaluates whether a State is a goal, THE Search_Engine SHALL decide using only the boolean result of the Scheduling_Model `is_goal` function, with no goal logic of its own (TR-02).
4. WHEN the Search_Engine expands a State, THE Search_Engine SHALL obtain every Successor only through the Scheduling_Model `successors` function and SHALL NOT construct or modify Successors itself (TR-03).
5. THE Search_Engine SHALL expose, in each of `bfs.py`, `ucs.py`, `greedy.py` and `astar.py`, exactly one public search function that accepts the task dictionary and the integer worker capacity as arguments and returns a Search_Result.
6. WHERE a Heuristic is accepted by Greedy_Search or AStar_Search, THE Search_Engine SHALL accept the Heuristic as an optional function argument whose default is the default Heuristic defined for that algorithm (Requirements 6 and 7), so that calling the function without a Heuristic argument runs successfully.
7. IF the task dictionary contains a task whose `workers_required` exceeds the worker capacity, THEN THE Search_Engine SHALL NOT expand any State and SHALL return the "invalid input" Search_Result defined in Requirement 10, identifying the offending task (TR-12).
8. IF the task dictionary is empty, contains a dependency cycle, or references an unknown dependency, THEN THE Search_Engine SHALL NOT expand any State and SHALL return the "invalid input" Search_Result defined in Requirement 10, indicating which of the three conditions was detected.
9. IF the worker capacity is not an integer or is less than 1, THEN THE Search_Engine SHALL NOT expand any State and SHALL return the "invalid input" Search_Result defined in Requirement 10, indicating invalid worker capacity.

### Requirement 3: Constraint enforcement during search

**User Story:** As a scheduler developer, I want the search to respect dependencies and resource limits, so that no algorithm produces an invalid schedule.

#### Acceptance Criteria

1. WHEN the Search_Engine starts a task in a Transition, THE Search_Engine SHALL verify that every task listed in that task's dependencies has status completed in the originating State, and SHALL NOT start the task if any dependency is not completed (TR-04).
2. WHEN the Search_Engine generates a State, THE Search_Engine SHALL ensure the sum of `workers_required` of all running tasks in that State is less than or equal to the worker capacity, and SHALL NOT generate any State where the sum exceeds the capacity (TR-05).
3. WHEN the Search_Engine returns a schedule, THE Search_Engine SHALL include exactly one start and exactly one completion for each task in the task set, with no task started or completed zero times or more than once (TR-06).
4. WHEN the Search_Engine generates a State, THE Search_Engine SHALL record for every running task its remaining duration as an integer from 1 to the task's total duration in working days, and SHALL record no remaining duration for tasks that are not running (TR-07).
5. WHEN the Search_Engine generates a Transition, THE Search_Engine SHALL set the Transition cost equal to the number of working days elapsed between the originating State and the resulting State (TR-08).
6. WHEN the Search_Engine generates a Transition, THE Search_Engine SHALL set the Transition cost to an integer greater than or equal to 1, and SHALL NOT generate any Transition with a cost of 0, a negative value, or a non-integer value.
7. IF a candidate Transition would violate a dependency (criterion 1), the worker capacity (criterion 2), or the single-start rule (criterion 3), THEN THE Search_Engine SHALL discard that Transition, SHALL NOT add its resulting State to the search, and SHALL leave the originating State unchanged.

### Requirement 4: Breadth-First Search

**User Story:** As a student comparing algorithms, I want a BFS implementation, so that I have an uninformed baseline measured in transitions.

#### Acceptance Criteria

1. THE BFS SHALL order its frontier as a first-in-first-out queue, expanding States in the order they were added to the frontier.
2. WHEN BFS generates a successor State that has already been visited, THE BFS SHALL skip that State and not add it to the frontier (TR-09).
3. WHEN BFS reaches a goal State, THE BFS SHALL return a Search_Result whose schedule uses the fewest Transitions of any complete schedule in the modeled State graph.
4. WHEN BFS returns a Search_Result for a reached goal State, THE BFS SHALL report the Makespan of the returned schedule, the number of Transitions in the schedule, and the number of States expanded, without claiming that the Makespan is minimal.
5. THE Test_Suite SHALL verify that the BFS schedule on the Baseline_Dataset passes schedule validation with zero violations and that its reported Makespan is greater than or equal to 11.
6. IF the BFS frontier becomes empty without reaching a goal State, THEN THE BFS SHALL return the "no solution" Search_Result defined in Requirement 10, containing no schedule and leaving the input dataset unmodified (TR-12).

### Requirement 5: Uniform-Cost Search

**User Story:** As a student comparing algorithms, I want a UCS implementation, so that I get a provably minimum-duration schedule to measure the other algorithms against.

#### Acceptance Criteria

1. THE UCS SHALL order its frontier as a priority queue keyed by g(n), where g(n) is the elapsed working days accumulated from the initial State to State n, and SHALL remove the entry with the lowest g(n) first.
2. WHEN UCS generates a State, THE UCS SHALL record the best-known g(n) for that State (TR-09).
3. WHEN UCS finds a route to a previously encountered State with a g(n) strictly lower than the recorded best-known g(n), THE UCS SHALL update the recorded g(n) and push the State onto the frontier again with the lower g(n).
4. WHEN UCS removes a State from the frontier with a g(n) strictly greater than the recorded best-known g(n) for that State, THE UCS SHALL discard the entry without expanding the State.
5. WHEN UCS removes a goal State from the frontier, THE UCS SHALL stop searching and return a Search_Result whose Makespan is less than or equal to the Makespan of every other valid complete schedule for the same dataset and worker count.
6. THE Test_Suite SHALL verify that UCS returns a Search_Result with a Makespan of exactly 11 on the Baseline_Dataset with two workers.
7. IF the UCS frontier becomes empty without reaching a goal State, THEN THE UCS SHALL return the "no solution" Search_Result defined in Requirement 10, containing no schedule assignments (TR-12).

### Requirement 6: Greedy Best-First Search

**User Story:** As a student comparing algorithms, I want a Greedy Best-First implementation, so that I can observe the speed versus optimality tradeoff.

#### Acceptance Criteria

1. THE Greedy_Search SHALL order its frontier as a priority queue keyed by h(n) only, where the State with the lowest h(n) value is expanded first and g(n) is excluded from the key.
2. WHEN two frontier States have equal h(n), THE Greedy_Search SHALL expand them in a deterministic order, so that repeated runs on the same input produce an identical Search_Result.
3. THE Greedy_Search SHALL use as its default Heuristic the longest remaining duration, in days, among the running tasks and the not-yet-started tasks, where each running task contributes its remaining days and each not-yet-started task contributes its full duration.
4. IF there are no running tasks and no not-yet-started tasks in a State, THEN THE Greedy_Search SHALL evaluate the default Heuristic for that State as 0.
5. WHEN Greedy_Search generates a State that is already in the visited set, THE Greedy_Search SHALL skip that State and SHALL NOT add it to the frontier (TR-09).
6. WHEN Greedy_Search reaches a goal State, THE Greedy_Search SHALL return a Search_Result containing a schedule that satisfies all dependency and worker-capacity constraints, and SHALL NOT report its Makespan as proven minimal.
7. THE Test_Suite SHALL verify that the Greedy_Search Makespan on the Baseline_Dataset is greater than or equal to 11 days.
8. IF the Greedy_Search frontier becomes empty without reaching a goal State, THEN THE Greedy_Search SHALL return the "no solution" Search_Result defined in Requirement 10, containing no schedule (TR-12).

### Requirement 7: A* Search

**User Story:** As a student comparing algorithms, I want an A* implementation, so that I can compare informed optimal search against UCS.

#### Acceptance Criteria

1. THE AStar_Search SHALL order its frontier as a priority queue keyed by f(n) = g(n) + h(n), expanding the State with the lowest f(n) first and breaking ties between equal f(n) values by lowest h(n), then by insertion order (first inserted expanded first).
2. THE AStar_Search SHALL use h(n) = 0 as its default Heuristic when no Heuristic is supplied.
3. WHEN AStar_Search encounters a State via a route whose g(n) is lower than the best-known g(n) recorded for that State, THE AStar_Search SHALL update the recorded g(n) and re-open the State (TR-09).
4. WHEN AStar_Search encounters a State via a route whose g(n) is greater than or equal to the best-known g(n) recorded for that State, THE AStar_Search SHALL discard that route without re-opening the State.
5. WHERE the supplied Heuristic is an Admissible_Heuristic, THE AStar_Search SHALL return a Search_Result with the minimum possible Makespan.
6. WHEN AStar_Search reaches a goal State, THE AStar_Search SHALL return a Search_Result with status "solved" containing the Makespan, the schedule with start and finish times, and the count of expanded States.
7. THE Test_Suite SHALL verify that AStar_Search with the default Heuristic returns a Makespan of 11 on the Baseline_Dataset with two workers, equal to the UCS Makespan.
8. THE Test_Suite SHALL verify that AStar_Search with a supplied admissible non-zero Heuristic returns a Makespan equal to the UCS Makespan (11) on the Baseline_Dataset with two workers.
9. IF the AStar_Search frontier becomes empty without reaching a goal State, THEN THE AStar_Search SHALL return the "no solution" Search_Result defined in Requirement 10, containing no schedule (TR-12).

### Requirement 8: Schedule reconstruction and metrics

**User Story:** As a scheduler developer, I want each result to carry a full schedule and consistent metrics, so that algorithms can be validated and compared.

#### Acceptance Criteria

1. WHEN a search reaches a goal State, THE Search_Helper SHALL reconstruct the schedule from the sequence of Actions along the path from the initial State to the goal State, producing exactly one Schedule_Entry for each task in the input task set (TR-10).
2. WHEN the Search_Helper reconstructs a Schedule_Entry, THE Search_Helper SHALL set the start_time to the cumulative elapsed days, as an integer of 0 or greater, at the beginning of the Action that started the task.
3. WHEN the Search_Helper reconstructs a Schedule_Entry, THE Search_Helper SHALL set the finish_time to the cumulative elapsed days at the end of the Action in which the task finished, such that finish_time is greater than start_time.
4. WHEN a search reaches a goal State, THE Search_Helper SHALL set the Makespan to the sum of the Transition costs, in days, along the path to the goal State.
5. WHEN a State is removed from the frontier and its successors are generated, THE Search_Helper SHALL increment states_explored by exactly 1, using the same counting rule in all four algorithms and counting neither States that are only generated nor States that are only discarded (TR-11).
6. WHEN a search is invoked, THE Search_Helper SHALL measure `execution_time_ms` in milliseconds with the same monotonic clock, starting immediately before the search begins and ending immediately after the goal State is reached or the search terminates, in all four algorithms (TR-11).
7. WHEN a search terminates, THE Search_Helper SHALL return a Search_Result containing the keys `algorithm`, `makespan`, `schedule`, `states_explored`, `execution_time_ms`, `schedule_valid` and `status`.
8. FOR ALL successful Search_Results, THE Makespan SHALL equal the maximum finish_time in the schedule.
9. IF a search terminates without reaching a goal State, THEN THE Search_Helper SHALL return a Search_Result containing all keys of criterion 7, with `schedule` set to an empty list, `makespan` set to None, and `schedule_valid` set to False, while still reporting the actual `states_explored` and `execution_time_ms` values.

### Requirement 9: Schedule validation

**User Story:** As a tester, I want every returned schedule validated independently of the search, so that an invalid schedule is never reported as a success.

#### Acceptance Criteria

1. WHEN a search returns a schedule, THE Schedule_Validator SHALL check the schedule with the Scheduling_Model `validate_schedule` function, set `schedule_valid` to true if the function reports no violations, and set `schedule_valid` to false otherwise, within 1 second for a schedule of up to 1,000 tasks.
2. WHEN the Schedule_Validator checks a schedule, THE Schedule_Validator SHALL report a violation for each task that is missing from the schedule, each task that appears more than once, and each task that is not in the input task set.
3. WHEN the Schedule_Validator checks a schedule, THE Schedule_Validator SHALL report a violation for each task whose finish_time minus start_time does not equal the task duration, with no tolerance, in the same time unit as the task duration.
4. WHEN the Schedule_Validator checks a schedule, THE Schedule_Validator SHALL report a violation for each task whose start_time is earlier than the finish_time of any of its dependencies.
5. WHEN the Schedule_Validator checks a schedule, THE Schedule_Validator SHALL report a violation for each working day on which the sum of worker demand of all tasks active on that day exceeds the worker capacity.
6. IF the Schedule_Validator finds one or more violations, THEN THE Search_Engine SHALL set `schedule_valid` to false, SHALL report an error that identifies each violation by type and affected task or working day, and SHALL NOT report the Search_Result as a success (TR-12).
7. IF the `validate_schedule` function raises an exception or cannot be run, THEN THE Search_Engine SHALL set `schedule_valid` to false, SHALL report an error indicating that validation could not be completed, and SHALL NOT report the Search_Result as a success.
8. FOR ALL schedules returned by BFS, UCS, Greedy_Search and AStar_Search on the Baseline_Dataset, THE `schedule_valid` value SHALL be true.

### Requirement 10: Failure, infeasibility and timeout reporting

**User Story:** As a tester, I want unsolvable inputs and timeouts reported explicitly, so that I can trust that a successful result is always a real schedule.

#### Acceptance Criteria

1. IF the Search_Engine exhausts all reachable States without reaching a goal State, THEN THE Search_Engine SHALL return a Search_Result with `makespan` set to None, an empty `schedule` (0 entries), `schedule_valid` set to False and a `status` field with the value "no solution" (TR-12).
2. WHERE a Search_Timeout is configured as a positive number of seconds, WHEN the elapsed search time reaches the Search_Timeout, THE Search_Engine SHALL stop the search within 1 second of the limit and return a Search_Result with `makespan` set to None, an empty `schedule` (0 entries), `schedule_valid` set to False and a `status` field with the value "timeout" (TR-12).
3. IF the input fails validation before search begins, THEN THE Search_Engine SHALL not start the search and SHALL return a Search_Result with `makespan` set to None, an empty `schedule` (0 entries), `schedule_valid` set to False, `states_explored` set to 0 and a `status` field with the value "invalid input" together with an error indication identifying the failed validation rule.
4. WHEN a Search_Result reports "no solution", "timeout" or "invalid input", THE Search_Result SHALL contain `states_explored` as a non-negative integer and `execution_time_ms` as a non-negative number.
5. THE Search_Engine SHALL report "no solution", "timeout" and "invalid input" using three mutually exclusive status values, each different from the status value "solved" used for a successfully found schedule.
6. WHEN a Search_Result has a status of "solved", THE Search_Engine SHALL set `schedule_valid` to True, `makespan` to a non-negative number and `schedule` to a non-empty list.

### Requirement 11: Test coverage for listed scenarios

**User Story:** As a tester, I want automated tests for each listed scenario, so that the Phase 2 reference values are verified on every run.

#### Acceptance Criteria

1. WHEN the Test_Suite is run, THE Test_Suite SHALL verify that UCS returns a Search_Result with a Makespan of exactly 11 days on the Baseline_Dataset with two workers.
2. WHEN the Test_Suite is run, THE Test_Suite SHALL verify that AStar_Search, using each admissible Heuristic defined for the project, returns a Search_Result with a Makespan of exactly 11 days on the Baseline_Dataset with two workers.
3. WHEN the Test_Suite is run, THE Test_Suite SHALL verify that UCS and AStar_Search each return a Makespan of exactly 15 days on the Baseline_Dataset with one worker.
4. WHEN the Test_Suite is run, THE Test_Suite SHALL verify that UCS and AStar_Search each return a Makespan of exactly 9 days on the Baseline_Dataset with three workers.
5. WHEN the Test_Suite is run, THE Test_Suite SHALL verify that UCS and AStar_Search each return a Makespan of exactly 12 days on the Baseline_Dataset with two workers when the T05 duration is changed to 3 days.
6. WHEN the Test_Suite is run, THE Test_Suite SHALL verify, for a dataset of independent tasks, that every algorithm returns a schedule in which the sum of workers required by tasks active on any single day never exceeds the worker capacity.
7. WHEN the Test_Suite is run, THE Test_Suite SHALL verify, for a dataset forming a single dependency chain, that every algorithm starts each task no earlier than the finish day of its prerequisite and that the Makespan equals the sum of all task durations.
8. WHEN the Test_Suite is run, THE Test_Suite SHALL verify that a task requiring more workers than the total worker capacity is rejected as infeasible with an "invalid input" status, and that no algorithm search is started for that input.
9. WHEN the Test_Suite is run, THE Test_Suite SHALL verify that, for an input with no valid solution, each algorithm returns a Search_Result with status "no solution" and no schedule.
10. WHEN the Test_Suite is run, THE Test_Suite SHALL execute using only the Python standard library `unittest` module, complete without any network access, and report a pass or fail result for each test case.
11. IF any verified scenario produces a value different from its expected value, THEN THE Test_Suite SHALL report that test case as failed, identify the scenario, and show both the expected and actual values.

### Requirement 12: Comparison output

**User Story:** As a team member, I want a CSV comparing the algorithms, so that the team can review makespan, search effort and runtime side by side.

#### Acceptance Criteria

1. WHEN the comparison script is run, THE Search_Engine SHALL write `comparison.csv` containing a header row followed by exactly one data row per algorithm per scenario, where the algorithms are BFS, UCS, Greedy_Search and AStar_Search.
2. THE Comparison_Report SHALL contain the columns `scenario`, `algorithm`, `makespan`, `states_explored`, `execution_time_ms`, `schedule_valid` and `status`, in that order, with no additional columns.
3. THE Comparison_Report SHALL contain one row for each of BFS, UCS, Greedy_Search and AStar_Search for each scenario listed in Requirement 11 that has a solution.
4. THE Comparison_Report SHALL take every `states_explored` and `execution_time_ms` value from an actual run of the algorithm on that scenario, with no placeholder values such as a `states_explored` of 0 or an `execution_time_ms` of 0.0 that were not measured.
5. THE Comparison_Report SHALL write `makespan` and `states_explored` as non-negative whole numbers, `execution_time_ms` as a non-negative decimal number in milliseconds, and `schedule_valid` as `true` or `false`, with each value equal to the corresponding field of the Search_Result.
6. WHEN the algorithm run for a row finds a schedule, THE Comparison_Report SHALL set `status` to `solved`.
7. IF an algorithm run for a scenario finds no schedule or ends with an error, THEN THE Search_Engine SHALL still write a row for that algorithm and scenario with `status` indicating the failure, `makespan` empty and `schedule_valid` set to `false`, and SHALL continue with the remaining algorithms and scenarios.
8. FOR ALL scenarios in the Comparison_Report, THE Comparison_Report SHALL show a `makespan` for UCS that is less than or equal to the `makespan` of every other algorithm row with `status` of `solved` for the same scenario.
9. IF `comparison.csv` cannot be written, THEN THE Search_Engine SHALL report an error indicating the write failure, SHALL leave any previously existing `comparison.csv` unmodified, and SHALL not leave a partially written file.

### Requirement 13: Serialization of results

**User Story:** As a team member, I want results written to and read back from CSV without loss, so that the comparison file can be trusted and reused.

#### Acceptance Criteria

1. WHEN a list of 0 to 100,000 Search_Results and a destination path are supplied to the CSV write function, THE Search_Engine SHALL write one header row followed by exactly one data row per Search_Result, in input order, using UTF-8 encoding.
2. WHEN a CSV file path is supplied to the CSV read function, THE Search_Engine SHALL return a list of Search_Result-like records with one record per data row, in file order, with every field value identical to the value that was written.
3. WHEN a list of valid Search_Results is written to CSV, read back, and written again to a second file, THE Search_Engine SHALL produce a second file that is byte-for-byte identical to the first file (round-trip property).
4. IF a CSV row is missing a required column, THEN THE reader SHALL return an error that identifies the missing column name and the 1-based row number, and SHALL return no partial list of records.
5. IF the CSV header row is missing a required column, THEN THE reader SHALL return an error that identifies the missing column name, and SHALL return no records.
6. IF the destination path of the write function cannot be written, or the source path of the read function does not exist or cannot be read, THEN THE Search_Engine SHALL return an error that identifies the path and the failure reason, and SHALL leave any previously existing file at the destination path unmodified.

### Requirement 14: Cross-algorithm consistency properties

**User Story:** As a tester, I want property-style checks across algorithms, so that implementation errors are caught on many generated inputs.

#### Acceptance Criteria

1. WHEN the property test suite is run, THE Test_Suite SHALL generate at least 100 random small valid datasets, each containing 1 to 8 tasks, using a fixed random seed so that the same datasets are generated on every run.
2. WHEN a generated dataset is used in a property check, THE Test_Suite SHALL confirm that the dataset passes the Data_Validator before any algorithm is run on it.
3. FOR ALL generated small valid datasets, WHEN UCS and AStar_Search (using an Admissible_Heuristic) are each run on the dataset, THE UCS Makespan SHALL equal the AStar_Search Makespan exactly.
4. FOR ALL generated small valid datasets, WHEN BFS, Greedy_Search and UCS are each run on the dataset, THE Makespan returned by BFS and the Makespan returned by Greedy_Search SHALL each be greater than or equal to the UCS Makespan.
5. FOR ALL generated small valid datasets, WHEN UCS is run on the dataset, THE UCS Makespan SHALL be greater than or equal to the Phase 1 `combined_lower_bound` of the dataset.
6. FOR ALL generated small valid datasets, WHEN any algorithm returns a schedule, THE Schedule_Validator SHALL report that schedule as valid (no dependency, resource, or completeness violations).
7. FOR ALL generated small valid datasets, WHEN the same algorithm is run twice on the same dataset with the same parameters, THE two runs SHALL return identical Makespan values and identical `states_explored` values.
8. IF any property check fails for a generated dataset, THEN THE Test_Suite SHALL report the test as failed and SHALL output the failing dataset, the algorithm name, and the violated property so that the failure can be reproduced.
