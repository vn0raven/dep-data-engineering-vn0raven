# M5 final QA and readiness report

Status: **Ready for owner review and an authorized submission snapshot.** Human M5 acceptance, source republication clearance, commit/push and public deployment are not claimed. M4 passed human review at 26a7f7e and its accepted analysis is preserved.

## Requirement coverage

Existing segmentation and five actual OSM time comparisons were retained. The cleaned LTFRB release is integrated through an explicit aggregate-only projection. The notebook compares modes/classifications, direction completeness, geographic labels, source validation and unresolved associations. A concise stakeholder brief is generated from the same aggregates. See COMPLIANCE_CHECKLIST.md and docs/M5_PATH_B.md.

## Verified results

- Full private path executed: workbook extraction, existing read-only GIS audit, immutable cleaned-release verification, allowlisted aggregation and figure/brief generation.
- Cleaned release: 709ce26a035742a54735; 285 records retained; 266 linked IDs; 262 layers; 266 features (263 geometry pass, 3 quarantined). No repair or service identity confirmation.
- Source direction slots: 570 = 442 populated + 128 explicit loop N/A. 118 candidate pairs, 324 unresolved; 0/118 candidate length flags above max(0.5 km,10%).
- Mode comparison: PUJ 117 candidate, 146 unresolved, 123 N/A; PUB 1 candidate, 124 unresolved, 5 N/A; UV Express 54 unresolved. Unresolved populated-slot shares are 55.51%, 99.20% and 100%, respectively. These describe matching evidence only.
- Layer pass count 259/262 is separate from feature pass count 263/266. Neither is misrepresented as improvement over time.
- Five OSM KPIs independently recomputed from both committed raw snapshots: 57.38%, 96.72%, 50%, 42.86%, 42.86% on both dates. No LTFRB historical series invented.
- The updated notebook executed end to end, with saved outputs and no saved error outputs. The stakeholder brief is under 500 words and included as a notebook section.
- 35 automated tests pass, including six new submission-consistency checks. Final JUnit evidence: pytest-results.xml.
- Code, aggregate mirrors, KPI arithmetic, segment totals, chart links and unknown navigation status are covered by tests. Figures were visually inspected for readable labels.

Reproduction, source-preservation and privacy results are recorded in reproduction-check.json, OUTPUT_MANIFEST.json and PRIVACY_REVIEW.json. These are local checks, not remote CI or browser viewport tests. No separate numerical course grading rubric was found in the inspected official materials.

## Privacy and scope

Government-provided raw and detailed derived data are restricted pending explicit clearance. Candidate outputs contain aggregate tables/charts, code, documentation and executed notebook results. Private workbook, route-level records, file URLs/IDs, original values, WKB, geometry, quarantine detail, audit caches and prototype files are excluded. PUBLIC_FILES.txt specifies the exact commit candidates. The actual index is inspected without staging or changing it. Passing checks is not legal or publication approval.

A public reviewer can reproduce displayed aggregate analysis and independently recompute OSM trends; reproducing government-source GIS findings requires private inputs. This limitation is documented rather than hidden.

## Remaining limitations

Two partial downloads, two incomplete shapefile bundles, three invalid features, duplicate/shared sources, uncertain municipality identities and 324 unresolved direction associations remain disclosed findings. No service activity, actual boarding/transfers, schedules, fares, travel times or navigation readiness is inferred. Existing M4 analysis is unchanged. M6 map/API and durable reviews remain future work.

## Next action

Review the exact candidate list and brief, authorize the commit/push, then use docs/REVIEW_AND_RELEASE_CHECKLIST.md to submit the actual pushed hash under Path B. No commit, push, issue comment, M5 submission or deployment was performed during preparation.

## Final independent package checks

The extracted candidate package rebuilt the aggregate analysis and passed all 35 tests using the existing isolated dependencies, without restricted government source files. Its rebuilt aggregate tables, report data mirrors and figures matched repository outputs. The original final notebook has 8/8 executed code cells and no saved errors. A repeat local aggregate rebuild matched 45 files byte-for-byte. All 26 protected M4/original-input files matched their start-of-task fingerprints. Privacy inspection found no violations in 87 explicit candidate files and confirmed zero staged files and six ignored private prefixes. No index mutation occurred.

The ZIP includes existing committed OSM inputs and approved-M4 artifacts for reproduction; it excludes raw and detailed LTFRB government data. Publication authorization remains pending. PACKAGE_VERIFICATION.json describes package scope and verification limits. The exact candidate list and the files modified/created for this snapshot are in PUBLIC_FILES.txt and CHANGES.md.
