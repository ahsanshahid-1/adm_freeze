# Available Is Not Enforced: A Resource-Matched Benchmark of Verification in Agentic Data Mining

Submission to the 4th International Workshop on Trustworthy and Aligned AI at IEEE BigData 2026
(full paper, 10 pages including references, IEEE two-column, single-blind). Deadline 16 Nov 2026 AoE.

| File | Content |
|---|---|
| `main.tex` | LaTeX source (IEEEtran conference class) |
| `refs.bib` | Bibliography (58 entries, all cited) |
| `figures/fig_main.pdf` | Fig. 1, generated from the E1 run records by `analysis_postfreeze/make_figure.py` |
| `main.pdf` | Compiled paper |
| `overleaf_upload.zip` | The three source items above, ready to upload to Overleaf |

## Compile

pdfLaTeX (for example Overleaf): upload `overleaf_upload.zip` as a new project and compile `main.tex` with
pdfLaTeX + BibTeX. Locally: `pdflatex main && bibtex main && pdflatex main && pdflatex main`.
The `\ifXeTeX` block in the preamble only selects a Times clone when compiling with XeLaTeX or Tectonic.

Every number in the paper comes from the frozen final report or from the scripts in `analysis_postfreeze/`
run on the formal run records.
