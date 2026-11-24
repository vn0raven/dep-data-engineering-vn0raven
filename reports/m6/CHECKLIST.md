> **Live release verified — 23 November 2026:** The [Observatory](https://vn0raven.github.io/dep-data-engineering-vn0raven/observatory/) now serves the maintainer-authorized OSM and selected LTFRB-derived release `9440df8235fdf5f6df7f`, deployed from `7af7487a014997339d5d9fedd25773a2baaadb86`. [Pages run](https://github.com/vn0raven/dep-data-engineering-vn0raven/actions/runs/45159911663) succeeded. Live browser checks passed OSM exploration and LTFRB source/classification filtering, missing geometry and candidate labels. The site states unspecified redistribution terms, no agency endorsement, separate source licensing and a correction/removal commitment. Private originals and review history remain excluded. Earlier preparation notes below are historical.

> **Publication update — 23 November 2026:** The project maintainer explicitly authorized publication of the reviewed OSM and selected LTFRB-derived layer. This is not source-agency permission or an open licence. The exact checked release is `9440df8235fdf5f6df7f`; raw files, private source identifiers, reviewer identities and notes remain excluded. The website includes a correction/removal request link and commitment to take down affected material when necessary, including at the source agency's request. Earlier preparation status below is historical. Deployment verification will be recorded after the authorized push.

> Current status, 23 November 2026: M5 passed human review at a75927d ([review](https://github.com/dataengineeringpilipinas/dep-data-engineering-open-track/issues/256#issuecomment-7069250924)). The new real-data revision is locally verified and awaits publication approval. See [current acceptance evidence](ACCEPTANCE.md), [controlled layers](../../docs/M6_CONTROLLED_LAYERS.md) and [exact proposed file list](RELEASE_FILES.txt). Earlier November 21 results below are historical.

# M6 readiness and verification

Checked November 21, 2026, Asia/Manila. Target December 6, 2026. Baseline branch `main` at `a75927d21d824b264a37a9067395c49a36cef5ae`. M5 issue [#256](https://github.com/dataengineeringpilipinas/dep-data-engineering-open-track/issues/256) is open. The [recheck automation](https://github.com/dataengineeringpilipinas/dep-data-engineering-open-track/issues/256#issuecomment-7060263282) marked the revised snapshot ready for human review. Human acceptance is pending.

| Official M6 requirement | Status and evidence |
|---|---|
| Dashboard or report built and committed | Functional private app and public demo built and tested locally. Publication authorized on November 21, 2026. Existing `dashboard/index.html` remains available. |
| Public GitHub Pages deployment | Prepared using the existing Pages workflow with a three-file demo allowlist. Passed: deployment run [44890913579](https://github.com/vn0raven/dep-data-engineering-vn0raven/actions/runs/44890913579) succeeded. |
| Live URL in README | README links to both live reports; M6 URL and assets verified below. |
| Working links and output | Browser loaded all demo assets from an isolated public checkout. The demo's M5 report link returned HTTP 200. Live M6 browser checks passed. |
| Final README and dependencies | The README covers the problem, data, pipeline, analysis, app and setup. Existing locked Python environment passed dependency checks. |
| 5â€“10 minute demo | [Seven-minute demo script](DEMO_SCRIPT.md) prepared. |

## Local results

- Verified current release `709ce26a035742a54735` using 29 checksummed outputs and SQLite and spatial verification. It contains 285 route records and 263 passing spatial features. Of 442 populated directions, 324 remain unresolved.
- In Edge, a real documented map line led to a route record and an unresolved review case. The form saved a decision with a reviewer, note, case, release and timestamp in scratch SQLite. After stopping and restarting the app, that same decision was retrieved through the case API. The automated restart test also confirmed that the release database checksum stayed unchanged and SQLite rejected update and delete attempts.
- A clean checkout reconstructed from the public baseline plus the candidate code served the demo without a private release. Edge verified mode and classification filters, map selection, positive and empty intersections, invalid bounds, empty route results, a narrow viewport and browser-local review persistence after refresh. The demo issued no API requests. The JavaScript syntax check passed.
- Full local test suite: 39 passed. Public checkout: 38 passed and one expected skip for the actual private release. These runs used the existing locked Python environment.
- The public demo uses fictional route coordinates and evidence. The private app uses loopback access and self-declared reviewer names. A shared review store needs a separately approved host and access controls. The coordinate map has no external basemap, and areas are rectangles. The private queue focuses on unresolved direction associations, with other route and direction issues available from route records.
- Candidate files are enumerated in [RELEASE_FILES.txt](RELEASE_FILES.txt). Existing M4 and M5 artifacts are outside the change set. The private release and scratch stores remain ignored. The deployment and verified URL are recorded below. The M6 submission issue has not been created.


## Verified public deployment

November 21, 2026, Asia/Manila: [Public Observatory](https://vn0raven.github.io/dep-data-engineering-vn0raven/observatory/) is live. Application commit `e75e51bd76f729a7006cdf63f8276f7379d54d21`; deployed workflow-fix commit `308c95bd2050c4370f5e8817a4914db4ac61ba8d`. [Successful Pages run](https://github.com/vn0raven/dep-data-engineering-vn0raven/actions/runs/44890913579).

The first run encountered delayed artifact visibility; retry encountered duplicate artifact names. The workflow now uses attempt-specific names and waits for the artifact before deployment. The corrected run passed. GitHub emits a non-blocking Node 20 action deprecation warning.

Live Edge checks passed: filters, evidence selection, map/list selection, rectangular area comparisons, invalid bounds, empty map evidence, keyboard map controls, narrow layouts and browser-local review persistence. No private API calls were made. The HTML, JavaScript, CSS and preserved M5 report returned HTTP 200 and matched local files after line-ending normalization. Pre-push Python tests: 39 passed. The exact 12 staged release files passed privacy checks; private data and review stores were excluded.

This verification is documented in a follow-up documentation-only commit; the deployed application assets remain those of `308c95b`. M5 remains open and ready for human review, not accepted. No M6 submission or issue comment was posted.
