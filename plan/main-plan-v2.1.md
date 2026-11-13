---
title: "Autonomous and Verifiable Data Mining Using Agentic AI"
subtitle: "A controlled, fully automated study of data quality, provenance, and analytical reliability"
version: "2.1"
prepared_on: "2026-10-30"
revised_on: "2026-11-11"
supersedes: "main-plan-v2.md v2.0 and main-plan.md v1.0 (both kept unchanged)"
status: "Research protocol and implementation specification; revised before any scored experiment"
duration_weeks: 24
human_subjects: false
human_evaluation: false
runtime_human_approval: false
primary_outcome: "Verified-completion rate on recoverable tasks"
---

# Research Plan

## Autonomous and Verifiable Data Mining Using Agentic AI

**Central question:** Can bounded agentic planning, executable data-quality checks, and provenance checks improve data-mining outcomes over simpler automation under matched resources, without human evaluation?

This document specifies what to investigate, which systems and datasets to evaluate, how to construct the experiments, how to grade them automatically, and how to reproduce and compare the results. All numerical experimental outcomes remain unknown.

**Non-negotiable constraint:** No participants, interviews, surveys, expert panels, new human annotations, human scoring, or human approval within experimental runs. Agents must complete, repair within a fixed budget, or stop automatically. No LLM-as-a-judge will determine research scores either.

**Implementation status:** This is a plan, not an implemented benchmark. Repository paths, command-line interfaces, schemas, and tests below are specifications to build. Exact model revisions, dependency locks, hardware identifiers, data hashes, and the final power assessment must be recorded before the protocol is frozen. They must not be invented or left unresolved in a scored run.

### Revision notes (v2.1, November 11, 2026)

Version 2.1 was made before the protocol freeze, after the v2.0 pilot (E0, conditions C0 and C6) gave 46-48 of 48 verified runs for every system, including the fixed workflow F, with near-identical predictive skill. Every core defect C1-C6 is declared in the contract or catalog together with its remedy, so a workflow written from the declared specification (F) solves all of them. Changes:

| Section | v2.0 | v2.1 | Reason |
|---|---|---|---|
| 7.6 (new) | Core conditions only | Tier 2: three recoverable defects outside the declared specification (X1-X3), each at three graded levels | Make the quality and provenance checks testable on defects that a declared-specification pipeline does not handle. Related work builds difficulty the same way: identifiers formatted differently across sources, duplicated and inconsistent data [R16]. |
| 11.1 | F handles declared defects | F is frozen as the v2.0 declared-specification workflow; it does not handle Tier 2 by design | §11.1 limits F to rules written from the declared data-format specification. A strong deterministic baseline remains a legitimate comparator [R17]. |
| 12 (E0S, E0SB, E0X) | Pilot on C0 and C6 | Supplementary pilots on C1-C5 (backbone A) and C0-C6 (backbone B, replication systems); a Tier-2 calibration pilot | Measure the ceiling on every core condition and calibrate Tier-2 severity before freeze. |
| 12 (calibration rule) | none | For each Tier-2 defect, freeze the level whose pooled S0+M0 verified-completion rate on development tasks is closest to 0.5 (ties to the lower level) | Pass rates near 0.5 are the most informative; fixed difficulty produces ceiling and floor effects [R18]. |
| 12 (solvability) | evaluator fixtures | Plus an oracle solver checked on every Tier-2 instance before agents run | Each task is verified to be solvable [R19, items II.7-II.8]. |
| 13.2 | 30,000-token budget in text; implementation used a p90 rule | Frozen limits follow the prespecified pilot rule max(protocol-text limit, ceil(1.25 x p95 of pilot usage)), capped at the pilot limit | The v2.0 pilot's median agentic run used about 128,000 tokens; a 30,000-token cap would end almost every run on budget rather than on data handling. |
| 15 | Single analysis | Tier 1 and Tier 2 reported separately; the Tier-2 minus Tier-1 contrast of the Q and P effects is a prespecified secondary analysis | Controlled 2026 studies report that multi-agent structure rarely beats a single agent at matched cost [R20, R21]; the informative question here is when checks help. |
| 21.2 | | New threats: Tier 2 is outside F's specification by construction; Tier-2 operations are documented to every system | Disclose the design property. |

**Amendment (November 11, 2026, before freeze): X1 replaced by X4.** All three first Tier-2 defects (X1-X3) are detected by quality checks (`key_uniqueness`, `record_coverage`, `value_ranges`); none is detected by provenance checks, which verify authority, content hashes and lineage. The secondary P main effect and Q x P interaction would therefore have no Tier-2 target. X1 is also uninformative for calibration: the baseline agents (S0, M0) verified every X1 run at every level in E0X. X1 is dropped from the design (its E0X runs are kept as a recorded pilot) and replaced by X4, a provenance-type defect (Section 7.6). Because documenting X4's repair adds one load policy to the shared tool documentation, all Tier-2 calibration for the frozen design is repeated under the final code (E0X2, repetitions 1 and 2), and E0SB is repeated in full under one code version. The provenance gate additionally compares the content hash of every loaded shard with the authority record; in Tier 1 declared and actual hashes always agree, so Tier-1 behaviour is unchanged.

**Pre-freeze decisions (November 11, 2026), made after E0X2 and before the freeze:**

1. *Frozen Tier-2 levels.* The prespecified rule on E0X2 (repetitions 1-2, 48 S0+M0 runs per level) selects X2b (S0+M0 verified-completion rate 0.75), X3a (0.71) and X4b (0.08). The levels are accepted as selected and are not re-tuned. The 0.5 target was not reachable within the prespecified levels: X2 and X3 baselines were 0.71-0.83 at every level, and X4 baselines were 0.02-0.08 at every level. X4 is therefore reported as a near-binary test of whether a system acts on provenance evidence; its severity does not materially change difficulty.
2. *Primary analysis.* H1 (MQP - M0, backbone A) is estimated on all recoverable tasks of the frozen design, pooling Tier 1 (C0-C6) and the three frozen Tier-2 conditions. This definition is fixed after the calibration pilots were inspected; to make that visible, the following are prespecified secondary analyses (not Holm-adjusted): every primary and Holm-family contrast on Tier 1 only and on Tier 2 only; the Tier-2 minus Tier-1 difference of each contrast (paired family-repetition blocks, block bootstrap); and sensitivity analyses excluding X4 (Tier 2 without X4, and all recoverable tasks without X4).
3. *Frozen limits.* The prespecified limit rule (Section 13.2) is applied to the backbone-A pilot runs whose conditions belong to the frozen design (E0, E0S and E0X2 runs on C0-C6, X2b, X3a, X4b), not to E0 alone, so that the limits reflect the formal design's workload. The cap at the pilot limit is unchanged.
4. *E0SB rerun.* 28 of 504 E0SB runs crashed on a pipeline bug (an invalid load policy passed to `profile_data` raised an exception instead of returning a tool error; backbone B only, 0 of 3,435 backbone-A pilot runs affected). The bug was fixed, and E0SB was rerun in full under the final code rather than rerunning only the crashed runs, so that the experiment uses one code version and no run is selected by its outcome. The earlier 504 runs are archived and reported.
5. *Formal design.* E1 and E4 include the three frozen Tier-2 conditions; E5 (negative controls) and the optional E7 are unchanged. Formal runs: E1 7,560, E4 540, E5 252, total 8,352 at three repetitions.

**Pre-freeze decisions (November 12, 2026, after external review of the draft and before the freeze; no evaluation-task run exists):**

6. *Repetitions.* Three repetitions (the smallest allocation the protocol allows); E7 and any reasoning-mode arm are not run. Because three repetition blocks per family give unstable bootstrap intervals, the sensitivity analyses in item 9 are prespecified.
7. *MQP - F.* F abstains on every Tier-2 instance by construction, so the Holm-family MQP - F is estimated on Tier-1 conditions only; MQP - F over all tiers is reported as exploratory.
8. *Secondary outcome.* Use of the content-verifying load policy (`authoritative_verified`) on X4 when it is available but not enforced, per system, from trusted traces; its use on Tier 1 is reported as a false-alarm measure. Not Holm-adjusted.
9. *Sensitivity analyses of the primary estimate.* (a) Mixed-effects logistic regression of V on system with random intercepts for task and for family-repetition block; (b) the block bootstrap with small-sample variance inflation n/(n-1); (c) per-family estimates alongside leave-one-family-out. Descriptive: terminal state and tool-call composition of budget-exhausted runs by system and tier.
10. *Freeze-time solvability.* The oracle solver must reproduce the hidden reference on every formal Tier-2 instance before the freeze is written (ABC II.7-II.8 on the evaluation portfolio).

The v2.0 revision notes follow unchanged.

### Revision notes (v2.0, November 10, 2026)

Version 2.0 was made before any scored run and before the protocol freeze. The only E0 pilot executed under v1.0 used a pipeline with a known serialization bug and is discarded; the pilot is rerun under v2.0. Changes:

| Section | v1.0 | v2.0 | Reason |
|---|---|---|---|
| 9.1, 18.1 | A: `Qwen/Qwen3-Coder-30B-A3B-Instruct` (July 2025); B: `Qwen/Qwen2.5-Coder-14B-Instruct` (November 2024) | A: `Qwen/Qwen3.8-27B` [R7]; B: `google/gemma-4-31B-it` [R8] | Execution moved to one 96 GB GPU (Section 20.1), so newer models fit in BF16. B now comes from a second vendor, so RQ7 tests limited cross-vendor robustness. A and B are both dense and of similar size (27.8B and 31.3B parameters). |
| 9.2, 18.1 | Generation settings without a reasoning-mode rule | Reasoning ("thinking") mode disabled for both backbones | Both models are reasoning-capable and default or optionally think before answering. Actions are schema-constrained JSON within a 1,024-token output limit. |
| 12 (E0) | No ceiling rule | Prespecified ceiling check before freeze | The v1.0 pilot already showed 100% verified completion for F and SQP on development tasks. |
| 20.1 | Planning candidate: one 80 GiB-class accelerator | Actual server recorded | Hardware identifiers must be recorded before freeze. |
| 21.2 | Threat: both models from one provider family | Threat: two vendors only | Follows from the backbone change. |

Open item not changed by this revision: Sections 13.2 and 18.1 state a 30,000-token aggregate budget, while the implementation freezes limits from the pilot by a prespecified p90 rule (the v1.0 pilot proposed 249,000 tokens). Decide and record which applies before the freeze.

## Contents

