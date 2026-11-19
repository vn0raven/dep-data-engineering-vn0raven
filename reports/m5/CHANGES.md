# M5 candidate change summary

The original routing question now motivates data-reliability analysis for the Davao Transport Data Observatory. Existing M4 analysis, notebook and figures are preserved. M5 retains five OSM completeness KPIs across two actual snapshots and integrates an allowlisted aggregate projection from the independently verified cleaned LTFRB release.

Implementation changes: scripts/m5_release.py adds verified aggregate projection; scripts/m5_delivery.py generates the cleaned-baseline figures/brief and aligned report; scripts/run_m5.py connects the existing cleaning pipeline to M5; scripts/check_m5_privacy.py inspects explicit commit candidates and the real index without staging. Existing ETL is reused, not rebuilt.

Outputs: executed notebook; primary KPI definitions/history; original and cleaned quality tables; segmentation CSV/JSON; 13 report figures; existing static report; concise stakeholder brief; methodology, compliance, privacy, test and reproduction evidence. PUBLIC_FILES.txt is the exact candidate list. It includes the previously created ETL and tests because they are still uncommitted in this checkout.

Restricted exclusions: raw workbook/files, route-level cleaned release, original values, IDs/URLs, WKB/GeoJSON/GeoPackage, detailed GIS audits and caches. Local prototype files outside the repository are not candidates. Safe aggregate projections remain subject to human publication review. No index mutation, commit, push, submission or deployment was performed.

Suggested commit title: feat(m5): finalize Observatory analysis, cleaned baseline and verified KPI evidence
