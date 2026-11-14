# Literature review: verifiable agentic data mining

Companion to `main.tex` (draft v0.2). It lists every work cited in the paper, grouped by theme, with what each work
reports and how it relates to this study. Summaries are paraphrased from each work's abstract or official page,
checked on 11–12 Nov 2026 (see `refcheck/REFERENCES_VERIFIED.md`). BibTeX keys refer to `refs.bib`.

**Status legend:** *Peer-reviewed* = venue confirmed on the venue's site, a Crossref DOI record, or an author note on
arXiv. *Preprint* = arXiv only.

---

## 1. Benchmarks for data-science and data agents

| Work | Venue / status | What it reports | Relevance to this study |
|---|---|---|---|
| Hu et al., *InfiAgent-DABench: Evaluating Agents on Data Analysis Tasks* (`hu2024infiagent`) | ICML 2024 (PMLR 235) | Data-analysis questions over CSV files, rewritten in closed form so they can be scored automatically; many LLMs benchmarked | Early example of automatic scoring for data agents; scores answers, not data-handling correctness |
| Jing et al., *DSBench: How Far Are Data Science Agents from Becoming Data Science Experts?* (`jing2025dsbench`) | ICLR 2025 | 466 data-analysis and 74 data-modeling tasks from Eloquence and Kaggle; best agent solved 34.12% of analysis tasks | Shows the low ceiling of current agents on realistic tasks; motivates our question of *correct* rather than *executed* pipelines |
| Chan et al., *MLE-bench: Evaluating Machine Learning Agents on ML Engineering* (`chan2025mlebench`) | ICLR 2025 | 75 Kaggle competitions; agents compared with human leaderboards; best setup reached bronze level in 16.9% | Scores predictive performance; we score whether the workflow obeys explicit data predicates |
| Egg et al., *DABstep: Data Agent Benchmark for Multi-step Reasoning* (`egg2025dabstep`) | Preprint | Over 450 multi-step tasks from a financial analytics platform; factoid answers; best agent 14.55% on hard tasks | Multi-source, multi-step data work; answer-level scoring |
| Lei et al., *Spider 2.0: Real-World Enterprise Text-to-SQL Workflows* (`lei2025spider2`) | ICLR 2025 | 632 enterprise text-to-SQL workflow problems on large real databases (BigQuery, Snowflake) | Enterprise data complexity; SQL focus |
| Ma et al., *Can AI Agents Answer Your Data Questions? A Benchmark for Data Agents (DAB)* (`ma2026dab`) | Preprint (v3) | 104 queries over 17 datasets in 4 database systems with duplicated and inconsistent data; best agent 57% pass@1 | Closest in motivation (inconsistent enterprise data); still answer-level scoring, no controlled mechanism comparison |
| Liu et al., *DataGovBench: Benchmarking LLM Agents for Data Governance Workflows* (`liu2025datagovbench`) | Preprint | 150 governance tasks with synthesised noise; models lack robust error correction; a planner–executor–evaluator agent raised task scores | Data correctness as the target; their evaluator is part of the agent, ours is independent of it |

## 2. Data-science agent systems

| Work | Venue / status | What it reports | Relevance |
|---|---|---|---|
| Guo et al., *DS-Agent: Automated Data Science with Case-Based Reasoning* (`guo2024dsagent`) | ICML 2024 | Case-based reasoning over Kaggle solutions; 100% development-stage success with GPT-4 | Agent design for modeling tasks; no data-defect focus |
| Hong et al., *Data Interpreter: An LLM Agent for Data Science* (`hong2024datainterpreter`) | Preprint | Hierarchical task graphs and node-level refinement and verification; gains on InfiAgent-DABench and ML tasks | Verification inside the agent's own code generation |
| Nam et al., *DS-STAR: Data Science Agent for Diverse Tasks across Heterogeneous Formats* (`nam2025dsstar`) | Preprint | Iterative planning with an LLM verifier that judges whether the plan is sufficient; state of the art on DABStep and others | Verification by LLM judgment; we test executable, deterministic checks instead |

## 3. Agentic data cleaning and data-quality assessment

