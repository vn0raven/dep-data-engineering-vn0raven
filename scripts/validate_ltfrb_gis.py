"""Read-only, resumable LTFRB GeoPackage quality audit.

Never guesses stop locations, route identity, direction, schedules or travel times.
Persisting per-file JSON caches avoids rechecking unchanged source files.
Can be run without GIS files: missing files then remain UNVERIFIED, never valid.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
from contextlib import closing
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

FILE_FIELDS = ['file_id','route_rows','route_names','source_url','path','size_bytes','sha256',
               'file_status','sqlite_integrity','gpkg_metadata','layer_count','layers_with_valid_crs',
               'layers_with_valid_geometries','error']
LAYER_FIELDS = ['file_id','path','layer_name','declared_geometry_type','feature_count','crs',
                'crs_present','geometry_types','null_geometry','empty_geometry',
                'invalid_geometry','duplicate_geometry_features','suspicious_overlap_pairs',
                'crs_metadata_consistent','metadata_srs_id','normalized_linework_digest','geodesic_line_km',
                'bbox_wgs84','philippines_bbox_plausible','error']
CMP_FIELDS = ['route_no','route_name','mode','route_classification','file_id','direction_index',
              'direction','declared_length_km','matched_layer','match_confidence','measured_length_km',
              'absolute_difference_km','percentage_difference','threshold_result','reason']


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):
            h.update(block)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig',newline='') as handle:
        return list(csv.DictReader(handle))


def save_csv(path: Path, data: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as handle:
        w=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore')
        w.writeheader();w.writerows(data)


def numerical(value):
    try:
        v=float(str(value).strip())
        return v if math.isfinite(v) and v>=0 else None
    except (ValueError,TypeError):return None


def is_nonempty_direction(value):
    return str(value or '').strip().lower() not in ('','n/a','na','none','-')


def classify_direction(text):
    normalized=str(text).lower().replace('_',' ').replace('-',' ')
    if re.search(r'\bnorthbound\b|\bnb\b',normalized):return 'northbound'
    if re.search(r'\bsouthbound\b|\bsb\b',normalized):return 'southbound'
    if re.search(r'\beastbound\b|\beb\b',normalized):return 'eastbound'
    if re.search(r'\bwestbound\b|\bwb\b',normalized):return 'westbound'
    if 'loop' in normalized:return 'loop'
    return ''


def audit_file(path: Path, file_id: str, quick: bool = False, export_features: bool = False):
    file_report={'file_id':file_id,'path':str(path),'size_bytes':path.stat().st_size,
                 'sha256':sha256_file(path),'file_status':'error','sqlite_integrity':'unverified',
                 'gpkg_metadata':'unverified','layer_count':0,'layers_with_valid_crs':0,
                 'layers_with_valid_geometries':0,'error':''}
    layers=[]; eligible=[]
    if path.suffix.lower() != '.gpkg':
        file_report.update(file_status='unrecognized_format',error='Expected .gpkg; check file signature/extension before any interpretation')
        return file_report,layers,eligible
    if path.stat().st_size < 100:
        file_report.update(file_status='invalid_or_empty_file',error='File too small to contain valid GeoPackage')
        return file_report,layers,eligible
    with path.open('rb') as f:
        if f.read(16) != b'SQLite format 3\x00':
            file_report.update(file_status='invalid_format',error='Not SQLite format 3')
            return file_report,layers,eligible
    try:
        uri=f'file:{quote(str(path.resolve()))}?mode=ro'
        with closing(sqlite3.connect(uri,uri=True,timeout=25)) as con:
            con.execute('PRAGMA query_only=ON')
            integrity=con.execute('PRAGMA quick_check' if quick else 'PRAGMA integrity_check').fetchone()[0]
            file_report['sqlite_integrity']=integrity
            if integrity != 'ok':
                file_report.update(file_status='sqlite_corrupt',error=f'SQLite integrity: {integrity}')
                return file_report,layers,eligible
            tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            needed={'gpkg_spatial_ref_sys','gpkg_contents','gpkg_geometry_columns'}
            missing=sorted(needed-tables)
            if missing:
                file_report.update(file_status='invalid_gpkg_metadata',gpkg_metadata='missing '+','.join(missing),error='Required GPKG tables absent')
                return file_report,layers,eligible
            app_id=con.execute('PRAGMA application_id').fetchone()[0]
            entries=con.execute("SELECT table_name, data_type, srs_id FROM gpkg_contents").fetchall()
            metadata_srs={name:srs for name,_,srs in entries}
            geometry_srs={name:srs for name,srs in con.execute("SELECT table_name, srs_id FROM gpkg_geometry_columns").fetchall()}
            file_report['gpkg_metadata']=f'present; app_id={app_id}; contents={len(entries)}'
        import geopandas as gpd
        import pyogrio
        import shapely
        from pyproj import Geod
        geod=Geod(ellps='WGS84')
        declared=pyogrio.list_layers(path)
        file_report['layer_count']=len(declared)
        if not len(declared):
            file_report.update(file_status='no_layers',error='GeoPackage lists no readable feature layers')
            return file_report,layers,eligible
        for layer_name, declared_type in declared:
            layer={'file_id':file_id,'path':str(path),'layer_name':str(layer_name),
                   'declared_geometry_type':str(declared_type),'feature_count':None,'crs':'',
                   'crs_present':False,'geometry_types':'','null_geometry':0,'empty_geometry':0,
                   'invalid_geometry':0,'duplicate_geometry_features':0,
                   'suspicious_overlap_pairs':0,'crs_metadata_consistent':None,'metadata_srs_id':None,
                   'normalized_linework_digest':'',
                   'geodesic_line_km':None,'bbox_wgs84':'','philippines_bbox_plausible':None,'error':''}
            try:
                frame=gpd.read_file(path,layer=str(layer_name),engine='pyogrio')
                layer['feature_count']=len(frame)
                layer['crs']=str(frame.crs) if frame.crs is not None else ''
                layer['crs_present']=frame.crs is not None
                content_id=metadata_srs.get(str(layer_name))
                geometry_id=geometry_srs.get(str(layer_name))
                layer['metadata_srs_id']=geometry_id
                epsg=frame.crs.to_epsg() if frame.crs is not None else None
                layer['crs_metadata_consistent']=(content_id == geometry_id and (epsg is None or epsg == geometry_id))
                if frame.crs is not None:file_report['layers_with_valid_crs']+=1
                if 'geometry' not in frame:
                    layer['error']='No geometry column'
                    layers.append(layer);continue
                geom=frame.geometry
                layer['null_geometry']=int(geom.isna().sum())
                layer['empty_geometry']=int(geom.is_empty.fillna(False).sum())
                layer['invalid_geometry']=int((~geom.is_valid & geom.notna()).sum())
                layer['geometry_types']=','.join(sorted(geom.geom_type.dropna().unique()))
                valid=frame.loc[geom.notna() & ~geom.is_empty & geom.is_valid]
                seen=set();duplicates=0
                for g in valid.geometry:
                    fingerprint=hashlib.sha256(g.normalize().wkb).hexdigest()
                    if fingerprint in seen:duplicates+=1
                    seen.add(fingerprint)
                layer['duplicate_geometry_features']=duplicates
                line_hashes=sorted(hashlib.sha256(g.normalize().wkb).hexdigest() for g in valid.geometry
                                   if g.geom_type in ('LineString','MultiLineString'))
                if line_hashes:
                    layer['normalized_linework_digest']=hashlib.sha256((str(frame.crs)+'|'+'|'.join(line_hashes)).encode()).hexdigest()
                # Exact duplicates are checked above; screen for substantial overlapping lines
                # only for bounded layers (avoid O(N^2) on citywide road networks).
                if len(valid)<=1500 and len(valid)>1:
                    from shapely.strtree import STRtree
                    seq=[g for g in valid.geometry if g.geom_type in ('LineString','MultiLineString') and g.length>0]
                    if 1<len(seq)<=1500:
                        tree=STRtree(seq); overlapping=0
                        for j,g in enumerate(seq):
                            for other_index in tree.query(g):
                                k=int(other_index)
                                if k<=j or g.equals(seq[k]):continue
                                other=seq[k]
                                overlap=g.intersection(other).length
                                if overlap/max(min(g.length,other.length),1e-9)>=0.80:
                                    overlapping+=1
                        layer['suspicious_overlap_pairs']=overlapping
                linear=valid.geometry.geom_type.isin(['LineString','MultiLineString'])
                if frame.crs is not None:
                    projected=valid.to_crs('EPSG:4326')
                    if len(projected):
                        bounds=[round(float(v),6) for v in projected.total_bounds]
                        layer['bbox_wgs84']=json.dumps(bounds)
                        # Loose Philippine geographic plausibility only, not legal service area.
                        layer['philippines_bbox_plausible']=(115<=bounds[0]<=130 and 4<=bounds[1]<=23 and
                                                                115<=bounds[2]<=130 and 4<=bounds[3]<=23)
                    lines=projected.loc[linear]
                    if len(lines):
                        layer['geodesic_line_km']=round(sum(abs(geod.geometry_length(g)) for g in lines.geometry)/1000,6)
                if layer['null_geometry']==0 and layer['empty_geometry']==0 and layer['invalid_geometry']==0 and frame.crs is not None and layer['crs_metadata_consistent'] and len(frame):
                    file_report['layers_with_valid_geometries']+=1
                if (export_features and frame.crs is not None and layer['crs_metadata_consistent']
                        and len(valid)==len(frame) and layer['duplicate_geometry_features']==0
                        and layer['suspicious_overlap_pairs']==0 and len(valid)):
                    line_valid=valid.loc[linear]
                    for g in line_valid.to_crs('EPSG:4326').geometry:
                        eligible.append((str(layer_name), g))
            except Exception as exc:
                layer['error']=f'{type(exc).__name__}: {str(exc)[:300]}'
            layers.append(layer)
        file_report['file_status']='audited' if all(not l['error'] for l in layers) else 'partial_layer_failure'
    except Exception as exc:
        file_report.update(file_status='unreadable',error=f'{type(exc).__name__}: {str(exc)[:500]}')
    return file_report,layers,eligible


def comparison_rows(records, layer_index, relative_threshold=0.10, min_absolute_km=0.5):
    """Conservative candidates: one workbook route/file; exact direction layer match, or sole one-way loop."""
    count=Counter(r['file_id'] for r in records if r['file_id'])
    output=[]
    for row in records:
        file_id=row['file_id']; layers=layer_index.get(file_id,[])
        for i in (1,2):
            raw_dir=row.get(f'direction_{i}','')
            length=numerical(row.get(f'length_km_{i}'))
            if not is_nonempty_direction(raw_dir) and length is None:continue
            state={'route_no':row['route_no'],'route_name':row['route_name'],
                   'mode':row['mode'],'route_classification':row['route_classification'],
                   'file_id':file_id,'direction_index':i,'direction':raw_dir,
                   'declared_length_km':length,'matched_layer':'','match_confidence':'unmatched',
                   'measured_length_km':None,'absolute_difference_km':None,'percentage_difference':None,
                   'threshold_result':'not_evaluated','reason':''}
            if length is None:state['reason']='Declared length unavailable'
            elif count[file_id]!=1:state['reason']='GeoPackage ID shared across workbook route records'
            else:
                candidates=[x for x in layers if (x.get('feature_count') == 1 and x.get('geodesic_line_km') is not None and
                                                         x.get('invalid_geometry') == 0 and x.get('null_geometry') == 0 and
                                                         x.get('empty_geometry') == 0 and x.get('crs_present') and
                                                         x.get('crs_metadata_consistent') is True and not x.get('error'))]
                direction=classify_direction(raw_dir)
                exact=[x for x in candidates if direction and classify_direction(x['layer_name']) == direction]
                if len(exact)==1:
                    picked=exact[0]; state['match_confidence']='direction_label_candidate'
                elif i==1 and direction=='loop' and len(candidates)==1 and not is_nonempty_direction(row.get('direction_2','')) and numerical(row.get('length_km_2')) is None:
                    picked=candidates[0];state['match_confidence']='single_one_way_candidate'
                else:picked=None
                if picked is None:state['reason']='Direction cannot be matched unambiguously; no inferred route-length comparison'
                else:
                    measured=picked['geodesic_line_km'];absolute=abs(measured-length)
                    state.update(matched_layer=picked['layer_name'],measured_length_km=measured,
                                 absolute_difference_km=round(absolute,6),
                                 percentage_difference=round(100*absolute/length,3) if length else None,
                                 threshold_result=('within_screening_tolerance' if absolute<=max(min_absolute_km,relative_threshold*length) else 'review_length_discrepancy'),
                                 reason='Candidate source-file association; verify geometry is complete and represents this direction')
            output.append(state)
    return output


def main():
    p=argparse.ArgumentParser(description='LTFRB GeoPackage read-only audit; no navigable service inference')
    p.add_argument('--register',required=True,type=Path)
    p.add_argument('--gis-dir',required=True,type=Path)
    p.add_argument('--out',default=Path('reports/ltfrb'),type=Path)
    p.add_argument('--quick',action='store_true',help='Use SQLite quick_check instead of full integrity_check')
    p.add_argument('--refresh',action='store_true',help='Ignore cached file audits')
    p.add_argument('--export-geometry',action='store_true',help='Write valid geographic linework as NOT navigation-eligible GeoPackage')
    args=p.parse_args()
    records=read_csv(args.register); args.out.mkdir(parents=True,exist_ok=True)
    by_id=defaultdict(list)
    for r in records:
        if r['file_id']:by_id[r['file_id']].append(r)
    inventory=defaultdict(list)
    if args.gis_dir.is_dir():
        for path in args.gis_dir.iterdir():
            if path.is_file() and path.suffix.lower() in ('.gpkg','.zip','.bin','.pdf','.shp'):
                inventory[path.stem].append(path)
    cache_dir=args.out/'_cache';cache_dir.mkdir(parents=True,exist_ok=True)
    files=[];layers=[];geom_to_export=[]
    for j,(file_id,rows) in enumerate(by_id.items(),1):
        paths=sorted(inventory.pop(file_id,[]),key=lambda x:(x.suffix.lower()!='.gpkg',str(x)))
        expected={'file_id':file_id,'route_rows':len(rows),'route_names':' | '.join(dict.fromkeys(r['route_name'] for r in rows)),
                  'source_url':rows[0]['source_url']}
        if not paths:
            files.append(dict(expected,path='',size_bytes=0,sha256='',file_status='missing_local_file',
                              sqlite_integrity='unverified',gpkg_metadata='unverified',layer_count=0,
                              layers_with_valid_crs=0,layers_with_valid_geometries=0,error='No local file supplied'))
            continue
        path=paths[0]
        stat=path.stat()
        sig=f'v4:{path.resolve()}:{sha256_file(path)}:{args.quick}:{args.export_geometry}'
        cache=cache_dir/(file_id+'.json')
        accepted=[]
        if cache.exists() and not args.refresh and not args.export_geometry:
            state=json.loads(cache.read_text(encoding='utf-8'))
            if state.get('sig')==sig:result,layer_rows=state['file'],state['layers']
            else: result,layer_rows,_=audit_file(path,file_id,args.quick)
        else:result,layer_rows,accepted=audit_file(path,file_id,args.quick,args.export_geometry)
        if args.export_geometry and accepted:
            geom_to_export.extend((file_id,name,geometry) for name,geometry in accepted)
            accepted=[]
        cache.write_text(json.dumps({'sig':sig,'file':result,'layers':layer_rows},ensure_ascii=False,default=str)+'\n',encoding='utf-8')
        files.append(dict(expected,**{k:v for k,v in result.items() if k not in expected}))
        layers.extend(layer_rows)
        for other in paths[1:]:
            files.append(dict(expected,path=str(other),size_bytes=other.stat().st_size,
                              sha256=sha256_file(other),file_status='multiple_local_candidates',
                              sqlite_integrity='not_checked',gpkg_metadata='not_checked',layer_count=0,
                              layers_with_valid_crs=0,layers_with_valid_geometries=0,
                              error=f'Additional candidate for same Drive ID; chosen {path.name}'))
        if j%25==0:print(f'Audited {j}/{len(by_id)} Drive IDs')
    extra_files=[str(p) for extra in inventory.values() for p in extra]
    comparisons=comparison_rows(records,{fid:[x for x in layers if x['file_id']==fid] for fid in by_id})
    save_csv(args.out/'file_inventory.csv',files,FILE_FIELDS)
    save_csv(args.out/'layer_quality.csv',layers,LAYER_FIELDS)
    save_csv(args.out/'directional_length_screening.csv',comparisons,CMP_FIELDS)
    checksums=defaultdict(list)
    for f in files:
        if f.get('sha256'):checksums[f['sha256']].append(f['file_id'])
    dup_hashes=[sorted(set(ids)) for ids in checksums.values() if len(set(ids))>1]
    geometry_groups=defaultdict(set)
    for layer in layers:
        if layer.get('normalized_linework_digest'):
            geometry_groups[layer['normalized_linework_digest']].add(layer['file_id'])
    duplicated_geometry_ids=[sorted(group) for group in geometry_groups.values() if len(group)>1]
    status=dict(sorted(Counter(f['file_status'] for f in files).items()))
    version_input='|'.join(sorted(f"{f['file_id']}:{f.get('sha256') or 'MISSING'}" for f in files))
    version_input+='|'+(records[0].get('source_workbook_sha256','') if records else '')
    dataset_version=hashlib.sha256(version_input.encode()).hexdigest()[:12]
    audit_summary={
        'dataset_version':dataset_version,
        'route_records':len(records),'unique_linked_drive_files':len(by_id),
        'local_files_found':sum(f['file_status']!='missing_local_file' for f in files),
        'missing_local_drive_files':sum(f['file_status']=='missing_local_file' for f in files),
        'file_status_distribution':status,'layers_inspected':len(layers),
        'layers_with_declared_crs':sum(bool(x['crs_present']) for x in layers),
        'layers_with_invalid_geometries':sum(x['invalid_geometry']>0 for x in layers),
        'layers_with_null_geometries':sum(x['null_geometry']>0 for x in layers),
        'layers_with_duplicate_geometry_features':sum(x['duplicate_geometry_features']>0 for x in layers),
        'layers_with_suspicious_overlaps':sum(x['suspicious_overlap_pairs']>0 for x in layers),
        'layers_with_crs_metadata_mismatch':sum(x['crs_metadata_consistent'] is False for x in layers),
        'candidate_length_comparisons':sum(x['measured_length_km'] is not None for x in comparisons),
        'length_discrepancies_to_review':sum(x['threshold_result']=='review_length_discrepancy' for x in comparisons),
        'duplicate_content_different_file_ids':dup_hashes,
        'exact_duplicate_linework_across_file_ids':duplicated_geometry_ids,
        'unmatched_local_files':extra_files,
        'thresholds':{'length_difference_fraction':0.10,'length_difference_minimum_km':0.5,
                      'philippines_bbox_longitude':[115,130],'philippines_bbox_latitude':[4,23]},
        'caveat':'All file geometry checks are mapping-quality checks, not government approval, active service or boarding points. Missing local files are unverified.',
    }
    (args.out/'audit_summary.json').write_text(json.dumps(audit_summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    notes=[
        '# LTFRB Region XI — Local GeoPackage Quality Assessment', '',
        '## Provenance and scope',
        'Source index: the supplied LTFRB Region XI workbook, SUMMARY tab. Local files are matched by Google Drive ID. Files are inspected read-only, checksums retained, and no current service or boarding claims are made.',
        '', '## Measured outcomes',
        f'- Workbook route records: **{len(records)}**; unique linked Drive IDs: **{len(by_id)}**.',
        f'- GeoPackage IDs absent from the **provided local folder**: **{audit_summary["missing_local_drive_files"]}** (unverified, not necessarily inaccessible online).',
        '- File status distribution: '+', '.join(f'{k}={v}' for k,v in status.items())+'.',
        f'- Spatial layers opened: **{len(layers)}**; layers reporting CRS: **{audit_summary["layers_with_declared_crs"]}**.',
        f'- Layers with invalid geometries: **{audit_summary["layers_with_invalid_geometries"]}**; null geometry: **{audit_summary["layers_with_null_geometries"]}**.',
        f'- Layers with repeated geometry within layer: **{audit_summary["layers_with_duplicate_geometry_features"]}**; suspicious substantial overlaps: **{audit_summary["layers_with_suspicious_overlaps"]}**.',
        f'- Layers with CRS metadata mismatch: **{audit_summary["layers_with_crs_metadata_mismatch"]}**.',
        f'- Identical file content across distinct Drive IDs: **{len(dup_hashes)}** groups; exact identical linework across IDs: **{len(duplicated_geometry_ids)}** groups.',
        f'- Candidate directional distance comparisons: **{audit_summary["candidate_length_comparisons"]}**, review flags: **{audit_summary["length_discrepancies_to_review"]}**.',
        '', '## Checks, assumptions and limits',
        '- Byte authenticity: SHA-256 for each opened file; SQLite `integrity_check` (or `quick_check` only if `--quick` is explicitly selected).',
        '- GeoPackage structure: required gpkg tables and layer enumeration; SRID consistency across `gpkg_contents`, `gpkg_geometry_columns` and layer CRS.',
        '- Coordinate range: very broad Philippine screening box (115–130 E, 4–23 N). Outside extent is a **warning**, not proof of a wrong route, because some routes extend outside Region XI.',
        '- Geometry: invalid, null, empty, duplicate hashes and substantial line overlaps (>=80% overlap of shorter line) for layers of at most 1500 features. Larger layers skip the overlap screen; invalid geometry is never silently repaired.',
        '- Lengths: WGS84 ellipsoidal geodesic metres converted to km, summed over valid line features; comparisons only for one workbook record per file and an explicit matching direction-labelled single feature, or a single one-way route candidate.',
        '- Screening distance threshold: flag if absolute difference exceeds max(0.5 km, 10% of declared km). This is a **review tolerance**, not a rule for approving routes.',
        '- No actual boarding stops, vehicle availability, fare schedule or measured travel times are inferred.',
        '', '## Files for follow-up',
        '- `file_inventory.csv`: per-ID presence, SQLite integrity, SHA-256 and source mapping.',
        '- `layer_quality.csv`: CRS, feature counts, invalid/null/empty/duplicate geometry and geodesic length.',
        '- `directional_length_screening.csv`: declared vs candidate measured km; `not_evaluated` means no defensible comparison.',
        '- `audit_summary.json`: machine-readable totals, thresholds and duplicates.',
        '', '## Corrective actions',
        '1. Resolve absent / damaged files and rescan. 2. Review suspect SRIDs and overlaps with QGIS and original source files. 3. Manually confirm route-to-layer and direction mapping for distance discrepancies. 4. Validate actual service, dated stops and permissions before use for navigation.',
    ]
    (args.out/'QUALITY_ASSESSMENT.md').write_text('\n'.join(notes)+'\n',encoding='utf-8')
    if args.export_geometry and geom_to_export:
        import geopandas as gpd
        outfile=args.out/f'quality_pass_linework_{dataset_version}_NOT_NAVIGATION_READY.gpkg'
        if outfile.exists():outfile.unlink() # only generated output, raw inputs untouched
        gdf=gpd.GeoDataFrame(
            [{'source_file_id':fid,'source_layer':layer,'navigation_eligible':False,'geometry':g} for fid,layer,g in geom_to_export],
            crs='EPSG:4326')
        gdf.to_file(outfile,driver='GPKG',layer='audit_valid_linework')
        print('Written optional, non-navigation-ready spatial output:',outfile)
    print(json.dumps(audit_summary,indent=2))

if __name__=='__main__':main()
