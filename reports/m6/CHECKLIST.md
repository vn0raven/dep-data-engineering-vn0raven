# M6 readiness and verification

Checked November 21, 2026, Asia/Manila. Target December 6, 2026. Baseline branch `main` at `a75927d21d824b264a37a9067395c49a36cef5ae`. M5 issue [#256](https://github.com/dataengineeringpilipinas/dep-data-engineering-open-track/issues/256) is open. The [recheck automation](https://github.com/dataengineeringpilipinas/dep-data-engineering-open-track/issues/256#issuecomment-7060263282) marked the revised snapshot ready for human review. Human acceptance is pending.

| Official M6 requirement | Status and evidence |
|---|---|
| Dashboard or report built and committed | Functional private app and public demo built and tested locally. Publication authorized on November 21, 2026. Existing `dashboard/index.html` remains available. |
| Public GitHub Pages deployment | Prepared using the existing Pages workflow with a three-file demo allowlist. Deployment verification is pending the current release. |
| Live URL in README | README links to M5 and the public M6 demo; live M6 verification is recorded below after deployment. |
| Working links and output | Browser loaded all demo assets from an isolated public checkout. The demo's M5 report link returned HTTP 200. Live M6 paths require a final verification. |
| Final README and dependencies | The README covers the problem, data, pipeline, analysis, app and setup. Existing locked Python environment passed dependency checks. |
| 5–10 minute demo | [Seven-minute demo script](DEMO_SCRIPT.md) prepared. |

## Local results

- Verified current release `709ce26a035742a54735` using 29 checksummed outputs and SQLite and spatial verification. It contains 285 route records and 263 passing spatial features. Of 442 populated directions, 324 remain unresolved.
- In Edge, a real documented map line led to a route record and an unresolved review case. The form saved a decision with a reviewer, note, case, release and timestamp in scratch SQLite. After stopping and restarting the app, that same decision was retrieved through the case API. The automated restart test also confirmed that the release database checksum stayed unchanged and SQLite rejected update and delete attempts.
- A clean checkout reconstructed from the public baseline plus the candidate code served the demo without a private release. Edge verified mode and classification filters, map selection, positive and empty intersections, invalid bounds, empty route results, a narrow viewport and browser-local review persistence after refresh. The demo issued no API requests. The JavaScript syntax check passed.
- Full local test suite: 39 passed. Public checkout: 38 passed and one expected skip for the actual private release. These runs used the existing locked Python environment.
- The public demo uses fictional route coordinates and evidence. The private app uses loopback access and self-declared reviewer names. A shared review store needs a separately approved host and access controls. The coordinate map has no external basemap, and areas are rectangles. The private queue focuses on unresolved direction associations, with other route and direction issues available from route records.
- Candidate files are enumerated in [RELEASE_FILES.txt](RELEASE_FILES.txt). Existing M4 and M5 artifacts are outside the change set. The private release and scratch stores remain ignored. The final commit, deployment run, verified M6 URL and submission issue are pending.
