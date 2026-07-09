# Davao Commute Router: Estimating the Fastest and Most Affordable Public Transport Route in Davao City

## Problem Statement
I want to answer: "How can route, stop, schedule, road-network, local transport-zone, traffic, and fare data be integrated into a routing pipeline that estimates the fastest and most affordable door-to-door public transport route between selected origin and destination points in Davao City in 2026, using jeepneys, DC Bus, Love Bus, tricycles, and other publicly documented free-ride services?"

## Audience
This project is for Davao commuters, especially students, workers, and first-time riders who need help choosing the best combination of public transport modes based on both travel time and fare cost. It can also support Davao City transport planners, LTFRB Region XI, CTTMO, and local researchers who want to understand how jeepney, bus, free-ride, and tricycle routes connect across the city.

## KPI or Key Metric
The main metrics I want to track are Estimated Door-to-Door Commute Time in minutes and Estimated Total Fare in PHP.

Estimated Door-to-Door Commute Time will measure the total travel time from Point A to Point B, including walking time, waiting time, in-vehicle travel time, transfer time, and possible traffic delay.

Estimated Total Fare will measure the total commute cost by adding the fare of each paid public transport segment. This is important because the fastest route may not always be the most practical route if it requires extra paid transfers.

## Likely Data Source
I will explore OpenStreetMap / Overpass API (https://overpass-api.de/) as the main source for roads, walkable paths, mapped routes, stops, and route relations. I will also explore DC Bus public route and schedule pages (https://davaobus.com/schedule), Davao City public transport mapping references (https://wiki.openstreetmap.org/wiki/Davao_City/Public_transportation), public route announcements for Love Bus and free-ride services, publicly available CTTMO or city government references for tricycle routes, terminals, service zones, and fare rules, and LTFRB Region XI public fare matrix references for jeepney and route fare data.

If complete official fare matrices are difficult to access or delayed, I will use fallback fare-estimation rules such as fixed fare, free fare, base fare, and distance-based per-kilometer calculations where applicable. I will also explore community mapping repositories such as ttg-eng/routes as a fallback source for public transport route geometry.

## Possible Final Dashboard
The dashboard should help the audience quickly see the best estimated commute options from Point A to Point B. It should show the top 3 route options, estimated total commute time, estimated total fare in PHP, fare breakdown per segment, walking time, waiting time, number of transfers, possible tricycle last-mile connections, and a map showing how jeepney, bus, free-ride, walking, and tricycle segments combine into one trip.

The dashboard should help compare the fastest route, cheapest route, and a balanced route that considers both time and fare.

ps. i hate davao traffic/commute