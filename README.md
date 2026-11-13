# Protocol freeze: Autonomous and Verifiable Data Mining

Frozen protocol for the formal experiments (E1, E4, E5). Created 2026-11-12T08:16:43Z.

| Hash | Value |
|---|---|
| Protocol | `22d4f2fa1dab5138402e649306a7cefc1c7ef5ad31d50b35f607785c6f7740f1` |
| Code | `c8cdef91e85a6f2a09719d22bc3cdabcea0222dce7d1c0eb199cf59773ae3fba` |
| Configuration | `5cfa0a57560cee1a0d4b6111a5b5dc3ee76d23eb22faf2567260b6b1d4ede492` |

## Contents

- `freeze/manifests/freeze.json`: the freeze record, with the primary hypothesis, the secondary Holm family, the prespecified tier, sensitivity and descriptive analyses, the frozen configuration and the model lock.
- `freeze/manifests/`: dataset, split, canonical-data and task-instance manifests; the Tier-2 calibration records.
- `freeze/configs/`: the study configuration and the model lock (model repositories and revisions).
- `freeze/outputs/tier2_solvability_formal.json`: oracle solvability check of the formal Tier-2 instances (324/324).
- `code/adm_code/`: the frozen package and tests (the input to the code hash).
- `driver/`: the session notebooks and run script used for the formal experiments.
- `plan/main-plan-v2.1.md`: the study plan.
- `analysis/`: analysis scripts for the prespecified outcomes.

## Verify

```
python3 verify_freeze.py
```

This recomputes the code, configuration, protocol and manifest hashes from the files here and compares them with `freeze.json`. It needs only the Python standard library.
