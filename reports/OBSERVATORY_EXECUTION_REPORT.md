# Observatory data preparation execution report

Updated November 19, 2026 PHT. M4 human review has passed at 26a7f7e; this status is supported by the reviewer message supplied by the user. M5 acceptance and M6 deployment are not claimed.

## Completed

Implemented scripts/observatory_etl.py and scripts/verify_observatory.py. The full local government-source dataset was processed, normalized and exported; no new UI mockup was created. Current release: **709ce26a035742a54735**. The source branch was checked and still pointed to 26a7f7e when inspected.

| Measure | Actual result |
|---|---:|
| Source records / cleaned records retained | 285 / 285 |
| Unique source names / normalized name comparison keys | 280 / 280 |
| Linked file IDs assessed | 266 |
| Readable spatial assets | 262 |
| Incomplete downloads | 2 |
| Incomplete SHP bundles | 2 |
| Spatial layers / source features | 262 / 266 |
| Geometry-pass features / quarantined features | 263 / 3 |
| Automatic candidate direction matches | 118 |
| Unresolved populated direction slots | 324 |
| Explicit loop second-direction N/A slots | 128 |
| Candidate length discrepancies above threshold | 0 of 118 |
| Route records needing review | 171 |
| Other normalized metadata candidates | 114 |
| Transformation history entries | 3,248 |
| Directional locality-label records | 2,094 |
| Verified canonical municipality identities | 0 |

Counts of features, layers, files, routes and direction slots use different grains. Previous M5 results reported 259 basic-clean layers; this release reports 263 passing individual features. Those are compatible denominators, not an improvement manufactured by repairing geometry.

## Quality findings and outstanding cases

Both SHP files have valid SHP signatures but lack SHX, DBF and PRJ companions. Both .partial downloads remain incomplete. Three MultiLineStrings contain components with too few points. The original WKB and exact validation reasons are retained; no geometry was repaired.

Ten records occur in duplicate-name candidate groups; all remain separate. Thirty-five route records share source-file IDs. One exact duplicate geometry group contains two features. Two locality comparison keys have conflicting source city/municipality labels; malformed prefixes, repeated labels and empty slash tokens are also flagged. Locality identities and abbreviations are not inferred without authoritative context.

All 118 length matches remain candidate source associations. Zero flags among that subset cannot validate 324 unpaired directions. Geometry-pass linework is structurally validated, not confirmed active transport service or approved navigation data. Record names, source classifications and timestamps do not establish fare applicability, schedules, boarding points or real transfers.

## Outputs

Private derived release:

`data/processed/ltfrb_observatory/releases/709ce26a035742a54735/`

Contains normalized CSV/JSON tables, relational SQLite with primary/foreign keys, EPSG:4326 geometry_pass.gpkg and geometry_pass.geojson, quarantined feature evidence, uncertain route records, transformation history, source provenance, column dictionary, source inventory, statistics, quality report and checksummed manifest. latest.json identifies the current immutable release. Earlier immutable development releases are retained, not silently overwritten.

Read the release DATA_DICTIONARY.md and QUALITY_REPORT.md for field meanings and interpretation. Source hashes and original workbook values are retained locally. Derived government datasets are excluded from Git and have not been published. The original government files are unchanged and were rehashed before promotion.

## Verification

- Full suite: **29 passed, 0 failed**, including existing M4/M5 tests and ten new ETL tests.
- Independent checker validated 29 output-file checksums, SQLite integrity, zero foreign-key violations, JSON/table record counts, quarantine separation and all 263 geometry round trips between GeoJSON and GeoPackage.
- Repeated actual-source execution returned verified_existing_release with the same version, preserving release bytes.
- Synthetic integration exercised a changed intake inventory with unchanged spatial source; one source audit was reused from cache, a new release was created, and the original release remained intact.
- Synthetic integration checked tampered-output rejection, unsupported/incomplete inputs, source-preserving reprojection, malformed lengths, duplicate identifiers and label ambiguity.
- One initial test run exposed an unclosed SQLite connection in a test on Windows. It was corrected; the final suite passes.
- README contained two legacy Windows-1252 0x97 dash bytes. They were converted to actual UTF-8 dashes while preserving valid UTF-8 content; no statistical conclusions were changed.

Evidence: observatory-tests.xml and observatory-verification.json alongside this report.

## Preservation and next work

M4 analysis, notebook, processed data and accepted figures are preserved. M5 processed outputs, notebook and dashboard are preserved. Documentation status has been updated for M4 human acceptance. The reviewer's minor M4 text correction is recorded separately because the user instructed preservation of M4; it was not applied to the accepted document.

Next: complete four source-file exceptions; review degenerate components and shared/duplicate geometry; reconcile locality identities with province context; confirm direction identities; then implement a read-only release-backed API and evidence/review workflow. The architecture and M6 plan are in docs/OBSERVATORY_MVP_ARCHITECTURE.md. No commit, push, issue comment or deployment was performed.
