# LTFRB Observatory data pipeline

This pipeline creates private, immutable data releases for geographic investigation. It retains all workbook records and original source values, produces structurally validated linework, and isolates unresolved identity and geometry cases. It does not modify M4, M5, raw government files or source-owner decisions.

## Run

Python 3.12 and the existing project virtual environment are supported. Activation and PowerShell policy changes are unnecessary.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe scripts/observatory_etl.py --workbook "C:\Users\dinga\Downloads\LTFRB DATA\LTFRB DATA\REGION 11 ROUTE STRUCTURE DATABASE.xlsx" --gis-dir "C:\Users\dinga\Downloads\LTFRB DATA\LTFRB DATA\LTFRB_GeoPackages"
.\.venv\Scripts\python.exe -m pytest -q
```

Default outputs are ignored by Git:

```text
data/processed/ltfrb_observatory/
  latest.json
  last_run.json
  cache/<content-and-validator-key>.json
  releases/<20-character-release-id>/
    manifest.json
    statistics.json
    provenance.json
    DATA_DICTIONARY.md
    data_dictionary.json
    QUALITY_REPORT.md
    observatory.sqlite
    geometry_pass.gpkg
    geometry_pass.geojson
    routes.csv / routes.json
    directions.csv / directions.json
    route_localities.csv / route_localities.json
    assets.csv / assets.json
    layers.csv / layers.json
    features.csv / features.json
    associations.csv / associations.json
    transformations.csv / transformations.json
    issues.csv / issues.json
    uncertain_routes.csv / uncertain_routes.json
    quarantined_features.json
```

The GeoPackage is created when at least one feature passes. Source files and all derived releases remain local pending an explicit data-release decision. The commit-ready code and documentation contain no government linework or row-level source register.

## Normalization policy

| Field | Action | Boundary |
|---|---|---|
| Text | Unicode NFKC, whitespace collapse, Unicode dash normalization | No spelling corrections, invented expansions or title-case rewriting |
| Route names | Preserve display wording; create case/punctuation comparison key | Same names are review candidates, never merged automatically |
| Modes | PUJ, PUB, UV_EXPRESS using explicit aliases | Unknown modes remain null and flagged |
| Classification | Uppercase EXISTING/IRIP labels | Does not establish active service |
| Directions | Explicit compass and one-direction-loop enum | Empty direction 2 on a documented loop is not applicable, not a missing return trip |
| Lengths | Positive finite decimal, rounded to 6 decimal places | Source numeric text retained; no inferred length substitution |
| LGUs | Split source slash-delimited lists and separate explicit City/Municipality of wording | PSGC is null; homonyms, outdated labels and spelling variants remain unresolved |
| IDs | Route key from region/source route number; observation key from workbook hash and Excel row | Source renumbering requires identity review; key collisions stop release |
| Geometry | Reproject passing linear features to EPSG:4326; compute WGS84 ellipsoidal km | No make_valid, snap, simplify, segment removal or source overwrite |

Every extracted source record remains in `routes.original_record_json`. Changed field values and explicit rules are retained in the transformations table. LGU token positions remain in route_localities, including repeated labels that are flagged rather than silently deleted.

## Quality and identity gates

1. Enumerate and SHA-256 hash every supplied file, including partial downloads, sidecars and acquisition manifests.
2. Audit all workbook-linked IDs independently. Incomplete sources are recorded without preventing other files from being inspected.
3. A `.partial` filename is never promoted to a complete input. For SHP, inspect the 9994 header signature and require SHP/SHX/DBF/PRJ as the minimum trusted bundle. Other available sidecars remain listed in provenance.
4. For GeoPackages, reuse the read-only SQLite integrity and required metadata audit; enumerate spatial layers and compare CRS/SRID declarations.
5. Quarantine null, empty, invalid, non-linear, CRS-inconsistent, implausibly located or nonpositive-length features. Preserve source FIDs and original WKB. The Philippine bounding extent is a broad quality screen, not a legal operating boundary.
6. Exact normalized EPSG:4326 WKB hashes identify duplicate features. Duplicates remain visible and flagged; no service or route deduplication is inferred.
7. Automatic length pairing requires one workbook route per source ID and a one-feature passing layer with a matching direction label, or a sole explicitly loop-labelled direction. All matches remain **candidates**.
8. Flag candidate distance differences above max(0.5 km, 10% declared km). Unpaired directions do not count as length passes.
9. Rehash original sources before promoting a complete release. Round-trip the generated GeoPackage and validate SQLite integrity and foreign keys.

`geometry_pass` means structurally screened linework. It is suitable for source investigation, not a confirmed operational route network. `uncertain_routes` contains record/direction review cases; check asset, layer, feature and locality evidence too. All navigation status values remain not_verified.

## Versioning, incrementality and failure behavior

The release ID hashes workbook bytes, the full source inventory, pipeline code, dependency versions and Python version. An unchanged run checks all existing output checksums and returns the same immutable release without rewriting its contents. A modified existing output fails verification rather than being silently replaced.

Per-source cache keys include source bytes, source identity, code and dependency versions. A new source inventory can reuse unchanged asset inspections. Corrupt cache entries are rebuilt. Changing validator code invalidates the current conservative cache. No claims are made about a live government update feed: acquiring new packages is currently manual, processing is automated.

Files are generated in temporary staging and promoted by a same-volume directory rename only after validation. Latest pointers are written atomically. A source change during processing aborts promotion. The CLI exits nonzero on orchestration, extraction or release-verification failure. Individual source defects are structured audit results, not batch success claims.

An existing release is never overwritten, even with `--refresh`. For a deliberate independent reconstruction use a new `--out` directory; compare semantic outputs and geospatial properties, since newly generated GeoPackage metadata includes creation information. Identical repeated executions in the same output root preserve the original release bytes.

## Tables and relationships

```text
routes (one workbook record)
  └─ directions (two source direction slots, including explicit loop N/A)
       ├─ route_localities (ordered source labels, not gazetteer identities)
       └─ associations (candidate feature or unresolved reason)
assets (one linked Drive ID)
  └─ layers
       └─ features (geometry pass or quarantine; original WKB retained)
issues (unresolved entity-specific evidence)
transformations (before/after values and rules)
```

Primary keys and foreign keys are enforced in SQLite. Common route, source-file and issue lookups are indexed. Geometry JSON uses EPSG:4326; source WKB is interpreted using the layer's retained source CRS. The SQLite database is relational evidence storage, not a SpatiaLite-enabled spatial query engine.

The release-specific data dictionary lists columns and meanings. Field definitions must not be used to infer current routes, authoritative place identities, actual transfers, schedules, fares or travel times.

## Further corrections

Review the two partial downloads, acquire complete shapefile dependencies, inspect degenerate components of the three invalid MultiLineStrings, resolve shared file and exact-linework relationships, and reconcile locality labels against an authoritative gazetteer with province context. Any approved repair needs a separate derived-geometry rule, original-to-derived lineage, reviewer evidence and new release; it is not part of this pipeline.
