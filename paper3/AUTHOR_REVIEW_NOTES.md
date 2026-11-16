# Author review notes

**Paper:** *Do LLM Agents Verify Their Data? Available vs. Enforced Checks in Data Mining*  
**Revision basis:** the uploaded `IEEE_BigData2026_paper2.zip`  
**Manuscript length:** 10 pages, including figures, tables, acknowledgment, AI disclosure, and references. This separate editorial note is not part of the manuscript.

## Scope and verification boundary

The supplied archive contains the manuscript, bibliography, compiled paper, and a vector results figure. Its nested Overleaf archive contains manuscript materials rather than the experimental implementation. No raw run records, executable study code, frozen protocol, or analysis scripts were available in the upload. The public GitHub address returned a 404 response during review, and the OSF record and reviewer link could not be inspected through the browsing tool. These access problems do not establish that the materials do not exist; they mean that independent reproduction was not possible in this revision.

The study's objectives, seven configurations, datasets, defects, resource ceilings, experiment counts, and reported findings were retained. No experiments, p-values, confidence intervals, or model outcomes were generated to fill gaps. The statistical equations clarify the estimator described in the original manuscript; they do not introduce a replacement analysis. The pseudocode summarizes the supplied algorithm and accompanying prose, not a code-to-pseudocode conversion verified against an executable implementation.

## What changed, section by section

| Section | Principal revisions |
|---|---|
| Abstract and introduction | Added a concrete, explicitly illustrative silent-file-replacement scenario; established historical context; stated the four research questions and three contributions; retained the unsupported primary hypothesis rather than recasting the study as a uniformly positive result. |
| Related work | Organized studies by evaluation, data quality/provenance, and verification/coordination; added a comparison table; replaced broad novelty claims with a specific account of the study's combined design; acknowledged that teams can help in some settings. |
| Methodology | Explained the paired design, shared ceilings, bounded operations, hidden evaluator, oracle check, and their limits. Distinguished task solvability from gate validity and equal budget ceilings from equal realized resource use. |
| Architecture and algorithm | Added a vector architecture diagram with visible/hidden information boundaries; explained components and their interaction; expanded inputs, termination, delegation, gate feedback, repair, and submission in the pseudocode. |
| Experimental setup and statistics | Consolidated model settings and experiment counts; explained family weighting, paired block resampling, sign-flip tests, Holm adjustment, absolute effect sizes, and the scope of uncertainty. |
| Results and discussion | Connected results to RQ1–RQ4, separated verification uptake from verified completion, interpreted opposing defect-specific effects, and labeled exploratory exclusions/model changes as post-hoc. |
| Limitations and reproducibility | Identified missing reproduction details, the enforcement/prompting confound, limited external validity, and the distinction between successful replay and imperfect corruption-audit tests. |
| Conclusion | Answered all four RQs and separated observed findings from proposed improvements, including calibrated ranges, advisory checks, and controlled enforcement ablations. |
| Author information and disclosures | Inserted the requested affiliation, exact NSF acknowledgment sentence, and exact supplied OpenAI disclosure. Preserved the original NVIDIA acknowledgment and previous Claude-use disclosure. |

## Author confirmations needed before submission

### 1. Make the underlying evidence accessible

Check the repository and OSF permissions using a reviewer account or private browser session. Provide an accessible frozen source release, full protocol hash, run records, analysis outputs, environment specification, and instructions for reproducing each table. The reviewer token supplied in the original paper is retained in a LaTeX comment, not printed in the manuscript. Ensure reviewers receive a working access route through the submission system; a source comment alone is not sufficient reviewer access.

Confirm the protocol freeze, registration, and evaluation dates separately. A locally frozen protocol and an OSF registration are distinct events. The revision does not assert that registration preceded evaluation unless the record establishes that chronology. The original abbreviated hash is not a substitute for an accessible full record.

### 2. Resolve the preprocessing/final-refit ambiguity

The source requires training-only preprocessing but also says that submission refits the selected model on training and validation data. Clarify which preprocessing objects are refitted, whether model-selection validation remains separate from final training, and how provenance checks distinguish those stages. The revision preserves both source statements and explicitly flags the missing final-refit semantics. It does not assume an implementation that was not supplied.

