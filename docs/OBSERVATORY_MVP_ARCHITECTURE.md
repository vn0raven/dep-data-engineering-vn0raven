> Update, 23 November 2026: see [controlled-layer implementation](M6_CONTROLLED_LAYERS.md) for the current local real-data application, publication boundary and commands. Earlier sections below document the prior stage.

# Observatory MVP architecture and M6 delivery

The Davao Transport Data Observatory will support documented-network exploration and evidence review across modes. Its foundation is the private versioned LTFRB ETL. No new UI prototype, live feed, commuter routing engine or prediction model is required to demonstrate this implementation.

## Practical first deployment

Use one Python application with FastAPI and SQLite for the first functional backend. Read only a validated immutable release, with separate SQLite storage for append-only review decisions. The application must never write into raw sources or a release directory. A later multi-user deployment can migrate spatial indexing and geometry queries to PostGIS if necessary.

FastAPI, API endpoints and durable review storage are a plan, not implemented dependencies or capabilities in this ETL delivery.

```text
Local official source package
  → deterministic intake inventory and hashes
  → normalization and isolated spatial audit
  → immutable private release with manifest
  → explicit publication review / approved release projection
  → read-only API
  → interactive network map, route details and comparisons
Separate reviewer store → append-only decisions and evidence references
```

Government-provided data is available for this local analysis. External redistribution remains a separate documented decision. Define the approved public projection before deployment. Never expose original_record_json, source WKB, private paths or source documents automatically through an unrestricted endpoint.

## MVP functions and acceptance tests

| Function | Proposed API / behavior | Acceptance evidence |
|---|---|---|
| Release health | GET /health and /releases/current | Returns exact manifest ID; refuses corrupt/missing release |
| Route exploration | GET /routes?mode=&classification=&q=; GET /routes/{id} | Stable IDs, pagination, provenance and uncertain-association labels |
| Interactive map | GET /features?bbox= | Bounding-box validation, response limits and EPSG:4326 linework; quarantine excluded |
| Direction evidence | GET /routes/{id}/directions | Explicit loop N/A, candidate confidence, length denominator and mismatch flags |
| Quality indicators | GET /quality | Source IDs, layers and features use distinct denominators |
| Source evidence | GET /sources/{id} | Source hashes, declared CRS, validation reason; access-controlled details as appropriate |
| Geographic comparison | Selected area/corridor intersection | Report geometry intersections; do not label as boarding access or current service coverage |
| Review queue | GET /issues; authenticated POST /reviews | Append-only evidence note, reviewer identity, timestamp and release/entity reference; never implies official approval |

Before shared-corridor statistics, define projected CRS/distance tolerances, opposing-direction treatment, map matching and near-duplicate handling. The current pipeline reports exact duplicate geometry; it has not computed a network graph or overlap score. Do not ship arbitrary buffer overlap as confirmed route equivalence.

## Scheduling and operations

Run the ETL on arrival of a new source package. A Windows Task Scheduler task or a private controlled runner can call the existing CLI. Scheduling, runner credentials and source downloading are not configured by this delivery. Do not repeatedly reprocess unchanged raw bytes and describe it as fresh transport data.

On failure, keep the last complete release available and expose the failed run separately. Monitor missing/incomplete assets, geometry quarantine, association resolution and manifest integrity. Alert on new failures or changed source counts. Do not hardcode 285 as an eternal contract: it is the current baseline, not a guarantee for future source releases.

## Deployment choices

GitHub Pages can host an approved static map and aggregate report. It cannot execute a Python API or store real review writes. Deploy the Python service separately only after selecting an authorized host and defining credentials, retention and allowed public fields. A local/private functional application is a useful engineering artifact while publication decisions are pending, but it does not satisfy the course's public Pages requirement by itself.

Retain the existing Pages workflow for M4/M5. Investigate the exact failed build log before changing deployment configuration; a prior screenshot showed a Jekyll build failure but did not establish the root cause.

## Sequence toward December 6, 2026 PHT

| Window | Deliverable | Gate |
|---|---|---|
| November 18–22 | Review cleaned release; source exception ledger; agree public fields | ETL tests, raw-byte preservation and output round trips |
| November 23–27 | Implement release-backed API and map; evidence pages | Contract tests and honest uncertainty labeling |
| November 28–December 2 | Implement authenticated append-only review workflow; geographic comparison | No raw/release edits; user input validation and provenance |
| December 3–5 | Authorized deployment, public artifact checks and 5–10 minute demonstration | Verified URL, API checks, fresh-setup reproduction |
| December 6 before 23:59:59 | M6 submission snapshot | Actual pushed commit, live URL, demo and reviewer evidence |

## Submission evidence

- Existing M4/M5 preservation checks and their test results.
- New ETL CLI, transformation rules, dictionary, dependencies and synthetic tests.
- Source checksum manifest and before/after counts with private detail handled appropriately.
- Evidence of same-input release reuse, changed-input asset-cache reuse and tamper rejection.
- Spatial round-trip and SQLite integrity/foreign-key results.
- Approved public dataset projection, verified hosted URL and actual remote workflow results if deployed.
- Demo: process package → inspect quarantine → explore accepted geometry → review evidence → trace every result to its source version.

No deployment, GitHub push, milestone acceptance or live observation feed is claimed by this plan.
