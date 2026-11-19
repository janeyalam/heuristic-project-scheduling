# Code vs Requirements Report (new project, 6-task baseline)

## Summary

The new project's code and data match Project_Requirements.md. No functional bugs were found against the requirements.

- 'tasks.csv' and 'reference_schedule.csv' match the requirements exactly.
- 'python data_validation.py tasks.csv --workers 2' prints VALID. The lower bounds are critical path 9 and workload 8.
- 'python -m unittest -v test_phase1.py' ran 20 tests, all OK. 'pytest' is not installed, so it was not used.
- 'python scheduling_model.py tasks.csv --workers 2' traces day 0 to 2 to 5 to 6 to 8 to 10 to 11 and prints "VALID reference schedule: 11 working days".
- No old 12-task leftovers remain in the three code files. There is no 'duration_days', 'task_name' or 'project_config.json', no 20-day figure, and no 2-worker tasks.

Real issues are minor:

1. README.md and Scheduling_Model.md refer to 'Project_Requirements_SS.md', which does not exist. The file is named 'Project_Requirements.md'.
2. Test coverage gaps.
3. Small robustness and cosmetic points.

The only old-project residue is generality, such as the ID regex and the '|' delimiter.

## Evidence

### tasks.csv
- Header is 'task_id,duration,depends_on,workers_required', with no 'task_name'.
- Durations are 2,4,3,3,2,1, as required.
- Dependencies are 'None' for T01, 'T01' for T02, T03 and T04, '"T02, T03, T04"' for T05, and 'T05' for T06.
- 'workers_required' is 1 for every task.
- The multi-predecessor delimiter is a comma, quoted in the CSV. The requirements leave the delimiter unspecified, so this is a valid choice. 'parse_dependencies' (data_validation.py:41-52) also accepts '|'.

### reference_schedule.csv
- The rows are T01 W1 0-2, T02 W1 2-6, T03 W2 2-5, T04 W2 5-8, T05 W1 8-10 and T06 W1 10-11, which equals the requirements table.
- The headers are 'task_id,worker_id,start_day,finish_day'. The doc uses Task, Worker, Start and Finish. This is a harmless renaming.
- 'validate_schedule' returns 11 for it.

### data_validation.py
- REQUIRED_COLUMNS (line 18) is correct and is checked in order (line 104).
- 'None' or an empty value becomes '()' (line 44).
- Duplicate IDs, bad durations, self-dependencies, missing dependencies and cycles (DFS, lines 77-94) are rejected.
- A task whose 'workers_required' exceeds capacity is rejected (line 67).
- The default worker count is 2 (line 141).
- Unquoted multi-predecessor rows are rejected as malformed (lines 107-108).

### scheduling_model.py
- 'advance' jumps to the next completion event. A worker that finishes at t is freed at t, because the ranges are half-open ('a <= day < b', line 146) and 'advance' completes tasks before computing the next start. This matches the requirements.
- 'validate_schedule' (lines 116-152) checks:
  - Each task appears exactly once.
  - Duration equals finish minus start.
  - Start is not negative.
  - Predecessors finish before a task starts.
  - Concurrent demand is within capacity.
  - There is no same-worker overlap.
- Tracer gate (line 189): 'trace_reference_schedule' is only run when workers == 2 and the IDs are T01..T06.

### test_phase1.py
The 20 tests cover:
- The dataset structure.
- The reference schedule at 11 days.
- Lower bounds of (9, 8).
- Legal start sets at day 2 (6 choices).
- Precedence and capacity violations.
- The sensitivity schedules: 1 worker gives 15 days, 3 workers give 9, and T05=3 with 2 workers gives 12.
- Invalid dependency and same-worker overlap schedules.
- Cycle, missing predecessor, over-capacity and zero-duration rejection.
- Unquoted multi-predecessor CSV rejection.

### Old project (CS-7375-Project-OLD), for contrast only
- Its data_validation.py:20 requires 'task_id, task_name, duration_days, depends_on, workers_required'.
- Its data_validation.py:22 has the same ID regex that the new project kept.
- It also has 'project_config.json', 'tasks_small.csv', Gantt scripts, TRACEABILITY.md and a 'quality_assurance/' directory.
- None of these appear in the new project.

