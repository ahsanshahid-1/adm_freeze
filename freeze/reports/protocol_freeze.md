# Protocol freeze

Created 2026-11-12T08:16:43Z.
Protocol hash `22d4f2fa1dab5138402e649306a7cefc1c7ef5ad31d50b35f607785c6f7740f1`; code hash `c8cdef91e85a6f2a09719d22bc3cdabcea0222dce7d1c0eb199cf59773ae3fba`.
Limits: `{'aggregate_tokens': 300000, 'model_calls': 48, 'tool_calls': 40, 'repair_cycles': 2, 'pipeline_evaluations': 6, 'wall_seconds': 600}`.
Repetitions: [0, 1, 2]. Optional E7: False.
Tier-2 conditions (main-plan-v2.1): ['X2b', 'X3a', 'X4b'].
Overrides of the prespecified rule: none.
Formal runs scheduled: 8352.
Oracle solvability of formal Tier-2 instances: 324/324.
LLM mode: vllm.

Primary analysis: H1: MQP - M0 verified completion, backbone A, all recoverable core tasks (Tier 1 and the frozen Tier-2 conditions, pooled; main-plan-v2.1)
Secondary (Holm): Q main effect, P main effect, Q x P interaction, MQP - SQP, MQP - F (Tier 1 conditions only)
