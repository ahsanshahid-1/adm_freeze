# Final validation report

This report concerns manuscript preservation, document consistency, and layout. It is not an independent replication of the experiment.

| Check | Outcome |
|---|---|
| Main result table | PASS — All 35 completion-rate values match the original source exactly. |
| Contrast table | PASS — Every original numerical estimate, confidence limit, and secondary p-value matches. The only added numerical cell is primary p=1.000, transferred from p=1.0 in the original prose. |
| Primary p-value source | PASS — Original results prose explicitly reports primary sign-flip p=1.0. |
| Run-count arithmetic | PASS — E1=7,560; E4=540; E5=252; total=8,352. E6 remains a separate audit. |
| Original results figure | PASS — Preserved byte-for-byte. SHA-256: 962ae0c7f3c925a14d6e0036617dfcbe4123bf66a56f29cec98bf236aaee1135 |
| Requested acknowledgment | PASS — Exact requested NSF sentence is present. |
| Requested AI disclosure | PASS — Exact supplied OpenAI paragraph is present; original Claude assistance is separately retained. |
| Affiliation | PASS — Requested center and institutional/address wording is present. |
| Citation resolution | PASS — All 59 unique cited keys resolve in refs.bib. |
| Build diagnostics | PASS — Final LaTeX log contains no overfull-box, undefined-reference, or LaTeX warning messages. Normal underfull justification notices are not compilation failures. |
| Standard page layout | PASS — Standard IEEEtran conference layout retained; no reduced body font, manual page-dimension overrides, or compressed line-spacing commands. |
| Total PDF length | PASS — 10 pages, including references, acknowledgment, and AI disclosure. |
| Page size | PASS — All pages are US Letter, 612 x 792 points. |
| Page-bound text | PASS — No extracted text spans extend outside the page boundaries. |
| Font embedding | PASS — All 24 PDF font entries are embedded. No font files are distributed in the source package. |

## Visual review

The original and revised PDFs were rendered. All ten revised pages were reviewed in a page montage, with detailed inspection of the title/abstract, related-work and dataset tables, architecture diagram, pseudocode, numerical result tables, results figure, acknowledgments/disclosure, and references. Arrow labels that crowded the first diagram rendering were removed; component responsibilities and interactions remain explained in the accompanying text.

## Not verified

Raw-record statistical reproduction; implementation-to-pseudocode fidelity; actual experimental model revisions; protocol registration timing; funding and historical AI-use attestations; and complete current venue-policy compliance. See AUTHOR_REVIEW_NOTES.md.
