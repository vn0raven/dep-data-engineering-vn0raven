"""Allowlisted M5 aggregate projection from a verified private LTFRB release."""
from collections import Counter
import json
from pathlib import Path

import pandas as pd

from scripts.verify_observatory import verify

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


def brief(cleaned):
    associations = cleaned['association_statuses']
    unresolved = associations['unresolved']
    populated = unresolved + associations['candidate']
    match_finding = (
        f'About {unresolved / populated:.0%} of the route directions we could assess '
        'still need a map line that can be linked to them with confidence.'
        if populated else 'The register did not contain any route directions we could assess.'
    )
    return f'''# Davao Transport Data Observatory — M5 stakeholder brief

We checked whether the Land Transportation Franchising and Regulatory Board (LTFRB) Region XI route register could be linked to the supplied map files. {match_finding} Planners can use the findings to decide which records to verify before relying on the map.

Most jeepney (PUJ) entries are listed as existing routes. Most bus and UV Express entries are marked IRIP, the register’s label for routes between provinces or regions. These labels describe how routes are recorded. Current service still needs confirmation.

Most map lines passed basic checks. Some map files were incomplete, and a few lines had errors that kept them out of the usable map files. A line that passes those checks still needs to be matched to the correct route and direction. OpenStreetMap showed no change in the completeness measures we checked between the July and August snapshots. We had a single LTFRB snapshot, so changes in the register over time remain unknown.

**Recommended next steps**

1. **LTFRB Region XI data team** should supply complete copies of the incomplete map files, review lines flagged for errors, and identify which line belongs to each route direction. This gives planners a sound basis for reviewing the network.
2. **Davao City Transport and Traffic Management Office** should check route paths and boarding points with operators on corridors under planning review. Recording the date of each check helps planners judge how current the evidence is.
3. **OpenStreetMap contributors** should update missing stop names and stop order where surveys or sources permitted for OpenStreetMap support the change. This makes routes easier to interpret and compare in future map snapshots.

The Observatory’s planned review tool can track these checks and the evidence behind each decision. The accompanying notebook and quality report contain the full counts and methods.
'''
