# Observatory M6 runbook

Target date: December 6, 2026, Asia/Manila. The [DEP Live Deployment checklist](https://github.com/dataengineeringpilipinas/dep-data-engineering-open-track/blob/main/docs/MILESTONE_CHECKLIST.md#m6--live-deployment-by-week-24) and [M6 issue template](https://github.com/dataengineeringpilipinas/dep-data-engineering-open-track/blob/main/.github/ISSUE_TEMPLATE/milestone-m6.yml) govern the submission.

The map uses the existing immutable LTFRB release. On startup, the Python app verifies the manifest, SQLite integrity, foreign keys and spatial outputs before opening a loopback server. Project reviews are separate SQLite events. The same browser interface can run directly on Pages with fixtures authored for the demo. The first slice uses Python's standard HTTP server and existing GIS libraries, so the existing Python setup covers both the application and its tests.

## Private app

From the repository root, use Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe scripts/verify_observatory.py
.\.venv\Scripts\python.exe -m scripts.observatory_app
```

Open http://127.0.0.1:8766/private/. Use the numeric loopback address shown by the server. To point to a different local release tree, pass `--release-root <directory-containing-latest.json>`. The default review history is stored in the ignored file `reports/observatory-private/m6-reviews.sqlite`. To try out review writes without changing your normal history, pass `--review-db reports/observatory-private/scratch-reviews.sqlite`. Use a separate approved host and access controls for any shared installation. Reviewer names in this local slice are self-declared. The app checks the local Host and Origin for writes and uses loopback binding for the access boundary.

Release startup errors are shown in the terminal. Check the pointer and run the verifier for a valid release directory before restarting. Restoration means selecting a previously verified complete release root or restoring its pointer through the existing release process. Review events remain scoped to the release on which they were made. Use the same review database after a restart to retrieve that history.

## Private API

| Method and path | Behavior |
|---|---|
| GET `/api/health`, `/api/quality` | Verified release version and quality counts with original count categories |
| GET `/api/routes` | Search by name or ID, optional mode and classification, paginated |
| GET `/api/routes/{id}` | Source record and file status, direction evidence and review-case references |
| GET `/api/features` | Passing GeoJSON lines linked by source file, with candidate associations separately tagged. Optional `bbox=west,south,east,north` tests exact intersection in WGS84 |
| GET `/api/cases` | Paginated queue for unresolved direction-to-line matches |
| GET `/api/cases/{id}` | Route, direction and source geometry evidence, and up to 100 recent review events |
| POST `/api/cases/{id}/reviews` | Append a project decision. Supply `release_version`, `reviewer`, `decision`, and `note` as JSON from the local origin |

The mode values are `PUJ`, `PUB`, and `UV_EXPRESS`. Classifications are `EXISTING` and `IRIP`. `q` is capped at 100 characters. Lists take `limit` from 1 to 100, default 40, and a nonnegative `offset` up to 10,000. Geographic bounds require ordered longitudes and latitudes, so rectangles crossing the antimeridian need two requests. Mode counts count distinct source-linked route records across matching lines before pagination. Source-file links can suggest multiple route records. Only candidates carry an explicit direction match from the release.

Reviews accept `keep_unresolved`, `request_evidence`, or `document_review`. Reviewer names and notes are required, with limits of 80 and 2,000 characters. The store generates UTC timestamps and records the case and release. SQLite triggers reject updates and deletes. A save against a stale release gets HTTP 409. Invalid filters or fields get 400, unknown records get 404, disallowed origins get 403, and local storage failures get 503. Scope is one local user at a time and 100 recent events per case in the UI.

## Public preview and verification

```powershell
.\.venv\Scripts\python.exe -m http.server 8767 --bind 127.0.0.1 --directory dashboard
```

Open http://127.0.0.1:8767/observatory/. The files in `dashboard/observatory/` use only authored synthetic routes, cases and map coordinates for interactive operations. The public review history uses local browser storage. Its M5 link points to the published aggregate analysis. The mode, route and area results describe the visible source lines and linked records. They provide no service, boarding or transfer information.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

HTTP tests require loopback connections. With real government files available, the local suite also tests the actual release in a temporary review store. The actual-release case skips in a public checkout. For optional browser checks, supply a local Node Playwright package (set `OBSERVATORY_PLAYWRIGHT` to its path when it is outside Node's default package lookup). Install Chromium for Playwright or set `OBSERVATORY_BROWSER_EXE` to a compatible local browser binary. Run the private app with a scratch review store before including its URL in this test:

```powershell
node tests/observatory_browser.cjs http://127.0.0.1:8767/observatory/ http://127.0.0.1:8766/private/
```

Omit the private URL for the public demo check. For live validation pass the final Pages URL as the public URL, then verify that the M5 link, script and stylesheet load. The published static demo does not require a Python process, API keys, raw files, private release, or shared review database.

## Authorized release and submission

Review the exact [candidate file list](../reports/m6/RELEASE_FILES.txt) and the [rubric status](../reports/m6/CHECKLIST.md). The existing Pages Actions workflow uploads `dashboard/` when relevant files reach `main`. Its preflight enforces the three-file Observatory demo tree. Pages must use GitHub Actions as its source. The planned public URL is https://vn0raven.github.io/dep-data-engineering-vn0raven/observatory/.

After approval, stage only the listed candidate files and inspect the staged names and diff. Run tests, commit and push the reviewed revision, then check the Pages run for that exact commit. Verify the actual URL, assets and interactions before recording the commit hash and live URL. Ensure the README identifies the verified URL. Use the official M6 form with the actual pushed hash, live URL and demo script. If M5 is still awaiting review, the course holds M6 in its prerequisite queue.

Private release files, government-derived route details and geometry, source links, and SQLite review history are excluded from the Pages tree and candidate file list. Any shared private API or store requires its own approved host and access controls.


## Map workspace redesign — 21 November 2026

The desktop workspace has collapsible Browse and Inspect panels around the map. Phones use Browse / Map / Inspect views. Search, mode, classification and map-evidence filters apply together to records and displayed geometry. The verification queue remains a separate queue of unresolved source-direction cases; project-review counts do not resolve source evidence.

The existing canvas was retained after evaluating Leaflet (https://leafletjs.com/reference.html). Leaflet would provide mature map gestures and tile integration, but tiles introduce provider terms, attribution and external viewport requests. This release makes no tile requests and uses a labeled offline coordinate map with approximate scale, north indication, pan, zoom, fit, selection and rectangular comparisons. It provides no street or municipal-boundary context. Dashed lines denote unconfirmed associations; thickness denotes selection. Keyboard arrows pan and plus/minus zoom; records and forms are keyboard accessible.

Only the private API exposes source geography and per-case project-review counts. It still verifies releases before serving, reads original evidence without modification and stores append-only reviews separately. The public examples remain synthetic and browser-local.

Verification: 39 Python tests passed, including actual-release restart/persistence, immutable source checks, append-only enforcement, bounds and privacy boundaries. Edge browser interactions passed public/private workflows, filter/map consistency, empty geometry, invalid areas, narrow layouts, save-failure note retention and simulated API release-error messaging. Initial restricted Windows execution produced three socket-permission failures; rerun with loopback access passed. Private QA writes use a separate ignored test database.

Screenshots are local artifacts outside the repository; they are synthetic and contain no government route details. No publication or deployment was performed for this redesign. Startup release failures still fail closed in the server: if the server cannot start, the browser cannot receive an error page; consult the PowerShell startup message. The UI reports unavailable API when an already-loaded page cannot reach it.
