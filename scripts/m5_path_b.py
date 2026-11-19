"""DEP M5 Path B: LTFRB route register segmentation + GIS data-quality KPIs.

Use only private staged workbook metadata and audited file results. Never infer
current operation, shared route identity with OSM, or navigation eligibility.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def rows(path: Path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def ratio(a,b):return round(100*a/b,2) if b else None


def present(v):return str(v or '').strip().lower() not in ('','n/a','na','-','none')

def positive_length(v):
    import math
    try:return math.isfinite(float(v)) and float(v)>0
    except (ValueError,TypeError):return False


def analyze(routes: list[dict],files: list[dict],layers: list[dict],lengths: list[dict],osm: dict) -> dict:
    mode=Counter(r['mode'] for r in routes)
    classification=Counter(r['route_classification'] for r in routes)
    segment=Counter((r['mode'],r['route_classification']) for r in routes)
    lptrp=Counter(r['lptrp_classification'] for r in routes)
    source_ids=[r['file_id'] for r in routes if r.get('file_id')]
    shared_ids={k:v for k,v in Counter(source_ids).items() if v>1}
    n=len(routes)
    first=sum(present(r['direction_1']) and positive_length(r['length_km_1']) for r in routes)
    second=sum(present(r['direction_2']) and positive_length(r['length_km_2']) for r in routes)
    one_way=sum('loop' in r['direction_1'].lower() and not present(r['direction_2']) for r in routes)
    file_ids=set(source_ids)
    davao_mention=sum('davao city' in r.get('lgu_1','').lower() for r in routes)
    audited={f['file_id'] for f in files if f['file_status']=='audited' and f['file_id'] in file_ids}
    missing={f['file_id'] for f in files if f['file_status']=='missing_local_file' and f['file_id'] in file_ids}
    gis_verified=bool(audited)
    validations=[r for r in lengths if r.get('measured_length_km') not in ('',None)]
    geometry_clean=[r for r in layers if str(r.get('feature_count')) not in ('0','',None) and
                    str(r.get('crs_present')).lower()=='true' and
                    str(r.get('crs_metadata_consistent')).lower()=='true' and
                    int(r.get('invalid_geometry') or 0)==0 and
                    int(r.get('null_geometry') or 0)==0 and
                    int(r.get('empty_geometry') or 0)==0 and not r.get('error')]
    return {
        'phase5_path':'B - Segmentation and KPIs',
        'scope':'LTFRB Region XI workbook route register; source inventory, not verified current public transport operations',
        'workbook_route_rows':n,
        'route_modes':dict(sorted(mode.items())),
        'classification':dict(sorted(classification.items())),
        'mode_by_classification':[{'mode':mode,'classification':cls,'count':v} for (mode,cls),v in sorted(segment.items())],
        'lptrp_classification':dict(sorted(lptrp.items())),
        'unique_linked_geo_packages':len(file_ids),
        'route_records_with_gpkg_link':len(source_ids),
        'lgu_field_mentions_davao_city':davao_mention,
        'lgu_field_mentions_davao_city_pct':ratio(davao_mention,n),
        'lgu_proxy_caveat':'String mentions in a corridor LGU field are not spatial coverage or operation evidence.',
        'duplicated_link_ids_count':len(shared_ids),
        'duplicate_link_extra_references':sum(v-1 for v in shared_ids.values()),
        'direction_1_filled_with_length':first,
        'direction_2_filled_with_length':second,
        'one_direction_loop_rows':one_way,
        'record_link_completeness_percent':ratio(len(source_ids),n),
        'direction_1_completeness_percent':ratio(first,n),
        'direction_2_completeness_percent':ratio(second,n),
        'audit_file_ids_readable':len(audited),
        'audit_file_ids_missing_locally':len(missing),
        'audit_coverage_percent':ratio(len(audited),len(file_ids)),
        'audited_gis_layers':len(layers),
        'geometry_crs_valid_layers':len(geometry_clean),
        'geometry_crs_valid_layer_percent':ratio(len(geometry_clean),len(layers)) if layers else None,
        'measurable_directional_length_candidates':len(validations),
        'directional_length_review_flags':sum(r.get('threshold_result')=='review_length_discrepancy' for r in validations),
        'directional_length_within_screening_tolerance':sum(r.get('threshold_result')=='within_screening_tolerance' for r in validations),
        'gis_evidence_present':gis_verified,
        'osm_m4_distinct_snapshot':{'mapped_route_relations':osm.get('routes'),
                                    'mapped_stop_records':osm.get('stops'),
                                    'ordered_stop_occurrences':osm.get('route_stop_occurrences')},
        'cross_source_matching': 'NOT PERFORMED: LTFRB route register entries and OSM route relations are not equivalent entities',
        'navigation_eligible_routes': None,
        'navigation_eligibility_note': 'Not assessed. Layer validity and government file provenance cannot establish real boarding or operational service.',
    }


def plot_bar(data, label, title, outfile):
    keys=list(data);values=[data[k] for k in keys]
    fig,ax=plt.subplots(figsize=(8,4.8))
    bars=ax.barh(keys,values)
    ax.invert_yaxis();ax.set_xlabel(label)
    ax.set_title(title,loc='left',weight='bold')
    ax.spines[['top','right']].set_visible(False)
    for bar,value in zip(bars,values):ax.text(value+max(values)*0.02,bar.get_y()+bar.get_height()/2,str(value),va='center')
    ax.set_xlim(0,max(values)*1.17)
    fig.tight_layout();fig.savefig(outfile,dpi=145,facecolor='white');plt.close(fig)


def main():
    p=argparse.ArgumentParser(description='M5 Path B: route segmentation and conditional GIS quality measures')
    p.add_argument('--register',required=True,type=Path)
    p.add_argument('--gis-report',type=Path,default=Path('reports/ltfrb'))
    p.add_argument('--out',type=Path,default=Path('reports/m5'))
    p.add_argument('--osm-summary',type=Path,default=Path('data/processed/m4_insights_summary.json'))
    p.add_argument('--dashboard',type=Path,default=Path('dashboard/m5.html'))
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    source=rows(args.register)
    def getrows(filename):
        path=args.gis_report/filename
        return rows(path) if path.is_file() else []
    files=getrows('file_inventory.csv')
    layers=getrows('layer_quality.csv')
    lengths=getrows('directional_length_screening.csv')
    osm=json.loads(args.osm_summary.read_text(encoding='utf-8')) if args.osm_summary.is_file() else {}
    k=analyze(source,files,layers,lengths,osm)
    (args.out/'m5_kpis.json').write_text(json.dumps(k,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    images=args.out/'figures';images.mkdir(exist_ok=True)
    plot_bar(k['route_modes'],'Workbook route records','Route register by transport category',images/'01_modes.png')
    plot_bar(k['classification'],'Workbook route records','Classification of workbook route entries',images/'02_classification.png')
    plot_bar({'Direction 1 with km':k['direction_1_filled_with_length'],
              'Direction 2 with km':k['direction_2_filled_with_length'],
              'One-direction loops':k['one_direction_loop_rows']},
              'Workbook route records','Directional fields and loop-route completeness',images/'03_direction_completeness.png')
    lines=[
        '# M5 — Path B: Segmentation and KPIs',
        '', '## Scope and stakeholders',
        'Audience: data stewards, GIS validators and transport stakeholders. This is an **inventory and data-quality** analysis, not a trip planner or a verified transport-service directory.',
        'LTFRB Region XI workbook route entries are not assumed to match OSM route relations. The workbook and M4 OSM inputs remain separately identifiable.',
        '', '## Observed segmentation',
        f'- **{k["workbook_route_rows"]}** workbook route records; {k["unique_linked_geo_packages"]} distinct Drive IDs.',
        '- By transport category: '+', '.join(f'{mode} {count}' for mode,count in k['route_modes'].items())+'.',
        '- By route classification: '+', '.join(f'{status} {count}' for status,count in k['classification'].items())+'.',
        f'- Repeated Drive IDs: {k["duplicated_link_ids_count"]} distinct IDs are reused, adding {k["duplicate_link_extra_references"]} extra links to workbook records. Reuse is not automatically a duplicate route.',
        f'- Corridor LGU fields mentioning Davao City: {k["lgu_field_mentions_davao_city"]}/{k["workbook_route_rows"]} ({k["lgu_field_mentions_davao_city_pct"]}%). Text mention is **not** measured geographic route coverage.',
        '', '![Categories](figures/01_modes.png)', '', '![Classifications](figures/02_classification.png)',
        '', '## Completeness and GIS quality',
        f'- First-direction fields with lengths: {k["direction_1_filled_with_length"]}/{k["workbook_route_rows"]} ({k["direction_1_completeness_percent"]}%).',
        f'- Second-direction fields with lengths: {k["direction_2_filled_with_length"]}/{k["workbook_route_rows"]} ({k["direction_2_completeness_percent"]}%).',
        f'- One-direction loop labels with no second direction: {k["one_direction_loop_rows"]}. Do **not** treat these necessarily as missing reciprocal route geometry.',
        '', '![Directional completeness](figures/03_direction_completeness.png)',
        f'- File IDs successfully audited locally: **{k["audit_file_ids_readable"]} / {k["unique_linked_geo_packages"]}**.',
        f'- File IDs without files in this local audit environment: **{k["audit_file_ids_missing_locally"]}**. This is not evidence they were never downloaded elsewhere.',
        f'- Audited spatial layers: **{k["audited_gis_layers"]}**; CRS-present and no null, empty or invalid geometries (basic screening): **{k["geometry_crs_valid_layers"]}**.',
        f'- Candidate measured directional length comparisons: **{k["measurable_directional_length_candidates"]}**, of which **{k["directional_length_review_flags"]}** exceed screening tolerances.',
        '', '## Interpretation and decision',
        'First-direction metadata is more complete than second-direction fields, partly because some routes are explicitly one-direction loops. Linked files are not the same as validated linework: GIS completeness must be measured from actually available files, and directional length comparisons require conservative pairing evidence.',
        'We do **not** treat the number of LTFRB workbook rows as the number of active Davao City routes, nor the number of OSM relations as an independent denominator for geographic coverage.',
        '', '## Stakeholder actions',
        '1. Resolve any remaining locally missing and corrupt GeoPackages; rerun the GIS auditor.',
        '2. Review CRS, feature validity, duplicated shapes and directional ambiguity before approving route-distance comparisons.',
        '3. Request official service and boarding verification before releasing an offline routing network.',
        '4. Obtain dated travel-time observations for any later empirical prediction project.',
        '', '## Caveats',
        'Workbook route metadata includes wider Region XI and intercity records; route classifications such as IRIP cannot be assumed to signify active service. Names, route IDs and actual geographic extents may differ across source systems. No predictive travel-time model or current fare calculation is supported by these inputs alone.',
        '', '## Evidence and repeatability',
        'Source: supplied `REGION 11 ROUTE STRUCTURE DATABASE.xlsx`, sheet `SUMMARY`; optional local `LTFRB_GeoPackages/` verified by `scripts/validate_ltfrb_gis.py`; M4 OSM source is separately documented. Aggregates are computed from staged CSVs and audit outputs, not hard-coded.',
    ]
    (args.out/'M5_STAKEHOLDER_BRIEF.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    args.dashboard.parent.mkdir(parents=True,exist_ok=True)
    rel_fig='m5_assets'
    from shutil import copyfile
    assets=args.dashboard.parent/rel_fig;assets.mkdir(exist_ok=True)
    for img in images.glob('*.png'):copyfile(img,assets/img.name)
    blocks=''.join(f'<figure><img src="{rel_fig}/{name}" alt="{name}" loading="lazy"></figure>' for name in ('01_modes.png','02_classification.png','03_direction_completeness.png'))
    args.dashboard.write_text(f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LTFRB M5 Path B audit</title><style>body{{font:16px/1.55 system-ui,sans-serif;background:#f4f7fb;color:#162c43;margin:0}}header{{background:#173955;color:white;padding:3.5rem max(1.5rem,calc((100% - 1000px)/2))}}main{{max-width:1000px;margin:auto;padding:2rem 1.5rem}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem}}.card,figure,section{{background:white;border:1px solid #dee7f0;border-radius:12px;padding:1.25rem}}.card strong{{display:block;font-size:2rem}}.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:1rem;margin:2rem 0}}figure{{margin:0}}img{{width:100%;height:auto}}a{{color:#146b85}}</style></head><body><header><p>DEP OPEN TRACK / M5 · PATH B</p><h1>Region XI transport register</h1><p>Segmentation, source completeness and validation readiness — not live routes.</p></header><main><div class="cards"><article class="card">Route records<strong>{k['workbook_route_rows']}</strong></article><article class="card">Distinct Drive IDs<strong>{k['unique_linked_geo_packages']}</strong></article><article class="card">Audited local files<strong>{k['audit_file_ids_readable']}</strong></article><article class="card">Evaluated length pairs<strong>{k['measurable_directional_length_candidates']}</strong></article></div><div class="charts">{blocks}</div><section><h2>Interpretation</h2><p>The workbook summarizes transportation metadata across Region XI. Routes are not independently verified active or navigation-ready. Missing GIS files in this audit environment are treated as unverified, not presumed absent at source.</p><p>OSM M4 mapping snapshot: {osm.get('routes','unknown')} relations and {osm.get('stops','unknown')} stop records. They use a different source universe from the {len(source)} LTFRB route entries, so no route-level match has been asserted.</p><p>For methods and limitations, see the generated stakeholder brief and the project documentation.</p></section></main></body></html>''',encoding='utf-8')
    print(json.dumps(k,indent=2))

if __name__=='__main__':main()
