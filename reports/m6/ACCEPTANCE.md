> **Live release verified — 23 November 2026:** The [Observatory](https://vn0raven.github.io/dep-data-engineering-vn0raven/observatory/) now serves the maintainer-authorized OSM and selected LTFRB-derived release `9440df8235fdf5f6df7f`, deployed from `7af7487a014997339d5d9fedd25773a2baaadb86`. [Pages run](https://github.com/vn0raven/dep-data-engineering-vn0raven/actions/runs/45159911663) succeeded. Live browser checks passed OSM exploration and LTFRB source/classification filtering, missing geometry and candidate labels. The site states unspecified redistribution terms, no agency endorsement, separate source licensing and a correction/removal commitment. Private originals and review history remain excluded. Earlier preparation notes below are historical.

> **Publication update — 23 November 2026:** The project maintainer explicitly authorized publication of the reviewed OSM and selected LTFRB-derived layer. This is not source-agency permission or an open licence. The exact checked release is `9440df8235fdf5f6df7f`; raw files, private source identifiers, reviewer identities and notes remain excluded. The website includes a correction/removal request link and commitment to take down affected material when necessary, including at the source agency's request. Earlier preparation status below is historical. Deployment verification will be recorded after the authorized push.

# M6 acceptance evidence — 23 November 2026

Status: local implementation verified; new publication awaiting authorization. Existing Pages synthetic release remains live. M5 passed human review at a75927d; M6 has not been submitted or accepted.

| Acceptance item | Actual result |
|---|---|
| Integrity and repeatability | Private release 709ce26a035742a54735 passed 29 output checksums, SQLite/FK and 263-feature spatial roundtrip. OSM v2 release 60a7d97ef7b3de73d1ad verified; repeat exports preserve bytes. Static OSM package da2754e6742a5c26640b and local proposal 76653dc1a19fbd09855b are checksummed. Tampered outputs are rejected. |
| Allowlist and publication boundary | Tests reject extra route fields, unexpected publish files, changed checksums and government proposals marked as public. Public Pages gate passed for the exact nine-file OSM application tree. LTFRB samples remain ignored outside dashboard/. |
| Source filters and labels | Browser passed OSM selection; proposal source filter returns 285 LTFRB records, IRIP returns 104, geography results all retain the selected label. OSM and LTFRB are never matched. |
| Map/list consistency | Keyboard Enter selects a list record; actual rendered line click selects its record. Source badge and inspector reflect selection. |
| Missing and uncertain geometry | Actual proposal record with no candidate line displays the missing-evidence state. Candidate record displays explicit unconfirmed candidate wording. |
| Area comparisons | Full rectangle returns 14 grouped OSM line sets; malformed bounds rejected. Original unsimplified geometry is fetched and checksummed for comparison. Existing API tests cover missed bounding-box intersections. |
| Private history | Actual-release test restarts the app and retrieves both append-only decisions; update/delete triggers reject modifications and original release checksum remains unchanged. Browser saves use an ignored scratch store. |
| Save failures | Browser intercepts failed private save and verifies note input is retained. |
| Clean public setup | Separate checkout without government data: 43 passed, 2 expected private-data skips. Browser passes from that checkout and makes no API/external requests. |
| Keyboard / phone | Enter selection, map arrow/plus controls, 390px layout with no horizontal overflow and retained Inspect selection passed. Desktop and phone screenshots inspected. |
| Failure states | Empty filter results, invalid areas, checksum failure and simulated private release-error response passed. Actual server refuses corrupt release startup in Python tests. Startup failures are reported in PowerShell because no server exists to serve an error page. |
| Performance | Final clean-checkout Edge run: 292 ms local loading, 8.35 ms average canvas redraw across ten draws. Earlier same-machine runs: 187–548 ms loading and 4.33–4.59 ms draw. Not an internet/mobile-device benchmark. OSM display 1,286,701 bytes; originals 3,526,771 bytes, loaded on demand. |
| Preservation | Git diff reports no changes to M4 notebook, M5 notebook/report/data/assets. M5 link retains existing published URL. |

Full local suite: **45 passed**, no failures. Clean checkout: **43 passed, 2 skipped**. Shapely emitted transform deprecation warnings; the existing compatible API remains functional. An initial test expected a proposal rejection at the source gate; the stricter unexpected-file gate rejected it earlier. The assertion was corrected to recognize both fail-closed outcomes and the suite rerun successfully.

Screenshots: `osm-desktop.png` and `osm-phone.png` in the local Codex visualizations directory. These contain OSM only. Proposal examples are in `reports/observatory-private/publication-proposal/REVIEW_SAMPLES.json`; do not include them in the OSM commit.

## M6 rubric

- Application artifact: built and verified locally; proposed changes not committed.
- Public URL: existing synthetic Pages application accessible; real OSM replacement awaits authorization and post-deployment checks.
- README: links current live application and distinguishes prepared changes; setup and source boundary documented.
- Links/assets: local checked manifest and browser loads passed; new live asset verification must follow authorized deployment.
- Problem/data/pipeline/analysis/app/setup: README and controlled-layer methodology linked.
- Demo: eight-minute script prepared in DEMO_SCRIPT.md.

Remaining: review the exact file list and government samples; authorize OSM-only commit/push/deployment if desired; verify resulting live assets and record the exact snapshot; separately decide whether any LTFRB projection may be published. No issue/comment is authorized by this work.

Authorized mixed-release verification: full regression suite 45 passed; an additional exact-release authorization test passed (46 passing tests across these runs). Mixed-source browser checks passed OSM exploration and LTFRB source/classification, missing-geometry and candidate-label checks. Publication notice and exclusion policy are included in the reviewed interface. Shapely deprecation warnings remain non-blocking.

Live mixed release: browser checks passed with first-load time 8,405 ms and mean canvas redraw 8.93 ms on the test connection. Source separation, candidate labels and missing geometry passed on the hosted URL. This is an observed network run, not a performance guarantee. Documentation-only commits after 7af7487 do not change deployed assets. M6 submission and issue comments were not posted.
