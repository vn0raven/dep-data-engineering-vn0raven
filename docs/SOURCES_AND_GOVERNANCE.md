# Provenance and release boundaries

| Source | Scope | Evidence and confidence | Distribution |
|---|---|---|---|
| OSM via Overpass | Davao-filtered mapping with route-member spillover | July 8 and August 1, 2026 snapshots; community mapping, not verified service | Existing committed inputs; retain © OpenStreetMap contributors and ODbL attribution |
| LTFRB Region XI workbook | SUMMARY register, 285 rows | Workbook SHA-256 in processed source_provenance.json; source effective date unknown; file inspection observed November 18, 2026 PHT | Raw workbook and row-level metadata private; publication permission not established |
| Linked LTFRB GIS | 266 unique IDs | 262 readable GeoPackages, two incomplete downloads, two SHP files; per-file checksums and quality evidence private | Original files unchanged; no raw or derived linework included in public package |
| DC Bus PDF | Separate supplied government-response document | Not ingested or independently validated in this delivery; no facts used in KPI calculations | Confirm document content, applicability and permissions separately |

Public products contain aggregate statistics only. These are prepared for owner review; no external publication was performed. Raw data, file-level URLs, absolute source paths and private staging are ignored by Git. Do not use `git add -f` for government files. Source authenticity, licensing, current operations and boarding locations are separate checks from valid geometry.

SHA-256 audit caches are reused only when file content and validator version match. The latest full audit evidence is in private `reports/ltfrb`; safe totals are in committed-candidate `data/processed/m5/gis_summary.json`. Do not rewrite source files to fix geometry: retain originals and create explicitly versioned derived corrections after review.
