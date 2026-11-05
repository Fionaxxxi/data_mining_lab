# Project instructions

- Canonical repository: https://github.com/Fionaxxxi/data_mining_lab. Preserve origin and existing history.
- Local project directory: D:\data_lab\scenic_lab1.
- Use only D:\miniconda3\envs\dm_scenic_lab for project dependencies and execution; never base, user site-packages or another project environment.
- Organize code in src/labN/, experiment-specific input in data/labN/, and results in outputs/labN/. Preserve existing experiment 1 paths in data/ and outputs/cleaned_data.jsonl because later experiments consume them.
- run.ps1 -Lab N runs an experiment; -Lab all runs 1 through 6 offline with saved inputs. Online acquisition requires explicitly invoking its script.
- Keep concise Markdown experiment reports at the root. Plans and stage acceptance reports belong in docs/. Keep one primary plan and one primary acceptance report per stage.
- Historical Word files, generators and logs belong in archive/labN/; do not generate Word unless explicitly requested. Archived scripts are historical evidence, not supported entry points.
- Keep large original corpus shards/candidate JSONL in Git LFS. Preserve provenance; do not invent URLs, experimental results or student contributions.
- Experiment 3 retains its own saved source/sample data under data/lab3/, rather than claiming it consumes experiment 1 text. Preserve algorithm limitations and historical evidence.

- Active lab3 is the Huangshan/Jiuzhaigou/Zhangjiajie version from commit 6d4750c, migrated into src/lab3, data/lab3 and outputs/lab3. The original current-version snapshot is retained under archive/lab3/versions/upstream_6d4750c.
- Lab6 uses current lab3 routes and labs1/2/4/5 evidence; run.ps1 -Lab 6 builds, queries, renders and validates. Its single report is 实验六报告.md. Old lab3/lab6 versions were deleted at the user's explicit request on 2026-11-05.
