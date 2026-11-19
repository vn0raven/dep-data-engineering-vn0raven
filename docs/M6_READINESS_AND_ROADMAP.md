# M6 readiness and roadmap — target December 6, 2026 PHT

## Achievable product

Deploy a static transport data-quality dashboard and reproducible aggregate pipeline. Full offline trip planning remains a later architecture objective, conditional on verified boarding points, service activity, route topology, schedules, fare applicability and field evidence. Do not synthesize missing operations.

## Readiness

Implemented locally: private workbook staging, read-only GIS audits, checksums, aggregate versions, five dated mapping KPIs, segmentation, static dashboard, notebook and synthetic/regression tests. M4 passed human review at 26a7f7e; reviewer confirmation was supplied November 19, 2026. GitHub workflow configuration exists but its remote execution and a live public URL have not been verified or triggered by this delivery.

## Schedule

| Window (PHT) | Action | Exit evidence |
|---|---|---|
| Nov 18–22 | Owner review; resolve four source-file exceptions; review invalid geometries and exact linework pair | Private correction log; rerun audit; M5 reviewed submission snapshot |
| Nov 23–27 | Confirm aggregate release permissions; run QA workflow after authorized push; review failure logs | Green workflow run, downloadable report evidence, versioned aggregate manifest |
| Nov 28–Dec 2 | Review existing GitHub Pages workflow; authorize deployment; verify /m5.html and all assets | Public URL, HTTP success and link checks, screenshot; add verified URL to README |
| Dec 3–5 | Rehearse 5–10 minute demo; refresh documentation and outstanding issue log | Reproducible fresh setup and recorded demo checklist |
| Dec 6, before 23:59:59 | Submit M6 form with exact pushed snapshot and verified live URL | Issue URL, commit hash, public URL and reviewer queue status |

## Deployment and automation

Existing `.github/workflows/pages.yml` deploys dashboard/ on main-branch dashboard changes. It is preserved. New `m5-qa.yml` provides manual/PR aggregate QA without government data and uploads test/notebook reports. User authorization is required before push or publication; no remote execution is claimed.

Keep processed output checksums, source versions and validator version in release manifests. For new private GIS data run the full local pipeline first, review failures, and release aggregates only after permission review. A scheduled raw-data refresh is deferred until a licensed stable acquisition process and permitted credentials are defined. Do not place private Drive URLs or raw government files in public Actions artifacts.

Monitoring: fail on script/notebook/test errors; inspect file audit statuses, missing sources, invalid/null/empty geometry, CRS mismatches and unpaired direction rates. All quality targets are analytical gates, not transport authority approval. Assign data-owner review to every exception; do not silently repair originals.

## Demo script (7 minutes)

1. (1 min) Explain commuter goal and why verified data comes before routing.
2. (1 min) Show separate OSM, LTFRB and DC Bus provenance.
3. (2 min) Walk through mode/status comparisons and GIS audit exceptions.
4. (1 min) Show five OSM KPIs across actual snapshots and explain unchanged values.
5. (1 min) Rebuild outputs and show tests and notebook evidence.
6. (1 min) Show deployed URL after verification, limits and next source-owner actions.

## Longer-term offline architecture

Versioned licensed source ingestion → provenance-preserving staging → reviewed route/direction/stop identity tables → validated connected graph and approved transfer edges → operational schedule/fare evidence → compact offline export → mobile routing. Each stage requires evidence before promoting data. The current delivery ends at mapping-quality aggregates.
