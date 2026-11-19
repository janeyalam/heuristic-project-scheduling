# Search test data
Shared input files for BFS, UCS, Greedy and A*. All files were written by hand (no generator, no seeds).
Each file uses the tasks.csv format, has 4 to 9 tasks, and needs at most 2 workers per task. Use capacity 2.
All files pass `python -m scheduling.data_validation <file> --workers 2`.
| File | Shape | Tasks | Optimal makespan (days) | Lower bound |
|---|---|---|---|---|
| tiny_chain.csv | chain of 4 tasks | 4 | 8 | 8 |
| tiny_parallel.csv | 4 independent tasks | 4 | 5 | 5 |
| wide_fanout.csv | wide: 1 root, 6 middle tasks, 1 join | 8 | 8 | 8 |
| deep_chain.csv | deep: chain with two extra dependencies | 8 | 16 | 16 |
| mixed_layers.csv | mixed: three layers, two 2-worker tasks | 9 | 15 | 12 |
| worker_bottleneck.csv | worker capacity is the limit | 6 | 12 | 12 |
Optimal makespan = result of UCS and A* (UCS searches exhaustively by cost). Lower bound = combined lower bound printed by `data_validation`.
## Design
- **tiny_chain, tiny_parallel**: small enough to check by hand.
- **wide_fanout**: six 2-day tasks wait on T01 and share 2 workers (6 days), plus 1 day before and 1 day after.
- **deep_chain**: the critical path (all tasks in sequence) decides the makespan; workers are not a limit.
- **mixed_layers**: independent starts, joins, and 2-worker tasks (T03, T06) that block other work.
- **worker_bottleneck**: T01, T02 and T05 need both workers (7 days, nothing else can run), T03 and T04 run side by side (4 days), then T06 (1 day).
## Algorithm differences
Only `mixed_layers.csv` separates the algorithms (capacity 2, default heuristics):
- UCS and A*: 15 days (optimal)
- BFS: 18 days (BFS minimises transitions, not days)
- Greedy: 20 days
On every other file all four algorithms return the optimal makespan.
All four algorithms solved every file in under 15 ms and returned schedules accepted by the Phase 1 validator.
