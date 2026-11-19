# M5 review and exact submission instructions

## Local readiness

Preparation is complete subject to final owner review. M4 passed at 26a7f7e; Path B is acknowledged. M5 human acceptance, source publication clearance and remote CI are not claimed. All work remains uncommitted. Raw and detailed LTFRB data are restricted unless explicitly cleared; no force-add or blanket directory staging.

Review the executed notebook, reports/m5/M5_STAKEHOLDER_BRIEF.md, COMPLIANCE_CHECKLIST.md, QA_REPORT.md, CHANGES.md, PRIVACY_REVIEW.json and PUBLIC_FILES.txt. The candidate list includes code, documentation, source-safe aggregates and rendered report figures only. The prior private release ZIP and UI prototype are not included.

## Reproduce before staging

From the repository root, Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe scripts/run_m5.py --execute-notebook
.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/m5/pytest-results.xml
.\.venv\Scripts\python.exe scripts/check_m5_privacy.py
git diff --check
git status --short
```

For private inputs, run the full command in docs/M5_PATH_B.md. Public aggregate reproduction needs none of those government files. Do not substitute aggregate reproducibility for independent access to the underlying source.

## Only after explicit authorization to commit and push

The following commands are provided for review; they have not been executed by the agent:

```powershell
git add --pathspec-from-file=reports/m5/PUBLIC_FILES.txt
git diff --cached --name-only
git diff --cached --check
.\.venv\Scripts\python.exe scripts/check_m5_privacy.py
git diff --cached --stat
git commit -m "feat(m5): finalize Observatory analysis and cleaned quality baseline"
git rev-parse HEAD
git push origin main
```

Use the actual branch name if not working on main; inspect branch and remote before push. Since the privacy report changes after staging, inspect it and stage the updated report only if its results are acceptable. Never stage restricted files or execute git add -A. There must be no workbook, row-level release, GPKG/GeoJSON, SHP dependencies, private audit or source URL/ID detail in the staged set.

## Submit the actual pushed snapshot

1. Confirm the new full commit hash is visible in https://github.com/vn0raven/dep-data-engineering-vn0raven.
2. Check for an existing M5 issue for this builder. If present, revise that same issue with `/recheck <actual-full-hash>`; do not open a duplicate.
3. Otherwise open https://github.com/dataengineeringpilipinas/dep-data-engineering-open-track/issues/new/choose and select **Milestone 5 — Predictive / Alt Track**.
4. Builder: **Vhon Raven Dingal**. Cohort: **2026-A**. Repository URL: **https://github.com/vn0raven/dep-data-engineering-vn0raven**. Commit: actual pushed hash. Path: **Path B — Advanced EDA & Stakeholder Track**.
5. Link notebook, methodology, stakeholder brief, quality/segmentation outputs and QA evidence at that exact commit. Explain the Observatory direction, five OSM trends, separate cleaned LTFRB baseline, privacy boundary and unresolved source issues. M4 passed human review on issue #225 at 26a7f7e.
6. Check both-path and Path B checks only after validating the pushed snapshot. Leave Path A checks unchecked. Do not claim active routes or application deployment.

Suggested submission notes:

> We standardized the transport register, measured its completeness and spatial quality, and identified the unresolved associations that the Observatory's verification workflow must address. Path B compares mode/classification/GIS and direction segments, retains five OSM completeness KPIs across two actual snapshots, and integrates a separate cleaned LTFRB baseline. Restricted source records and geometry remain excluded; the repository includes aggregate analysis, source-to-aggregate code, executed notebook, brief and QA evidence. Two partial downloads, two incomplete SHP bundles, three invalid features and 324/442 unresolved populated directions remain disclosed. M4 passed at 26a7f7e. Network X-Ray and durable verification workflows are future M6 work.

The official M5 target was November 8, 2026 at 23:59:59 PHT; late submissions still receive review. M6 target is December 6, 2026 at 23:59:59 PHT. No issue submission or comment is authorized by this instruction document itself.