| Work | Venue / status | What it reports | Relevance |
|---|---|---|---|
| Fadlallah, *Agentic Data Cleaning Without a Clean Reference* (`fadlallah2026cleaning`) | Preprint (submitted to New Generation Computing) | Seven configurations, 126 runs; a deterministic profiling baseline had the best detection F1 (0.561); added capabilities gave trade-offs, not consistent gains | Supports keeping a strong deterministic baseline (our F) and expecting non-uniform gate effects |
| Fadlallah et al., *An Agentic Retrieval Framework for Context-Aware Data Quality Assessment* (`fadlallah2026dqa`) | Preprint | Multi-agent generation of validation logic, with a feasibility-validation stage before deterministic execution | Closest to our gates; their stage vets the agent's own rules, our gates are fixed task-independent predicates evaluated against matched ungated systems |
| Narayan et al., *Can Foundation Models Wrangle Your Data?* (`narayan2022wrangle`) | PVLDB 16(4), 2022 | Five data cleaning and integration tasks cast as prompting; large foundation models performed well without task-specific training | Establishes LLMs as capable data wranglers; motivates testing them under controlled defects |

## 4. Multi-agent versus single-agent under matched compute

| Work | Venue / status | What it reports | Relevance |
|---|---|---|---|
| Wu et al., *AutoGen: Multi-Agent Conversation* (`wu2023autogen`) | Preprint | Open framework for conversing, role-based agents | Representative multi-agent framework |
| Hong et al., *MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework* (`hong2024metagpt`) | ICLR 2024 | Standard operating procedures encoded in role-based agent pipelines; more coherent solutions on collaborative software tasks | Role specialisation, the design our three-role team follows |
| Cemri et al., *Why Do Multi-Agent LLM Systems Fail?* (`cemri2025mas`) | Preprint | Failure taxonomy (MAST) from 1,600+ annotated traces across 7 frameworks; 14 failure modes in 3 categories, including task verification | Verification failures are a known MAS weakness; we make verification a controlled factor |
| Tran & Kiela, *Single-Agent LLMs Outperform Multi-Agent Systems … Under Equal Thinking Token Budgets* (`tran2026single`) | Preprint | Information-theoretic argument plus experiments: single agents match or beat MAS on multi-hop reasoning at equal reasoning-token budgets | Motivates our matched-budget design and the two-sided H3 |
| Fu et al., *Do More Agents Help? Evaluating Accuracy and Cost in LLM Multi-Agent Workflows* (`fu2026moreagents`) | Preprint (v2) | Six MAS versus one single-agent reference across ten benchmarks with GPT-4.1; one MAS (EvoAgent) exceeded the reference in pooled accuracy, the other five trailed | Same conclusion pattern; their tasks are reasoning, coding and tool use, not data mining |
| Dylan et al., *At Equal Inference Cost, Multi-Agent Structure Does Not Beat a Single Frozen Agent* (`dylan2026equalcost`) | Preprint | With model calls fixed, an evolved three-role team was not significantly better than an evolved single agent on ALFWorld (0.769 vs 0.754, p = 0.80); null or worse on WebShop | Equal-cost comparison; our pilots showed the same for data mining |
| Xu et al., *Rethinking the Value of Multi-Agent Workflow: A Strong Single Agent Baseline* (`xu2026oneflow`) | Preprint | A single agent in multi-turn conversation reached the performance of homogeneous workflows (same base model), with a KV-cache efficiency advantage | Our team is homogeneous, so a single agent is the right comparator |
| Jwalapuram et al., *The Illusion of Multi-Agent Advantage* (`jwalapuram2026illusion`) | Preprint (Salesforce Research and others, v2 June 2026) | Earlier comparisons rarely control inference budgets (LLM calls, total cost, retries, sampled paths); automatically generated MAS underperform chain-of-thought with self-consistency while costing up to 10x more; expert-designed MAS do better on a diagnostic dataset | Direct support for budget-matched comparison; our budgets cover all roles, tool calls and retries |
| Kim et al., *Towards a Science of Scaling Agent Systems* (`kim2025scaling`) | Preprint | 260 configurations, six benchmarks, five architectures, standardised tools, prompts and compute; coordination effect ranges from +80.8% to −70.0% depending on task structure; architectures without centralised verification tend to propagate errors | Links verification placement to MAS reliability; our gates are centralised, enforced verification |

## 5. Feedback, tool use, and self-correction

