# Heuristic Analysis (Phase 3)

**Source of all numbers:** `heuristic_results.csv` (70 rows, 10 instances, 7 methods each), summarised with `python -m experiments.heuristic_summary results/heuristic_results.csv`. Nothing was re-run for this document. Group figures below are the medians in that summary. Instance figures are single rows of the CSV. Where a ratio or per-state figure appears, it is computed by dividing two CSV medians and is marked "computed".

**Status:** SS's review of `Heuristic_Scenarios.md` is still pending. The business reading of the four baseline scenarios in this document has not been checked by SS.

## 1. What was measured

- Four baseline scenarios from SS's six-task pilot: `baseline_2w` (optimum 11 days), `baseline_1w` (15), `baseline_3w` (9) and `baseline_t05_3days` (12).
- Six synthetic instances with two workers: `wide_01`, `wide_02`, `deep_01`, `deep_02`, `mixed_01`, `mixed_02`.
- Seven methods per instance: UCS, A* with H0, H1, H2, H3, and Greedy with H1 and H3.
- Heuristics (from the Phase 3 section of `Technical_Requirements.md`): H0 is zero. H1 is the longest remaining unfinished task. H2 is the remaining critical path. H3 is the larger of the H2 value and the workload bound, which is the sum of worker demand times remaining days, divided by capacity and rounded up.
- Every row has `search_status = solved` and `solution_valid = true`. Every A* row has the same makespan as UCS on its instance (gap 0.0).

### Median results per group

States expanded / runtime in ms. Group sizes: baseline 4 instances, wide 2, deep 2, mixed 2.

| method | baseline | deep | mixed | wide |
|---|---|---|---|---|
| ucs | 15.0 / 0.29 | 9.0 / 0.14 | 350.5 / 13.98 | 1892.0 / 127.32 |
| astar/H0 | 15.0 / 0.29 | 9.0 / 0.14 | 350.5 / 13.97 | 1892.0 / 126.20 |
| astar/H1 | 12.5 / 0.26 | 9.0 / 0.19 | 318.0 / 14.07 | 1754.0 / 125.62 |
| astar/H2 | 6.0 / 0.15 | 9.0 / 0.19 | 261.5 / 12.18 | 1625.0 / 118.29 |
| astar/H3 | 6.0 / 0.16 | 9.0 / 0.17 | 29.5 / 1.27 | 9.0 / 3.13 |
| greedy/H1 | 5.5 / 0.15 | 9.0 / 0.15 | 58.0 / 3.12 | 218.0 / 40.21 |
| greedy/H3 | 5.0 / 0.15 | 9.0 / 0.16 | 10.0 / 0.44 | 8.5 / 3.66 |

Greedy median optimality gap (%), median / max:

| method | baseline | deep | mixed | wide |
|---|---|---|---|---|
| greedy/H1 | 4.2 / 9.1 | 0.0 / 0.0 | 22.4 / 35.3 | 13.1 / 17.9 |
| greedy/H3 | 4.2 / 9.1 | 0.0 / 0.0 | 26.6 / 29.4 | 6.0 / 8.3 |

## 2. Answers to the research questions

**Main question: can a dependency- and worker-aware heuristic reduce the states explored while A* still finds the minimum makespan?**
In this data, yes on baseline, mixed and wide instances, and not on deep instances. Every A* run with H1, H2 and H3 returned the UCS makespan, so no optimality was lost. A* with H3 expanded 6.0 states in the baseline group against 15.0 for UCS, 29.5 against 350.5 in mixed, and 9.0 against 1892.0 in wide. In the deep group every method expanded 9.0 states (see section 3).

**How much does the critical-path bound (H2) improve on the simple H1 estimate?**
It helps modestly on the larger groups and clearly on the baseline group. Medians for H1 against H2: baseline 12.5 against 6.0, mixed 318.0 against 261.5, wide 1754.0 against 1625.0. Over H0, H1 saved 2.5 states in baseline (15.0 to 12.5), 32.5 in mixed and 138.0 in wide. On the two wide and two mixed instances, H2 alone left most of the search in place. For example `wide_02` expanded 3247 states with H0 and 2879 with H2.

