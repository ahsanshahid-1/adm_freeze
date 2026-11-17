# Autonomous and Verifiable Data Mining: frozen protocol, code, results, and paper

Frozen protocol for the formal experiments (E1, E4, E5). Created 2026-11-12T08:16:43Z.

Registered on OSF: https://osf.io/bn6va (embargoed). The registered archive `adm_freeze_20261112.tgz` (SHA-256 `305cba70a80363d9be59295f1a1039499c41a54c21ef18d3ef8f2a854093877a`) is `git archive` of tag `freeze-20261112`.

| Hash | Value |
|---|---|
| Protocol | `22d4f2fa1dab5138402e649306a7cefc1c7ef5ad31d50b35f607785c6f7740f1` |
| Code | `c8cdef91e85a6f2a09719d22bc3cdabcea0222dce7d1c0eb199cf59773ae3fba` |
| Configuration | `5cfa0a57560cee1a0d4b6111a5b5dc3ee76d23eb22faf2567260b6b1d4ede492` |

The frozen files (`freeze/`, `code/`, `driver/`, `analysis/`, `plan/main-plan-v2.1.md`, `verify_freeze.py`) are
unchanged since tag `freeze-20261112`. Everything else was added after the formal runs finished.

## Contents

Frozen at tag `freeze-20261112`:
- `freeze/manifests/freeze.json`: the freeze record, with the primary hypothesis, the secondary Holm family, the prespecified tier, sensitivity and descriptive analyses, the frozen configuration and the model lock.
- `freeze/manifests/`: dataset, split, canonical-data and task-instance manifests; the Tier-2 calibration records.
- `freeze/configs/`: the study configuration and the model lock (model repositories and revisions).
- `freeze/outputs/tier2_solvability_formal.json`: oracle solvability check of the formal Tier-2 instances (324/324).
- `code/adm_code/`: the frozen package and tests (the input to the code hash).
- `driver/`: the session notebooks and run script used for the formal experiments.
- `plan/main-plan-v2.1.md`: the study plan.
- `analysis/`: analysis scripts for the prespecified outcomes, as frozen.

Added after the formal runs:
- `paper/`: the IEEE BigData 2026 workshop paper (LaTeX source, bibliography, figure, compiled PDF, Overleaf zip).
- `paper2/`: paper 2, an academic-structure version of the same paper (research questions, literature review, methodology with architecture diagram, formal model and algorithm, results by research question).
- `paper3/`: co-author revision of paper 2 (unchanged).
- `paper4/`: paper 3 with corrected acknowledgment and AI disclosure, OSF DOI, and verified method details.
- `paper5/`: paper 4 with the recommendations-report revisions and the post-hoc gate-acceptance audit (latest).
- `results/state/`: the run state of the study.
  - `outputs/runs/<experiment>/*.json`: one record per run, for the pilots (E0, E0B, E0S, E0SB, E0X, E0X2) and the formal experiments (E1 7,560; E4 540; E5 252).
  - `outputs/traces/`: the trusted trace of every run (gzip JSON lines).
  - `outputs/attempts/`: infrastructure-retry records (10 in E1).
  - `reports/final_report.md`: the report written by the frozen pipeline; `reports/` also has the pilot reports.
  - `outputs/e6_replay.json`, `outputs/e6_deviation.json`: the E6 replay audit and the one post-freeze deviation (below).
  - `outputs/references_*.json`, `outputs/evaluator_fixtures*.json`, `outputs/tier2_solvability*.json`, `outputs/figures/`, `outputs/stage_log.jsonl`, `outputs/gpu_accounting.jsonl`.
  - Submitted artifacts (`outputs/submissions/`, 758 MB of fitted models and predictions) are not included because of their size; they are kept in the server backup `adm_state_FORMAL_COMPLETE_20261114.tgz` (SHA-256 `4daccc85112c3f4446c75458bf9ab6b382ffecc4ea007963760909ab9907f5ac`).
- `results/analysis/`: outputs of the prespecified extra analyses on E1, the figure data, and the pilot numbers used in the paper.
- `analysis_postfreeze/`: every script used for numbers in the paper beyond the frozen report, including the post-hoc analysis that excludes the two quality-gate false-alarm blocks (labelled post hoc in the paper).
- `source/`: the full development source (`notebook_src/` with the package and tests, the notebook builder, the generated notebook) and the server tools (`tools/`).
- `plan/`: all versions of the study plan.
- `datasets/`: CSV exports of the canonical datasets with `MANIFEST.csv`. D1 to D4 are UCI datasets under CC BY 4.0 (citations in `freeze/manifests/datasets.json`); D5 and D6 are generated.
- `literature/`: literature review and the reference-verification records.

## Licence

Software is under the MIT licence (`LICENSE`). Study records, results, and generated data are under CC BY 4.0; the UCI
datasets keep their CC BY 4.0 licence and creators' credit. Paper manuscripts are not openly licensed. Details:
`LICENSE-DATA.md`.

## Post-freeze deviation

After all 8,352 formal runs were recorded, the frozen E6 replay audit raised a `TypeError` under pandas 3 on integer
columns. E6 was run with one line changed at run time (`analysis_postfreeze/run_e6_fixed.py`, recorded in
`results/state/outputs/e6_deviation.json`); the frozen package was not modified, and the frozen pipeline then
completed and passed its freeze verification. No run, outcome or analysis setting changed.

## Verify

```
python3 verify_freeze.py
```

This recomputes the code, configuration, protocol and manifest hashes from the files here and compares them with `freeze.json`. It needs only the Python standard library.
