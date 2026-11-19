"""Allowlisted M5 aggregate projection from a verified private LTFRB release."""
from collections import Counter
import json
from pathlib import Path

import pandas as pd

from scripts.verify_observatory import verify

CONCLUSION = ('We standardized the transport register, measured its completeness and spatial quality, '
              "and identified the unresolved associations that the Observatory's verification workflow must address.")


def aggregate(release):
    release=Path(release)
    checked=verify(release)
    load=lambda name:json.loads((release/(name+'.json')).read_text(encoding='utf-8'))
    routes,directions,associations,features,layers,assets=[load(n) for n in ('routes','directions','associations','features','layers','assets')]
    manifest=load('manifest');provenance=load('provenance')
    by_route={r['route_id']:r for r in routes}
    by_direction={r['direction_id']:r for r in directions}
    segmented=[]
    def group(dimension,values,denominator,grain):
        for key,count in sorted(Counter(values).items()):
            segmented.append(dict(dimension=dimension,segment=key,count=count,denominator=denominator,grain=grain))
    group('mode x association status',
          (by_route[by_direction[a['direction_id']]['route_id']]['mode']+' | '+a['association_status'] for a in associations),len(directions),'source direction slots, including loop N/A')
    group('mode x review status',(r['mode']+' | '+r['review_status'] for r in routes),len(routes),'workbook route records')
    group('mode x classification',(r['mode']+' | '+r['classification'] for r in routes),len(routes),'workbook route records')
    group('asset status',(r['status'] for r in assets),len(assets),'linked unique source IDs')
    group('feature status',(r['status'] for r in features),len(features),'spatial features')
    group('association status',(r['association_status'] for r in associations),len(associations),'source direction slots, including loop N/A')
    group('route review status',(r['review_status'] for r in routes),len(routes),'workbook route records')
    fields=('route_name','mode','classification','file_id')
    complete=sum(all(r.get(k) for k in fields) for r in routes)
    inspected=sum(a['status']=='inspected' for a in assets)
    present=sum(a['filename'] is not None and a['status']!='incomplete_download' for a in assets)
    crs=sum(l['crs_consistent'] for l in layers)
    passing=sum(f['status']=='geometry_pass' for f in features)
    active=[a for a in associations if a['association_status']!='not_applicable_loop']
    candidates=[a for a in active if a['association_status']=='candidate']
    unresolved=sum(a['association_status']=='unresolved' for a in active)
    flags=sum(a['length_screen']=='review_length_discrepancy' for a in candidates)
    review=sum(r['review_status']=='needs_review' for r in routes)
    records=[
        ('identity_fields_complete',complete,len(routes),'workbook route records','All four normalized identity fields present; validation flags remain separate','100% target','Metadata presence alone does not establish current service'),
        ('complete_source_file_presence',present,len(assets),'linked unique source IDs','Located non-partial files / linked IDs','100% target','Includes incomplete shapefile bundles; not a validity pass'),
        ('spatial_asset_inspection',inspected,len(assets),'linked unique source IDs','Spatial assets inspected / linked IDs','100% target','Readable sources can contain quarantined features'),
        ('consistent_layer_crs',crs,len(layers),'spatial layers','CRS-consistent inspected layers / all inspected layers','100% target','Does not establish route identity or operations'),
        ('geometry_feature_pass',passing,len(features),'spatial features','Structurally passing linear features / inspected features','100% target','Original defects quarantined without repairs; exact duplicates flagged separately'),
        ('unresolved_populated_direction',unresolved,len(active),'populated source direction slots','Directions without candidate geometry / populated directions','Lower is better','Explicit loop N/A slots excluded; candidate is not confirmed'),
        ('candidate_length_review',flags,len(candidates),'candidate direction-feature pairs','Flagged candidate lengths / measured candidate pairs','Flag abs difference > max(0.5 km,10% declared km)','Zero flags does not clear unpaired directions'),
        ('route_review_required',review,len(routes),'workbook route records','Routes with recorded source/direction review flags / workbook rows','Lower is better','Other metadata candidates are not certified services'),
    ]
    metrics=[dict(kpi=k,numerator=n,denominator=d,value_pct=round(100*n/d,2) if d else None,
                  grain=grain,definition=definition,formula='100 * numerator / denominator; null if denominator = 0',
                  threshold=threshold,interpretation=interpretation,source='cleaned_LTFRB_release',
                  release_version=manifest['version'],status='measured' if d else 'not_verified')
             for k,n,d,grain,definition,threshold,interpretation in records]
    metrics.append(dict(kpi='navigation_readiness',numerator=None,denominator=len(routes),value_pct=None,
                        grain='workbook route records',definition='Operationally verified services with boarding and connectivity evidence',
                        formula='Not calculated: required evidence is absent',threshold='All required evidence must be verified',
                        interpretation='Geometry screening cannot verify current operations',source='cleaned_LTFRB_release',
                        release_version=manifest['version'],status='not_verified'))
    # Explicit projection only: never copy release rows, geometry, Drive IDs, WKB or paths.
    stats=manifest['statistics']
    summary={k:stats[k] for k in (
        'source_route_records','normalized_route_records','source_unique_names','normalized_unique_names',
        'linked_source_ids','asset_statuses','spatial_layers','feature_statuses','geometry_duplicate_groups',
        'direction_statuses','association_statuses','length_screening','route_review_statuses',
        'lgu_label_rows','canonical_municipalities_verified','transformation_events','issue_codes')}
    summary.update(release_version=manifest['version'],workbook_sha256=provenance['workbook_sha256'],
                   schema='m5-cleaned-baseline-1',time_scope='single source baseline; no LTFRB historical trend',
                   source_effective_date=None,spatial_roundtrip_features=checked['geometry_roundtrip_features'])
    assert sum(r['count'] for r in segmented if r['dimension']=='mode x association status')==len(directions)
    return summary,metrics,segmented