| Work | Venue / status | What it reports | Relevance |
|---|---|---|---|
| Yao et al., *ReAct: Synergizing Reasoning and Acting* (`yao2023react`) | ICLR 2023 | Interleaved reasoning traces and tool actions; gains on QA, fact checking, ALFWorld, WebShop | Base pattern for our tool-using agents |
| Shinn et al., *Reflexion: Language Agents with Verbal Reinforcement Learning* (`shinn2023reflexion`) | NeurIPS 2023 | Agents reflect verbally on feedback and store reflections across trials; large gains on coding and decision tasks | Feedback-driven improvement; we restrict feedback to deterministic gate verdicts within one run |
| Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet* (`huang2024selfcorrect`) | ICLR 2024 | Without external feedback, LLMs struggle to self-correct reasoning and can get worse | Argues for external, executed checks rather than self-judgment |
| Gou et al., *CRITIC: Self-Correct with Tool-Interactive Critiquing* (`gou2024critic`) | ICLR 2024 | Critiques obtained by interacting with tools consistently improve LLM outputs | Supports tool-based verification; our gates are a fixed form of it |

## 5a. Available versus enforced verification (added 12 Nov 2026)

| Work | Venue / status | What it reports | Relevance |
|---|---|---|---|
| Besanson, *SARC-DQ: Runtime Data-Quality Gating for Agentic AI* (`besanson2026sarcdq`) | Preprint (Jul 2026) | Metadata-borne defects (stale or superseded records) turned into costly actions about 60% of the time; rate flat across four model tiers spanning ~15x price; a metadata-aware pre-action gate recovered the loss on the signals its predicates covered | Closest prior work. Its defect signal never reaches the agent; in ours the agent can reach it (the verifying operation is available) but is not forced to use it |
| Li, *Where Does Exactly-Once Live? (LIMBO)* (`li2026limbo`) | Preprint (Sep 2026) | When a read-back reveals what happened, instructed frontier models rarely duplicate writes (0.5%); when it cannot, the tool contract decides; agents use idempotency keys when they exist | Supports "reachability of the signal decides"; different domain (side-effecting tools) |
| Zhang et al., *RITE* (`zhang2026rite`) | Preprint (Oct 2026) | Silent tool errors roughly halve task success across 10 models; recognition, use of an available verification path, and evidence integration are successive bottlenecks | Direct evidence that agents skip available verification; e-commerce domain |
| Zhang et al., *Rethinking Verification in Agent Harnesses* (`zhang2026rethinking`) | Preprint (Oct 2026) | 17 verification designs on 7 coding models: instructions give modest gains; completion gates larger gains at higher cost; independent review best accuracy-cost trade-off | Closest to instruction vs enforcement; coding domain |
| Yang et al., *Agents' Overreliance on Unreliable Tools* (`yang2026overreliance`) | Preprint (Sep 2026) | 14 models adopt corrupted tool returns at high rates (68% for web search); verification prompts reduce adoption | Instructions help but do not remove the problem |
| Sharma, *ContextCov* (`sharma2026contextcov`) | Preprint (Feb 2026) | Executable guardrails from instruction files: 88.3% constraint compliance vs 67.0% prompt-only and 50.3% reflection on SWE-bench Lite | Enforcement beats instructions in software engineering |
| Besanson, *One Gate Is Not Enough: Composing Stateful Pre-Action Controls for Agentic AI* (`besanson2026onegate`) | Preprint (Aug 2026) | When several pre-action gates are composed, a remediation by one gate can invalidate another's earlier judgment; remediation order matters | Relevant if gates are composed; our two gates check independently and do not remediate |
| Li et al., *The Silent Failures in Agentic Data Science* (`li2026silent`) | Preprint (Oct 2026) | Beyond-accuracy audit of agentic data science over 220 tasks; most solutions contain at least one methodological failure such as data leakage or inappropriate validation; a test suite for six failures | Closest data-science evaluation beyond accuracy; audits solutions rather than comparing enforced checks |
| Parmar et al., *Multi-Agent Debate for Data Cleaning* (`parmar2026debate`) | Preprint (Jun 2026) | Debate degrades generation but improves error detection; a separate critic grounded in code execution is needed to beat a single agent | Multi-agent structure helps only with grounded verification, consistent with our team-vs-single results |
| Faghih et al., *Tool Preferences in Agentic LLMs are Unreliable* (`faghih2025toolprefs`) | EMNLP 2025 (main) | Edited tool descriptions receive over 10x the usage of originals (GPT-4.1, Qwen2.5-7B); trends across 17 models | Threat to validity: our measured uptake depends on the fixed tool wording |

## 6. Data validation, quality, cleaning, and provenance