### 3. Complete the reproducibility configuration

Document the exact six candidate pipelines and hyperparameters; candidate-selection metric and tie-breaking; train/validation/test construction and proportions; stratification where applicable; generator, split, and repetition seeds; prompts and tool schemas; software versions; and the complete model revision identifiers. The model identifiers and revision strings already in the source were retained, but their actual use in the recorded runs was not independently verified. Confirm whether “600 seconds of active time” excludes queueing and how concurrent execution affects accounting.

### 4. Check pseudocode against the implementation

Verify the exact tool/action names, handling of malformed actions, consecutive-invalid-action counter, feedback added to history, gate invocation order, and repair-counter semantics. In particular, confirm what happens after a successful repair, whether the repair allowance is cumulative, and whether a failed submission affects the next materialization in the way shown. Confirm the 12-step specialist bound, shared blackboard updates, shared budget accounting, and coordinator-only submission. The expanded delegation and invalid-action branches are explanatory representations of the source prose, not new evaluated features.

### 5. Confirm the statistical implementation and hypothesis wording

The revision preserves the reported 10,000 bootstrap draws, 10,000 sign-flip draws, 18 family–repetition blocks, and five-test secondary family. Add or expose the bootstrap interval construction, random seeds, exact block aggregation, sign-flip p-value convention, variance-inflation formula, mixed-model specifications, and convergence diagnostics. The primary p-value of 1.000 added to the table comes from the original results prose; it was not recalculated.

The original text is not fully consistent about the directional expectation for H3. Confirm its wording against the frozen protocol. The revised RQ4 is neutral and reports the actual contrast rather than silently inventing a prespecified direction. Likewise, retain the distinction between prespecified no-X4 sensitivity analysis and post-hoc removal of the false-alarm blocks. A nonsignificant primary test is not an equivalence test.

### 6. Clarify secondary reporting details

The original runtime comparison is 223 versus 138 seconds per run, but the supplied manuscript does not establish whether these are means, medians, or another summary. Identify the statistic and its population. Report E5 refusal counts by system when available. For E6, supply the denominator and disposition of the 45 corruption-audit exceptions, together with the patch/diff for the reported one-line pandas compatibility change. Successful replay of 146 retained submissions does not establish that all corruption tests were valid. Do not exclude exceptions or reinterpret outcomes without explicitly documenting the change.

### 7. Confirm acknowledgments, affiliation, and AI-use statements

The institution wording and funding statement were inserted as requested, not independently certified. Confirm the preferred official affiliation spelling and all author addresses. The exact requested disclosure naming “OpenAI GPT-6.1 Sol” was included as an author-provided statement of historical use. Verify that every named tool/model and described use accurately reflects the research record; the revision process does not establish those historical facts. The original manuscript also disclosed an IDE-based assistant using Anthropic Claude models. That disclosure was retained because the request was to add the new statement, not to remove earlier disclosed assistance. Revise either statement only to reflect actual use.

### 8. Check the venue's submission requirements

The delivered PDF meets the requested total limit of 10 pages in the supplied IEEE conference layout. The revision does not certify compliance with every current venue policy. Confirm anonymity, acknowledgment/disclosure placement, paper-size requirements, permitted supplementary materials, artifact-link policies, and the required publication version of the template. Later edits may change pagination; recompile and check the final PDF again.

## Completed checks

All 35 main-table completion rates match the supplied source exactly. All original numerical contrast estimates, confidence limits, and secondary p-values were retained; the primary p-value was transferred from the original prose. Run-count arithmetic remains 7,560 + 540 + 252 = 8,352, with E6 treated separately as an audit. The results figure is byte-for-byte identical to the supplied PDF. The requested NSF and OpenAI text is present. Citations resolve, cross-references compile, and the PDF has been rendered and visually reviewed. These checks establish manuscript consistency and presentation quality, not independent reproduction of the experiments.

See `REFERENCE_AUDIT.md` for the scope of the targeted primary-source literature checks and `VALIDATION_REPORT.md` for the final build checks.
