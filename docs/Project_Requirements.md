# Project Requirements

CS 7375 · AI-Based Intelligent Project Scheduling and Resource Optimization · Phase 1 (P1-01)

## Project background

A fictional workforce training team is preparing a small onboarding pilot. Before it can launch, the team must prepare the training materials, set up registration, and run a rehearsal. Two coordinators are available for the work. The scheduling goal is to reach launch approval in the fewest working days while meeting every prerequisite and staying within the staffing limit.

This is a proposed six-task baseline for the team’s dataset and scheduler. The project, task estimates, and staffing assumptions are synthetic.

## Tasks

| `task_id` | Task and completion condition | `duration` (working days) | `depends_on` | `workers_required` |
| --- | --- | ---: | --- | ---: |
| T01 | Define the pilot scope. Agree on the audience, learning goals, and launch criteria. | 2 | None | 1 |
| T02 | Build the training module. Prepare the lesson, exercises, and a short knowledge check. | 4 | T01 | 1 |
| T03 | Configure registration. Set up the signup form and test enrollment with sample accounts. | 3 | T01 | 1 |
| T04 | Prepare participant communications. Draft the invitation, instructions, and support FAQ. | 3 | T01 | 1 |
| T05 | Run the rehearsal. Walk through registration, the invitation, and the lesson with sample participants. | 2 | T02, T03, T04 | 1 |
| T06 | Approve the launch. Confirm the rehearsal passed and the pilot is ready to open. | 1 | T05 | 1 |

For `tasks.csv`, use `task_id`, `duration`, `depends_on`, and `workers_required` from the table. `None` represents an empty dependency list. A task with multiple predecessors must wait for all of them.

## Scheduling rules and assumptions

- Time starts at day 0 and advances in whole working days. Both coordinators are available throughout the baseline.
- Workers are interchangeable. Each active task uses one worker for its full duration, and each worker can work on at most one task at a time.
- Durations are fixed. Once a task starts, it runs to completion without interruption.
- A task can start when all its predecessors are complete and a worker is free. A worker who finishes at time `t` can start another task at time `t`.
- The schedule is complete when all six tasks finish. Report each task’s start and finish and the project’s total completion time (makespan). A feasible schedule completes every task once, respects its prerequisites, and uses at most two workers at any time.

## Reference schedule

| Task | Worker | Start | Finish |
| --- | --- | ---: | ---: |
| T01 | 1 | 0 | 2 |
| T02 | 1 | 2 | 6 |
| T03 | 2 | 2 | 5 |
| T04 | 2 | 5 | 8 |
| T05 | 1 | 8 | 10 |
| T06 | 1 | 10 | 11 |

**Minimum completion time with two workers is 11 working days.** After T01, three tasks of 4, 3, and 3 days share two workers. One worker must perform at least two of them in sequence, which takes at least 6 days. Adding 2 days for T01, 2 for T05, and 1 for T06 gives a lower bound of 11 days. The reference schedule meets that bound. A solver that claims optimality should return 11 days, and its task assignments may differ from the table.

## Suggested business refinements

- **Compare staffing options.** With the same tasks and assumptions, the pilot takes at least 15 days with one worker, 11 with two, or 9 with three. Use the time saved to decide whether bringing in a third coordinator for the parallel work is worth the staffing cost.
- **Use the rehearsal as a launch gate.** Define three checks in advance: a sample participant can register, the invitation provides the right instructions, and the participant can finish the lesson. If the rehearsal needs an extra day, rerun the schedule with T05 set to three days. The minimum moves from 11 to 12 days with two workers.
- **Test what happens when workers have different skills.** In a later scenario, require a coordinator with access to the registration system for T03 and a reviewer for T06. Use fictional roles and availability to test how those limits change the launch date.
