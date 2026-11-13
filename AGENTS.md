# Project instructions

- Canonical repository: https://github.com/Fionaxxxi/data_mining_lab. Preserve origin and existing history.
- Local project directory: D:\data_lab\scenic_lab1.
- Use only D:\miniconda3\envs\dm_scenic_lab for project dependencies and execution; never base, user site-packages or another project environment.
- Organize code in src/labN/, experiment-specific input in data/labN/, and results in outputs/labN/. Preserve existing experiment 1 paths in data/ and outputs/cleaned_data.jsonl because later experiments consume them.
- run.ps1 -Lab N runs an experiment; -Lab all runs 1 through 7 offline with saved inputs. Online acquisition requires explicitly invoking its script.
- Keep concise Markdown experiment reports at the root for all labs. Organize every lab consistently under src/labN/, data/labN/ and outputs/labN/; put plans, test guides and run guides in docs/. Keep one primary plan and one primary acceptance report per stage.
- Do not recreate deleted historical archives unless explicitly requested. Do not generate Word unless explicitly requested; supported entry points are the current source and documented Markdown reports.
- Keep large original corpus shards/candidate JSONL in Git LFS. Preserve provenance; do not invent URLs, experimental results or student contributions.
- Experiment 3 retains its own saved source/sample data under data/lab3/, rather than claiming it consumes experiment 1 text. Preserve algorithm limitations and historical evidence.

- Active lab3 is the Huangshan/Jiuzhaigou/Zhangjiajie version from commit 6d4750c, migrated into src/lab3, data/lab3 and outputs/lab3. Historical archives have been deleted at the user's request.
- Lab6 uses current lab3 routes and labs1/2/4/5 evidence; run.ps1 -Lab 6 builds, queries, renders and validates. Its single report is 实验六报告.md. Old lab3/lab6 versions were deleted at the user's explicit request on 2026-11-05.
- Lab7 follows the shared layout: src/lab7/, data/lab7/, outputs/lab7/, root report 实验七报告.md, and supporting plans/guides in docs/. It reads outputs/lab6/ directly; do not maintain a duplicate graph snapshot. Keep local credentials in the ignored root .env; do not create or retain a distribution ZIP unless explicitly requested.
