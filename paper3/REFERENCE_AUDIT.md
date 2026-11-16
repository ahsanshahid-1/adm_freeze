# Targeted reference audit

## Scope

This is a targeted primary-source review supporting the manuscript revision, not a systematic literature review or a certification that every detail of every cited study has been independently reproduced. Central recent studies were checked against author abstracts, official proceedings, or paper text. Selected bibliographic discrepancies were checked against the published/version-pinned PDFs, including rendered first pages. The supplied bibliography's earlier claim of a complete audit referenced files not included in the upload; that blanket claim was replaced with an accurate statement of the checks performed here.

The paper retains numbered IEEE citations and identifies arXiv works as preprints unless a proceedings publication was supported. Claims about the present study remain grounded in the uploaded manuscript, not in the external literature. Model cards establish model identities; they do not verify which models actually produced the study's runs.

## Specific bibliographic corrections and retained discrepancies

| Entry | Check and disposition | Primary source |
|---|---|---|
| InfiAgent-DABench | Added the official ICML/PMLR page range, 19544–19572. | https://proceedings.mlr.press/v235/hu24s.html |
| Data Validation for Machine Learning | Corrected author order to the paper's first page: Eric Breck, Neoklis Polyzotis, Sudip Roy, Steven Euijong Whang, Martin Zinkevich. The paper PDF was used where landing-page ordering differed. | https://proceedings.mlsys.org/paper_files/paper/2019/file/928f1160e52192e3e0017fb63ab65391-Paper.pdf |
| Data Agent Benchmark | Pinned the reference URL to version 3. Retained Adit Chintamaneni because the version-3 PDF includes this author, although the arXiv abstract metadata omits the name. Removed the lengthy metadata-discrepancy explanation from the printed bibliography. | https://arxiv.org/pdf/2603.20576v3 |
| Automating Large-Scale Data Quality Verification | Retained Andreas Grafberger in the author list, as shown on the paper's first page. | https://www.vldb.org/pvldb/vol11/p1781-schelter.pdf |
| MLE-bench | Retained the author ordering shown in the conference PDF, including Lilian Weng before Aleksander Madry. | https://proceedings.iclr.cc/paper_files/paper/2025/file/7e3767db483c942b883eb4f8cfb74e31-Paper-Conference.pdf |

## Central claim checks

| Literature area | Primary sources consulted | Consequence for the revision |
|---|---|---|
| Data-science benchmarks | DSBench: https://proceedings.iclr.cc/paper_files/paper/2025/hash/50e9ad960ae78b741a6b4fea533f2eaf-Abstract-Conference.html ; InfiAgent-DABench: https://proceedings.mlr.press/v235/hu24s.html ; MLE-bench: https://proceedings.iclr.cc/paper_files/paper/2025/hash/7e3767db483c942b883eb4f8cfb74e31-Abstract-Conference.html | Described complementary task coverage rather than treating benchmark scores as directly comparable. |
| Broader data workflows | DABstep: https://arxiv.org/abs/2506.23719 ; Spider 2.0: https://arxiv.org/abs/2411.07763 ; DAB: https://arxiv.org/abs/2603.20576v3 | Acknowledged existing multi-step, enterprise, and heterogeneous-data evaluations. |
| Agent architecture | DS-Agent: https://proceedings.mlr.press/v235/guo24b.html ; Data Interpreter: https://arxiv.org/abs/2402.18679 ; DS-STAR: https://arxiv.org/abs/2509.21825 | Explained how related systems organize tasks without claiming to benchmark those systems directly. |
| Process quality and governance | Silent Failures in Agentic Data Science: https://arxiv.org/abs/2610.14115 ; DataGovBench: https://arxiv.org/abs/2512.04416 | Removed the implication that prior benchmarks never assess data-handling processes. |
| Agentic cleaning and assessment | https://arxiv.org/abs/2608.14765 ; https://arxiv.org/abs/2606.02866 ; https://arxiv.org/abs/2606.13692 | Emphasized detection/repair trade-offs and the need to evaluate checking rules themselves. |
| Verification gates | SARC-DQ: https://arxiv.org/abs/2607.26313 ; One Gate Is Not Enough: https://arxiv.org/abs/2608.18360 ; RITE: https://arxiv.org/abs/2610.27777 | Positioned the study as a controlled data-mining extension, not the invention of executable verification. |
| Tool and harness guarantees | LIMBO: https://arxiv.org/abs/2609.29095 ; Rethinking Verification: https://arxiv.org/abs/2610.34577 ; ContextCov: https://arxiv.org/abs/2603.00822 ; tool overreliance: https://arxiv.org/abs/2609.05587 | Distinguished model behavior from guarantees and costs imposed by tools or controllers. |
| Resource-aware team comparisons | https://arxiv.org/abs/2604.02460 ; https://arxiv.org/abs/2609.04217 | Qualified coordination claims by resource constraints and the tested design. |
| Mixed evidence for teams | Do More Agents Help?: https://arxiv.org/abs/2606.05670 ; The Illusion of Multi-Agent Advantage: https://arxiv.org/abs/2606.13003 ; Scaling Agent Systems: https://arxiv.org/abs/2512.08296 | Explicitly acknowledged successful team configurations and task-dependent benefits; avoided a universal “single agents are better” conclusion. |
| Self-correction and feedback | https://arxiv.org/abs/2310.01798 ; https://arxiv.org/abs/2305.11738 | Distinguished intrinsic revision from correction supported by external tool evidence. |
| Provenance and methodology | PROV-DM: https://www.w3.org/TR/prov-dm/ ; hierarchical bootstrap: https://arxiv.org/abs/2007.07797 ; benchmark checklist: https://arxiv.org/abs/2507.02825 | Supported the methodological rationale without treating these references as proof of the present implementation. |
| Pilot severity and tool descriptions | https://arxiv.org/abs/2605.06213 ; https://arxiv.org/abs/2505.18135 | Retained the rationale for avoiding ceiling/floor settings and the limitation that tool descriptions can affect uptake. |

The key correction to the multi-agent synthesis is substantive: Fu et al. report a successful configuration alongside five that trail their single-agent reference, while the scaling study reports strong task dependence. The revision preserves that mixed evidence rather than using those papers to support a universal claim of team inferiority.

## Artifact and model-access checks

The study repository named in the source, `https://github.com/ahsanshahid-1/adm_freeze`, returned 404 during review. The OSF record `https://osf.io/bn6va` and supplied reviewer route could not be inspected with the browsing tool. Access must therefore be confirmed by the authors; neither protocol timing nor analysis reproduction was independently verified.

The model cards at `https://huggingface.co/Qwen/Qwen3.8-27B` and `https://huggingface.co/google/gemma-4-31B-it` were consulted for model identity. The revision retains the source's pinned revisions and experimental settings without claiming to have verified their actual execution. The user-supplied AI disclosure is an author attestation and is not validated by these model-card checks.

## Remaining reference checks

Before submission, authors should confirm any newer publication versions, final author preferences, DOI/venue metadata, and the current venue's citation requirements. The original UCI identifiers and foundational references were retained unless a targeted correction was supported. No conclusion should be drawn that all 59 cited entries received the same depth of full-text review.