| Work | Venue / status | What it reports | Relevance |
|---|---|---|---|
| Sculley et al., *Hidden Technical Debt in Machine Learning Systems* (`sculley2015debt`) | NIPS 2015 | ML systems accumulate maintenance risk, including data dependencies and configuration issues | Data dependencies as a source of silent failure |
| Polyzotis et al., *Data Validation for Machine Learning* (`polyzotis2019datavalidation`) | MLSys 2019 | Production data-validation system in Google's TFX that detects anomalies in data fed to ML pipelines | Industrial precedent for our quality gate |
| Schelter et al., *Automating Large-Scale Data Quality Verification* (`schelter2018deequ`) | PVLDB 11(12), 2018 | Production system with a declarative API that combines common quality constraints with user code ("unit tests for data"), run as aggregation queries on Apache Spark, with incremental validation and anomaly detection | Declarative quality checks in production; our quality gate is a fixed set of such checks |
| Chu et al., *Data Cleaning: Overview and Emerging Challenges* (`chu2016cleaning`) | SIGMOD 2016 (tutorial) | Taxonomy of data-cleaning work: qualitative cleaning with constraints, rules or patterns, quantitative approaches such as outlier detection, ML for cleaning, and effects of cleaning on analysis | Background on error types and repair; our Tier 2 defects are qualitative errors detectable by rules |
| Grafberger et al., *mlinspect: A Data Distribution Debugger for ML Pipelines* (`grafberger2021mlinspect`) | SIGMOD 2021 (demo) | Inspects ML pipelines for data distribution issues introduced by operations such as joins and filters | Pipeline-level data checks, the non-agent counterpart of our quality gate |
| Wang & Strong, *Beyond Accuracy: What Data Quality Means to Data Consumers* (`wang1996beyond`) | J. Management Information Systems 12(4), 1996 | Data quality as multiple dimensions beyond accuracy, from the data consumer's view | Grounds our predicates (completeness, consistency, source authority) in DQ theory |
| Rekatsinas et al., *HoloClean: Holistic Data Repairs with Probabilistic Inference* (`rekatsinas2017holoclean`) | PVLDB 10(11), 2017 | Combines integrity constraints, external data and statistics in probabilistic repair; ~90% precision, >76% recall | Automated repair baseline in the data-management literature |
| Li et al., *CleanML: Impact of Data Cleaning on ML Classification* (`li2021cleanml`) | ICDE 2021 | 14 real datasets, five error types, seven models; measures how cleaning changes downstream classifiers, with false-discovery control | Links data errors to model outcomes, as our VCR and predictive metrics do |
| Moreau & Missier (eds.), *PROV-DM: The PROV Data Model* (`w3c2013provdm`) | W3C Recommendation, 2013 | Standard model of entities, activities and agents for provenance | Basis of our provenance records |
| Namaki et al., *Vamsa: Automated Provenance Tracking in Data Science Scripts* (`namaki2020vamsa`) | KDD 2020 | Infers which dataset columns feed an ML model's features and labels from Python scripts; evaluated on 26K scripts | Provenance extraction after the fact; we record it with trusted wrappers and use it as a treatment |
| Kapoor & Narayanan, *Leakage and the Reproducibility Crisis in ML-based Science* (`kapoor2023leakage`) | Patterns 4, 2023 | Leakage found in 17 fields affecting 329 papers; taxonomy of 8 leakage types | Motivates the fit-scope and leakage predicates in our evaluator |

## 7. Benchmark design and rigor

| Work | Venue / status | What it reports | Relevance |
|---|---|---|---|
| Zhu et al., *Establishing Best Practices for Building Rigorous Agentic Benchmarks* (ABC) (`zhu2025abc`) | Preprint | Many agentic benchmarks misestimate performance by up to 100% relative; checklist includes solvability checks and an oracle solver | We run an oracle on every Tier-2 instance (216 development, 324 evaluation) before agents |
| Jimenez et al., *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* (`jimenez2024swebench`) | ICLR 2024 | 2,294 real GitHub issues from 12 Python repositories; generated patches are evaluated against the repositories' real tests | Precedent for execution-based verification of agent output, which our evaluator applies to data workflows |
| Wang et al., *Dynamic Boundary Evaluation for Language Models* (`wang2026dbe`) | Preprint | Fixed item sets cause ceiling and floor effects; items near 0.5 pass probability are most informative | Basis of our Tier-2 calibration rule (target 0.5) |
| Ge et al., *Agent Psychometrics: Task-Level Performance Prediction* (`ge2026psychometrics`) | Preprint | Item response theory with task features predicts task-level agent success; aggregate pass rates hide task diversity | Supports reporting per-defect and per-family results, not only pooled VCR |

## 8. Statistical methods

