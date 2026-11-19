# Heuristic Scenarios

> **DRAFT: awaiting SS review.** The scenarios and expected values below are not approved until the SS signs off.

## Purpose
These scenarios are used to check the Phase 3 heuristics. Each scenario differs from the baseline in exactly one factor. Expected values are optimal makespans in days.

## Base task data (`tasks.csv`)

| Task | Duration (days) | Depends on | Workers required |
|------|-----------------|------------|------------------|
| T01 | 2 | None | 1 |
| T02 | 4 | T01 | 1 |
| T03 | 3 | T01 | 1 |
| T04 | 3 | T01 | 1 |
| T05 | 2 | T02, T03, T04 | 1 |
| T06 | 1 | T05 | 1 |

## Scenarios

| # | Scenario | Workers | Change from baseline | Expected optimal makespan |
|---|----------|---------|----------------------|---------------------------|
| 1 | Baseline | 2 | None | 11 |
| 2 | One worker | 1 | Workers 2 to 1 | 15 |
| 3 | Three workers | 3 | Workers 2 to 3 | 9 |
| 4 | T05 takes 3 days | 2 | T05 duration 2 to 3 | 12 |

## Reasoning
1. **Baseline (11).** T01 runs days 0-2. T02 and T03 start at day 2. T03 ends at 5, so T04 runs 5-8. T02 ends at 6. T05 runs 8-10 and T06 runs 10-11.
2. **One worker (15).** Tasks run one at a time, so the makespan is the sum of durations: 2+4+3+3+2+1 = 15.
3. **Three workers (9).** T02, T03 and T04 run together from day 2, and T02 ends at 6. T05 runs 6-8 and T06 runs 8-9. This equals the critical path T01, T02, T05, T06 = 2+4+2+1.
4. **T05 = 3 days (12).** The schedule matches the baseline until day 8. T05 then runs 8-11 and T06 runs 11-12.

## Scope
- Worker qualifications and skills are **out of scope**. Every worker can do every task.
- Each worker is assumed to do one task at a time, and every task needs 1 worker.

## Review status
- [ ] SS review pending
