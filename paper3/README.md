# Revised IEEE conference manuscript

**Title:** Do LLM Agents Verify Their Data? Available vs. Enforced Checks in Data Mining

The included `main.pdf` is the revised manuscript. It has **10 pages total**, including acknowledgment, AI disclosure, and references. The editable source preserves the supplied IEEEtran conference class and standard body typography; the page limit was not achieved by shrinking the page margins or body font.

## Files

- `main.tex`: revised manuscript; the architecture diagram is editable TikZ within this file.
- `refs.bib`: bibliography, with targeted primary-source corrections.
- `figures/fig_main.pdf`: unchanged original vector results figure.
- `main.pdf`: compiled 10-page manuscript.
- `AUTHOR_REVIEW_NOTES.md`: revision summary and author-confirmation items.
- `REFERENCE_AUDIT.md`: scope and findings of the targeted reference checks.
- `VALIDATION_REPORT.md`: final consistency, compilation, and layout checks.

The editorial notes and validation files are separate from the manuscript and are not additional manuscript pages. No experiment implementation or raw run data are included: those were not present in the uploaded source archive.

## Overleaf

Upload this ZIP as a new project, select `main.tex` as the main document, and use pdfLaTeX. The bibliography is generated from `refs.bib` with BibTeX. Standard TeX Live installations provide IEEEtran, TikZ, algorithm, and algpseudocode.

## Local build

```sh
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Recheck pagination after author changes or a change of TeX distribution. The delivered 10-page count applies to the included compiled PDF, not to arbitrary future revisions.

## Important verification boundary

Numerical results were preserved and checked against the supplied manuscript, not independently recomputed. Pseudocode was reconstructed from the supplied algorithm and prose, not verified against experimental code. Resolve the author-confirmation items before representing the paper as independently reproducible or fully submission-certified.
