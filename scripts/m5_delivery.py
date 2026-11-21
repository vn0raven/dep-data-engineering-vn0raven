"""Reproducible M5 aggregate products. Private source files are never published."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from html import escape

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import transform as t
from scripts.m5_path_b import analyze, rows, present, ratio
from scripts.m5_release import write_projection, brief as observatory_brief

PRIMARY = {
    'named_stops': ('Named mapped stops', 'stop records with nonblank name', 'all mapped stop records', 'Find missing passenger-facing labels'),
    'geocoded_stops': ('Geocoded mapped stops', 'stop records with latitude and longitude', 'all mapped stop records', 'Prioritize location verification'),
    'ordered_routes': ('Routes with ordered stop members', 'route relations with at least one ordered stop member', 'bus/ferry route relations', 'Identify mapping gaps before graph construction'),
    'origin_routes': ('Routes with origin metadata', 'route relations with nonblank from tag', 'bus/ferry route relations', 'Check directional metadata'),
    'destination_routes': ('Routes with destination metadata', 'route relations with nonblank to tag', 'bus/ferry route relations', 'Check directional metadata'),
}

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')

def save_table(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(data).to_csv(path, index=False)

def temporal():
    """Apply the unchanged M3 selection to each real committed snapshot in memory."""
    output=[]
    for path in sorted((ROOT/'data/raw').glob('osm_davao_transit_elements_*.json')):
        if path.name.endswith('.metadata.json'): continue
        meta=json.loads(path.with_suffix('.metadata.json').read_text(encoding='utf-8'))
        source_date=meta.get('accessed_date_utc') or meta['accessed_at_utc'][:10]
        lookup,_=t.deduplicate_elements(t.load_raw(path))
        relations=[x for x in lookup.values() if t.is_transit_route(x)]
        stops=t.build_stops(lookup,relations,path.name)
        routes=t.build_routes(relations,path.name)
        links=t.build_route_stops(relations)
        t.validate(stops,routes,links)
        counts={'named_stops':int(stops.name.fillna('').str.strip().ne('').sum()),
                'geocoded_stops':int(stops[['latitude','longitude']].notna().all(axis=1).sum()),
                'ordered_routes':int(links.route_id.nunique()),
                'origin_routes':int(routes.origin_name.fillna('').str.strip().ne('').sum()),
                'destination_routes':int(routes.destination_name.fillna('').str.strip().ne('').sum())}
        raw=path.read_bytes()
        sha=hashlib.sha256(raw).hexdigest()
        source_sha=meta.get('response',{}).get('sha256')
        checksum_status='no_original_checksum' if source_sha is None else 'exact_match'
        if source_sha not in (None,sha):
            if hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()!=source_sha:
                raise ValueError(f'Snapshot checksum mismatch: {path.name}')
            checksum_status='matches_after_Git_CRLF_to_LF_normalization'
        for key,n in counts.items():
            d=len(stops) if key.endswith('stops') else len(routes)
            output.append(dict(source='OSM',snapshot_date=source_date,kpi=key,numerator=n,
                               denominator=d,value_pct=ratio(n,d),source_sha256=sha,
                               source_file=path.name,checksum_status=checksum_status))
    return output

def diagnostics(register, files, layers, comparisons):
    ids={r['file_id'] for r in register if r['file_id']}
    linked={r['file_id']:r for r in files if r['file_id'] in ids and r['file_status']!='multiple_local_candidates'}
    available=sum(r['file_status']!='missing_local_file' for r in linked.values())
    audited=sum(r['file_status']=='audited' for r in linked.values())
    clean=[r for r in layers if not r['error'] and int(r['feature_count'] or 0)>0 and
           str(r['crs_present']).lower()=='true' and str(r['crs_metadata_consistent']).lower()=='true' and
           all(int(r[k] or 0)==0 for k in ('null_geometry','empty_geometry','invalid_geometry'))]
    usable=[r for r in comparisons if r['measured_length_km'] not in ('',None)]
    definitions=[
        ('source_metadata',sum(all(present(r.get(k)) for k in ('route_no','mode','route_name','route_classification','file_id')) for r in register),len(register),'Rows with all five identity fields / workbook rows','100% target'),
        ('file_availability',available,len(ids),'Located recognized files / linked unique Drive IDs','100% target; extension does not imply valid GPKG'),
        ('successful_file_audit',audited,len(ids),'Fully readable files / linked unique Drive IDs','100% target; readability is not geometry approval'),
        ('clean_geometry_crs',len(clean),len(layers),'Nonempty, CRS-consistent layers without null/empty/invalid features / inspected layers','100% target; overlaps and identity assessed separately'),
        ('crs_presence',sum(str(r['crs_present']).lower()=='true' for r in layers),len(layers),'Layers declaring CRS / inspected layers','100% target'),
        ('length_review',sum(r['threshold_result']=='review_length_discrepancy' for r in usable),len(usable),'Flagged candidate direction lengths / measured candidate pairs','Flag abs difference > max(0.5 km,10% declared km)'),
        ('unmatched_direction',len(comparisons)-len(usable),len(comparisons),'Directions without defensible length pairing / directions with a label or length','Lower is better; source-file pairing is not field confirmation'),
        ('duplicate_link',sum(Counter(r['file_id'] for r in register).values())-len(ids),len(register),'Extra source-file references / workbook rows','Review only; shared sources may be intentional'),
    ]
    hashes=Counter(r['sha256'] for r in linked.values() if r['sha256'])
    definitions.append(('duplicate_file_bytes',sum(v-1 for v in hashes.values()),available,'Excess identical SHA-256 files / located linked files','Review only; checksum cannot certify authenticity'))
    result=[dict(kpi=k,numerator=n,denominator=d,value_pct=ratio(n,d),formula=f,threshold=th,
                 status='measured' if d else 'not_verified') for k,n,d,f,th in definitions]
    matched_routes={r['route_no'] for r in usable}
    result.append(dict(kpi='unmatched_route_record',numerator=len(register)-len(matched_routes),
                       denominator=len(register),value_pct=ratio(len(register)-len(matched_routes),len(register)),
                       formula='Workbook rows without any candidate directional length pairing / workbook rows',
                       threshold='Lower is better; any paired direction does not establish full route coverage',status='measured'))
    line_hashes=Counter(r['normalized_linework_digest'] for r in layers if r.get('normalized_linework_digest'))
    result.append(dict(kpi='duplicate_layer_linework',numerator=sum(v-1 for v in line_hashes.values()),
                       denominator=sum(line_hashes.values()),value_pct=ratio(sum(v-1 for v in line_hashes.values()),sum(line_hashes.values())),
                       formula='Excess normalized linework digests / inspected layers with valid linework digest',
                       threshold='Review only; exact coordinates and CRS, not a complete near-duplicate screen',status='measured' if line_hashes else 'not_verified'))
    result.append(dict(kpi='navigation_readiness',numerator=None,denominator=len(register),value_pct=None,
                       formula='Operationally verified routes with approved stops, topology, schedule and fare evidence / workbook rows',
                       threshold='All evidence required',status='not_verified'))
    return result

def prepare(register_path, gis_dir):
    register=rows(register_path)
    files=rows(gis_dir/'file_inventory.csv'); layers=rows(gis_dir/'layer_quality.csv')
    comparisons=rows(gis_dir/'directional_length_screening.csv')
    processed=ROOT/'data/processed/m5'; processed.mkdir(parents=True,exist_ok=True)
    metrics=analyze(register,files,layers,comparisons,json.loads((ROOT/'data/processed/m4_insights_summary.json').read_text()))
    dump(processed/'ltfrb_kpis.json',metrics)
    save_table(processed/'quality_kpis.csv',diagnostics(register,files,layers,comparisons))
    segments=[]
    for fields in [('mode',),('route_classification',),('mode','route_classification'),('lptrp_classification',)]:
        for values,count in sorted(Counter(tuple(r.get(f,'') for f in fields) for r in register).items()):
            segments.append(dict(dimension=' x '.join(fields),segment=' | '.join(values),count=count,denominator=len(register)))
    geography=Counter()
    for r in register:
        # Keep whole source labels: no unverified gazetteer normalization.
        labels={x.strip() for field in ('lgu_1','lgu_2') for x in r[field].split('/') if present(x)}
        geography.update(labels)
    for label,count in sorted(geography.items()):
        segments.append(dict(dimension='LGU label (text proxy)',segment=label,count=count,denominator=len(register)))
    for label,count in Counter(f['file_status'] for f in files).items():
        segments.append(dict(dimension='GIS file status',segment=label,count=count,denominator=len({r['file_id'] for r in register})))
    status={f['file_id']:f['file_status'] for f in files}
    for fields in [('mode','route_classification','GIS status'),('mode','direction state'),('mode','metadata state')]:
        counts=Counter()
        for r in register:
            vals=dict(r)
            vals['GIS status']=status.get(r['file_id'],'not_verified')
            vals['direction state']='explicit one-direction loop' if 'loop' in r['direction_1'].lower() and not present(r['direction_2']) else ('two directions with numeric km' if all(numeric(r[f'length_km_{i}']) and present(r[f'direction_{i}']) for i in (1,2)) else 'incomplete direction metadata')
            vals['metadata state']='complete identity' if all(present(r.get(f)) for f in ('route_no','mode','route_name','route_classification','file_id')) else 'missing identity'
            counts[tuple(vals[f] for f in fields)]+=1
        for vals,count in sorted(counts.items()):
            segments.append(dict(dimension=' x '.join(fields),segment=' | '.join(vals),count=count,denominator=len(register)))
    save_table(processed/'segmentation.csv',segments); dump(processed/'segmentation.json',segments)
    save_table(processed/'kpi_history.csv',temporal())
    # Aggregate lengths and quality only; no government linework or route-level metadata released.
    save_table(processed/'length_screening_summary.csv',[dict(status=k,count=v) for k,v in Counter(r['threshold_result'] for r in comparisons).items()])
    summary=json.loads((gis_dir/'audit_summary.json').read_text())
    public={k:v for k,v in summary.items() if k not in ('unmatched_local_files','duplicate_content_different_file_ids','exact_duplicate_linework_across_file_ids')}
    public['duplicate_file_groups']=len(summary['duplicate_content_different_file_ids'])
    public['duplicate_linework_groups']=len(summary['exact_duplicate_linework_across_file_ids'])
    dump(processed/'gis_summary.json',public)
    dump(processed/'source_provenance.json',{'LTFRB':{'workbook_sha256':register[0]['source_workbook_sha256'],'sheet':'SUMMARY','scope':'Region XI register records','source_effective_date':None,'observation_date':'2026-11-18','confidence':'official source attribution; operational currency unverified','distribution':'Raw workbook, route metadata and GIS kept private; aggregate publication requires owner review'},'OSM':{'license':'ODbL; contributors attribution required','scope':'Davao query bus/ferry mapping snapshots; not a service census','confidence':'community mapping; no operational verification'},'DC Bus':{'file':'Data Request-USeP-Dingal (1).PDF','status':'Provided separately; not ingested or used for M5 calculations','confidence':'Document contents not independently validated in this delivery'}})

def numeric(value):
    try: return float(value)>0 and float(value)<float('inf')
    except (ValueError,TypeError): return False

def bar(series,title,path,xlabel='Records'):
    series=series.copy()
    series.index=[str(x).replace('_',' ') for x in series.index]
    fig,ax=plt.subplots(figsize=(9,5))
    series.plot.barh(ax=ax,color='#176e89'); ax.invert_yaxis()
    ax.set(title=title,xlabel=xlabel); ax.bar_label(ax.containers[0],padding=3)
    ax.set_xlim(0,max(float(series.max()),1)*1.2)
    fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)

def render():
    p=ROOT/'data/processed/m5'; out=ROOT/'reports/m5'; out.mkdir(parents=True,exist_ok=True)
    figs=ROOT/'dashboard/m5_assets';figs.mkdir(parents=True,exist_ok=True)
    seg=pd.read_csv(p/'segmentation.csv'); hist=pd.read_csv(p/'kpi_history.csv')
    q=pd.read_csv(p/'quality_kpis.csv'); k=json.loads((p/'ltfrb_kpis.json').read_text())
    gis=json.loads((p/'gis_summary.json').read_text())
    cleaned=json.loads((p/'cleaned_release_summary.json').read_text())
    clean_q=pd.read_csv(p/'cleaned_quality_kpis.csv')
    clean_seg=pd.read_csv(p/'cleaned_segmentation.csv')
    if cleaned['normalized_route_records'] != k['workbook_route_rows']:
        raise ValueError('Cleaned release and source-register aggregate populations differ')
    for dim,name,title in [('mode','01_modes','Workbook records by mode (UVE = UV Express)'),('route_classification','02_classification','Register classification: document labels, not active services'),('LGU label (text proxy)','04_geography','Top LGU text mentions across either direction'),('GIS file status','05_gis_status','Linked-file audit outcomes')]:
        frame=seg[seg.dimension==dim].sort_values('count',ascending=False).head(12)
        bar(frame.set_index('segment')['count'],title,figs/f'{name}.png')
    cross=seg[seg.dimension=='mode x route_classification'].copy()
    cross[['mode','classification']]=cross.segment.str.split(' | ',regex=False,expand=True)
    ax=cross.pivot(index='mode',columns='classification',values='count').fillna(0).plot.bar(figsize=(8,5))
    ax.set(title='Mode and classification comparison',ylabel='Workbook route records',xlabel='Mode')
    ax.figure.tight_layout(); ax.figure.savefig(figs/'03_mode_classification.png',dpi=140);plt.close(ax.figure)
    ds=seg[seg.dimension=='mode x direction state'].set_index('segment')['count']
    bar(ds,'Direction metadata by mode',figs/'06_direction.png')
    bar(q[q.kpi.isin(['source_metadata','file_availability','successful_file_audit','clean_geometry_crs','crs_presence'])].set_index('kpi')['value_pct'],'Quality indicators (different denominators; see KPI table)',figs/'07_quality.png','Percent')
    ls=pd.read_csv(p/'length_screening_summary.csv').set_index('status')['count']
    bar(ls,'Candidate directional length screening',figs/'08_lengths.png','Direction entries')
    for dim,name,title,xlabel in [
        ('association status','10_associations','All source direction slots: candidates, unresolved and loop N/A','Direction slots (570 total)'),
        ('feature status','11_features','Spatial features: structural passes and quarantine','Features (266 total)'),
        ('route review status','12_review','Workbook records requiring verification','Route records (285 total)')]:
        frame=clean_seg[clean_seg.dimension==dim]
        bar(frame.set_index('segment')['count'],title,figs/(name+'.png'),xlabel)
    frame=clean_seg[clean_seg.dimension=='mode x association status'].copy()
    frame[['mode','association']]=frame.segment.str.split(' | ',regex=False,expand=True)
    ax=frame.pivot(index='mode',columns='association',values='count').fillna(0).plot.bar(figsize=(9,5))
    ax.set(title='Direction association status by normalized mode',ylabel='Source direction slots',xlabel='Mode')
    ax.set_xticklabels(['UV Express' if tick.get_text()=='UV_EXPRESS' else tick.get_text() for tick in ax.get_xticklabels()],rotation=0)
    handles,labels=ax.get_legend_handles_labels()
    ax.legend(handles,[label.replace('_',' ') for label in labels],title='Association status')
    ax.figure.tight_layout();ax.figure.savefig(figs/'13_mode_associations.png',dpi=140);plt.close(ax.figure)
    fig,ax=plt.subplots(figsize=(10,5))
    for key,group in hist.groupby('kpi',sort=True):
        ax.plot(group.snapshot_date,group.value_pct,marker='o',label=PRIMARY[key][0])
    ax.set(title='OSM metadata completeness across real snapshots',ylabel='Percent of source-specific denominator',xlabel='Snapshot access date (UTC)',ylim=(0,105))
    ax.legend(fontsize=8,loc='best');fig.tight_layout();fig.savefig(figs/'09_trends.png',dpi=140);plt.close(fig)
    definitions=[dict(kpi=key,title=v[0],numerator=v[1],denominator=v[2],formula='100 * numerator / denominator; null if denominator is zero',decision=v[3],target='100% mapping completeness; analytical target, not official approval',limitations='Repeated cross-sections, not a fixed cohort. Mapping changes and extraction differences are not changes in transport operations.') for key,v in PRIMARY.items()]
    dump(p/'kpi_definitions.json',definitions)
    save_table(p/'kpi_definitions.csv',definitions)
    latest=hist.sort_values('snapshot_date').groupby('kpi').tail(1)
    brief=observatory_brief(cleaned)
    (out/'M5_STAKEHOLDER_BRIEF.md').write_text(brief,encoding='utf-8')
    (out/'GIS_QUALITY_SUMMARY.md').write_text('# GIS validation summary\n\n'+json.dumps(gis,indent=2)+'\n\nFull private evidence: reports/ltfrb/QUALITY_ASSESSMENT.md and CSVs. SHA-256 identifies bytes; it does not certify source authenticity. Overlap screen is within-layer only, not a complete inter-route network overlap analysis.\n',encoding='utf-8')
    chart_html=''.join(f'<figure><img src="m5_assets/{f.name}" alt="{escape(f.stem)}"><figcaption>{escape(f.stem.replace("_"," "))}</figcaption></figure>' for f in sorted(figs.glob('*.png')) if f.name!='03_direction_completeness.png')
    table=latest[['kpi','snapshot_date','numerator','denominator','value_pct']].to_html(index=False)
    content=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Davao M5 | Data readiness</title><style>body{{font:16px/1.6 system-ui;margin:0;background:#f2f6fa;color:#15334a}}header,main{{max-width:1100px;margin:auto;padding:30px}}header{{background:#15334a;color:white}}section,figure{{background:white;padding:20px;border-radius:12px}}.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:18px}}figure{{margin:0}}img{{width:100%}}table{{border-collapse:collapse;font-size:14px;width:100%}}td,th{{padding:8px;border:1px solid #ccd8e2}}.scroll{{overflow:auto}}a{{color:#197290}}</style><header><p>DEP · M5 PATH B</p><h1>Davao transport data readiness</h1><p>{len(seg)} aggregate segments · {k['workbook_route_rows']} Region XI register records · {k['audit_file_ids_readable']} readable linked files</p></header><main><p><a href="index.html">M4 OSM analysis</a> · <a href="m5_data/segmentation.csv">Segmentation CSV</a> · <a href="m5_data/quality_kpis.csv">GIS KPI definitions/results</a> · <a href="m5_data/kpi_history.csv">Dated KPI observations</a> · <a href="m5_data/kpi_definitions.json">Five primary KPI definitions</a></p><section><h2>Use this evidence to prioritize validation</h2><p>LTFRB register records, OSM route relations and DC Bus operational documents describe different populations. No cross-source route equivalence is asserted. Government labels and valid geometry do not establish current operations, stops, fares or travel times.</p><h2>Five primary metadata KPIs: latest OSM snapshot</h2><div class="scroll">{table}</div><p>Every percentage uses its own stated numerator and denominator. Historical LTFRB trends and navigation eligibility: <strong>not verified</strong>. OSM comparisons are mapping snapshots, not service changes. Attribution: © OpenStreetMap contributors (ODbL).</p></section><div class="charts">{chart_html}</div></main></html>'''
    content=content.replace('Davao transport data readiness','Davao Transport Data Observatory')
    baseline=clean_q[['kpi','numerator','denominator','value_pct','grain','status']].to_html(index=False)
    section=f'<section><h2>Cleaned LTFRB baseline</h2><p>Release {escape(cleaned["release_version"])}: 285 records, 266 linked IDs, 262 layers and 266 spatial features. These are distinct grains. 263 features pass structural checks; three remain quarantined. Network X-Ray and the verification workbench are future components, not M5 application features.</p><div class="scroll">{baseline}</div><p>324 of 442 populated directions remain unresolved. The 128 explicit loop N/A slots are excluded from that denominator. No historical LTFRB trend or current service verification is inferred.</p></section>'
    content=content.replace('<div class="charts">',section+'<div class="charts">')
    (ROOT/'dashboard/m5.html').write_text(content,encoding='utf-8')
    from shutil import copyfile
    public=ROOT/'dashboard/m5_data';public.mkdir(exist_ok=True)
    for f in p.iterdir():
        if f.is_file():copyfile(f,public/f.name)
    return brief

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--register',type=Path)
    parser.add_argument('--gis-report',type=Path,default=ROOT/'reports/ltfrb')
    parser.add_argument('--release',type=Path,help='Verified private cleaned LTFRB release to project into allowlisted aggregates')
    args=parser.parse_args()
    if args.register:prepare(args.register,args.gis_report)
    if args.release:
        source=json.loads((ROOT/'data/processed/m5/source_provenance.json').read_text())
        write_projection(args.release,ROOT/'data/processed/m5',source['LTFRB']['workbook_sha256'])
    render()
    print('M5 aggregate outputs, stakeholder brief and dashboard generated.')

if __name__=='__main__':main()
