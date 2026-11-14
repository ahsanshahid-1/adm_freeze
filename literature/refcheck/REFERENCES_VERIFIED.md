# Reference verification log (2026-11-11, America/Chicago)

Every entry in `../refs.bib` was checked against the source listed here. Author lists were copied from the
source, not from memory. Raw records: `arxiv_meta.json` (arXiv abstract-page `citation_*` metadata and abstract,
fetched by `arxiv_meta.py`), `crossref_meta.json` (Crossref API, fetched by `crossref_meta.py`).

Rules used:
- A peer-reviewed venue is cited only when the venue's own site (ICLR/PMLR/NeurIPS/MLSys proceedings, Crossref DOI
  record) or an author-written arXiv comment confirms it. Otherwise the arXiv preprint is cited.
- Where the published author list differs from arXiv, the published list is used (noted below).
- Claims in the paper about a work are limited to what its abstract or the checked page states.

| Key | Verified against | Venue status | Notes |
|---|---|---|---|
| jing2025dsbench | arXiv 2409.07703; ICLR 2025 proceedings page | ICLR 2025 (proceedings page) | 34.12% figure from abstract |
| nam2025dsstar | arXiv 2509.21825 (abs + HTML v1) | preprint | verifier agent = LLM judge (Sec. 3.2 of the paper) |
| egg2025dabstep | arXiv 2506.23719 | preprint | >450 tasks, 14.55% hard-task accuracy |
| ma2026dab | arXiv 2603.20576 v3 (abs metadata + v3 HTML author block, rechecked 2026-11-12) | preprint | 104 queries, 17 datasets, 4 DBMS, 57% pass@1; v3 paper lists Adit Chintamaneni, the arXiv metadata does not; paper list used |
| xu2026oneflow | arXiv 2601.12307 (rechecked 2026-11-12) | preprint | single agent matches homogeneous workflows; KV-cache reuse |
| fadlallah2026dqa | arXiv 2606.13692 (rechecked 2026-11-12) | preprint | feasibility validation stage before deterministic execution |
| hu2024infiagent | arXiv 2401.05507; PMLR v235 page hu24s (search result) | ICML 2024 | question counts differ across versions (311/55 in v1, 257/52 in v3); paper avoids counts |
| guo2024dsagent | PMLR v235 guo24b (BibTeX on page) | ICML 2024, pp. 16813-16848 | |
| hong2024datainterpreter | arXiv 2402.18679 | preprint | |
| chan2025mlebench | arXiv 2410.07095; ICLR 2025 proceedings page (search result) | ICLR 2025 | 75 competitions |
| lei2025spider2 | arXiv 2411.07763 (author comment "ICLR 2025 Oral") | ICLR 2025 | |
| liu2025datagovbench | arXiv 2512.04416 | preprint | 150 tasks |
| fadlallah2026cleaning | arXiv 2608.14765 | preprint (submitted to New Generation Computing) | F1 0.561 for deterministic baseline |
| yao2023react | arXiv 2210.03629 (abs + HTML author block) | ICLR 2023 (author comment) | |
| jimenez2024swebench | arXiv 2310.06770 (abs + HTML author block) | ICLR 2024 (author comment) | |
| wu2023autogen | arXiv 2308.08155 | preprint | |
| hong2024metagpt | arXiv 2308.00352; ICLR 2024 proceedings page (search result) | ICLR 2024 | |
| cemri2025mas | arXiv 2503.13657 | preprint | MAST, 1600+ traces, 3 categories |
| tran2026single | arXiv 2604.02460 | preprint | |
| fu2026moreagents | arXiv 2606.05670 (v2, 9 Oct 2026; rechecked 2026-11-12) | preprint | BenchAgent; EvoAgent the only MAS above Core. A reviewer reported a retitled 7-author version; v2 on arXiv still has the original title and 8 authors incl. Z. Wen, so the citation is unchanged |
| jwalapuram2026illusion | arXiv 2606.13003 abs metadata + v2 HTML (12 Nov 2026) | preprint | located via the HackerNoon article's link; budget-control sentence found verbatim in the introduction; affiliations Salesforce Research, HKUST (Guangzhou), UBC, NTU |
| besanson2026sarcdq | arXiv 2607.26313 abs metadata (12 Nov 2026) | preprint | abstract does not name the model tiers; the paper says "four model tiers spanning about 15x in inference price" only |
| li2026limbo | arXiv 2609.29095 abs metadata (12 Nov 2026) | preprint | LIMBO sandbox; 0.5% / 56% / 74% / 28%->4% from the abstract |
| zhang2026rethinking | arXiv 2610.34577 abs metadata (12 Nov 2026) | preprint | 17 designs, 7 frontier coding models |
| zhang2026rite | arXiv 2610.27777 abs metadata (12 Nov 2026) | preprint | 10 LLMs; model names not in the abstract, so not cited |
| yang2026overreliance | arXiv 2609.05587 abs metadata (12 Nov 2026) | preprint | 14 models; 68.0% web-search adoption |
| sharma2026contextcov | arXiv 2603.00822 abs metadata (12 Nov 2026) | preprint | 88.3% vs 67.0% vs 50.3% |
| faghih2025toolprefs | arXiv 2505.18135 abs metadata (12 Nov 2026) | EMNLP 2025 main (author comment) | >10x usage from edited descriptions |
| li2026silent | arXiv 2610.14115 abs metadata (12 Nov 2026) | preprint | suggested by an independent reviewer; 220 tasks, six failures |
| besanson2026onegate | arXiv 2608.18360 abs metadata (12 Nov 2026) | preprint | suggested by an independent reviewer |
| parmar2026debate | arXiv 2606.02866 abs metadata (12 Nov 2026) | preprint | suggested by an independent reviewer |
| grafberger2021mlinspect | Crossref DOI 10.1145/3448016.3452759 | SIGMOD 2021 (demo), pp. 2736-2739 | |
| wang1996beyond | Crossref DOI 10.1080/07421222.1996.11518099 | JMIS 12(4):5-33 | |
| (not cited) JENGA, BART, KramaBench, AGATE, PACE | not verified in this pass | -- | suggested by reviewers; add only after checking the source |
| kim2025scaling | arXiv 2512.08296 abs metadata (12 Nov 2026) | preprint | 260 configurations; +80.8% to -70.0%; centralised verification finding from the abstract |
| dylan2026equalcost | arXiv 2609.04217 | preprint | MA-Evolve; 0.769 vs 0.754, p=0.80 |
| shinn2023reflexion | Crossref DOI 10.52202/075280-0377 | NeurIPS 2023, pp. 8634-8652 | NeurIPS list has 5 authors; arXiv lists 6 (adds Edward Berman). Published list used |
| huang2024selfcorrect | arXiv 2310.01798 (author comment "ICLR 2024") | ICLR 2024 | |
| gou2024critic | arXiv 2305.11738 (author comment "ICLR 2024") | ICLR 2024 | |
| zhu2025abc | arXiv 2507.02825; ABC.md in github.com/uiuc-kang-lab/agentic-benchmarks | preprint | items II.7 (solvable) and II.8 (oracle solver) checked in ABC.md |
| wang2026dbe | arXiv 2605.06213 | preprint | |
| ge2026psychometrics | arXiv 2604.00594 | preprint | |
| kapoor2023leakage | Crossref DOI 10.1016/j.patter.2023.100804 | Patterns 4, 100804 (2023) | issue number not in Crossref record, omitted |
| polyzotis2019datavalidation | MLSys 2019 proceedings page + official BibTeX | MLSys 2019, vol. 1, pp. 334-347 | official first author is Polyzotis (not Breck) |
| schelter2018deequ | Crossref DOI 10.14778/3229863.3229867; abstract via OpenAlex (12 Nov 2026) | PVLDB 11(12):1781-1794 | |
| sculley2015debt | NeurIPS proceedings page + official BibTeX | NIPS 2015, vol. 28 | |
| li2021cleanml | Crossref DOI 10.1109/icde51399.2021.00009; arXiv 1904.09483 | ICDE 2021, pp. 13-24 | |
| rekatsinas2017holoclean | Crossref DOI 10.14778/3137628.3137631 | PVLDB 10(11):1190-1201 | |
| narayan2022wrangle | Crossref DOI 10.14778/3574245.3574258; arXiv 2205.09911 | PVLDB 16(4):738-746 | PVLDB lists 4 authors; arXiv lists 5 (adds Simran Arora). Published list used |
| chu2016cleaning | Crossref DOI 10.1145/2882903.2912574; abstract via OpenAlex (12 Nov 2026) | SIGMOD 2016, pp. 2201-2206 (tutorial) | |
| jimenez2024swebench | (see above) | ICLR 2024 | now cited; "evaluated against real tests" from the paper's Figure 1 caption |
| w3c2013provdm | w3.org/TR/prov-dm (editors block) | W3C Recommendation, 30 Apr 2013 | editors Moreau and Missier |
| namaki2020vamsa | Crossref DOI 10.1145/3394486.3403205 | KDD 2020, pp. 1542-1551 | |
| holm1979 | Scanned original (ime.usp.br) via search; PubMed citation | Scand. J. Statist. 6:65-70 | issue number not confirmed, omitted |
| efron1979bootstrap | Crossref DOI 10.1214/aos/1176344552 | Ann. Statist. 7(1):1-26 | |
| saravanan2020hierarchical | arXiv 2007.07797 | preprint | |
| kwon2023vllm | Crossref DOI 10.1145/3600006.3613165 | SOSP 2023, pp. 611-626 | |
| vllm2026structured | docs.vllm.ai page title "Structured Outputs - vLLM" (HTTP 200) | documentation | |
| pedregosa2011sklearn | jmlr.org citation_* metadata | JMLR 12(85):2825-2830 | |
| sklearn2026pitfalls | scikit-learn.org page title (1.9.1 docs) | documentation | |
| raasveldt2019duckdb | Crossref DOI 10.1145/3299869.3320212 | SIGMOD 2019, pp. 1981-1984 | |
| qwen2026qwen38 | Hugging Face API: sha 37561816..., created 2026-08-05, apache-2.0, 27,781,427,952 params | model card | revision equals the locked revision |
| google2026gemma4 | Hugging Face API: sha 842da379..., created 2026-03-11, apache-2.0, 31,273,088,876 params | model card | revision equals the locked revision |
| uci601ai4i / matzka2020ai4i | UCI API (DOI 10.24432/C5HS5C); Crossref DOI 10.1109/ai4i49448.2020.00023 | dataset; AI4I 2020 pp. 69-74 | UCI abstract: synthetic dataset |
| uci198steel | UCI API (DOI 10.24432/C5J88N; creators Buscema, Terzi, Tastle; 2010) | dataset | |
| uci165concrete / yeh1998concrete | UCI API (DOI 10.24432/C5PK67); Crossref DOI 10.1016/s0008-8846(98)00165-3 | dataset; CCR 28(12):1797-1808 | |
| uci242energy / tsanas2012energy | UCI API (DOI 10.24432/C51307); Crossref DOI 10.1016/j.enbuild.2012.03.003 | dataset; Energy Build. 49:560-567 | |

Licence check (2026-11-12): the dataset pages for UCI IDs 601, 198, 165 and 242 each state "Creative Commons
Attribution 4.0 International (CC BY 4.0)" and link to creativecommons.org/licenses/by/4.0/legalcode. CC BY 4.0
requires attribution, which the paper gives through the dataset citations.
