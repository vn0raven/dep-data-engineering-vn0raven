# Davao Commute Router: Estimating the Fastest and Most Affordable Public Transport Route in Davao City

## Problem Statement
I want to answer: "How can route, stop, schedule, road-network, local transport-zone, traffic, and fare data be integrated into a routing pipeline that estimates the fastest and most affordable door-to-door public transport route between selected origin and destination points in Davao City in 2026, using jeepneys, DC Bus, Love Bus, tricycles, and other publicly documented free-ride services?"

## Audience
This project is for Davao commuters, especially students, workers, and first-time riders who need help choosing the best combination of public transport modes based on both travel time and fare cost. It can also support Davao City transport planners, LTFRB Region XI, CTTMO, and local researchers who want to understand how jeepney, bus, free-ride, and tricycle routes connect across the city.

## KPI or Key Metric
The main metrics I want to track are Estimated Door-to-Door Commute Time in minutes and Estimated Total Fare in PHP.

Estimated Door-to-Door Commute Time will measure the total travel time from Point A to Point B, including walking time, waiting time, in-vehicle travel time, transfer time, and possible traffic delay.

Estimated Total Fare will measure the total commute cost by adding the fare of each paid public transport segment. This is important because the fastest route may not always be the most practical route if it requires extra paid transfers.

## Data Source Notes

### Primary Source

- **Name:** OpenStreetMap (OSM) Data via Overpass API
- **URL:** https://overpass-api.de/
- **Format:** JSON / XML
- **Ingestion Strategy:** I will develop a Python-based extraction script (`scripts/ingest.py`) that uses Overpass API queries to retrieve transportation-related geographic features within Davao City. Extracted features will include road networks, pedestrian paths, public transport stops, and mapped route relations. The collected data will be stored locally for route analysis, visualization, and transportation modeling.
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

- Fixed fare values where officially published
- Free-fare rules for government-supported services
- Base fare plus distance-based per-kilometer calculations where applicable

Estimated fares will be clearly labeled as approximations and separated from officially sourced fare information to avoid confusing estimated values with official fares.

## Possible Final Dashboard
The dashboard should help the audience quickly see the best estimated commute options from Point A to Point B. It should show the top 3 route options, estimated total commute time, estimated total fare in PHP, fare breakdown per segment, walking time, waiting time, number of transfers, possible tricycle last-mile connections, and a map showing how jeepney, bus, free-ride, walking, and tricycle segments combine into one trip.

The dashboard should help compare the fastest route, cheapest route, and a balanced route that considers both time and fare.

ps. i hate davao traffic/commute
