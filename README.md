# Davao Commute Router: Estimating the Fastest and Most Affordable Public Transport Route in Davao City

## Problem Statement

I want to answer: "How can route, stop, schedule, road-network, local transport-zone, traffic, and fare data be integrated into a routing pipeline that estimates the fastest and most affordable door-to-door public transport route between selected origin and destination points in Davao City in 2026, using jeepneys, DC Bus, Love Bus, tricycles, and other publicly documented free-ride services?"

## Audience

This project is for Davao commuters, especially students, workers, and first-time riders who need help choosing the best combination of public transport modes based on both travel time and fare cost. It can also support Davao City transport planners, LTFRB Region XI, CTTMO, and local researchers who want to understand how jeepney, bus, free-ride, and tricycle routes connect across the city.

## KPI or Key Metric

The main metrics I want to track are Estimated Door-to-Door Commute Time in minutes and Estimated Total Fare in PHP.

Estimated Door-to-Door Commute Time will measure the total travel time from Point A to Point B, including walking time, waiting time, in-vehicle travel time, transfer time, and possible traffic delay.

Estimated Total Fare will measure the total commute cost by adding the fare of each paid public transport segment. This is important because the fastest route may not always be the most practical route if it requires extra paid transfers.

## Milestone 2 — Data Ingestion

### Ingestion method

Milestone 2 uses **Path A: API ingestion**. The script `scripts/ingest.py` sends an Overpass QL query by HTTP POST and downloads transportation-related OpenStreetMap elements within the Davao City administrative area.

- **Source:** OpenStreetMap data via Overpass API
- **Exact API endpoint:** `https://overpass-api.de/api/interpreter`
- **Source landing page:** `https://overpass-api.de/`
- **Format:** JSON
- **Geographic filter:** Davao City OSM relation `3936841`, represented by Overpass area ID `3603936841`
- **Committed sample raw file:** `data/raw/osm_davao_transit_elements_20260708.json`
- **Committed sample access date:** `2026-07-08` UTC
- **Committed sample source record:** `data/raw/osm_davao_transit_elements_20260708.metadata.json`

The committed sample was created by the earlier date-only version of the script. The exact time was not retained, so the metadata sidecar records the known access date without inventing a time. New runs retain the exact UTC timestamp automatically.

### What the script extracts

The embedded Overpass query retrieves:

- nodes tagged with `public_transport`;
- nodes tagged as `highway=bus_stop`;
- bus stations and ferry terminals;
- ways tagged with `public_transport`; and
- route relations inside Davao City.

