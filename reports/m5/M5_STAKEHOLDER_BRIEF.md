# Davao Transport Data Observatory — M5 stakeholder brief

**Purpose.** The original commuter-routing question exposed a prerequisite: transport records must be dependable before navigation features can be justified. M5 assesses that foundation for data stewards, researchers and transport planners. Network X-Ray and the Route Verification Workbench are future application components, not implemented M5 features.

**Segment findings.** The LTFRB Region XI register contains 285 records: 193 PUJ, 65 PUB and 27 UV Express. EXISTING/IRIP comparisons differ sharply: PUJ 168/25, PUB 12/53, UV Express 1/26. These are source classifications, not current service counts. All 285 records have first-direction metadata; 157 have second-direction metadata and 128 explicitly describe one-direction loops. LGU text mentions indicate documentary scope, not measured municipal access.

**Quality baseline.** The cleaned release retains all 285 records and logs 3,248 transformations. Of 266 linked file IDs, 262 spatial assets were inspected; two downloads are partial and two shapefiles lack dependencies. The 262 layers contain 266 features: 263 pass structural checks and three are quarantined without repair. Layer-level screening separately passes 259/262. File, layer, feature and route counts are different denominators.

**Unresolved evidence.** Of 442 populated direction slots, 118 have automatic candidate geometry matches and 324 (73.30%) remain unresolved; 128 loop N/A slots are excluded. Candidates comprise 117 PUJ and one PUB direction, with none for UV Express; this describes matching evidence, not service reliability. All 118 candidate lengths fall within max(0.5 km, 10% declared distance); this does not validate the unpaired directions. One exact geometry-duplicate group and 171 route review cases need investigation. Municipality identities remain unverified.

**Time comparison.** Five OSM completeness KPIs are unchanged between July 8 and August 1, 2026: named stops 57.38%, geocoded stops 96.72%, ordered-stop routes 50%, origin metadata 42.86%, destination metadata 42.86%. These are mapping cross-sections, not service or ridership trends. LTFRB supplies one separate baseline; historical change is not verified.

**Priorities.** Complete four source-file exceptions; review invalid/duplicate geometry and direction identity; reconcile locality labels with authoritative context. Keep raw and row-level government-derived records private unless cleared. No boarding, transfers, current schedules, fares, travel times or navigation readiness are established. These findings define the future verification queue; application development belongs to M6.

**Conclusion.** We standardized the transport register, measured its completeness and spatial quality, and identified the unresolved associations that the Observatory's verification workflow must address.
