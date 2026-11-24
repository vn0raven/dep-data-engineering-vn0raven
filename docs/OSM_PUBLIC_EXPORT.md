> Update, 23 November 2026: see [controlled-layer implementation](M6_CONTROLLED_LAYERS.md) for the current local real-data application, publication boundary and commands. Earlier sections below document the prior stage.

# Controlled public OSM export

This database is derived exclusively from the repository's OpenStreetMap snapshot. It does not load, match, enrich from, or redistribute LTFRB records. Cleaning government data is not a mechanism for adding it to this export.

## Reproduce

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m scripts.export_osm_public
.\.venv\Scripts\python.exe -m pytest tests/test_osm_public_export.py -q
```

The default input is the real August 1, 2026 snapshot, not a fresh observation. Its metadata sidecar must identify the OSM ingestion source and match the input checksum after CRLF-to-LF normalization. The exporter does not edit raw inputs or M4/M5 outputs. The source path must belong to the project's OSM ingestion directory and naming convention. A source checksum establishes consistency with recorded provenance, not an independent authenticity guarantee.

## Export boundary

`data/processed/osm_public/latest.json` points to a versioned release containing:

- `routes.json`: OSM relation ID, public OSM source link, allowlisted name/ref/route/from/to tags, geometry counts and summed member length.
- `lines.geojson`: separate explicit way-member geometry, original member role and ordinal, OSM way ID, structural status and geodesic length.
- `quality.json`: actual counts, missing geometry and rejected member references.
- `provenance.json`: source snapshot, checksum, date, licence, transformation version and limitations.
- `manifest.json`: output SHA-256 checksums and content-derived release identity.

Allowed route tags: bus, minibus, share_taxi, trolleybus, tram, train, subway, light_rail, ferry. These stay OSM categories; they are not mapped to PUJ/PUB/UV Express or EXISTING/IRIP. Platform member ways are excluded from route-line exports. Missing or invalid members are reported and never bridged. Nested relations are not expanded. Exported lines can extend outside Davao because the original query selected intersecting relations.

Names and direction endpoints are source tags, not verified official names or operational directions. User names, contributor IDs, contact tags, free-text notes, LTFRB geometry, source Drive IDs and review history are outside the field allowlist.

`sum(member length)` may count overlapping and repeated members. It is not an end-to-end route distance. Structural success and explicit OSM membership do not establish active service, boarding access, transfers or government confirmation.

## Licence and publication

Database: Open Database License 1.0 (ODbL), https://opendatacommons.org/licenses/odbl/1-0/ . Attribution: © OpenStreetMap contributors, https://www.openstreetmap.org/copyright . Keep attribution visible on any map using this export and provide this licence and downloadable derived database with public distribution. Application code licensing is separate.

This release is prepared locally outside `dashboard/`; the existing Pages workflow will not publish it. A subsequent integration must explicitly load this OSM release, replace synthetic/LTFRB-specific labels, expose provenance/downloads and validate manifest checksums. It must not treat these relations as matched LTFRB routes. The private LTFRB verification workbench remains separate.

## Verified baseline

The current August 1 snapshot exports 14 public-transport relations and 9,858 line-member features, with zero unavailable member geometries and zero rejected member geometries within this selected scope. All 14 have exported lines. This does not measure the completeness of Davao's transport system. Run results are recorded in the release's `quality.json`.
