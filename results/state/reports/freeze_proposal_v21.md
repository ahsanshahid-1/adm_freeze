# Freeze proposal (main-plan-v2.1)

Frozen Tier-2 conditions (prespecified rule on E0X2): X2b, X3a, X4b.
Design conditions: C0, C1, C2, C3, C4, C5, C6, X2b, X3a, X4b.
Pilot runs used for limits and power: 1680 (sources E0, E0S, E0X2, design conditions only).
Limits (max(protocol-text limit, ceil(1.25 x p95 of pilot usage)), capped at the pilot limit; agentic SUBMITTED/ABSTAINED runs pooled): `{'aggregate_tokens': 300000, 'model_calls': 48, 'tool_calls': 40, 'repair_cycles': 2, 'pipeline_evaluations': 6, 'wall_seconds': 600}`; p95 `{'aggregate_tokens': 245962, 'model_calls': 33, 'tool_calls': 30, 'wall_seconds': 249}`.
Recommended repetitions: [0, 1, 2].

| repetitions | runs | estimated GPU hours |
|---|---|---|
| 3 | 8352 | 40.0 |
| 4 | 11136 | 53.4 |
| 5 | 13920 | 66.7 |
| 6 | 16704 | 80.1 |