| Work | Venue / status | Used for |
|---|---|---|
| Efron, *Bootstrap Methods: Another Look at the Jackknife* (`efron1979bootstrap`) | Annals of Statistics, 1979 | Bootstrap intervals |
| Saravanan, Berman & Sober, *Hierarchical Bootstrap for Multi-Level Data* (`saravanan2020hierarchical`) | Preprint | Resampling that respects nesting (blocks within families); naive tests can exceed 45% false positives on nested data |
| Holm, *A Simple Sequentially Rejective Multiple Test Procedure* (`holm1979`) | Scand. J. Statistics 6, 1979 | Holm adjustment of the secondary family |

## 9. Datasets, models, and software

All four UCI datasets are licensed CC BY 4.0 (stated on each dataset page, checked 12 Nov 2026).

| Item | Source | Role |
|---|---|---|
| AI4I 2020 Predictive Maintenance (`uci601ai4i`, `matzka2020ai4i`) | UCI ID 601, DOI 10.24432/C5HS5C; Matzka, AI4I 2020 | D1 |
| Steel Plates Faults (`uci198steel`) | UCI ID 198, DOI 10.24432/C5J88N | D2 |
| Concrete Compressive Strength (`uci165concrete`, `yeh1998concrete`) | UCI ID 165, DOI 10.24432/C5PK67; Yeh, Cement and Concrete Research 1998 | D3 |
| Energy Efficiency (`uci242energy`, `tsanas2012energy`) | UCI ID 242, DOI 10.24432/C51307; Tsanas & Xifara, Energy and Buildings 2012 | D4 |
| Qwen3.8-27B (`qwen2026qwen38`) | Hugging Face, revision 37561816…, Apache-2.0 | Backbone A |
| gemma-4-31B-it (`google2026gemma4`) | Hugging Face, revision 842da379…, Apache-2.0 | Backbone B |
| vLLM / PagedAttention (`kwon2023vllm`, `vllm2026structured`) | SOSP 2023; vLLM documentation | Model serving and JSON-constrained output |
| scikit-learn (`pedregosa2011sklearn`, `sklearn2026pitfalls`) | JMLR 12, 2011; documentation | Candidate models and leakage-safe pipelines |
| DuckDB (`raasveldt2019duckdb`) | SIGMOD 2019 | Read-only SQL tool |

---

## 10. The gap this study addresses

1. **Scoring.** Data-agent benchmarks (Sections 1–2) mostly score final answers or predictive performance. Few check
   whether the submitted workflow used authorised data, kept every record exactly once, and fitted transforms only on
   training data. Our evaluator scores those predicates independently of the agent.
2. **Verification type.** Existing verification is mostly by LLM judgment (DS-STAR) or inside the agent loop
   (Data Interpreter, DataGovBench). Work on self-correction (Huang et al.; CRITIC) suggests executed checks should
   matter more. We test deterministic gates and compare them with matched ungated systems.
3. **Available versus enforced.** Recent work in other domains (Section 5a) finds that agents often skip an available
   verification path (RITE) and that enforced checks beat instructions (Rethinking Verification, ContextCov); for data
   quality, SARC-DQ studies defects whose signal never reaches the agent. What we found no study of is the data-mining
   case where the verifying operation is available and documented to every system, but enforced only for some, with
   matched budgets and an independent evaluator. In our pilots, ungated agents used the available hash-verifying
   operation in 3–7% of the runs where it was needed.
4. **Matched compute.** Matched-budget comparisons of single and multi-agent systems (Section 4) cover reasoning,
   coding and embodied tasks, not data mining with controlled data defects.
5. **Benchmark validity.** Following ABC and boundary-evaluation work (Section 7), we separate declared from
   undeclared defects, calibrate severity with a fixed rule, and check solvability with an oracle; the pilots showed
   that declared-defect benchmarks saturate, even for a non-agent baseline.

## 11. Verification status

All 68 entries in `refs.bib` are cited in `main.tex` and were checked against an official source; for every work in
this review the abstract or official description was read. The three items left open in the first version were
closed on 12 Nov 2026:

- **Jwalapuram et al.** located as arXiv 2606.13003 (v2, 13 Jun 2026); the reviewer's quoted point about budget
  control was confirmed in the paper's introduction; now cited. Kim et al. (arXiv 2512.08296), found through the same
  source, was added.
- **UCI licences:** all four dataset pages state CC BY 4.0.
- **SWE-bench:** now cited in the paper's benchmark-rigour paragraph.
