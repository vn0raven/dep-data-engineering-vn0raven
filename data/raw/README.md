# Raw data

Files in this directory are immutable source extracts. Do not edit a raw JSON file after ingestion.

A new run of `python scripts/ingest.py` creates a timestamped pair:

- `osm_davao_transit_elements_YYYYMMDDTHHMMSSZ.json`
- `osm_davao_transit_elements_YYYYMMDDTHHMMSSZ.metadata.json`

The metadata sidecar records the exact API endpoint, UTC access time, Overpass query, request settings, row/element count, byte count, and SHA-256 checksum.

The previously committed `osm_davao_transit_elements_20260708.json` uses the older date-only naming format. Its source and access date are documented in `osm_davao_transit_elements_20260708.metadata.json`.
