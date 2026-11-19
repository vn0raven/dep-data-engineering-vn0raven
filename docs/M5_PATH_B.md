# M5 Path B — Davao Transport Data Observatory

## Purpose and scope

The original commuter-routing concept revealed a prerequisite: dependable underlying transport data. M5 standardizes the register and evaluates source completeness, spatial quality and unresolved associations. Future Network X-Ray and Route Verification Workbench functions will use this foundation; M5 implements analysis and QA, not those application features.

The central conclusion is: **We standardized the transport register, measured its completeness and spatial quality, and identified the unresolved associations that the Observatory's verification workflow must address.**

## Official requirement mapping

Verified against the [official checklist](https://github.com/dataengineeringpilipinas/dep-data-engineering-open-track/blob/main/docs/MILESTONE_CHECKLIST.md) and local Weeks 17–20 materials. No separate numerical grading rubric was found in the inspected sources.

| Requirement | Evidence |
|---|---|
| Segmentation across 2–3 dimensions with comparisons | Mode × classification × GIS status; directional/metadata comparisons; cleaned mode × association status; LGU-label proxy |
| 3–5 KPIs with logic and trends | Five primary OSM metadata KPIs, each with July 8 and August 1 observations, formulas, numerators and denominators |
| One-page plain-language brief or notebook section | Concise generated stakeholder brief embedded in executed notebook |
| Integrated runnable pipeline | scripts/run_m5.py, source extraction, read-only audit, immutable-release verification, aggregate projection, figures and notebook execution |
| Professional repo and dependencies | README, locked and compatible dependencies, tests, explicit public file list and privacy review |
| Prerequisite M4 | Human passed at 26a7f7e; accepted analysis preserved |

Final execution and test evidence: reports/m5/QA_REPORT.md. This local checklist is not a claim of human M5 acceptance.

## Source populations and grains

| Population | Count | Meaning |
|---|---:|---|
| LTFRB workbook records | 285 | Register rows, not confirmed active services |
| Unique linked IDs | 266 | Source-file references, not route counts |
| Inspected layers | 262 | Spatial tables read from files |
| Spatial features | 266 | Individual geometries across layers |
| All direction slots | 570 | Two slots per workbook record |
| Populated direction slots | 442 | Excludes 128 explicit loop second-slot N/A values |

The geographic charts count distinct slash-separated source labels per route across either direction. These counts are non-additive and are not measured municipal coverage, confirmed stops or accessibility. Homonyms and province context are unresolved. OSM mapping relations and LTFRB records are never treated as equivalent denominators. DC Bus, fare and Love Bus facts are not used in M5 calculations.

## Five primary OSM KPIs

Named mapped stops, geocoded stops, route relations with ordered stop members, origin metadata and destination metadata. Formula: 100 × numerator / eligible stop or bus/ferry relation denominator, null if empty. Each target is an analytical completeness goal, not official approval. Full definitions: data/processed/m5/kpi_definitions.csv and JSON.

Both real snapshots produce 57.38%, 96.72%, 50%, 42.86%, 42.86% respectively. Zero percentage-point changes are actual aggregate observations, not absent results. The same unchanged M3 selection is applied independently. Repeated cross-sections do not establish service, ridership, causality or a long-term trend. July's exact access time is unavailable; August's original SHA-256 matches after Git CRLF-to-LF normalization, with original bytes left untouched.

## Cleaned LTFRB baseline

The private version 709ce26a035742a54735 retains all records and original values, recording 3,248 transformations. The detailed release includes provenance, dictionary, structured issues, uncertain records, SQLite and geometry-pass/quarantine separation. M5 publishes only an allowlisted aggregate projection; the release's raw rows, Drive IDs, paths, WKB and geometry are excluded.

The cleaned baseline is a single source observation, not a historical series. Its metrics have explicit grain, numerator, denominator, formula, threshold, source version and interpretation in cleaned_quality_kpis.csv/JSON. Results: 262/266 inspected source assets; 262/262 CRS-consistent layers; 263/266 structurally passing features; 324/442 populated directions unresolved; 171/285 route review cases. Legacy layer-level screening is 259/262 and uses a different denominator from the feature pass rate.

Candidate lengths: 118 comparisons, zero flags above max(0.5 km,10% declared length). A match requires conservative file/layer/direction evidence; all matches remain candidates, not authority-confirmed route identity. Unpaired directions are never counted as passes. Navigation readiness remains undefined/not verified.

## Reproduction

From repository root after installing requirements-lock.txt in Python 3.12:

```powershell
.\.venv\Scripts\python.exe scripts/run_m5.py --execute-notebook
.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/m5/pytest-results.xml
.\.venv\Scripts\python.exe scripts/check_m5_privacy.py
```

This public path rebuilds all displayed analysis from aggregate inputs. OSM results can also be recalculated from committed snapshots. Full private-source refresh:

```powershell
.\.venv\Scripts\python.exe scripts/run_m5.py --workbook "<private workbook.xlsx>" --gis-dir "<private geographic directory>" --execute-notebook
```

This executes extraction, GIS audit, cleaned ETL (or immutable release verification), source-hash-checked projection, figures, brief and notebook. An existing private release can be integrated using `--release <private release directory>`. A reviewer without restricted inputs cannot independently recreate raw-source GIS findings; the committed aggregates preserve reproducibility of the displayed analysis.

## Limits and release boundary

No geometry repair, source-record merge, current service, schedule, fare, boarding point, actual transfer or travel time is inferred. Complete cross-route overlap/topology analysis and canonical place matching are future work. Source authenticity and publication permission are separate from a checksum or geometry pass. Treat raw and detailed government-derived data as restricted unless explicitly cleared. Passing automated privacy checks is not licensing approval.