### Setup

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
```

Activate the environment:

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the dependency:

```bash
pip install -r requirements.txt
```

### Repeatable ingestion command

Run this command from the repository root:

```bash
python scripts/ingest.py
```

The script also works when launched from another directory because the default output path is calculated from the script location rather than the current working directory.

A successful run creates two new files without overwriting an earlier pull:

```text
data/raw/osm_davao_transit_elements_YYYYMMDDTHHMMSSZ.json
data/raw/osm_davao_transit_elements_YYYYMMDDTHHMMSSZ.metadata.json
```

The raw `.json` file contains the unmodified API response. The `.metadata.json` sidecar records the exact source URL, UTC access time, full query, HTTP settings, response status, element count, byte count, and SHA-256 checksum.

### Request handling and options

The script:

- retries HTTP `429`, `500`, `502`, `503`, and `504` responses with exponential backoff;
- handles connection, timeout, HTTP, malformed JSON, and file-write errors;
- validates that the response contains an Overpass `elements` list;
- writes files atomically so a failed run does not leave a partial raw file; and
- returns a nonzero exit code when ingestion fails.


## Data Source Notes

### Primary Source

- **Name:** OpenStreetMap (OSM) Data via Overpass API
- **URL:** https://overpass-api.de/
- **Format:** JSON / XML
- **Ingestion Strategy:** A Python extraction script (`scripts/ingest.py`) uses an Overpass API query to retrieve transportation-related geographic features within Davao City. Extracted features include public transport stops, stations, mapped ways, and route relations. The raw API response and its source metadata are stored locally for route analysis, visualization, and transportation modeling.
- **Coverage:** Global geographic coverage filtered to Davao City, Philippines. Available features include roads, walkable paths, mapped public transport routes, stops, and route relations contributed by OpenStreetMap users.
- **Why it fits the problem:** OpenStreetMap provides the geographic foundation needed to model transportation networks, analyze accessibility, and generate multimodal route recommendations. It enables extraction of spatial data required for route planning and connectivity analysis.
- **Known Limitations:** Coverage depends on community contributions. Some routes, stops, and transport features may be incomplete, outdated, or incorrectly mapped. OSM does not provide guaranteed official schedules, fares, vehicle availability, or real-time transport updates.

---

### Fallback Source

- **Name:** Davao City Bus Route and Schedule Information
- **URL:** https://davaobus.com/schedule
- **Format:** HTML / Web pages
- **Ingestion Strategy:** Route and schedule information will be manually reviewed or extracted where possible to validate and supplement route information from OpenStreetMap.
- **Coverage:** Publicly available Davao City bus routes, schedules, stops, and service information.
- **Why it could still work:** Provides operational transport information that can help validate mapped routes and identify active public transport services, particularly for bus operations.
- **Known Limitations:** Information may not be available in a structured data format and may not cover all public transportation modes.

---

### Additional Supporting Sources

#### Name: Davao City Public Transportation Mapping References

- **URL:** https://wiki.openstreetmap.org/wiki/Davao_City/Public_transportation
- **Format:** HTML documentation
- **Coverage:** Community documentation and references for mapping public transportation features in Davao City.
- **Why it fits the problem:** Provides additional context for interpreting and validating transport-related OpenStreetMap features.
- **Known Limitations:** Community documentation may not always reflect current transport operations or recent route changes.

---

#### Name: LTFRB Region XI Transport References

- **URL:** https://ltfrb.gov.ph/
- **Format:** HTML / PDF
- **Coverage:** Official transport regulations, fare matrices, route references, and announcements for Region XI.
- **Why it fits the problem:** Provides official references for jeepney fares, route information, and transport regulations that are not available from mapping datasets.
- **Known Limitations:** Some route documents and fare matrices may be difficult to access, outdated, or require manual extraction.

---

#### Name: Davao City Government / CTTMO Transport References

- **URL:** https://davaocity.gov.ph/
- **Format:** HTML / PDF / Public announcements
- **Coverage:** City transport programs, terminals, service zones, route announcements, and mobility initiatives.
- **Why it fits the problem:** Provides official local references for transportation services, including city-managed programs, terminals, and possible tricycle route information.
- **Known Limitations:** Transport information may be distributed across multiple announcements instead of a single structured dataset.

---

#### Name: Sakay Davao Community Transport Project

- **URL:** https://github.com/Hanseooo/sakay-davao
- **Format:** GitHub repository files (format depends on repository contents)
- **Coverage:** Davao City public transport-related information and commuter-oriented route references from a community-developed project.
- **Why it fits the problem:** Provides supplementary local transport information that can help identify route patterns and fill gaps when official datasets or OpenStreetMap route relations are incomplete.
- **Known Limitations:** This is a community-developed resource and is not an official government transport dataset. Information must be validated against OpenStreetMap and official transport references before final use.

---

### Fare Data Fallback Strategy

If official fare matrices are unavailable, delayed, or incomplete, I will apply documented fare-estimation rules based on available transport information, including:

- fixed fare values where officially published;
- free-fare rules for government-supported services; and
- base fare plus distance-based per-kilometer calculations where applicable.

Estimated fares will be clearly labeled as approximations and separated from officially sourced fare information to avoid confusing estimated values with official fares.

## Possible Final Dashboard

The dashboard should help the audience quickly see the best estimated commute options from Point A to Point B. It should show the top three route options, estimated total commute time, estimated total fare in PHP, fare breakdown per segment, walking time, waiting time, number of transfers, possible tricycle last-mile connections, and a map showing how jeepney, bus, free-ride, walking, and tricycle segments combine into one trip.

The dashboard should help compare the fastest route, cheapest route, and a balanced route that considers both time and fare.

# Phase 3 / Milestone 3 — Clean Dataset

## Overview

Phase 3 transforms the raw OpenStreetMap transit extract into a clean,
structured, validated, and reproducible dataset for SQL analysis and future
routing logic.

Current processed outputs:

- `data/processed/stops.csv`
- `data/processed/routes.csv`
- `data/processed/route_stops.csv`
- `data/processed/processing_summary.json`
- `data/processed/davao_transit.db`
- `data/processed/business_question_results.txt`

The full schema design is documented in:

```text
docs/schema.md
```

---

## Pipeline

```text
data/raw/osm_davao_transit_elements_20260708.json
        |
        v
scripts/transform.py
        |
        +--> stops.csv
        +--> routes.csv
        +--> route_stops.csv
        +--> processing_summary.json
        |
        v
scripts/load_sqlite.py
        |
        v
davao_transit.db
        |
        v
sql/business_questions.sql
        |
        v
scripts/run_sql.py
        |
        v