## Findings by file

### data_validation.py
- Line 19: 'TASK_ID_PATTERN = [A-Z][A-Z0-9_]*' is a leftover from the old uppercase-letter-ID rule. It is more general than the new T01..T06 format. T1 and TASK would both pass.
- Line 46: the comment "team's earlier prototype" and the '|' delimiter support are legacy. They are harmless but undocumented in the requirements.
- Lines 124-135: 'lower_bounds' returns (9, 8). The requirements' stronger argument (after T01, 4, 3 and 3 days on two workers needs at least 6 days, so at least 11) is not implemented. The docstring does say that neither bound alone proves the optimum.
- Line 1 docstring and line 139 say "SS" requirements. This is cosmetic.

### scheduling_model.py
- Lines 138-152: 'worker_id' is not checked against the capacity range. A schedule using worker 3 with capacity 2 passes if nothing overlaps. Low risk.
- Lines 128 and 132: a malformed row (missing 'start_day') raises KeyError, not ValueError.
- Line 189: the tracer is hard-coded to T01..T06 with 2 workers. This is fine for Phase 1, but it will not trace the sensitivity cases.
- Lines 1 and 181: the "JA" and "SS" role labels are cosmetic.

### test_phase1.py
- 'test_ss_dataset_structure' (line 22) checks IDs, the duration total of 15, and the T01 and T05 dependencies. It does not assert the individual durations, the T02..T04 dependencies, T06's dependency, or 'workers_required == 1'.
- There is no test that the 'tasks.csv' header is exactly the four columns, and none for a 'task_name' or 'duration_days' header being rejected. The only malformed-CSV test is the unquoted multi-predecessor one.
- There is no test of the CLI 'main()' or of 'read_reference_schedule' column handling.
- The 12-day case (line 95) and the 9-day and 15-day cases only prove that a feasible schedule of that length exists. Nothing proves 11, 12, 9 or 15 is the minimum. That is expected, because there is no solver in Phase 1. It is worth stating in the test names or docs.
- There is no test that a worker finishing at t can start another task at t on the same worker. The reference schedule exercises this implicitly (W1 T01 ends at 2 and T02 starts at 2), but there is no explicit test.
- No stale 12-task, 20-day or 'duration_days' content.
- The file ends with 'unittest.main' while pytest is not installed. README.md says to run unittest, which works.

### README.md and Scheduling_Model.md
- README.md and Scheduling_Model.md (line 5) cite 'Project_Requirements_SS.md' as the source of truth, but that file is not in the directory. The actual file is 'Project_Requirements.md'. README.md's file table also says "included unchanged". This is the most visible stale reference.
- README.md mentions the earlier 12-task SkillBridge sample and the five-column schema. This is intentional historical context, not a bug.
- Scheduling_Model.md line 40 documents the quoted-comma format and '|' support, which agrees with the code.
- Not verified: the requirements file showed mojibake in terminal output ('Â·', 'â€™'). This may be a PowerShell code-page display issue or a real encoding problem in the file. I did not check the raw bytes.
- Not checked: the full text of Scheduling_Model.md was only grepped, not read in full.

## Recommended fixes (prioritized, none implemented)

1. Fix the 'Project_Requirements_SS.md' references in README.md and Scheduling_Model.md, or rename the file.
2. Strengthen 'test_ss_dataset_structure' to assert every duration, every dependency tuple and 'workers_required == 1'. Add a header-exactness test and a test that the old five-column header is rejected.
3. Add an explicit test that a task starts at the moment another finishes on the same worker, plus a test that malformed schedule rows raise ValueError.
4. Optional: tighten 'TASK_ID_PATTERN' to 'T\d{2}', or document why it stays general. Decide whether the '|' delimiter should remain.
5. Optional: validate 'worker_id' against 1..capacity in 'validate_schedule', and convert KeyError to ValueError.
6. Optional: add the sharper lower bound (best two-worker split of the parallel tasks) so the tool can show 11 for this dataset.
7. Confirm the encoding of Project_Requirements.md as UTF-8.

## Environment notes
- The new project is not a git repository, so git status and diff were not available.
- 'pytest' is not installed. unittest was used instead.
