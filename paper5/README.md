# Paper 5: Do LLM Agents Verify Their Data? Available vs. Enforced Checks in Data Mining

Paper 4 with the text-level revisions from the co-author's recommendations report (16 Nov 2026). Papers 1-4 are unchanged.
- Rec. 1: the evaluated treatment is named "the tested enforced-check configuration", with the four differences listed.
- Rec. 3: plausible ranges explained as training-derived statistical expectations; Table II gives two rejected valid values.
- Rec. 4: post-hoc gate-acceptance audit of the oracle's correct workflows on all 1,080 E1 instances
  (`analysis_postfreeze/gate_acceptance_audit.py`; output `results/analysis/gate_audit.json`).
- Rec. 8 and 12: run-outcome table (verified, invalid, abstain, budget, error) with tokens per run and per verified run.
- Rec. 10: H1 per family-repetition block.
- Rec. 13: exact timeline in Section VIII.
- References: SPADE and AI Agents That Matter added; published version of Saravanan et al.; arXiv version of Wang et al. pinned.
- Proposed follow-up experiments listed in the conclusion (not run).
The positioning table of paper 3/4 was removed to stay within 10 pages.