**Does the workload bound (H3) improve further?**
On the synthetic mixed and wide instances, a lot. H2 to H3 medians: mixed 261.5 to 29.5, wide 1625.0 to 9.0. Per instance, `wide_02` went from 2879 states (H2) to 11 (H3), and `mixed_02` from 438 to 37. In the baseline group H3 and H2 tie at 6.0 states, and in the deep group they tie at 9.0. The synthetic instances use capacity 2 and many independent tasks, which is where a worker-time bound has the most to say. The data does not show whether this holds for other capacities.

**Does the improvement change with worker capacity, durations or size?**
Capacity and duration changes are visible only in the four baseline scenarios, where tasks and structure are the same:

| scenario | UCS expanded | H1 | H2 | H3 |
|---|---|---|---|---|
| baseline_1w | 10 | 10 | 8 | 6 |
| baseline_2w | 15 | 15 | 6 | 6 |
| baseline_3w | 15 | 9 | 5 | 5 |
| baseline_t05_3days | 15 | 15 | 6 | 6 |

H1 helped only with three workers (15 to 9). H2 and H3 helped in all four scenarios. With one worker, H3 beat H2 (6 against 8), the only baseline scenario where it did. On size, the effect depended on structure more than on task count. `deep_02` (10 tasks) gained nothing, while `wide_01` (9 tasks) went from 537 states (UCS) to 7 (H3). Six synthetic instances are too few to separate size from structure.

**Does fewer states mean less time?**
Mostly, with exceptions. A* with H3 expanded the fewest states in the baseline, mixed and wide groups (6.0, 29.5, 9.0, tied with H2 at 6.0 in baseline). Runtime followed in mixed (1.27 ms against 13.98 for UCS) and wide (3.13 ms against 127.32). In the baseline group H2 (0.15 ms) and H3 (0.16 ms) were both about half of UCS (0.29 ms), and the 0.01 ms gap between them is within the noise discussed in section 4. Time per expanded state is not constant, though (see section 3).

**When is Greedy faster but longer?**
Greedy expanded fewer states than UCS in every group except deep, where all methods expanded 9.0 states. It returned a longer schedule on 6 of the 10 instances for H1 and 6 of 10 for H3 (rows with gap above 0 in the CSV):

- `baseline_2w`: Greedy returned 12 days against the optimum of 11 (gap 9.1%), expanding 5 states against 15 for UCS. Runtime was 0.15 ms (H1) and 0.16 ms (H3), against 0.30 ms for UCS and 0.15 to 0.16 ms for A* with H2 or H3. So A* with H2 or H3 was equally fast here and optimal.
- `baseline_t05_3days`: 13 days against 12 (gap 8.3%).
- `mixed_01`: Greedy/H3 took 0.39 ms and returned 22 days against 17 (gap 29.4%). A*/H3 took 0.80 ms and returned 17. Greedy/H1 returned 23 (gap 35.3%).
- `mixed_02`: Greedy/H3 took 0.50 ms and returned 26 days against 21 (gap 23.8%). A*/H3 took 1.75 ms. Here H3 gave a worse schedule than H1 (23, gap 9.5%).
- `wide_01`: Greedy/H3 took 1.01 ms against 1.08 ms for A*/H3, with a gap of 8.3%. The time saving is 0.07 ms.
- `wide_02`: Greedy/H1 returned 33 days against 28 (gap 17.9%) and Greedy/H3 returned 29 (gap 3.6%). Greedy/H3 took 6.31 ms, slower than A*/H3 at 5.17 ms, which was optimal.

Greedy was clearly faster than A*/H3 only in the mixed group (median 0.44 ms against 1.27 ms), and there its median gap was 26.6% for H3 and 22.4% for H1. Greedy matched the optimum on all deep instances and on `baseline_1w` and `baseline_3w`.

