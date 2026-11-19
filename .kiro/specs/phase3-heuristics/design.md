# Design: Phase 3 Heuristics

Python, standard library only, `unittest`, matching Phases 1 and 2. No change to `scheduling_model.py`.

## Changes to existing code

- `search_common.make_result` gains a `states_generated` field (default 0). `best_first_search` adds `len(successors(...))` to a counter at each counted expansion and passes it to the result.
- `bfs_search`, `ucs_search`, `greedy_search`, `astar_search` accept `max_expansions=None` and pass it to `best_first_search`. When the limit is reached the loop stops with status `state_limit`. `check_input` and the status list are updated everywhere statuses are validated, including the Phase 2 result-shape test.
- `results_io.py` is unchanged. Phase 2 `comparison.csv` keeps its seven columns.

## New files

| File | Purpose |
|---|---|
| `test_heuristics.py` | Tests HT-01 to HT-11 plus runner and CSV tests |
| `heuristic_data.py` | Seeded generator of 8 to 12 task instances; writes `heuristic_test_data/*.csv` and `heuristic_test_data/NOTES.md` |
| `heuristic_comparison.py` | Runner. Builds the instance list, runs the seven methods, repeats timing, writes the CSV, prints a summary table |
| `heuristic_io.py` | Atomic writer and validating reader for `heuristic_results.csv` |
| `Heuristic_Scenarios.md` | SS scenarios, draft for review |
| `Heuristic_Analysis.md` | Findings from measured results |

## Runner rules

- Instances: the four SS baseline scenarios (2 workers, 1 worker, 3 workers, T05 at 3 days) plus the synthetic ones. Tasks are loaded only through `load_tasks`. Temporary CSVs are written to a temp folder and removed.
- Methods: `ucs`, `astar/H0`, `astar/H1`, `astar/H2`, `astar/H3`, `greedy/H1`, `greedy/H3`. H0 to H3 map to `zero_heuristic`, `longest_remaining`, `critical_path_remaining`, `combined_heuristic`.
- One shared timeout and one shared `max_expansions` for all methods.
- Runtime: median of 5 repeats of the whole search call, with the heuristic time inside it. State counts are deterministic and come from the first run.
- Optimum: the UCS makespan for the instance. If UCS itself times out, the gap is empty for that instance.
- A* rows with an admissible heuristic must equal the UCS makespan. If one does not, the runner exits with code 1 and writes nothing.
- Output path is validated before any run. Nothing is passed to a shell.

## Error handling

An exception in one run becomes a row with status `error`, empty makespan and gap, and `solution_valid` false. The runner continues with the remaining runs.