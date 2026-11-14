# Protocol deviations (recorded automatically)

1. This run follows main-plan-v2.md, a revision of main-plan.md v1.0 made before the pilot: backbones changed to Qwen/Qwen3.8-27B (A) and google/gemma-4-31B-it (B), reasoning mode disabled (Section 9.2), single-GPU hardware (Section 20.1) and a ceiling check in E0. Exact repositories and revisions are in configs/models.lock.json.
2. Isolation is process-level instead of containers (the CRC JupyterHub server provides no container runtime). Agents act only through bounded tools; DuckDB runs in memory with external access disabled and configuration locked; the evaluator runs in a separate process and is the only component given the private evaluation directory.
3. The 8 GiB per-run memory cap is measured (peak RSS) rather than enforced.
4. Monetary cost is not available for the CRC server (no per-run tariff); GPU-seconds (1 x RTX PRO 6000 server wall time) and active seconds are reported instead.
5. Pilot limits are a calibration budget (300k tokens, 48 calls, 40 tool calls, 20 minutes). Frozen limits are set by the prespecified p90 rule in adm/power.py; the protocol text's 30k-token budget is reported alongside.
6. The AI4I identifier column is UDI in the archive (the protocol says UID); it is mapped to uid and excluded.
7. Repair cycles are counted as materialize_features calls issued after a failure verdict (gate failure or execution error).
8. Workers in the three-agent team cannot submit or abstain; those are coordinator decisions (Section 9.4 responsibilities).
9. One-hot encoding groups categories beyond 64 levels (max_categories) to protect memory if an identifier is used as a predictor.
10. Fitted model pickles are deleted after evaluation except for a 2% deterministic sample retained for E6 replay; graphs, choices, provenance and test predictions are kept for every submission.
11. Pickled models and hidden data are regenerated deterministically in each session and verified against recorded content digests.

Resolved serving stack: vLLM 0.33.0 on 1 x NVIDIA RTX PRO 6000 Blackwell (96 GB).
- Backbone A: Qwen/Qwen3.8-27B @ 37561816e66b5b9153b1b64c10968c18c1e6f4a0 (base Qwen/Qwen3.8-27B), dtype bfloat16, launch variant 'default', structured output via response_format.
- Backbone B: google/gemma-4-31B-it @ 842da3794eaa0b77d5f08bae87a17459d91ff475 (base google/gemma-4-31B-it), dtype bfloat16, launch variant 'default', structured output via response_format.