## 3. Unexpected results

1. **Deep group: no heuristic reduced the search.** Every method expanded 8 states on `deep_01` and 10 on `deep_02` (group median 9.0). These instances appear to leave almost no choice of which task to start, so a better estimate has nothing to prune. This is an interpretation. The CSV only shows the equal counts. Runtime then reflected only heuristic cost: A*/H1 and A*/H2 had a group median of 0.19 ms against 0.14 ms for A*/H0 and UCS, for the same 9.0 states. On `deep_02`, A*/H1 took 0.25 ms and UCS 0.16 ms for 10 states each.
2. **Heuristic overhead on small instances.** Where states were not saved, the heuristic only added time. The deep result above is one case. In the mixed group A*/H1 expanded fewer states than A*/H0 (318.0 against 350.5) but its median runtime was slightly higher (14.07 ms against 13.97 ms).
3. **A*/H3 on wide instances: runtime does not scale down with states.** A*/H3 expanded 9.0 states (against 1892.0 for UCS, which is 0.5% of the states, computed) but took 3.13 ms against 127.32 ms (2.5% of the time, computed). Per expanded state that is about 0.35 ms for A*/H3 and about 0.067 ms for UCS (both computed from the medians). Each H3 evaluation, together with the successors it scores, costs more than a UCS expansion. Part of it is that H3 makes A* generate more successors per expanded state: `wide_02` generated 93 successors for 11 expansions (H3), against 12344 for 3247 (UCS). I did not profile the heuristic, so the cost split is not measured.
4. **Greedy/H3 slower than A*/H3 in wide.** Group medians were 3.66 ms for Greedy/H3 (8.5 states) and 3.13 ms for A*/H3 (9.0 states). On `wide_02` the same happened: 6.31 ms against 5.17 ms. Expanding fewer states did not give less time.
5. **H3 was not always the better guide for Greedy.** On `mixed_02`, Greedy/H3 returned 26 days and Greedy/H1 returned 23. In the mixed group the median gap for H3 (26.6%) was above that for H1 (22.4%). In the wide group H3 was better (6.0% against 13.1%). With two instances per group, neither result is stable.
6. **Baseline timing noise.** On `baseline_2w`, A*/H1 expanded the same 15 states as UCS and A*/H0, yet its runtime was 0.50 ms against 0.30 ms. Differences of a few hundredths of a millisecond in the baseline group should not be read as real.

## 4. Limits

- **Instance sizes.** The instances have 6 tasks (the four SS baseline cases) and 8 to 12 tasks (the six synthetic ones), per the `task_count` column. The CSV has no instance with fewer than 6 tasks. Results say nothing about larger projects.
- **Few instances.** There are 6 synthetic instances and 4 SS instances. Two instances per structure group means group medians are medians of two values. The four SS instances are variants of one project (changed capacity or one duration), so they are not independent.
- **Capacity.** All synthetic instances use capacity 2 (`worker_capacity` column). Only the SS baseline varies it (1, 2 and 3).
- **Exact search only.** Every run finished with status `solved`. No timeouts or state limits were hit, so the data does not show how the methods behave on instances too large for UCS.
- **Timing.** Each runtime is the median of 5 repeats on a single machine, with the heuristic time included. Sub-millisecond values (all baseline and deep rows) are within timing noise, as the `baseline_2w` A*/H1 case shows. State counts are deterministic and do not have this problem.
- **Heuristic definitions.** The results apply to H0 to H3 as defined in the Phase 3 section of `Technical_Requirements.md` and implemented in `heuristics.py`, with the Phase 1 model (fixed durations, no interruption, interchangeable workers). Worker skills are not modelled.
- **Review status.** SS has not yet reviewed `Heuristic_Scenarios.md`. JC's comparison figures have not been made.
- **No speedup claim.** The numbers describe these 10 instances. They do not show that H3 will reduce search effort on other projects, and deep-structure instances show it may not.
