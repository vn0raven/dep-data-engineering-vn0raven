> **Publication update — 23 November 2026:** The project maintainer explicitly authorized publication of the reviewed OSM and selected LTFRB-derived layer. This is not source-agency permission or an open licence. The exact checked release is `9440df8235fdf5f6df7f`; raw files, private source identifiers, reviewer identities and notes remain excluded. The website includes a correction/removal request link and commitment to take down affected material when necessary, including at the source agency's request. Earlier preparation status below is historical. Deployment verification will be recorded after the authorized push.

# M6 controlled layers: publication review and schema

## Current boundary (23 November 2026)

The deployed Pages app is the November 21 synthetic release. This local revision prepares real OSM exploration and an isolated OSM + LTFRB proposal. No new commit, push, deployment or agency correspondence has been performed. M5 passed human review at a75927d: https://github.com/dataengineeringpilipinas/dep-data-engineering-open-track/issues/256#issuecomment-7069250924 . December 6 remains the project target; the reviewer announced cohort closure December 11 and Demo Day December 12 at 7 PM PHT.

## Exact LTFRB field proposal

All fields below await publication authorization. They are derived from the verified private release, not openly licensed by this project.

| Field | Meaning and decision |
|---|---|
| route_id | New release-scoped ordinal ID, e.g. ltfrb-record-001. Does not expose internal IDs; not stable across future releases. Include for map/list links. |
| route_name | Normalized register name. Include as source description, not current service verification. |
| source | Literal LTFRB. Keep separate from OSM. |
| mode | Register mode PUJ/PUB/UV_EXPRESS. No conversion from OSM categories. |
| classification | EXISTING/IRIP as supplied. IRIP expansion not inferred. |
| geography | Distinct source locality labels; no claim of verified municipality identity. |
| observed_at | Explicitly unknown because the register's observation date is not supplied. |
| directions[].ordinal | Direction order within the register record. |
| directions[].direction | Documented direction text, nullable. |
| directions[].declared_km | Source-declared kilometres, nullable; not a measured journey distance. |
| directions[].association_status | candidate / unresolved / not_applicable_loop from existing conservative ETL. |
| quality | Controlled explanation of normalization, unverified geography and association limitations. No source free-text notes. |
| provenance | Fixed agency attribution and statement that redistribution terms were not specified. No download links. |
| geometry | Only structurally passing linework associated by existing candidate pairing. Retained as a candidate, never government-confirmed. Unresolved directions have no assigned line. |

Feature properties are exactly `route_ids`, `candidate_route_ids`, `status`, `source`, `association`. Feature envelopes contain `type`, new `id`, `geometry`, `properties`. Geometry may be LineString or MultiLineString in WGS84. Original and simplified linework are separate.

Excluded: raw workbooks and geographic files, source Drive links, internal record/direction/feature/file IDs, workbook hashes in individual records, source file paths, contributor identities, personal contact information, reviewer names, private notes, review history, original row JSON and unsupported active-service statements. The field allowlist rejects additional fields and checks LTFRB text for URLs, email markers and long identifier strings. This supports, but does not replace, human review of the exact record content.

Reviewable samples and the complete proposed export remain in the ignored `reports/observatory-private/publication-proposal/` directory. `REVIEW_SAMPLES.json` contains an actual candidate/unresolved example and a record without candidate map evidence. Review the complete bundle, not only these samples, before authorizing publication.

## Reproduce and preview

```powershell
.\.venv\Scripts\python.exe -m scripts.export_osm_public
.\.venv\Scripts\python.exe -m scripts.build_observatory_layers
.\.venv\Scripts\python.exe scripts/check_observatory_public.py
.\.venv\Scripts\python.exe -m scripts.build_observatory_layers --proposal
```

Public OSM preview (contains no government input files):

```powershell
.\.venv\Scripts\python.exe -m http.server 8767 --bind 127.0.0.1 --directory dashboard
```

Open http://127.0.0.1:8767/observatory/ . Isolated proposal preview:

```powershell
.\.venv\Scripts\python.exe -m http.server 8768 --bind 127.0.0.1 --directory reports/observatory-private/publication-proposal
```

