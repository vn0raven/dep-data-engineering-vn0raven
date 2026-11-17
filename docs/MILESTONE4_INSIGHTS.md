# M4 — Initial Insights: Davao Commute Router

**Source snapshot:** `osm_davao_transit_elements_20260708.json` (OpenStreetMap via Overpass; route and stop records may be intercity).  
**Interpretive scope:** A descriptive audit of the Milestone 3 OSM extract, **not** a measured assessment of Davao City's current public transport coverage, actual operations or rider experience.

## Figure 1 — Route-to-stop coverage

![Mapped route stop occurrences](../output/figures/01_route_stop_coverage.png)

**Observation.** 7 of 14 mapped OSM route relations (50.0%) include explicit stop/platform members; 7 have none. There are 37 ordered route-stop occurrences in total. Some long-distance routes have more recorded stops than local numbered routes.

**Interpretation.** The extracted stop sequences are insufficient to operate a reliable Davao-only bus/jeepney router. A route with zero explicit stops is not proof that it has no real-world stops.

## Figure 2 — Stop metadata completeness

![Stop metadata completeness](../output/figures/02_stop_metadata_quality.png)

**Observation.** 52 of 122 stops (42.6%) have no name; 4 lack valid point coordinates.

**Interpretation.** Unnamed records reduce destination search usability. Non-point or missing coordinates prevent direct map snapping without additional geometry processing. These records were intentionally retained instead of guessed or deleted.

## Figure 3 — Geographic dispersion

![Coordinate spread](../output/figures/03_stop_coordinate_spread.png)

**Observation.** The 118 valid stop coordinates have a broad geographic spread. Some belong to route relations connecting Davao with destinations elsewhere in the Philippines.

**Interpretation.** A Davao-filtered OSM extraction can still include out-of-area *relation members*. We must clip and verify the actual geographic service area before presenting city-specific coverage. This scatterplot is **not** a cartographic route map or service-area polygon.

## Figure 4 — Candidate shared stops

![Shared stop identifiers](../output/figures/04_candidate_transfer_stops.png)

**Observation.** 10 unique stop identifiers occur in two or more route relations; 1 of these records have names, and 2 lack point coordinates.

**Interpretation.** These overlaps are *candidate* transfer references only. They do not prove walkability, direction, local relevance, transfer legality, operating hours or current service.

## Descriptive statistics and interpretation

**Unit of analysis:** all 14 OSM route relations for stop occurrences (including zeros), and all 122 unique stop records for distinct-route membership (including zeros). These are *population statistics of the July 2026 extract*, not estimates of all active transport routes. Standard deviation uses `ddof=0`; quartiles use NumPy's linear interpolation.

| Key measure | Mean | Median | Population SD | Q1 | Q3 | IQR | Minimum–maximum | Range | Zeros |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Ordered stop occurrences per route | 2.64 | 0.50 | 3.60 | 0.00 | 4.75 | 4.75 | 0–10 | 10 | 7 |
| Distinct route relations per stop | 0.30 | 0.00 | 0.64 | 0.00 | 0.00 | 0.00 | 0–3 | 3 | 96 |

**Interpretation.** Ordered stops have mean 2.64 but median 0.50. The difference and the 7 zero-count relations indicate highly uneven mapping across route relations; a few have many recorded stop members while half have none. Distinct-route membership likewise describes mapping relationships, not confirmed passenger transfers. A median of zero or one is a data gap, not a real-world service claim.

## Hypothesis-based comparison (exploratory, not causal)

**Plain-language hypothesis.** Mapped stop IDs shared by >=2 route relations are more likely to have names.

**Evidence.** Among stop IDs shared by at least two distinct route relations, 1/10 (10.00%) have names. Among stops with zero or one relation, 69/112 (61.61%) have names. The difference (shared minus other) is -51.61 percentage points: **this extract does not support the hypothesis**.

**Caveats.** Single nonrandom OSM extract; small unequal groups and intercity relation members. Name completeness does not establish a real transfer or active route. This comparison was proposed for descriptive exploration; there is no random sample, causal inference or operational transfer verification.

## Cautious inference and next action

The first barrier to estimating the **fastest and cheapest door-to-door commute** is not algorithm selection: it is data completeness and geographic/service validation. The Milestone 3 data contain **no validated fares, timetables, waiting-time profiles, tricycle operating zones or local walking network**. Therefore, neither commute time nor fare can be calculated responsibly from these tables alone.

The analyses support prioritizing (1) Davao-only route scope and ordered boarding data, (2) verifiable local service records, (3) route/fare operating rules, and (4) separate walkable-road extraction. The charts cannot establish the true number of active routes in the city, overall stop coverage, traffic conditions or whether any specific transfer is feasible.

## Reproducibility

From repository root:

```powershell
pip install -r requirements.txt
python scripts/m4_insights.py
```

This builds four PNG charts, `data/processed/m4_insights_summary.json`, this document, and a **static offline-viewable** `dashboard/index.html`. These artifacts are generated from the checked-in M3 CSVs with no internet calls. Open the dashboard locally in a browser. Inspect `notebooks/m4_initial_insights.ipynb` to run the analysis interactively.

## Data governance

OpenStreetMap data: © OpenStreetMap contributors, ODbL 1.0. See <https://www.openstreetmap.org/copyright>. The descriptive charts are generated from the July 8, 2026 committed extract. Do not label OSM route relations as current government-authorized services without corroboration.
