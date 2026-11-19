# Heuristic Search for Project Scheduling — Implementation Plan

This document says **who builds what, in what order, and what is done**. What the system must do is in `Technical_Requirements.md`. The business problem is in `Project_Requirements.md`.

**Team:** JA (Software Engineering / Search), SB (Computer Science / AI), SS (Business Development), JC (Testing / Visualization; provisional).

| Phase | Status |
|---|---|
| Phase 1 — Scheduling model and data validation | Done (files exist, Phase 1 tests pass) |
| Phase 2 — Search algorithms | Code, tests and comparison done. Two documentation deliverables are still missing (see the checklist). |
| Phase 3 — Heuristics | Code, tests, results and analysis done. SS review of `Heuristic_Scenarios.md` is pending and no comparison figures were made (see the checklist). |

## Phase 1 plan

| Phase 1 deliverable | Owner | Needed for Phase 2 |
|---|---|---|
| `Project_Requirements.md` | SS | Defines the scheduling problem and baseline assumptions |
| `tasks.csv` | SB | Task durations, dependencies and worker requirements |
| `data_validation.py` | SB | Validates inputs |
| `Scheduling_Model.md` | JA | Defines states, actions, transitions, costs and goals |
| `scheduling_model.py` | JA | Generates valid successor states |
| `test_phase1.py` | JC / JA | Verifies scheduling constraints |

## Phase 2 plan

### Task assignments

| Task ID | Task | Owner | Deliverable |
|---|---|---|---|
| **P2.1** | Implement Breadth-First Search | JA | `bfs.py` |
| **P2.2** | Implement Uniform-Cost Search | JA | `ucs.py` |
| **P2.3** | Implement Greedy Best-First Search | JA | `greedy.py` |
| **P2.4** | Implement A* Search | JA | `astar.py` |
| **P2.5** | Prepare common test datasets for all algorithms | SB | `search_test_data/` |
| **P2.6** | Define additional scheduling scenarios | SS | `Scheduling_Scenarios.md` |
| **P2.7** | Test schedules and compare algorithms | JC, JA | `test_search.py`, `comparison.csv` |
| **P2.8** | Integrate and review the components | All | Working Phase 2 search engine |

### Completion checklist

- [x] **P2.1 — JA:** BFS implementation complete (`bfs.py`).
- [x] **P2.2 — JA:** UCS implementation complete (`ucs.py`).
- [x] **P2.3 — JA:** Greedy Best-First implementation complete (`greedy.py`).
- [x] **P2.4 — JA:** A* implementation complete (`astar.py`).
- [x] **P2.5 — SB:** Shared test datasets prepared (`data/search_test_data/`). *6 hand-made CSVs and `NOTES.md`. `comparison.py` does not use them.*
- [ ] **P2.6 — SS:** Scheduling scenarios documented (`Scheduling_Scenarios.md`). *The file does not exist yet.*
- [x] **P2.7 — JC/JA:** Algorithm tests and comparison completed (`test_search.py`, `comparison.csv`).
- [ ] **P2.8 — All:** Integrated search engine reviewed and working. *It works: `python -m unittest discover` runs 129 tests (including the Phase 3 tests), all passing. The team review is not recorded.*

`comparison.py` currently builds its six scenarios itself, so it does not depend on `search_test_data/` or `Scheduling_Scenarios.md`.

### Implementation order

1. Confirm that `scheduling_model.py` exposes `initial_state()`, `successors(state)` and `is_goal(state)`. Each successor provides the next state, the elapsed transition cost and enough action information to reconstruct the schedule. *Done.*
2. Implement **BFS** and confirm it returns a valid schedule. *Done.*
3. Implement **UCS** and verify the 11-day baseline minimum. *Done.*
4. Implement **Greedy Best-First Search** with a simple heuristic. *Done.*
5. Implement **A***, first with h(n) = 0, and verify the 11-day baseline minimum. *Done.*
6. Run all four algorithms on the same scenarios, record metrics and review the comparison with JC. *Metrics recorded in `comparison.csv`. The review with JC is not recorded.*
7. Complete integration and hand the working search engine to Phase 3. *Pending the P2.8 review.*

**Immediate milestone (reached):** BFS and UCS run on SS's six-task dataset, both generate valid schedules, and UCS finds the 11-day minimum makespan.

## Phase 3 plan

The tasks, owners and test requirements are in the Phase 3 section of `Technical_Requirements.md`. Phase 3 implements and compares stronger heuristics, including remaining critical-path and resource-workload lower bounds. The heuristics H0 to H3 are in `heuristics.py`. The search functions gained a `max_expansions` argument, a `states_generated` result key and the `state_limit` status.

### Completion checklist

- [x] **P3.1 to P3.4 — JA:** Heuristics H0 to H3 implemented (`heuristics.py`). *The team approval of the definitions is not recorded.*
- [x] **P3.5 — SB:** Synthetic instances and notes (`heuristic_data.py`, `heuristic_test_data/`).
- [ ] **P3.6 — SS:** Scenarios reviewed and approved (`Heuristic_Scenarios.md`). *The file exists as a draft. SS has not reviewed it.*
- [x] **P3.7 — JC:** Heuristic and schedule-validity tests (`test_heuristics.py`, 29 tests, all passing).
- [x] **P3.8 — JC:** Comparison run and results recorded (`heuristic_comparison.py`, `heuristic_io.py`, `heuristic_summary.py`, `heuristic_results.csv`).
- [ ] **P3.8 — JC:** Comparison figures. *Not made. Skipped by decision, and no plotting dependency was added.*
- [x] **P3.9 — All:** Findings written up (`Heuristic_Analysis.md`). *The business reading of the baseline scenarios awaits SS.*

Run: `python -m experiments.heuristic_data`, then `python -m experiments.heuristic_comparison`, then `python -m experiments.heuristic_summary results/heuristic_results.csv`. `python -m unittest -v tests.test_heuristics` runs the Phase 3 tests.