def write_projection(release, destination, expected_workbook_sha=None):
    summary,metrics,segments=aggregate(release)
    if expected_workbook_sha and summary['workbook_sha256']!=expected_workbook_sha:
        raise ValueError('Cleaned release workbook differs from existing segmentation source')
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    for name,value in [('cleaned_release_summary',summary),('cleaned_quality_kpis',metrics),('cleaned_segmentation',segments)]:
        (destination/(name+'.json')).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
        if isinstance(value,list):pd.DataFrame(value).to_csv(destination/(name+'.csv'),index=False)
    return summary


def brief(k,gis,cleaned):
    s=cleaned
    return f'''# Davao Transport Data Observatory — M5 stakeholder brief

**Purpose.** The original commuter-routing question exposed a prerequisite: transport records must be dependable before navigation features can be justified. M5 assesses that foundation for data stewards, researchers and transport planners. Network X-Ray and the Route Verification Workbench are future application components, not implemented M5 features.

**Segment findings.** The LTFRB Region XI register contains {k['workbook_route_rows']} records: 193 PUJ, 65 PUB and 27 UV Express. EXISTING/IRIP comparisons differ sharply: PUJ 168/25, PUB 12/53, UV Express 1/26. These are source classifications, not current service counts. All 285 records have first-direction metadata; 157 have second-direction metadata and 128 explicitly describe one-direction loops. LGU text mentions indicate documentary scope, not measured municipal access.

**Quality baseline.** The cleaned release retains all {s['normalized_route_records']} records and logs {s['transformation_events']:,} transformations. Of {s['linked_source_ids']} linked file IDs, 262 spatial assets were inspected; two downloads are partial and two shapefiles lack dependencies. The 262 layers contain 266 features: 263 pass structural checks and three are quarantined without repair. Layer-level screening separately passes 259/262. File, layer, feature and route counts are different denominators.

**Unresolved evidence.** Of 442 populated direction slots, 118 have automatic candidate geometry matches and 324 (73.30%) remain unresolved; 128 loop N/A slots are excluded. Candidates comprise 117 PUJ and one PUB direction, with none for UV Express; this describes matching evidence, not service reliability. All 118 candidate lengths fall within max(0.5 km, 10% declared distance); this does not validate the unpaired directions. One exact geometry-duplicate group and {s['route_review_statuses']['needs_review']} route review cases need investigation. Municipality identities remain unverified.

**Time comparison.** Five OSM completeness KPIs are unchanged between July 8 and August 1, 2026: named stops 57.38%, geocoded stops 96.72%, ordered-stop routes 50%, origin metadata 42.86%, destination metadata 42.86%. These are mapping cross-sections, not service or ridership trends. LTFRB supplies one separate baseline; historical change is not verified.

**Priorities.** Complete four source-file exceptions; review invalid/duplicate geometry and direction identity; reconcile locality labels with authoritative context. Keep raw and row-level government-derived records private unless cleared. No boarding, transfers, current schedules, fares, travel times or navigation readiness are established. These findings define the future verification queue; application development belongs to M6.

**Conclusion.** {CONCLUSION}
'''