business_question_results.txt
```

---

## Processed Schema

### `stops`

**Grain:** one unique OSM transit stop, platform, station, or stop-like route
member.

**Primary key:** `stop_id`

**Identifier format:** `<osm_type>:<osm_id>`

Current count:

```text
122 stops
```

---

### `routes`

**Grain:** one OSM public-transport route relation.

**Primary key:** `route_id`

**Identifier format:** `relation:<osm_relation_id>`

Current count:

```text
14 routes
```

Processed modes:

- 13 bus
- 1 ferry

---

### `route_stops`

**Grain:** one ordered stop/platform occurrence within one route relation.

**Primary key:** `(route_id, stop_sequence)`

**Foreign keys:**

```text
route_id -> routes.route_id
stop_id  -> stops.stop_id
```

Current count:

```text
37 route-stop occurrences
```

---

## Cleaning Decisions

The transform applies the following rules:

- deduplicates records using `(OSM type, OSM ID)`
- keeps the richer record when duplicates exist
- retains only `bus` and `ferry` route relations
- preserves valid unnamed stops as null
- preserves missing route metadata instead of guessing values
- keeps route-referenced stops even when they are not independently tagged
- treats unlabeled route members as route geometry, not stops
- preserves stops without coordinates instead of fabricating locations

Current data-quality results:

| Metric | Value |
|---|---:|
| Raw OSM elements | 77,701 |
| Unique elements after deduplication | 77,697 |
| Duplicate records removed | 4 |
| Processed stops | 122 |
| Processed routes | 14 |
| Route-stop occurrences | 37 |
| Stops missing names | 52 |
| Stops missing coordinates | 4 |

---

## Validation

Validation checks are built into `scripts/transform.py`.

The pipeline checks:

- non-null and unique stop IDs
- non-null and unique route IDs
- unique OSM relation IDs
- valid latitude and longitude ranges
- unique `(route_id, stop_sequence)` values
- valid route and stop foreign-key references
- processed route mode is only `bus` or `ferry`

SQLite also applies primary-key, foreign-key, unique, and range constraints.

---

## SQL Business Questions

Queries are stored in:

```text
sql/business_questions.sql
```

Results are saved in:

```text
data/processed/business_question_results.txt
```

The three questions are:

1. Which transit routes have the most explicitly mapped stops?
2. Which stops are shared by multiple mapped routes?
3. Which consecutive stop-to-stop connections can be derived from ordered
   route-stop data?

Current findings:

- only 7 of 14 processed routes contain explicit stop/platform members
- 10 stops are shared by at least two mapped routes
- Davao City Overland Transport Terminal is shared by 3 mapped routes
- 30 consecutive route-stop edges can currently be derived

---

## Known Limitations

The current OSM extract is not yet a complete Davao City transit network.

Important limitations:

- several local numbered bus routes have no explicit stop sequence
- the source includes both local and intercity routes
- some stops have missing names
- 4 stops have no coordinates
- shared stops are only candidate transfer points, not confirmed transfers
- fare, schedule, tricycle-zone, walking, waiting-time, and traffic data are not
  yet integrated

These gaps are preserved as source limitations rather than filled with
assumptions.

---

## Reproducibility

Running the same transform against the same raw input produced identical
SHA256 hashes across repeated runs.

Run:

```powershell
python .\scripts\transform.py --input .\data\raw\osm_davao_transit_elements_20260708.json
```

Verified outputs:

```text
stops.csv
243B289F5094018CD82652E32529B500861F2B81F5DF6072EAA792ABBB22774D

routes.csv
53FA8F00DD33087DB029DEA66982C11075E55C2923ABEFE4622FA4423E3328E6

route_stops.csv
C39587E5604D0FA9A8172BEB3A4D4675289754A3DE16BD98CB6DDA5D6D537F64

processing_summary.json
0023DB0D700D3A30B42102B05079644BF4C3C0356C18568CFFB423806E5929B7
```

---

## Run the Phase 3 Pipeline

Install dependencies:

```powershell
pip install -r .\requirements.txt
```

Transform the raw dataset:

```powershell
python .\scripts\transform.py --input .\data\raw\osm_davao_transit_elements_20260708.json
```

Load SQLite:

```powershell
python .\scripts\load_sqlite.py
```

Run the SQL questions:

```powershell
python .\scripts\run_sql.py
```

---

## Milestone 3 Checklist

- [x] Processed dataset saved in `/data/processed/`
- [x] Schema plan documented
- [x] Three SQL business questions documented and executed
- [x] Missing values and cleaning decisions documented
- [x] Validation checks integrated into the transform
- [x] Reproducibility confirmed with matching output hashes

This Phase 3 output is the clean foundation for later integration of fares,
schedules, traffic, walking, transfers, tricycle zones, and route optimization.
