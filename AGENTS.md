# Project instructions

- Canonical GitHub repository: https://github.com/Fionaxxxi/data_mining_lab
- Local project directory: D:\data_lab\scenic_lab1
- All future work on this data-mining course project belongs to this repository. Preserve the `origin` remote and use its existing branches/history.
- Use the dedicated Conda environment D:\miniconda3\envs\dm_scenic_lab for project dependencies and execution. Never use base or another project's environment.
- Organize code by experiment: src/lab1/ for data collection/preprocessing, src/lab2/ for entity extraction/validation, and src/labN/ for future experiments. run.ps1 -Lab N selects an experiment; -Lab all runs completed experiments in order.
- Current reports are 实验一报告.md and 实验二报告.md in the project root. Use concise Markdown reports with tables where helpful; do not fill or export Word reports unless explicitly requested again.
- Historical Word generation, report drafts, screenshots and exploratory review artifacts are retained under archive/lab1/. They are not active experiment entry points. Optional corpus exploration utilities are in src/lab1/tools/.
- Keep experiment 1 data paths (data/ and outputs/cleaned_data.jsonl) stable because experiment 2 consumes them. Experiment 2 outputs belong to outputs/lab2/.
- Keep original corpus shards and large candidate JSONL files in Git LFS; keep selected data and final structured results available in the repository.
- Preserve real provenance and disclose missing original web URLs; do not invent sources, experimental results, personal details, or student contributions.