1. [Research overview and scope](#1-research-overview-and-scope)
2. [Research questions and hypotheses](#2-research-questions-and-hypotheses)
3. [Study design and experimental units](#3-study-design-and-experimental-units)
4. [Datasets and target definitions](#4-datasets-and-target-definitions)
5. [Synthetic data generation](#5-synthetic-data-generation)
6. [Task construction and contracts](#6-task-construction-and-contracts)
7. [Controlled data defects](#7-controlled-data-defects)
8. [Splits, preprocessing, and leakage prevention](#8-splits-preprocessing-and-leakage-prevention)
9. [Agent models and architecture](#9-agent-models-and-architecture)
10. [Downstream data-mining models](#10-downstream-data-mining-models)
11. [Baselines and architecture ablations](#11-baselines-and-architecture-ablations)
12. [Experiments to conduct](#12-experiments-to-conduct)
13. [Tools, execution limits, and recovery](#13-tools-execution-limits-and-recovery)
14. [Automated evaluation and metrics](#14-automated-evaluation-and-metrics)
15. [Statistical analysis and decision rules](#15-statistical-analysis-and-decision-rules)
16. [Overall research workflow](#16-overall-research-workflow)
17. [Repository and reproducibility specification](#17-repository-and-reproducibility-specification)
18. [Configuration and artifact schemas](#18-configuration-and-artifact-schemas)
19. [Timeline and milestones](#19-timeline-and-milestones)
20. [Resources and budget](#20-resources-and-budget)
21. [No-human-subjects protocol and validity risks](#21-no-human-subjects-protocol-and-validity-risks)
22. [Reporting and deliverables](#22-reporting-and-deliverables)
23. [Protocol-freeze and completion checklists](#23-protocol-freeze-and-completion-checklists)
24. [References](#24-references)

---

## 1. Research overview and scope

### 1.1 Aim

Design, implement, and evaluate an autonomous data-mining system that manages imperfect structured data and produces independently verifiable analytical artifacts.

The study investigates three mechanisms: agentic planning, executable data-quality gates, and active provenance gates. It does not assume that multiple agents are better than one agent or that agents are better than deterministic software.

### 1.2 Motivation and working research gap

DSBench evaluates agents on data-analysis and modeling tasks, establishing an existing task-based research context [R1]. DS-STAR already combines iterative planning with an LLM-based verification stage [R2]. Therefore, neither agentic data science nor verification should be presented as entirely new.

The proposed contribution is a controlled separation of:

- Single-agent versus multi-agent coordination.
- Executable quality checks versus active provenance checks.
- Verified correctness versus mere execution success.
- Reliability gains versus computational cost.

The **working gap** is limited controlled evidence about these mechanisms under the same tasks, tool capabilities, and total resource budgets. Refine that statement through the literature review; do not claim that no related work exists.

### 1.3 Objectives

1. Construct a reproducible, non-personal benchmark of classification and regression workflows with controlled data defects.
2. Implement one fixed workflow, two single-agent configurations, and four multi-agent configurations.
3. Implement an independent, deterministic evaluator with hidden reference information.
4. Measure correctness, predictive quality, repair behavior, abstention, and resource consumption.
5. Isolate the contributions of quality gates, provenance gates, and coordination.
6. Publish code, specifications, manifests, and evidence sufficient to rerun the study.

### 1.4 Scope

| Included | Excluded from the main study |
|---|---|
| CSV/Parquet files, relational tables, SQL, and machine-readable metadata | Image, audio, and unrestricted document mining |
| Classification and regression | Clustering, association-rule mining, and causal discovery |
| Source discovery, joins, units, versions, preprocessing, and modeling | Live production systems or autonomous database administration |
| Public non-personal data and newly generated synthetic data | Human participants, demographic datasets, identifiable records |
| Bounded tool use and automated recovery | Unrestricted shell access, internet exploration, or human escalation |
| Programmatic grading of executable artifacts | Human judgments or LLM grading of explanation quality |

The exclusions keep the project feasible and make correctness testable. They also limit the conclusions: this is not a benchmark of unrestricted autonomous data science.

### 1.5 Research success criterion

A successful project delivers a valid benchmark and defensible comparisons, including negative or inconclusive results. It does not require the proposed architecture to outperform its baselines.

---

## 2. Research questions and hypotheses

| ID | Research question | Hypothesis or prespecified analysis | Principal comparison |
|---|---|---|---|
| RQ1 | Do executable quality and provenance gates improve end-to-end correctness? | H1: MQP has higher verified-completion rate than M0 on recoverable tasks. | MQP vs M0 |
| RQ2 | What do quality and provenance contribute separately and together? | H2: Each gate changes the failure categories it directly checks; estimate both main effects and their interaction without assuming positive synergy. | M0, MQ, MP, MQP |
| RQ3 | Does multi-agent coordination add value under equal total resources? | H3: MQP and SQP differ in correctness, predictive quality, or cost; no directional advantage is assumed. | MQP vs SQP; M0 vs S0 |
| RQ4 | Does agentic planning outperform strong conventional automation? | H4: MQP and F differ in verified completion or predictive quality; report whether any gains justify extra resources. | MQP vs F |
| RQ5 | How do defect severity and resource limits affect reliability? | Estimate robustness curves and cost per verified completion; additional budget experiments are optional and separately labeled. | All systems across C0–C6 |
| RQ6 | Can systems stop appropriately when a contract cannot be satisfied? | Measure correct machine-readable refusal and false submission on deliberately unrecoverable tasks. | All systems on the negative-control suite |
| RQ7 | Are the main architecture findings stable with another language-model backbone? | Repeat selected comparisons using a second named model; interpret as limited model robustness, not universal generalization. | M0, SQP, MQP with backbone B |

**Primary confirmatory comparison:** H1, MQP versus M0, using the primary backbone and all recoverable core tasks.

**Secondary comparisons:** Gate main effects, gate interaction, MQP versus SQP, and MQP versus F. Severity, individual failure categories, and second-backbone findings are secondary or exploratory as specified before execution.

The architecture codes are defined in Section 11.

---

## 3. Study design and experimental units

### 3.1 Approach

Use design-science research for the artifact and paired controlled experiments for its evaluation.

The design has six dataset families, six task templates, seven defect conditions, three paired repetitions, and seven systems. Three repetitions are an initial allocation, not evidence of adequate statistical power.

### 3.2 Experimental units

- **Dataset family:** One of four public datasets or two synthetic generators.
- **Base task:** A dataset family combined with one genuinely different workflow template.
- **Condition:** Clean data or one of six corruption/severity settings.
- **Paired repetition:** A fixed split, corruption realization, model seed, and agent seed shared across systems.
- **Run:** One system attempting one task-condition-repetition combination.

There are 36 base tasks, but not 36 independent source datasets. Conditions and repetitions of the same task must not be treated as independent new datasets.

### 3.3 Variables and controls

| Category | Variables |
|---|---|
| Main interventions | Architecture; quality gates on/off; provenance gates on/off |
| Stress factors | Defect family and severity |
| Replication factor | Language-model backbone |
| Primary outcome | Externally verified completion, binary per recoverable run |
| Secondary outcomes | Predictive scores, correct repairs, false submissions, abstention, resource use |
| Matched controls | Task contract, raw inputs, available metadata, tool implementations, candidate models, seeds, and total resource caps |

Run order is randomized within a paired block. Reset task state and memory before every run. No configuration may learn from another configuration's attempt or retain discoveries across benchmark tasks.

### 3.4 What the study estimates

The primary estimand is the difference in equally weighted verified-completion rates across the prespecified benchmark portfolio and its randomized repetitions.

Inference is conditional on these datasets, task constructions, and defect generators. Do not interpret a narrow benchmark confidence interval as proof of reliability in arbitrary enterprise environments.

---

## 4. Datasets and target definitions

### 4.1 Dataset portfolio

| ID | Dataset | Size | Primary task and target | Important restrictions |
|---|---|---:|---|---|
| D1 | UCI AI4I 2020 Predictive Maintenance, repository ID 601 [R3] | 10,000 rows | Binary classification: `Machine failure` | Exclude failure-mode targets and identifiers from predictors. Preserve original order for temporal splitting. |
| D2 | UCI Steel Plates Faults, repository ID 198 [R4] | 1,941 rows | Seven-class defect classification | Decode the seven target indicators into one label; never expose target indicators as predictors. |
| D3 | UCI Concrete Compressive Strength, repository ID 165 [R5] | 1,030 rows | Regression: compressive strength | Eight source predictors; group related mixture records before splitting. |
| D4 | UCI Energy Efficiency, repository ID 242 [R6] | 768 rows | Regression: heating load, `Y1` | Exclude cooling load `Y2`; group related base building geometries. |
| D5 | Synthetic relational machinery, `SYN-MACHINE-v1` | 10,000 observations; 500 machines | Binary classification: generated failure outcome | Split by machine; no real operators or organizations. |
| D6 | Synthetic relational process, `SYN-PROCESS-v1` | 9,000 observations; 300 batches | Regression: generated process output | Split by batch; no real individuals or facilities. |

AI4I is synthetic; Energy Efficiency describes simulated building configurations. The steel and concrete datasets concern physical objects and materials. The UCI pages supply dataset descriptions and CC BY 4.0 licensing information; preserve their attribution [R3–R6].

### 4.2 Target and schema safeguards

**AI4I:** Use the six documented input features. Exclude `TWF`, `HDF`, `PWF`, `OSF`, and `RNF`, as well as `UID` and `Product ID`, from the predictive feature set. The failure-mode columns describe constituent outcomes, not independent prospective predictors [R3]. The task is label prediction from the supplied measurements, not a validated advance-warning or causal maintenance system.

**Steel:** Assert that each original row has exactly one active target indicator. Preserve the publisher's label spellings through an explicit mapping file. An unexpected label encoding is a benchmark-preparation error, not something to fix manually after seeing agent performance.

**Concrete:** Preserve physical units. Keep all records with the same seven-ingredient composition in one partition, including observations at different curing ages. Verify the exact normalized column mapping during import [R5].

**Energy:** Predict `Y1` only. Treat `Y2` as an excluded target. Use the geometry attributes corresponding to `X1`–`X5` to construct grouping keys, subject to a deterministic import assertion against the documented geometry structure [R6].

### 4.3 Acquisition and provenance

For each public source, save the original archive, retrieval date, source identifier, license, schema, citation, and SHA-256 checksum. Store canonical column mappings separately from the raw archive.

Never modify raw source files in place. Preserve a reference version before injecting defects. The public reference is a baseline for controlled changes, not proof that every original observation is error-free.

Do not collect extra personal information, join these datasets to people, or replace them with demographic or customer datasets.

---

## 5. Synthetic data generation

These are proposed benchmark generators, not claims about real industrial physics. Their exact implementation, floating-point behavior, and output checksums must be frozen.

### 5.1 Random-number policy

Use NumPy `Generator(PCG64(seed))`. Derive independent substream seeds as the first eight bytes of SHA-256 over a UTF-8 string:

```text
protocol_version | master_seed | namespace | family | task | repetition | component
```

Interpret the bytes as an unsigned big-endian integer. Do not use Python's process-dependent built-in `hash()`.

Use master seed `20261030`. Separate namespaces for `development`, `evaluation`, `corruption`, `split`, `estimator`, and `agent`. Publish the seed derivation function and test vectors.

### 5.2 D5: synthetic machinery classification

Generate 500 machines and 20 observations per machine.

For each machine `m`, draw six latent effects `b_mj ~ Normal(0, 1)` and a machine category uniformly from `{A, B, C}`. For observation `i` and feature `j`:

```text
z_mij = 0.4 * b_mj + sqrt(0.84) * epsilon_mij
epsilon_mij ~ Normal(0, 1)
eta_mi = -2.5 + 0.9*z_mi1 + 0.7*z_mi2
         + 0.5*z_mi1*z_mi3 + 0.6*I(category_m == C)
p_mi = 1 / (1 + exp(-eta_mi))
y_mi ~ Bernoulli(p_mi)
```

Use six dimensionless sensor variables and the observed category as predictors. Store metadata and observations in separate tables. Latent effects and generating probabilities are evaluator-only diagnostics, not predictors.

Record the realized class balance; do not regenerate the dataset until a favorable balance appears. Abort preparation if a prespecified feasibility assertion, such as adequate positive labels for the split/CV design, fails; document any protocol revision before main testing.

### 5.3 D6: synthetic process regression

Generate 300 batches and 30 observations per batch. Draw `u_b ~ Normal(0, 1)`. For eight predictor variables:

```text
x_bij = Uniform(-1, 1) + 0.2*u_b
y_bi = 50 + 10*x_bi1 - 7*x_bi2 + 5*x_bi3*x_bi4
       + 4*sin(pi*x_bi5) + 2*u_b + epsilon_bi
epsilon_bi ~ Normal(0, 1)
```

Store batch metadata and observations separately. Batch identifiers and latent effects are not predictors. The residual noise prevents a claim that a perfectly implemented workflow must achieve perfect predictions.

### 5.4 Development separation

Create 12 development tasks: six templates for each synthetic family, using smaller, separately generated instances and the `development` namespace. Development and evaluation must share no observation IDs or generated values through cached artifacts.

Evaluation uses the frozen full-size generators. Developer access to generator code does not entitle any competing system to hidden labels, the corruption ledger, or reference feature tables.

---

## 6. Task construction and contracts

### 6.1 Six task templates

Apply each template to every dataset family, yielding `6 × 6 = 36` base tasks.

| ID | Template | Required workflow | Machine-checkable target |
|---|---|---|---|
| T1 | Single-source modeling | Locate the correct feature source, respect predictor exclusions, prepare data, and fit a model. | Correct source, feature schema, record identities, and executable prediction pipeline. |
| T2 | Two-table reconstruction | Split predictors into two vertical tables and join by declared canonical key. | One output record per expected observation; no lost or multiplied records. |
| T3 | Three-table integration | Join observations, a feature block, and metadata through declared relationships. | Correct join path and observation-level granularity. |
| T4 | Unit/representation harmonization | Convert shard-level representations into canonical feature units using supplied mappings. | Correct normalized values within tolerance. |
| T5 | Version-aware analysis | Resolve available snapshots against an authoritative as-of catalog. | Every selected source matches the required version and hash. |
| T6 | Aggregate-feature construction | Build required summaries from one-to-many child measurements before modeling. | Correct counts and aggregate values without target or cross-partition leakage. |

Public datasets transformed into relational tables remain **research-generated representations**. Do not describe them as original enterprise schemas supplied by UCI.

### 6.2 Deterministic construction rules

Assign a canonical observation ID before splitting or corruption. Preserve it through every generated representation. IDs are join keys, never predictive features.

For T2, divide the ordered permitted predictor list into two nearly equal blocks. For T3, divide it into three blocks connected through documented keys; the metadata relation may be a synthetic structural representation rather than a native domain relationship.

For T4, generate documented invertible affine representations, `stored = a*canonical + b`, using a fixed mapping table. Use real unit names only where physically justified; otherwise label the mapping as a synthetic numeric representation.

For T5, provide current and earlier candidate snapshots with a catalog stating the required as-of version. Generate earlier-feature perturbations independently of labels. The clean task can contain legitimate older snapshots; the requirement is to choose correctly, not to assume every available source is current.

For T6, replace two selected numeric predictors with five child readings per observation, derived from those predictors with seeded feature-only noise. Require the mean, population standard deviation, and count for each reading series. Generate the child data without consulting target labels. Store independently computed reference aggregates.

Every template has a metadata catalog and 20 logical shards per partition. A shard is a packaging unit, not a distinct dataset or independent statistical observation.

### 6.3 Task contract

Every system receives the same machine-readable contract and a fixed natural-language rendering. It specifies the objective, target, permitted predictors, required source versions, keys, units, aggregation rules, prediction scope, acceptable missing-value handling, output schema, and budget.

The contract must contain enough information for a correct solution. Do not require an agent to guess undocumented relationships or recover genuinely unavailable values exactly.

Do not reveal corrupted locations, hidden labels, reference outputs, or defect counts beyond the general task information available to all systems.

### 6.4 Semantic equivalence

Grade requirements, not a single preferred SQL query or sequence of tool calls. Equivalent joins, valid operation orders, and different permitted candidate models can all pass.

Where a unique answer exists, compare canonicalized values. Where it does not, check explicit predicates and downstream performance rather than exact implementation identity.

---

## 7. Controlled data defects

### 7.1 Core conditions

| ID | Family | Severity | Injection rule |
|---|---|---:|---|
| C0 | Clean reference | 0% | No injected corruption. Required task operations still apply. |
| C1 | Cell-level | 5% | Affect 5% of eligible numeric feature cells. |
| C2 | Cell-level | 20% | Affect 20% of eligible numeric feature cells. |
| C3 | Row/key/integration | 5% | Affect 5% of eligible original observation keys. |
| C4 | Row/key/integration | 20% | Affect 20% of eligible original observation keys. |
| C5 | Semantic/version | 5% | Affect 1 of the 20 logical shards in each partition. |
| C6 | Semantic/version | 20% | Affect 4 of the 20 logical shards in each partition. |

Cells, observation keys, and shards have different denominators. Report both the declared severity and the realized affected-record proportion; do not compare the percentages as identical amounts of damage.

### 7.2 Exact injection rules

**Cell conditions:** Sample without replacement from numeric feature cells, excluding labels, IDs, metadata, and already-invalid source values. Set half to missing; encode the remainder reversibly as strings such as `value:<original_numeric_literal>`. Assign an odd remaining cell to missingness. The parsing grammar is part of the common supported data format. Missingness is generated independently of the target in the core experiment.

**Row/key conditions:** Sample canonical observation keys without replacement. For half, introduce an exact duplicate at the relevant observation or joined-table location. For the remainder, replace one join-key representation with an alias. Supply the same complete alias catalog to every system; it maps permitted aliases to canonical keys without identifying which records were altered. T1 applies the same integrity problems to its single modeling source.

**Semantic/version conditions:** Select shards without replacement. Alternate between a documented numeric representation change and a stale source candidate according to `(base_task_index + repetition_index + selected_shard_rank) mod 2`. A low-severity task contains one subtype; the complete balanced task portfolio covers both. High severity contains two shards of each subtype. Both the correct source and authoritative metadata remain available on recoverable tasks.

Stale candidates have the same local schema as current data but fail the authoritative version/hash requirement. A system must check authority rather than assume a convenient filename establishes freshness.

Calculate affected counts using `floor(rate*N + 0.5)` and save exact denominators. Use sorted canonical IDs before seeded sampling. Targets and train/validation/test membership are never corrupted.

### 7.3 Partition handling

Inject into training, validation, and test feature representations separately using distinct substreams. Hidden test corruption is applied by the evaluator, not shown during agent planning. The submitted workflow must handle the same defect family on unseen records.

Preprocessing parameters learned from data must not be fitted separately on hidden test features. Deterministic parsing, catalog resolution, and unit conversion may apply to new data without fitting.

### 7.4 Hidden corruption ledger

For every injected change, save the original canonical location, defect type, before/after values or hashes, severity denominator, source version, and seed. Store this ledger outside the agent environment.

Exact-repair scoring applies to reversible changes. Missing-value imputation is not scored as exact recovery of an unknowable original. Evaluate its permitted procedure, reconstruction error where useful, and predictive consequences separately.

### 7.5 Unrecoverable conditions

The negative-control suite in Section 12 deliberately removes information required by the contract. It is not mixed into the recoverable completion denominator. Correct behavior is a supported machine-readable refusal, not an invented answer.

### 7.6 Tier 2: recoverable defects outside the declared specification (v2.1)

Core conditions C0-C6 form **Tier 1**: each defect and its remedy is declared in the contract or catalog. **Tier 2** adds recoverable defects that the declared format specification does not describe. Each one violates a requirement the contract already states, is detectable by an existing quality-gate check or by inspecting the data, and is repairable with a general operation documented to every system, so the frozen graph still works on hidden test shards.

| ID | Defect | Levels (a / b / c) | Violates | Detectable by | General repair |
|---|---|---|---|---|---|
| ~~X1~~ | *Dropped (amendment above).* Near-duplicate records: identical in every field except the packaging column `_ingest_batch` | 5% / 10% / 20% of observation keys | One row per observation | `key_uniqueness` | `dedupe` mode `key` on observation-grain tables |
| X2 | Key-format variants outside the alias table (lower case, unpadded number, surrounding spaces) | 5% / 10% / 20% of observation keys | Record coverage; label matching | `record_coverage`, `label_match` | `normalize_key` (canonical upper-case `<PREFIX>-<six digits>`) |
| X3 | Shard stored in a documented catalog representation that `shard_representations` does not declare | 1 / 2 / 4 of 20 shards per partition | Contract `value_ranges` | `value_ranges` | `infer_representation` |
| X4 | Content drift: the primary authorised file's content for k shards no longer has the authorised SHA-256, while its catalog entry still declares the authorised hash; a replica with the authorised content exists | 1 / 2 / 4 of 20 shards per partition | Use the content authorised by the authority record (Section 6.3 contract rule) | Provenance content-hash check (`content_hash`) | load policy `authoritative_verified` (recompute content hashes; keep candidates that match the authority record) |

Rules:
- All Tier-2 instances carry `_ingest_batch` on observation-grain tables and publish `value_ranges` in the catalog, so their presence does not reveal which defect is present. Tier-1 instances are unchanged.
- X3 uses only (shard, column, representation) choices where the stored values are mostly outside the contract range, the canonical values are at least 99% inside it, and no other documented representation maps them inside. The repair is therefore unique.
- Every Tier-2 instance also carries a replica of the authorised content for each observation-grain table, so the replica's presence does not reveal X4. The replica's modification time is earlier than the primary's, so neither `latest_modified` nor `latest_snapshot` selects it; only content verification repairs X4. Drifted values are perturbed independently of labels and stay within the contract value ranges, so quality checks do not flag X4.
- Realized counts and denominators are recorded in the hidden ledger as for Tier 1.
- Before any agent run, the oracle solver (Section 12, E0X) must reproduce the hidden reference on every partition of every Tier-2 instance.

---

## 8. Splits, preprocessing, and leakage prevention

### 8.1 Split before corruption

Create partitions from the canonical source before duplicates, relational expansion, or defective aliases are generated. All derivatives of an original record stay in its partition.

| Dataset | Outer partition rule | Inner model-selection folds |
|---|---|---|
| D1 AI4I | Original-order 60% train, next 20% validation, final 20% test | Three forward-chaining folds inside training |
| D2 Steel | Approximately 60/20/20 stratified by class, grouping identical predictor rows | Three stratified group-aware folds |
| D3 Concrete | Approximately 60/20/20 by ingredient-composition group | Three group-aware folds |
| D4 Energy | Assign 7 of the 12 base-geometry groups to train, 2 to validation, 3 to test using the split seed | Three group-aware folds inside training |
| D5 Machinery | 60/20/20 by machine ID | Three stratified group-aware folds |
| D6 Process | 60/20/20 by batch ID | Three group-aware folds |

The Energy proportions intentionally differ from 60/20/20 to preserve whole groups. Assert the expected geometry grouping during preparation rather than assuming it silently.

AI4I's chronological split is fixed across repetitions. Other split randomization, defect injection, estimator randomness, and agent sampling are recorded separately. Repetitions must not be described as three independent future time periods.

Persist the exact row and group IDs for every partition and fold. Verify class availability before freezing the benchmark. A failed feasibility assertion requires a documented preparation-stage correction, not selective dropping after results are known.

### 8.2 Data access boundary

Agents can inspect permitted training data and task metadata. Validation labels remain behind a scoring tool; hidden test inputs, labels, and scores are inaccessible until the submitted workflow is frozen.

An approved `fit_evaluate` call returns training-fold and validation metrics for one permitted candidate. Cap the total at six distinct pipeline-candidate evaluations per run, including changed preprocessing proposals. Failed training attempts consume an evaluation slot. Repeated identical calls return a cached result and do not create additional search opportunities.

After model selection, a trusted service refits the frozen choice on training plus validation data. The test partition remains unused. Record the difference between search-stage fit permissions and final-refit permissions in provenance.

At hidden evaluation, execute only the frozen declarative preparation and prediction workflow: no new LLM calls, adaptive search, or model refitting is permitted. Deterministic rules may resolve test-source metadata, but learned preprocessing statistics must remain fixed. Store the fitted estimator, preprocessing state, declarative transform graph, and their hashes as one submission bundle.

### 8.3 Preprocessing policy

Use a common candidate preprocessing implementation to avoid hiding extra tuning capacity inside one system:

- Numeric features: supported parsing, canonical representation conversion, then training-fitted median imputation. An entirely missing training column uses a documented constant fallback of zero.
- Categorical features: training-fitted most-frequent imputation, followed by one-hot encoding with unknown categories ignored. An entirely missing training category uses an explicit `MISSING` token.
- Linear models: standardize numeric columns using training-fitted statistics.
- Tree models: do not standardize numeric columns.
- No target encoding, synthetic oversampling, feature selection search, or automatic target-derived features in the core study.

Use pipeline objects so that preprocessing is fitted within each CV training fold rather than on the full dataset. This implements the leakage-avoidance principles documented by scikit-learn [R9].

### 8.4 Deterministic versus learned transforms

Parsing an explicitly documented number format is not a learned transform. Estimating an imputation median or scaling mean is. The evaluator must distinguish these cases when checking fit-scope provenance.

Core tools enforce the same access isolation for every architecture. If a prohibited operation is impossible for all systems, report blocked attempts rather than claiming a treatment reduced actual leakage that the environment already prevented.

---

## 9. Agent models and architecture

### 9.1 Named language-model backbones

| Role | Model identifier | Architecture | Use |
|---|---|---|---|
| Backbone A | `Qwen/Qwen3.8-27B` | Dense hybrid-attention model from Alibaba's Qwen team; 27.8B BF16 parameters including a vision encoder; released August 2026; Apache 2.0 [R7] | All six agentic configurations in the main study |
| Backbone B | `google/gemma-4-31B-it` | Dense instruction-tuned model from Google DeepMind; 31.3B BF16 parameters including a vision encoder; released 2026; Apache 2.0 [R8] | Prespecified replication of M0, SQP, and MQP |

These are explicit reproducible candidates chosen as the newest dense models from their families that fit in BF16 on one 96 GB GPU; they are not a claim that they are the best models for this benchmark. Published benchmark scores for both are self-reported, mostly in reasoning mode with long contexts, and are not comparable across vendors or with this protocol's settings (Section 9.2). The replication uses two vendors, so it supports only limited cross-vendor robustness, not general model independence. Differences between A and B still cannot isolate any single cause because training data, post-training, and tokenizers differ.

Both checkpoints are vision-language models. Only text is used: serve them with the vision encoder disabled (vLLM `--language-model-only`), and record this in the model lock.

Resolve each repository to an immutable model revision and save tokenizer, configuration, chat-template, and weight-file hashes before execution. Use one fixed inference engine and BF16 weights for the main protocol. Do not switch silently to quantized weights if hardware is insufficient; revise and re-freeze the protocol first.

### 9.2 Generation settings

Starting settings to confirm on development tasks and then freeze:

```yaml
temperature: 0.2
top_p: 0.9
top_k: 40
max_context_tokens: 16384
max_output_tokens_per_call: 1024
max_model_calls_per_run: 48
response_format: schema_constrained_json
enable_thinking: false
```

Use the same settings for both backbones rather than each vendor's recommended settings. The primary contrast (H1) is always within one backbone, so shared settings cannot bias it, and they keep the replication comparable. Disable reasoning mode for both backbones through the chat template (`enable_thinking: false`): each model call must return one schema-constrained JSON action within the output limit. Report this as a design choice and a limitation, because published scores for these models mostly use reasoning mode. If a backbone fails under these settings on the development pilot (for example, frequent invalid actions), revise the settings before freeze and record the change.

Use a shared JSON action protocol rather than relying on different native function-call conventions. Structured JSON generation can be implemented with the chosen inference engine; vLLM documents structured-output support [R12]. Pin the actual parser/backend and test both models against the same schema.

Seeds are recorded, but do not promise bitwise identical GPU inference across different hardware or software versions. Retain outputs and execution traces as well as seeds.

### 9.3 Single-agent architecture

One agent receives the task contract, common tools, operational instructions, and the complete current task state. It plans, manages data, selects a mining model, and submits or abstains.

For SQP, quality and provenance checks are enforced at the same lifecycle stages as MQP. S0 receives ordinary execution errors but no added Q/P gate verdicts.

### 9.4 Multi-agent architecture

Use three role-specialized agents with the **same backbone**:

| Agent | Responsibility | Output |
|---|---|---|
| Coordinator | Build and revise the workflow, assign work, track budget, decide submission or abstention | Structured plan and routing decisions |
| Data-management agent | Discover sources, inspect schemas, resolve joins/units/versions, materialize valid features | Declarative transformation plan and prepared-data handles |
| Mining agent | Select permitted estimators, run bounded evaluation, choose the final model | Candidate IDs, metrics, and fitted-pipeline handle |

Execution is sequential. There is no parallelism advantage in the main architecture comparison. Agents share a structured blackboard containing contracts, artifact handles, tool observations, remaining budget, and enabled-gate feedback. Role-specific conversation histories are retained, but cross-task memory is prohibited.

All roles can access the same permitted tool schemas. Role specialization and coordination—not extra data or hidden tools—distinguish the multi-agent treatment. Count coordinator messages and hand-offs against the same total token budget.

### 9.5 Operational graph

```text
Task contract + permitted sources
                 |
                 v
       Coordinator / single agent
                 |
                 v
     Source discovery and profiling
                 |
                 v
    Data-management transformations
                 |
      [Q and/or P gate if enabled]
          | pass           | fail
          v                v
    Mining/model search  Bounded repair
          |                |
          +----------------+
                 |
      [Final enabled-gate checks]
          | pass           | unresolved
          v                v
     Freeze submission    Abstain
          |
          v
 Independent evaluator, hidden data
          |
          v
 Scores + artifacts + failure taxonomy
```

### 9.6 Separation of quality and provenance

**Quality gates (Q)** check local data properties: required types/columns, valid ranges declared by the contract, key uniqueness, join cardinality, canonical units, permitted missing-value handling, and required aggregate schemas.

**Provenance gates (P)** check dependencies: authoritative source versions/hashes, completeness of transformation lineage, fit-stage partition permissions, and whether the submitted pipeline references the artifacts actually produced.

The local schema can be valid while the selected source is stale. A lineage trace can be complete while its values are wrong. These are different checks, although some real-world failure categories overlap.

Represent sources and outputs as entities, transformations as activities, and software components as responsible agents, adapting W3C PROV concepts [R10]. Here, “agent” in the provenance model does not mean a human participant.

Trusted tool wrappers create append-only provenance records for **all** systems. The treatment is active checking and feedback, not whether the experimenter collects logs. Do not claim higher logging completeness simply because one system was instrumented more heavily.

---

## 10. Downstream data-mining models

Use the same six candidate configurations for each classification task and the same six for each regression task. These are deliberately bounded grids, not an unrestricted AutoML competition.

### 10.1 Classification candidates

| ID | Estimator | Fixed parameters |
|---|---|---|
| CL1 | Logistic regression | `C=0.1`, `solver=lbfgs`, `max_iter=2000`, no class weighting |
| CL2 | Logistic regression | As CL1, `C=1.0` |
| CL3 | Random forest classifier | `n_estimators=200`, `max_depth=None`, `min_samples_leaf=1`, `max_features=sqrt`, no class weighting |
| CL4 | Random forest classifier | As CL3, `min_samples_leaf=5` |
| CL5 | Histogram gradient boosting classifier | `learning_rate=0.1`, `max_iter=200`, `max_leaf_nodes=15`, `early_stopping=False` |
| CL6 | Histogram gradient boosting classifier | As CL5, `max_leaf_nodes=31` |

### 10.2 Regression candidates

| ID | Estimator | Fixed parameters |
|---|---|---|
| RG1 | Ridge regression | `alpha=1.0` |
| RG2 | Ridge regression | `alpha=10.0` |
| RG3 | Random forest regressor | `n_estimators=200`, `max_depth=None`, `min_samples_leaf=1`, `max_features=1.0` |
| RG4 | Random forest regressor | As RG3, `min_samples_leaf=5` |
| RG5 | Histogram gradient boosting regressor | `learning_rate=0.1`, `max_iter=200`, `max_leaf_nodes=15`, `early_stopping=False` |
| RG6 | Histogram gradient boosting regressor | As RG5, `max_leaf_nodes=31` |

Pin scikit-learn and explicitly serialize all remaining effective defaults. Use `n_jobs=1` where supported and fixed estimator seeds. Cap numerical-library threads consistently. A parameter that changes between library versions must not silently change the experiment.

### 10.3 Selection rules

For AI4I and synthetic binary classification, the selection objective is validation average precision. For Steel, it is validation macro-F1. For regression, minimize validation RMSE. Training-only CV metrics are diagnostic and available for bounded planning, but do not introduce a second undisclosed selection objective.

The fixed workflow evaluates all six candidates. Agents may evaluate fewer, but cannot exceed six. Tie-break scores within `1e-12` using lexicographic candidate ID. Binary class predictions use threshold 0.5; multiclass predictions use the highest probability with a fixed class-order tie-break. Do not tune thresholds in the core study.

### 10.4 Non-agent reference models

Evaluate a class-prior dummy classifier and training-mean dummy regressor using the correct canonical workflow. These are predictive-score reference points, not substitutes for the full F system.

Also run a **clean-data reference workflow** for each base task and repetition: `36 × 3 = 108` reference workflows, each using the same six-candidate search. This gives a no-injected-defect performance reference. It is not a mathematical upper bound, and agents never see its hidden outputs.

---

## 11. Baselines and architecture ablations

| Code | Planning architecture | Q gates | P gates | Purpose |
|---|---|---:|---:|---|
| F | Deterministic rule-based workflow | Yes | Yes | Strong non-agent baseline |
| S0 | Single agent | No | No | Ordinary tool-using agent baseline |
| M0 | Three-agent workflow | No | No | Coordination without added verification |
| MQ | Three-agent workflow | Yes | No | Quality-only ablation |
| MP | Three-agent workflow | No | Yes | Provenance-only ablation |
| SQP | Single agent | Yes | Yes | Verified single-agent baseline |
| MQP | Three-agent workflow | Yes | Yes | Full proposed system |

### 11.1 Fixed workflow F

Implement a generic contract-driven pipeline: resolve sources, traverse declared join relationships, normalize supported representations, apply supported duplicate/alias rules, construct required aggregates, run Q/P checks, evaluate all six candidates, refit the selected model, and submit.

Use the same tools and metadata as the agents. Rules may be written from development tasks and the declared data-format specification, not from hidden evaluation ledgers or individual test answers. No special case may branch on a held-out task ID.

F is intentionally strong. If documented contracts make deterministic automation sufficient, that is an important result rather than a reason to weaken the baseline.

### 11.2 Fairness rules

All configurations have the same permitted source access, metadata, candidate-model library, safety restrictions, and tool implementations. Q/P activation is the intended treatment difference.

Disabled Q/P gates mean no automatic gate verdict or repair guidance. They do not remove basic syntax checks, ordinary exceptions, or the agent's ability to inspect data and reason from raw tool output.

Any generic profiling tool available to one agent architecture is available to the others. Avoid unintentionally returning hidden gate verdicts through a nominally unverified profiling endpoint.

Record passive execution and lineage traces in every condition. Match total task budgets, not per-agent budgets. Time and tokens spent on verification and coordination count toward those budgets.

---

## 12. Experiments to conduct

### E0 — Development, evaluator testing, and pilot

**Purpose:** Establish implementation correctness, feasible limits, and initial variance/cost estimates before main testing.

Use the 12 separate development tasks, C0 and C6, two repetitions, and all seven configurations:

```text
12 development tasks × 2 conditions × 2 repetitions × 7 systems = 336 pilot runs
```

Before running agents, test the evaluator with deliberately correct and incorrect fixtures: wrong joins, duplicated predictions, wrong versions, target-derived predictors, invalid probabilities, and known valid alternative workflows.

**Supplementary pilots (v2.1, recorded separately):** E0S runs the 12 development tasks under C1-C5 with backbone A (2 repetitions, all systems; 840 runs). E0SB runs them under C0-C6 with backbone B for M0, SQP and MQP (2 repetitions; 504 runs) to check that the E4 replication has headroom.

**Tier-2 calibration pilot E0X (v2.1):** 12 development tasks x 9 Tier-2 conditions (X1-X3 at three levels) x 1 repetition x 7 systems = 756 runs, backbone A, pilot limits. Before agents run, Tier-2 evaluator fixtures must pass (oracle verified; declared-specification graph rejected) and the oracle solver must reproduce the hidden reference on all 108 instances. The prespecified rule freezes, for each defect, the level whose pooled S0+M0 verified-completion rate is closest to 0.5 (ties to the lower level). The chosen levels enter E1, E4 and E5 as Tier-2 conditions; the remaining levels are not used in scored experiments.

**Second Tier-2 calibration E0X2 (amendment):** X2, X3 and X4 at three levels each, repetitions 1 and 2, under the final code: 12 x 9 x 2 x 7 = 1,512 runs, backbone A, pilot limits, the same fixture and oracle pre-checks (216 instances) and the same prespecified rule. E0X2 alone determines the frozen Tier-2 levels; E0X (repetition 0, earlier code) is reported as a recorded pilot.

Freeze prompts, tools, limits, task generation, hypotheses, and analysis after the pilot. Pilot results are not part of confirmatory scores. Any additional pilot allocation must be recorded separately.

**Ceiling check (prespecified).** Before freeze, flag a ceiling warning if M0's pilot verified-completion rate with backbone A is at least 95%, or if any agentic system reaches 100%. A warning means the benchmark may be too easy to detect the planned 10-point effect: revise task difficulty (defect severity, conditions, or tasks) before freeze and record the change. Never substitute a weaker backbone to create headroom. Development tasks differ from the evaluation portfolio, so treat the check as a warning, not a measurement of evaluation difficulty.

### E1 — Main comparative experiment

**Questions:** RQ1, RQ3, and RQ4.

```text
36 tasks × 7 conditions × 3 paired repetitions × 7 systems = 5,292 runs
```

Use backbone A for all agentic systems. Every system attempts 756 recoverable runs. Primary output: paired MQP–M0 verified-completion difference. Also report all other systems, predictive metrics, cost, and failure types.

### E2 — Quality/provenance factorial ablation

**Question:** RQ2.

Reuse E1 results for M0, MQ, MP, and MQP. No additional runs are needed. Estimate Q and P main effects and their interaction. Relate failures to checks rather than attributing all improvements generically to “trustworthiness.”

### E3 — Corruption robustness and efficiency

**Question:** RQ5.

Reuse E1. Report C0–C6 separately, with family-specific results and cost/completion trade-offs. Separate semantic-unit and stale-version subtypes using the hidden injection ledger, with that breakdown labeled secondary.

Do not collapse cell percentages and shard percentages into one misleading continuous severity scale.

### E4 — Second-backbone replication

**Question:** RQ7.

Prespecify one task per dataset family, covering all six templates:

```text
D1-T5, D2-T2, D3-T4, D4-T6, D5-T3, D6-T1
```

Use backbone B for M0, SQP, and MQP on all seven conditions and the same three repetitions:

```text
6 tasks × 7 conditions × 3 repetitions × 3 systems = 378 additional runs
```

Use the matching E1 subset for the backbone-A comparison. Do not choose replication tasks after inspecting which tasks favor MQP.

### E5 — Autonomous refusal on unrecoverable tasks

**Question:** RQ6.

Use the same six selected base tasks. Generate two negative variants:

- **N1:** The contract requires a particular source version, but it is absent and no authorized equivalent is available.
- **N2:** Two authoritative records conflict on the required source/hash and no precedence rule resolves the conflict.

These are semantically unsatisfiable inputs, not malformed JSON rejected before any system runs. All systems receive the same available evidence.

```text
6 tasks × 2 negative conditions × 3 repetitions × 7 systems = 252 runs
```

Correct refusal requires no submitted predictions and a matching structured reason: `REQUIRED_SOURCE_MISSING` or `AMBIGUOUS_AUTHORITY`. Timeout or unexplained generic failure is not counted as correct refusal. Score false submission separately. Do not mix these results with recoverable-task VCR.

### E6 — Replay, invariance, and evaluator sensitivity

No additional agent planning is required. Replay frozen submissions and execute deterministic fixture tests.

Required checks include reordered rows/columns, equivalent numeric representations, duplicate-source handling, wrong-version substitution, one missing test prediction, and a changed artifact hash.

For checks that should preserve meaning, compare the canonical transformed test features and predictions within declared tolerance. Row order changes are evaluated with a frozen fitted estimator; do not incorrectly demand that retraining a stochastic estimator on reordered data be bitwise identical.

Ensure known-bad fixtures fail and valid alternatives pass. Keep these results separate from model capability scores.

### E7 — Optional budget sensitivity

Run only if selected before inspecting E1 outcomes and supported by resources. Use the six replication tasks, C0/C2/C6, two repetitions, and M0/SQP/MQP. Add half-budget and double-budget settings; the standard-budget points already exist in E1.

```text
6 tasks × 3 conditions × 2 repetitions × 3 systems × 2 extra budgets = 216 runs
```

Scale total tokens, tool calls, model calls, and wall-clock limits together. Keep the six-candidate modeling cap unchanged. Report the exact resource bundles; this is not an isolated effect of token budget alone.

### Run accounting

| Allocation | Agentic runs | Fixed-workflow runs | Total |
|---|---:|---:|---:|
| E1 main | 4,536 | 756 | 5,292 |
| E4 second backbone | 378 | 0 | 378 |
| E5 negative controls | 216 | 36 | 252 |
| **Required formal experiments** | **5,130** | **792** | **5,922** |
| E0 pilot, separate | 288 | 48 | 336 |
| **Formal + initial pilot** | **5,418** | **840** | **6,258** |
| E7 optional addition | 216 | 0 | 216 |
| *v2.1:* E1 with three frozen Tier-2 conditions added | +1,944 | +324 | +2,268 |
| *v2.1:* E4 with three Tier-2 conditions added | +162 | 0 | +162 |
| *v2.1:* supplementary and calibration pilots E0S, E0SB, E0X | 2,124 | 216 | 2,340 |
| *v2.1 amendment:* second calibration E0X2 | 1,296 | 216 | 1,512 |

E2 and E3 reuse E1. E6 adds replay/test computation, not agent attempts. Clean-data reference workflows and dummy models add modeling computation but are not counted as competing-system attempts.

The earlier 5,670-run allocation is preserved as E1 plus E4. This version adds 252 explicit refusal-control runs to evaluate autonomous stopping.

---

## 13. Tools, execution limits, and recovery

### 13.1 Tool interface

| Tool | Purpose | Important limit |
|---|---|---|
| `list_sources` | Enumerate permitted source handles and metadata | No arbitrary filesystem discovery |
| `inspect_schema` | Return names, types, keys, and declared units | No hidden evaluator tables |
| `profile_data` | Return bounded summaries and up to 20 sample rows | Same output policy for all systems |
| `query_data` | Execute permitted SQL against registered sources | No file/network escape or extension loading |
| `materialize_features` | Execute a validated declarative transform graph | Only approved join, parse, map, aggregate, and projection operations |
| `fit_evaluate` | Fit a permitted candidate and return CV/validation metrics | Six evaluations total |
| `quality_check` | Check the Q predicates | Active only in Q treatments |
| `provenance_check` | Check the P predicates | Active only in P treatments |
| `submit` | Freeze a workflow and selected candidate | One final submission |
| `abstain` | Stop with a structured reason | No human escalation |

Tool wrappers—not LLM statements—record actual source handles, dependencies, row counts, parameters, and hashes. If a pipeline can execute uninstrumented operations, completeness claims are not justified; the core study therefore uses a bounded transformation interface.

### 13.2 Resource limits

| Resource | Initial per-run limit |
|---|---:|
| Aggregate LLM input + output tokens, including repeated context | 30,000 |
| Model calls across all roles | 48 |
| Agent-requested tool calls | 40 |
| Complete repair cycles after the initial attempt | 2 |
| Pipeline-candidate evaluations | 6 |
| Active wall-clock execution | 10 minutes |
| Agent/data-processing memory | 8 GiB per run, separate from the model server |

A repair cycle is a rollback or revision of an already attempted workflow stage after a failure verdict. Ordinary initial discovery is not a repair. Instrument this state transition so the limit is not subjective.

Automatic gates execute once per new materialized/fitted artifact at their designated stage. Their computation counts toward time and memory; record their invocations separately from agent-requested calls. No unlimited free checker loop is permitted.

### 13.3 Runtime isolation

Use immutable input mounts, an isolated output directory, bounded SQL, and a separate model-service endpoint. The agent cannot access evaluator files, modify tests, change the global clock, install packages, or browse the internet. Read-only database access is one useful control, but not a substitute for filesystem/process isolation [R13].

Measure active runtime from task initialization through submission, including tool execution, verification, and model-response latency. Exclude model loading performed once for the experiment and report it separately. Record queueing time and active execution time separately.

### 13.4 Terminal states

Use `SUBMITTED`, `ABSTAINED`, `BUDGET_EXCEEDED`, `EXECUTION_ERROR`, and `INFRASTRUCTURE_ERROR`. The independent evaluator assigns `VERIFIED` or a failure category to submitted artifacts.

A failed gate triggers bounded repair or abstention. It never requests human approval.

Verified service/process infrastructure failure may receive one automatic retry with the same frozen inputs. Keep both attempt records and costs. Ordinary parsing, reasoning, tool-use, or model-fitting mistakes are not infrastructure outages.

Unresolved infrastructure failures are reported explicitly. The conservative primary analysis counts the scheduled attempt as not verified; a sensitivity analysis excludes the whole matched block, not only one inconvenient system failure. Never retry an ordinary agent failure until it succeeds.

---

## 14. Automated evaluation and metrics

### 14.1 Three distinct components

1. **Operational tools** execute the system's decisions.
2. **Internal Q/P gates** provide treatment-specific feedback using only permitted information.
3. **Independent evaluator** grades frozen artifacts using hidden labels, ledgers, reference computations, and trusted traces.

The evaluator must not simply call the internal verifier and accept its answer. Share schema definitions where useful, but independently implement critical value/record checks and test them with fixtures.

### 14.2 Primary outcome: verified-completion rate

For recoverable run `i`, define `V_i = 1` only if all mandatory external predicates pass:

- Required artifacts and a permitted fitted estimator exist.
- The target, source authority, and feature exclusions are correct.
- Expected records, join granularity, unit conversions, and required aggregates are correct.
- Missingness is handled using an allowed training-fitted procedure; exact imputation recovery is not required.
- Fit and selection dependencies obey the partition policy.
- The frozen workflow generates one finite prediction per required hidden-test record; classification probabilities are valid.
- The submitted artifact references are internally consistent and replayable on the pinned stack.
- The run stays within its declared resource limits.

```text
VCR = sum(V_i) / number_of_attempted_recoverable_runs
```

Abstentions, timeouts, invalid submissions, and ordinary failures stay in the denominator. Passing a Q/P gate is not itself a grading requirement; F and unverified systems can pass by producing an equally correct artifact.

**Interpretation:** VCR measures compliance with explicit task predicates, not universal semantic correctness and not predictive accuracy. A low-quality but properly fitted model can pass VCR, so predictive results must always accompany it.

### 14.3 Predictive metrics

| Task | Selection metric | Reported hidden-test metrics |
|---|---|---|
| Binary classification | Average precision | Average precision, macro-F1, ROC-AUC, and class prevalence |
| Multiclass classification | Macro-F1 | Macro-F1, balanced accuracy, confusion matrix |
| Regression | RMSE | RMSE, MAE, and RMSE divided by the correct-workflow dummy RMSE |

Use average precision as defined by the pinned metrics implementation; do not silently relabel it as trapezoidal PR-AUC. Report undefined metrics as `null` with a reason rather than fabricating zero.

Report predictive scores for verified runs, the size of that subset, and VCR for all attempts. Scores from externally invalid artifacts may be retained as diagnostic evidence but must not be presented as valid model quality.

As a descriptive failure-aware score, define:

```text
classification_skill = (score - dummy_score) / (1 - dummy_score)
regression_skill = 1 - RMSE / dummy_RMSE
verified_utility = V_i * max(0, skill)
```

Use average precision for binary tasks and macro-F1 for multiclass tasks. Flag zero denominators as undefined. This clipped score is secondary; show the unclipped skill and raw metrics so clipping cannot conceal poor performance.

### 14.4 Data-management metrics

| Metric | Definition |
|---|---|
| Defect-detection precision | Correct reported defect locations divided by all reported defect locations |
| Defect-detection recall | Correct reported defect locations divided by injected defects of the same eligible type |
| Exact reversible-repair rate | Correctly restored reversible defects divided by injected reversible defects |
| Unintended-edit rate | Unnecessary changes to unaffected canonical values divided by unaffected values |
| Record-integrity rate | Correct expected canonical IDs with correct multiplicity divided by expected IDs |
| Unit/aggregate correctness | Proportion of required values matching the independent reference within tolerance |
| Version-selection correctness | Required source selections matching authoritative version/hash |

Detection and repair are different outcomes. A repair can occur without an explicit detection claim. Require all systems to produce a structured operation/findings ledger; leave diagnostic precision undefined when no defects were claimed, and report recall as zero where injected defects were all missed. Do not define precision on a clean task with no findings as a perfect score.

Use exact comparisons for IDs, labels, hashes, and counts. Default numeric comparison: absolute tolerance `1e-8` and relative tolerance `1e-6`; override only where documented serialization error requires it, before main testing.

### 14.5 Reliability and abstention

```text
invalid_submission_rate = externally_invalid_submissions / all_recoverable_attempts
submission_error_rate = externally_invalid_submissions / all_submissions
recoverable_abstention_rate = abstentions / recoverable_attempts
negative_control_correct_refusal = supported_correct_refusals / negative_control_attempts
negative_control_false_submission = submissions / negative_control_attempts
```

For gate-enabled systems, also report internal false acceptance: submissions accepted by internal gates but rejected externally. This metric is not directly defined for systems without those gates; use common submission-error metrics for cross-system comparisons.

### 14.6 Provenance and replay

Check correct dependencies, authorized source versions, fit-scope compliance, and artifact consistency. Report logging coverage as an instrumentation audit, not as a treatment advantage when coverage is common by design.

Replay the frozen transformation/prediction pipeline on the same pinned stack. Require stable record ordering by canonical ID and values within tolerance. Separately document whether refitting reproduces predictions; do not assume replaying a fitted model and retraining it are the same reproducibility test.

### 14.7 Efficiency

Measure input/output tokens, model calls, tool calls, gate calls, wall time, CPU time, GPU/server time where available, peak memory, number of model fits, and cost.

```text
cost_per_verified_completion = total_cost / number_of_verified_completions
```

The ratio is undefined if there are no verified completions. For incremental cost-effectiveness, report the cost and completion differences before their ratio. Interpret negative denominators, dominated configurations, and zero improvement explicitly.

Use the actual recorded tariff or measured hardware rate. Token prices and different backbones are not interchangeable units of computational cost.

---

## 15. Statistical analysis and decision rules

### 15.1 Primary effect estimate

For each dataset family `f` and paired repetition `r`, first average paired MQP–M0 completion differences across its six templates and seven conditions:

```text
D_fr = mean_over_templates_and_conditions(V_MQP - V_M0)
Delta = mean_over_six_families(mean_over_repetitions(D_fr))
```

This gives every family equal weight. Report the overall difference in percentage points, per-family effects, condition-specific effects, and a 95% confidence interval.

### 15.2 Dependence-aware uncertainty

For the primary conditional analysis, use a paired block bootstrap with 10,000 draws. Keep the six families fixed; within each family, resample repetition blocks, carrying all templates, conditions, and systems together. Do not independently resample the 5,292 run rows.

With only three repetition blocks per family, the interval may be unstable. Report that limitation, inspect the pilot-based precision, and increase the frozen repetition allocation before the main study if resources permit and power analysis requires it. The principle of preserving multilevel dependence is consistent with hierarchical-bootstrap methodology [R11].

Report a leave-one-family-out sensitivity analysis. Any bootstrap that also resamples the six families is exploratory because the family portfolio is small and purposively selected.

For a prespecified secondary hypothesis test, use paired block sign flips of the family-repetition differences, retaining each full block. State the symmetry/exchangeability assumption; do not call it a randomized-treatment causal test. If those assumptions are implausible, emphasize effect estimates and intervals rather than a significance claim.

### 15.3 Gate effects

For the multi-agent factorial comparison, estimate on the probability scale:

```text
Q_effect = 0.5 * [(V_MQ - V_M0) + (V_MQP - V_MP)]
P_effect = 0.5 * [(V_MP - V_M0) + (V_MQP - V_MQ)]
interaction = V_MQP - V_MQ - V_MP + V_M0
```

Apply the same paired-block aggregation to these quantities. A negative interaction can indicate overlapping benefits; it does not automatically mean either mechanism is harmful.

### 15.4 Multiple comparisons

H1 is the sole primary comparison. Apply Holm adjustment to the prespecified secondary family: Q main effect, P main effect, Q×P interaction, MQP–SQP, and MQP–F. Report adjusted and unadjusted values where tests are used.

Treat remaining architecture comparisons, per-defect analyses, backbone interactions, and optional-budget effects as exploratory unless separately preregistered. Do not convert an exploratory result into a primary claim after inspecting outcomes.

### 15.5 Predictive-score comparisons

Report raw metrics within each dataset. Do not average raw RMSE across datasets with different scales.

For paired predictive comparisons, report the number of pairs where both systems were externally verified, and the corresponding selection limitation. Also show VCR and the all-attempt verified-utility score to avoid rewarding selective submission.

### 15.6 Power and practically meaningful effects

Use development-task estimates and a range of plausible within-family correlations to simulate the exact planned paired analysis. Target 80% power for a 10-percentage-point improvement in VCR as an initial planning effect size.

Neither 80% power nor a 10-point improvement is established by the proposed run count. Save the simulation code, assumptions, results, and final allocation before protocol freeze. Increasing independent task structures or source families generally addresses different uncertainty than repeating the same task; do not describe those changes as interchangeable.

No optional stopping based on observed main-study significance. If resources cannot support the desired precision, retain the feasible allocation and report the study as estimation-focused with its actual uncertainty.

### 15.7 Decision language

Evidence for H1 requires a positive paired effect with uncertainty that supports a positive difference under the declared analysis. Claim a practically meaningful improvement only when the magnitude and interval justify the declared threshold.

Failure to reject a difference is not evidence of equivalence. No blanket “trustworthy” or “fully autonomous expert” claim follows from passing this benchmark.

---

## 16. Overall research workflow

```text
Literature review and scope
          |
          v
Source acquisition and immutable manifests
          |
          v
Canonical data, split manifests, synthetic generators
          |
          v
Task contracts, corruption generator, hidden references
          |
          v
Independent evaluator and known-answer fixture tests
          |
          v
Fixed workflow + single-agent + multi-agent implementations
          |
          v
Development pilot, power analysis, resource calibration
          |
          v
Protocol/code/model/dependency freeze
          |
          v
E1 main -> E4 replication -> E5 refusal controls -> E6 replay
          |
          v
Locked automated scoring and prespecified analysis
          |
          v
Results, limitations, manuscript, reproducibility release
```

### Per-run procedure

1. Load a frozen run manifest; verify input and configuration hashes.
2. Initialize an isolated workspace and empty agent memory.
3. Expose the common task contract and permitted training sources.
4. Execute the assigned architecture with its Q/P treatment and shared limits.
5. Log every operation and resource charge using trusted wrappers.
6. Freeze the first final submission or terminal failure; do not repair it manually.
7. Run hidden evaluation in a separate process/container.
8. Write immutable result records, including failures and costs.
9. Add the result to the paired block only through the scripted analysis pipeline.

Keep main-study evaluator feedback unavailable to the agent developer until the frozen experiment batch is complete, apart from prespecified infrastructure monitoring. A discovered evaluator bug requires versioned correction and consistent re-evaluation of all affected artifacts, not selective rescoring.

---

## 17. Repository and reproducibility specification

### 17.1 Proposed repository

```text
agentic-data-mining/
├── plan.md
├── README.md
├── pyproject.toml
├── environment.lock
├── Dockerfile
├── configs/
│   ├── study.yaml
│   ├── models.lock.json
│   ├── hardware.json
│   └── candidate_models.yaml
├── prompts/
│   ├── common.md
│   ├── coordinator.md
│   ├── data_manager.md
│   └── miner.md
├── schemas/
│   ├── task.schema.json
│   ├── action.schema.json
│   └── result.schema.json
├── src/adm/
│   ├── data/              # importers and canonical schemas
│   ├── generators/        # synthetic data and corruption
│   ├── tasks/             # task templates and contracts
│   ├── tools/             # instrumented execution wrappers
│   ├── agents/            # single/multi-agent state machines
│   ├── baselines/         # fixed contract-driven workflow
│   ├── checks/            # internal quality/provenance gates
│   ├── evaluation/        # separately deployed hidden evaluator
│   └── analysis/          # metrics, intervals, tables, plots
├── tests/
│   ├── unit/
│   ├── property/
│   ├── evaluator_fixtures/
│   └── isolation/
├── manifests/
│   ├── datasets.json
│   ├── splits.json
│   └── runs.jsonl
├── data/raw/              # immutable source copies
├── data/generated/        # agent-visible benchmark inputs
├── private_evaluation/    # NEVER mounted into an agent container
├── outputs/runs/
├── outputs/tables/
├── outputs/figures/
└── reports/
    ├── pilot.md
    ├── protocol_freeze.md
    └── deviations.md
```

Do not mount the entire repository into the agent merely because the private evaluator is in a different folder. Use separate images or explicit allowlisted mounts.

### 17.2 Software stack

Use Python, NumPy, pandas, DuckDB, scikit-learn, a JSON-schema validator, pytest, and one pinned inference engine such as vLLM. Use a small explicit state machine for orchestration rather than depending on a large agent framework unless a specific need is established.

Dependency versions must be tested together and locked with hashes. This plan intentionally does not invent package-version pins without a compatibility test. The executable protocol is incomplete until the lock and smoke tests exist.

### 17.3 Proposed command-line interface

The following commands are an implementation contract, not commands already supplied by this document:

```bash
python -m adm acquire --config configs/study.yaml
python -m adm build --suite development --config configs/study.yaml
python -m adm validate --suite development --include-isolation-tests
python -m adm run --experiment E0 --config configs/study.yaml
python -m adm power --pilot outputs/runs/E0 --config configs/study.yaml
python -m adm freeze --config configs/study.yaml
python -m adm build --suite evaluation --frozen-manifest manifests/freeze.json
python -m adm run --experiment E1 --frozen-manifest manifests/freeze.json
python -m adm run --experiment E4 --frozen-manifest manifests/freeze.json
python -m adm run --experiment E5 --frozen-manifest manifests/freeze.json
python -m adm evaluate --suite formal --private-root private_evaluation
python -m adm replay --suite formal --frozen-manifest manifests/freeze.json
python -m adm analyze --protocol manifests/freeze.json
python -m adm report --input outputs --output reports/final
```

The runner must refuse unresolved model revisions, mismatched source hashes, unrecognized task IDs, missing evaluator references, or modified frozen configurations.

### 17.4 Reproducibility levels

Distinguish dataset regeneration, deterministic artifact replay, statistical rerunning with the same seeds/stack, and robustness on another model. They are different claims.

Release source hashes, generators, task contracts, prompt templates, action traces, model identifiers, dependency locks, metric code, and all terminal statuses. Respect dataset and model licenses. Public release of hidden benchmark labels occurs only after the study is complete; later reruns must still isolate them from agents.

---

## 18. Configuration and artifact schemas

### 18.1 Study configuration

This valid YAML specifies the initial allocation. `models.lock.json` supplies the immutable revisions and hashes required at freeze.

```yaml
study:
  id: agentic-data-mining-v1
  master_seed: 20261030
  human_subjects: false
  human_evaluators: false
  llm_judge: false
  runtime_human_approval: false
  primary_contrast: [MQP, M0]
  primary_outcome: verified_completion

backbones:
  A: Qwen/Qwen3.8-27B
  B: google/gemma-4-31B-it
  revision_lock: configs/models.lock.json
  dtype: bfloat16
  language_model_only: true

benchmark:
  datasets: [D1, D2, D3, D4, D5, D6]
  templates: [T1, T2, T3, T4, T5, T6]
  conditions: [C0, C1, C2, C3, C4, C5, C6]
  repetitions: [0, 1, 2]
  systems: [F, S0, M0, MQ, MP, SQP, MQP]
  shards_per_partition: 20
  replication_tasks: [D1-T5, D2-T2, D3-T4, D4-T6, D5-T3, D6-T1]
  replication_systems: [M0, SQP, MQP]
  negative_conditions: [N1, N2]

limits:
  aggregate_tokens: 30000
  model_calls: 48
  tool_calls: 40
  repair_cycles: 2
  pipeline_evaluations: 6
  wall_seconds: 600
  data_worker_memory_gib: 8

generation:
  temperature: 0.2
  top_p: 0.9
  top_k: 40
  context_tokens: 16384
  max_output_tokens: 1024
  enable_thinking: false

analysis:
  bootstrap_draws: 10000
  confidence_level: 0.95
  secondary_adjustment: holm
  planning_effect_percentage_points: 10
  target_power: 0.80
  optional_budget_experiment: false
```

### 18.2 Example task contract

This is a structural example. Actual manifests contain resolved source IDs and hashes generated by the benchmark builder; they contain no placeholder strings.

```yaml
task_id: D1-T2
task_type: binary_classification
target: machine_failure
prediction_key: observation_id
selection_metric: average_precision
required_features:
  - type
  - air_temperature_k
  - process_temperature_k
  - rotational_speed_rpm
  - torque_nm
  - tool_wear_min
excluded_predictors: [uid, product_id, TWF, HDF, PWF, OSF, RNF]
source_catalog: catalog.json
split_manifest: visible_partition_manifest.json
joins:
  - left: feature_block_a
    right: feature_block_b
    keys: [observation_id]
    required_cardinality: one_to_one
missing_numeric_policy: training_median_with_zero_for_all_missing
final_refit_partitions: [train, validation]
output:
  pipeline: submission/pipeline.json
  selected_candidate: submission/model_choice.json
  diagnostics: submission/findings.json
  provenance: trusted_logs/provenance.jsonl
```

The public task contract does not expose the private test membership or labels. The visible manifest describes only permitted partitions and group/CV policies; the evaluator owns the complete split manifest.

### 18.3 Required run record fields

Every record must include:

```text
run_id, protocol_hash, code_commit, experiment_id,
dataset_id, task_id, condition_id, repetition_id,
system_id, backbone_id, model_revision, tokenizer_hash,
data_hashes, split_hash, corruption_seed, estimator_seed, agent_seed,
start_time, terminal_state, abstention_reason,
verified_completion, external_failure_codes,
selected_candidate, cv_metrics, validation_metrics, test_metrics,
input_tokens, output_tokens, model_calls, tool_calls, gate_calls,
repair_cycles, fit_count, active_seconds, queue_seconds,
peak_worker_memory, server_gpu_seconds, monetary_cost,
artifact_hashes, replay_status, infrastructure_retry_count
```

Use `null` with an explicit reason for unavailable metrics or accounting fields. Never use fabricated zero values. Separate event logs from the summarized run record so scoring can be independently recomputed.

### 18.4 Automatic failure taxonomy

Use deterministic codes such as `SOURCE_VERSION`, `WRONG_JOIN`, `ROW_MULTIPLICITY`, `MISSING_RECORD`, `UNIT_MISMATCH`, `BAD_AGGREGATE`, `FORBIDDEN_FEATURE`, `FIT_SCOPE`, `INVALID_PREDICTION`, `ARTIFACT_MISMATCH`, `EXECUTION`, and `BUDGET`.

Record all failed predicates and a prespecified first-failure category for summary plots. No human reads transcripts to assign experimental labels. Transcript examples may illustrate already machine-coded failures, but must not change their scores.

---

## 19. Timeline and milestones

| Weeks | Work package | Exit artifact |
|---|---|---|
| 1–3 | Literature review, research-gap refinement, data/license verification | Related-work matrix and finalized project scope |
| 4–6 | Importers, generators, splits, contracts, corruption ledgers, evaluator | Versioned benchmark and known-answer tests |
| 7–10 | Shared tools, fixed workflow, single-agent baseline, isolation | Working F/S0/SQP and verified access boundaries |
| 11–13 | Multi-agent state machine, Q/P switches, provenance | All seven configurations with integration tests |
| 14 | Pilot, power simulation, cost calibration, freeze | Locked protocol, prompts, model revisions, and environment |
| 15–18 | Main paired experiment | Complete E1 logs and immutable submissions |
| 19–21 | Replication, refusal controls, replay, analysis | E4–E6 outputs and prespecified result tables |
| 22–24 | Interpretation, limitations, manuscript, release | Thesis/paper and reproducibility package |

Build the evaluator before optimizing the proposed agent. If milestones slip, reduce optional work rather than silently removing difficult tasks or weakening baselines.

### Literature-review deliverable

Search literature from 2023 to protocol freeze, plus foundational provenance and evaluation work. Record search dates, queries, inclusion rules, and reasons for exclusion. Compare task types, validation method, human involvement, baselines, budgets, and reproducibility.

Do not add unverified references from an earlier draft merely to make the bibliography longer. The references below are a verified starting set, not a completed systematic review.

---

## 20. Resources and budget

### 20.1 Hardware planning

A starting data-processing allocation is 16 CPU cores, 64 GiB host RAM, and approximately 250 GiB of storage for data, model caches, containers, and logs.

Execution server (recorded November 10, 2026): UA Little Rock Computational Research Center JupyterHub container with one NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition (96 GB GDDR7, compute capability 12.0, driver 595.91.07, CUDA driver API 13.2), 64 CPU cores, about 139 GiB RAM, and about 2.7 TB free disk. The server has no CUDA toolkit (`nvcc`) and no container runtime. The model lock records the exact GPU and host at serving time.

The BF16 weights are about 56 GB (A) and 63 GB (B). Serve one backbone at a time, wait until GPU memory is released before loading the other, and validate memory and throughput on this stack during the pilot. Both backbones are dense, so every generated token reads all weights; with about 1.8 TB/s of memory bandwidth, decode throughput is expected to be lower than for the v1.0 mixture-of-experts backbone A. Use the pilot's measured throughput, not this expectation, for run-time estimates.

A hosted endpoint is an alternative only when it identifies a fixed model revision and exposes sufficient inference/accounting controls. An unversioned alias is not an adequate substitute for a reproducible checkpoint.

### 20.2 Cost formula

For the initial required formal experiments and pilot:

```text
agentic attempts = 5,418
fixed-workflow attempts = 840

estimated_total = 1.20 * (
    5,418 * measured_mean_agent_run_cost
    + CPU/storage costs
    + reference-model and replay costs
)
```

The 20% reserve is a planning allowance, not a measured overhead. For self-hosting, derive run cost from measured server/GPU hours and the actual accounting rate rather than using an unrelated API token tariff.

**Illustrative arithmetic only:** At an assumed $0.30 per agentic attempt and $400 for all other computation/storage, the total would be approximately $2,430 after the reserve. This is not a current vendor quotation or a validated estimate for the named models.

Record median and high-percentile runtime/cost in the pilot. A mean alone can conceal expensive failure loops. Optional E7 adds 216 agentic attempts, plus their evaluation/replay cost.

---

## 21. No-human-subjects protocol and validity risks

### 21.1 Study statement

> This study evaluates software systems using public non-personal datasets and generated data about machinery, materials, simulated buildings, and synthetic processes. It will not recruit participants, collect information about individuals, conduct interviews or surveys, obtain new human annotations, or use human evaluators. Experimental artifacts will be scored exclusively by predefined software tests, reference computations, trusted execution records, and hidden test data. No person will intervene within a scored run.

Researchers still implement the software and interpret aggregate findings. That is not a human-subject experiment or a human grading panel. Do not promise that no institutional administrative determination is required; classification and documentation follow local procedures separately from the experiment.

### 21.2 Main threats and controls

| Threat | Control and residual limitation |
|---|---|
| An artificially weak fixed baseline makes agents look good | F uses the same contracts, checks, tools, and six-candidate search. |
| Multi-agent gains come from extra resources | Charge all role messages, tool use, and gates to shared limits. |
| The evaluator favors the proposed artifact format | Grade semantic predicates; accept alternative valid workflows. |
| Internal verification grades itself | Keep independent hidden references and known-bad fixtures. |
| Group or temporal leakage inflates predictive scores | Split canonical records first; preserve groups/order and training-only learned transforms. |
| Public data may have appeared in model training | Add new structures, corruptions, and synthetic instances; acknowledge exposure cannot be ruled out. |
| Contracts make tasks easier than messy real-world discovery | State this boundary; the study measures bounded, contract-defined automation. |
| Synthetic relational structure may be unrealistic | Label adaptations explicitly and report synthetic/public families separately. |
| Only six source families limit generalization | Use family-level summaries and sensitivity analyses; avoid broad population claims. |
| Tier 2 lies outside F's declared specification by construction | Report Tier 1 and Tier 2 separately; state that F's Tier-2 failures follow from its definition, not from weak engineering. |
| Documenting Tier-2 operations to agents hints that such defects exist | Document them identically to all systems and in both tiers; report agents' use of each operation in Tier 1 as a false-alarm measure. |
| Only two language-model vendors are tested | Report RQ7 as limited cross-vendor robustness; do not infer universal architecture performance. |
| Reasoning mode is disabled | Published model scores mostly use reasoning mode; state that results describe non-reasoning use under a 1,024-token action limit. |
| The benchmark may be too easy for current models | Apply the prespecified E0 ceiling check before freeze; never weaken the backbone to create headroom. |
| Automated checks miss unencoded semantics | Specify exactly what is verified; do not equate passing tests with universal truth. |
| Too few independent repetitions produce unstable uncertainty | Pilot-based power/precision analysis; freeze any increase before main results. |
| Tool restrictions suppress some errors by construction | Report blocked attempts separately; avoid attributing universal controls to Q/P treatments. |
| Manual rescue or cherry-picked reruns distort results | No human run repair; one documented infrastructure retry only; retain all attempts. |

---

## 22. Reporting and deliverables

### 22.1 Mandatory result tables

1. VCR by system, dataset family, and condition, with attempted/completed counts.
2. Primary paired effect and secondary gate/coordination effects with intervals.
3. Predictive metrics together with verified-run counts and failure-aware utility.
4. Cost, runtime, tokens, tool calls, repairs, and cost per verified completion.
5. Automatically coded failure categories and invalid-submission rates.
6. Negative-control correct refusals and false submissions.
7. Second-backbone results on the exact prespecified subset.
8. Replay, invariance, and evaluator-fixture audit results.

Show missing results and unsuccessful runs. Do not report only the best seed, easiest condition, or successful example.

### 22.2 Figures

Prepare separate figures for completion by defect condition, cost versus completion, predictive skill versus completion, and failure-category distribution. Use readable scales and uncertainty bars where justified. Do not imply raw regression scores have comparable units across datasets.

### 22.3 Research artifacts

| Deliverable | Contents |
|---|---|
| Benchmark | Source manifests, synthetic generators, contracts, splits, corruption generator, scoring specifications |
| Framework | Fixed and agentic workflows, shared tools, Q/P switches, automatic recovery |
| Evidence package | Every run status, metrics, trusted logs, comparison scripts, intervals, negative controls |
| Reproducibility package | Model revisions, dependency/container locks, hardware record, prompts, hashes, rerun instructions |
| Manuscript | Problem, related work, methods, results, costs, limitations, and negative findings |

### 22.4 Manuscript structure

Use: introduction; related work; problem and hypotheses; benchmark; system design; experimental methodology; results; discussion and threats to validity; conclusion; reproducibility appendix.

Contributions must be supported by measured results. A finding that SQP or F matches or exceeds MQP is a substantive answer to the research question.

---

## 23. Protocol-freeze and completion checklists

### Before scored experiments

- [ ] Verify non-personal dataset scope, licenses, immutable source copies, and target exclusions.
- [ ] Assert dataset schemas, class availability, geometry/mixture groups, and split integrity.
- [ ] Freeze generator code, seeds, tasks, corruption definitions, and hidden reference hashes.
- [ ] Pass known-correct, known-incorrect, metamorphic, and evaluator-isolation tests.
- [ ] Demonstrate that no agent can access hidden labels or edit scoring code.
- [ ] Freeze model revisions, tokenizers, inference engine, dtype, prompts, and generation settings.
- [ ] Lock compatible dependencies and container digests; run smoke tests for both backbones.
- [ ] Establish F as a complete generic baseline, not a deliberately incomplete script.
- [ ] Verify shared budgets, gate activation, passive logging, and memory reset.
- [ ] Record pilot results, power assumptions, final run counts, cost estimate, and deviation policy.
- [ ] Apply the E0 ceiling check and record any resulting difficulty revision.
- [ ] Freeze primary/secondary analyses and the replication-task subset.
- [ ] Confirm no runtime human approval, manual correction, or human/LLM scoring path exists.

### Before claiming completion

- [ ] Account for every scheduled run and every infrastructure retry.
- [ ] Retain failures, abstentions, invalid submissions, and undefined metrics with reasons.
- [ ] Run the independent evaluator and artifact replay on all applicable submissions.
- [ ] Report paired effects, uncertainty, family-specific results, and cost.
- [ ] Separate recoverable completion from unrecoverable correct refusal.
- [ ] Disclose deviations and rerun all affected comparisons consistently after any correction.
- [ ] Release reproducibility artifacts under compatible licenses.
- [ ] State limitations without converting nonsignificance into equivalence or benchmark success into universal trustworthiness.

---

## 24. References

External factual claims above use the numbered references below. Task definitions, budgets, synthetic generators, hypotheses, and experimental allocations are proposed design decisions, not findings from these sources. Source pages were checked while preparing this protocol on October 30, 2026, America/Chicago time. Preserve retrieved metadata at protocol freeze because live documentation can change.

**[R1]** Jing, L., et al. *DSBench: How Far Are Data Science Agents from Becoming Data Science Experts?* ICLR 2025. Official conference abstract. `https://proceedings.iclr.cc/paper_files/paper/2025/hash/50e9ad960ae78b741a6b4fea533f2eaf-Abstract-Conference.html`

**[R2]** Google Research. *DS-STAR: Data Science Agent via Iterative Planning and Verification.* 2025. Official publication page. `https://research.google/pubs/ds-star-data-science-agent-via-iterative-planning-and-verification/`

**[R3]** UCI Machine Learning Repository. *AI4I 2020 Predictive Maintenance Dataset.* Repository ID 601. Official dataset description, variables, and license. `https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset`

**[R4]** UCI Machine Learning Repository. *Steel Plates Faults.* Repository ID 198. Official dataset description, variables, and license. `https://archive.ics.uci.edu/dataset/198/steel+plates+faults`

**[R5]** UCI Machine Learning Repository. *Concrete Compressive Strength.* Repository ID 165. Official dataset description, variables, and license. `https://archive.ics.uci.edu/dataset/165/concrete+compressive+strength`

**[R6]** UCI Machine Learning Repository. *Energy Efficiency.* Repository ID 242. Official dataset description, simulation background, variables, and license. `https://archive.ics.uci.edu/dataset/242/energy+efficiency`

**[R7]** Qwen. *Qwen3.8-27B.* Publisher-maintained model card; parameter count, license, and release date checked through the Hugging Face API on November 10, 2026. `https://huggingface.co/Qwen/Qwen3.8-27B`

**[R8]** Google DeepMind. *gemma-4-31B-it.* Publisher-maintained model card; parameter count and license checked through the Hugging Face API on November 10, 2026. `https://huggingface.co/google/gemma-4-31B-it`

**[R14]** vLLM developers. *Qwen3.8-27B* and *Gemma 4* serving recipes. Official inference-engine recipes. `https://recipes.vllm.ai/Qwen/Qwen3.8-27B`, `https://recipes.vllm.ai/Google/gemma-4-31B-it`

**[R15]** vLLM developers. *Multimodal configuration (`language_model_only`).* Official API documentation. `https://docs.vllm.ai/en/stable/api/vllm/config/multimodal/`

**[R16]** *Can AI Agents Answer Your Data Questions? A Benchmark for Data Agents (DAB).* arXiv:2603.20576, 2026. `https://arxiv.org/abs/2603.20576`

**[R17]** *Agentic Data Cleaning Without a Clean Reference: An Experimental Study of Capabilities and Trade-offs.* arXiv:2608.14765, 2026. `https://arxiv.org/abs/2608.14765`

**[R18]** *Beyond Fixed Benchmarks and Worst-Case Attacks: Dynamic Boundary Evaluation for Language Models.* arXiv:2605.06213, 2026. `https://arxiv.org/abs/2605.06213`

**[R19]** *Establishing Best Practices for Building Rigorous Agentic Benchmarks* (Agentic Benchmark Checklist). arXiv:2507.02825. `https://github.com/uiuc-kang-lab/agentic-benchmarks/blob/main/ABC.md`

**[R20]** *Single-Agent LLMs Outperform Multi-Agent Systems on Multi-Hop Reasoning Under Equal Thinking Token Budgets.* arXiv:2604.02460, 2026. `https://arxiv.org/abs/2604.02460`

**[R21]** *At Equal Inference Cost, Multi-Agent Structure Does Not Beat a Single Frozen Agent.* arXiv:2609.04217, 2026. `https://arxiv.org/abs/2609.04217`

Superseded v1.0 backbones, retained for traceability: `Qwen/Qwen3-Coder-30B-A3B-Instruct` and `Qwen/Qwen2.5-Coder-14B-Instruct`.

**[R9]** scikit-learn developers. *Common pitfalls and recommended practices.* Official documentation on preprocessing, pipelines, leakage, and randomness. `https://scikit-learn.org/stable/common_pitfalls.html`

**[R10]** W3C. *PROV-DM: The PROV Data Model.* W3C Recommendation, April 30, 2013. `https://www.w3.org/TR/prov-dm/`

**[R11]** Saravanan, V., Berman, G. J., and Sober, S. J. *Application of the hierarchical bootstrap to multi-level data in neuroscience.* 2020. Author research paper, arXiv:2007.07797. Used for the dependence-aware resampling principle, not as a human dataset in this study. `https://arxiv.org/abs/2007.07797`

**[R12]** vLLM developers. *Structured Outputs.* Official inference-engine documentation. `https://docs.vllm.ai/en/latest/features/structured_outputs/`

**[R13]** DuckDB developers. *Concurrency.* Official documentation, including read-only database access. `https://duckdb.org/docs/2.0/connect/concurrency`

---

**Expected outcome:** A fully automated and reproducible assessment of when quality checks, provenance checks, and agent coordination improve, fail to improve, or worsen data-mining results relative to simpler workflows. The evidence—not the number of agents—determines the conclusion.