Open http://127.0.0.1:8768/ . Durable private workbench:

```powershell
.\.venv\Scripts\python.exe -m scripts.observatory_app
```

Open http://127.0.0.1:8766/private/ . This workbench uses the full verified source release and its existing append-only review store. Static public/proposal exploration cannot write private decisions. Public synthetic review examples were removed from this prepared revision to avoid confusing annotations with real reviews.

## Schema, provenance and checks

`schema_version=1` bundles contain exactly publication, routes, features, provenance and display metadata alongside schema_version. Route fields and direction/feature allowlists above are enforced before export. Original OSM member identity is retained in the separate full OSM release; grouped map features represent one OSM relation each. OSM geography is the relation's from/to labels, not verified administrative coverage. Source observation dates remain visible in the inspector.

The OSM source checksum is compared after explicit CRLF-to-LF normalization. Exporter v2 excludes checkout-specific byte hashes from release identity so Windows and Linux can reproduce the same release. Existing releases are not overwritten. Bundles use sorted compact JSON; their manifest checksums determine a 20-character release version. The browser checks manifest identity and bundle/original-file hashes. The Pages gate checks exact filenames, hashes, OSM source labels and source URLs. It rejects proposals and unexpected files. The deployment's artifact visibility and per-attempt naming safeguards remain intact.

The build never copies the LTFRB proposal into dashboard/. Its local hostname guard is an additional precaution, not access control; the proposal must never be served publicly. There is deliberately no publication bypass switch. Authorizing a government release requires a separately reviewed change to the gate and exact artifact list.

## Map performance and semantics

Canvas retained after evaluating the real data: 14 OSM relations group 9,858 original members. The original database remains available under ODbL with visible attribution. A 10-metre topology-preserving simplification in EPSG:32651 reduces 143,277 coordinates to 38,481; the display bundle is approximately 1.29 MB and originals 3.53 MB. This is a projected display tolerance, not a geodesic accuracy guarantee across intercity geometry. No simplified length is used. Area tests download and verify original geometry on demand and use segment/rectangle intersection; counts are grouped relations or candidate directions, not individual roads, services or transfers.

The proposal has 299 records (14 OSM + 285 LTFRB), 132 map groups (14 OSM + 118 LTFRB candidate directions), approximately 2.01 MB display data and 6.10 MB originals. No cross-source association is computed. Geographic overlap does not establish identity. Initial Davao-area viewport is a viewing preset, not an administrative boundary; Fit network includes the full intercity relations. No tile requests or external geometry processing occur. Offline operation covers already-loaded display data; first-time downloads require the local/static host to be reachable. Area comparisons require originals to have loaded successfully.

## Remaining publication decision

Review `reports/m6/RELEASE_FILES.txt` for the proposed OSM/code/docs commit. It excludes all government proposal content. The current public release can be upgraded to OSM only after commit/push/deployment authorization. LTFRB detail requires a second explicit approval of the actual proposal; user approval is not represented as agency permission or an open licence. M6 submission and any issue comment remain separate actions.

## Authorized publication and removal procedure

The maintainership authorization is recorded in `dashboard/observatory/publication-approval.json` and covers only the exact manifest version. Generate mixed candidates with `python -m scripts.build_observatory_layers --authorized-ltfrb`; a changed version requires a newly reviewed authorization record. The Pages gate still rejects local proposals, unknown files and changed checksums. OSM-only builds remain supported. ODbL applies only to the OSM-derived data; LTFRB terms remain unspecified. Unsimplified exported geometry is derived data, not the original government source files.

Correction/removal requests use the repository issue link displayed on the site. Review the request, remove or correct affected records from the public tree and deploy the corrected release. For a broad removal, rebuild OSM-only, remove the mixed release from the Pages tree and its authorization file, test, commit and deploy. Assess repository history separately if removing published data from Git is also necessary; removing a live page does not remove prior clones or cached copies. Keep the source agency and requestor informed through an authorized communication channel. Do not promise automatic monitoring or deletion of third-party copies.
