# Milestone 3 schema — processed transport records

The Milestone 4 analysis reads the three CSVs below from `data/processed/`.
These represent OpenStreetMap **features**, not a verified local transport service registry.

## `stops.csv`

**Grain:** one unique OSM stop, platform or stop-like route member.
**Primary key:** `stop_id` (`node:<osm_id>` or `way:<osm_id>`).

| Column | Meaning |
|---|---|
| `stop_id` | OSM type and identifier; primary key |
| `osm_type`, `osm_id` | Raw OSM reference |
| `name` | Name if mapped, otherwise null |
| `stop_type` | Standardized stop/platform/station classification |
| `latitude`, `longitude` | Point coordinate if available; **null for some ways** |
| `public_transport`, `highway`, `amenity`, `bus`, `ferry` | Selected OSM tags |
| `evidence`, `route_member_roles` | Basis of inclusion |
| `source_file` | Raw extract provenance |

## `routes.csv`

**Grain:** one retained OSM `route` relation (`bus` or `ferry`).
**Primary key:** `route_id` (`relation:<osm_id>`).

| Column | Meaning |
|---|---|
| `route_id`, `osm_relation_id` | OSM relation identifier |
| `route_ref`, `route_name` | Mapped route reference/name, if present |
| `route_mode` | Bus or ferry in the M3 transform |
| `operator`, `network` | OSM tags when present |
| `origin_name`, `destination_name` | As mapped in OSM, may be missing/inconsistent |
| `source_file` | Extract provenance |

## `route_stops.csv`

**Grain:** one explicit ordered route member identified as a stop/platform.
**Composite primary key:** `(route_id, stop_sequence)`.

| Column | Meaning |
|---|---|
| `route_id` | Foreign key to `routes.route_id` |
| `stop_sequence` | Occurrence order within mapped route relation |
| `stop_id` | Foreign key to `stops.stop_id` |
| Other columns | Check current CSV header and `scripts/transform.py` for source tags |

A route can have no stop members while still containing geometry ways. A route can also contain non-Davao stops because OSM relation members can span wider geography. **Do not infer travel time, valid transfers, fare, or route authorization from these tables.**

Milestone 4 outputs: `data/processed/m4_insights_summary.json`, four figures in `output/figures/`, and `docs/MILESTONE4_INSIGHTS.md`.
