# References and research lineage

Every reference file cites this one by bracket number. The numbering is stable — do not renumber, or
every citation in the skill points at the wrong paper.

| # | Work | Where it is used here |
|---|---|---|
| [1] | Patil et al. (2025), *The Berkeley Function Calling Leaderboard (BFCL): From Tool Use to Agentic Evaluation of Large Language Models*, ICML. | Tool-call and argument evaluation as structured-data comparison — `references/tool-and-argument-metrics.md` |
| [2] | Yao et al. (2024/2025), *tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains*. | Final-database-state scoring and `pass^k` — `references/reliability.md` |
| [3] | Lu et al. (2025), *ToolSandbox: A Stateful, Conversational, Interactive Evaluation Benchmark for LLM Tool Use Capabilities*. | State dependencies and milestone checks — `references/reliability.md` |
| [4] | Liu et al. (2023, revised 2025), *AgentBench: Evaluating LLMs as Agents*. | Multi-environment agent scenario slicing — `jobs/run-eval-pass.md` |
| [5] | Mialon et al. (2024), *GAIA: a benchmark for General AI Assistants*, ICLR. | Long-horizon assistant task design — `jobs/run-eval-pass.md` |
| [6] | Zhou et al. (2023), *WebArena: A Realistic Web Environment for Building Autonomous Agents*. | Realistic environment + end-state checking — `specs/case-schema.md` |
| [7] | Liang et al. (2022), *Holistic Evaluation of Language Models (HELM)*. | Multi-metric reporting: robustness, calibration, efficiency — `references/efficiency-and-calibration.md` |
| [8] | Es et al. (2024), *RAGAs: Automated Evaluation of Retrieval Augmented Generation*, EACL System Demonstrations. | Retrieval quality vs generation faithfulness — `references/grounding-and-judges.md` |
| [9] | Zheng et al. (2023), *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, NeurIPS. | Judge biases: position, verbosity, self-enhancement, reasoning — `references/grounding-and-judges.md` |
| [10] | Debenedetti et al. (2024), *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents*. | Prompt injection through tool-returned data — `references/safety.md` |
| [11] | Jarvelin & Kekalainen (2002), *Cumulated Gain-Based Evaluation of IR Techniques*, ACM TOIS 20(4). | DCG/IDCG/NDCG — `references/ranking-metrics.md` |
| [12] | OpenAI / SWE-bench authors (2024, updated 2025), *Introducing SWE-bench Verified*. | Benchmark quality biases measured capability — `references/aggregation.md` |
| [13] | Rana et al. (2025), *AgentChangeBench: Goal-Shift Robustness in Conversational AI*. | Goal-shift stress row — `references/reliability.md` |

## Locators

Public identifiers only, so a reader can find the source without this document:

| # | Locator |
|---|---|
| [1] | proceedings.mlr.press/v267/patil25a.html · gorilla.cs.berkeley.edu/leaderboard |
| [2] | arXiv:2406.12045 |
| [3] | machinelearning.apple.com/research/toolsandbox-stateful-conversational-llm-benchmark |
| [4] | arXiv:2308.03688 |
| [5] | proceedings.iclr.cc, 2024 · GAIA, Abstract-Conference |
| [6] | arXiv:2307.13854 |
| [7] | arXiv:2211.09110 |
| [8] | aclanthology.org/2024.eacl-demo.16/ |
| [9] | NeurIPS 2023 Datasets and Benchmarks proceedings |
| [10] | arXiv:2406.13352 |
| [11] | doi:10.1145/582415.582418 |
| [12] | openai.com/index/introducing-swe-bench-verified/ |
| [13] | openreview.net, forum id ZCi58UP9uR |

## Research note — read this before citing the skill

**This playbook synthesizes benchmark design patterns rather than claiming that every metric is
standardized by one paper.** Several engineering metrics — **JSON-field F1, LCS trajectory score,
citation F1, retry efficiency, and lower-tail aggregation** — are *derived diagnostics*, included
because they make failures easier to localize in production traces.

Say which is which when you report. Presenting a derived diagnostic as a standardized benchmark metric
invites a comparison against published numbers that were never computed the same way, and the
comparison is then wrong in a direction nobody can audit. The normalization problem for the LCS
trajectory score is spelled out in `references/tool-and-argument-metrics.md`.
