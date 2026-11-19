"""Private, immutable LTFRB data releases; no network, source edits or implicit repairs.

Geometry passes certify structural checks only. Route/direction associations remain
candidates and municipality labels are not promoted to authoritative PSGC identities.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import struct
import sys
import tempfile
import unicodedata

import geopandas as gpd
import pandas as pd
import pyogrio
from pyproj import Geod
import shapely
from shapely.geometry import mapping, shape
from shapely.validation import explain_validity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.extract_ltfrb_routes import extract
from scripts.validate_ltfrb_gis import audit_file, comparison_rows

VERSION = 'observatory-etl-1'
NULLS = {'', 'n/a', 'na', 'none', 'null', '-'}
MODE = {'PUJ': 'PUJ', 'PUB': 'PUB', 'UVE': 'UV_EXPRESS', 'UV EXPRESS': 'UV_EXPRESS'}
DIRECTIONS = {'northbound': 'NORTHBOUND', 'southbound': 'SOUTHBOUND',
              'eastbound': 'EASTBOUND', 'westbound': 'WESTBOUND',
              'loop route (one direction only)': 'LOOP_ONE_DIRECTION'}
GEOD = Geod(ellps='WGS84')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)+'\n'
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False,suffix='.tmp') as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()


def text(value):
    if value is None:
        return None
    value = unicodedata.normalize('NFKC', str(value))
    value = re.sub('[\u2010-\u2015\u2212]', '-', value)
    value = ' '.join(value.split())
    return None if value.casefold() in NULLS else value


def match_key(value):
    return re.sub(r'[^\w]+', ' ', text(value).casefold()).strip() if text(value) else None


def field_description(table, column):
    descriptions = {
        'route_id':'Stable project key from source region and route number; cross-release identity is a candidate if authorities renumber records.',
        'source_record_id':'Workbook SHA-256 and Excel row; identifies a particular source observation.',
        'original_record_json':'Entire extracted workbook record, unchanged; JSON encoded.',
        'name_match_key':'Casefolded punctuation-normalized name used only to identify review candidates.',
        'mode':'Controlled PUJ, PUB or UV_EXPRESS enum; unknown remains null and flagged.',
        'classification':'EXISTING or IRIP source label; not a current-service assertion.',
        'direction_id':'Route key plus source direction ordinal; not a verified trip identifier.',
        'direction':'Controlled compass or LOOP_ONE_DIRECTION enum; unknown explicit.',
        'declared_km':'Positive finite source distance, rounded to six decimals; original text retained separately.',
        'corridor':'Normalized source corridor description; not a graph or stop sequence.',
        'locality_name':'Source label after separating explicit administrative prefix/suffix; no gazetteer inference.',
        'canonical_psgc':'Always null in this release; authoritative place identity not established.',
        'locality_match_key':'Conservative comparison key; homonymous municipalities are not merged.',
        'source_label':'Normalized source locality label, retaining original administrative wording.',
        'admin_label_type':'city_label, municipality_label or unspecified according to source wording only.',
        'file_id':'Google Drive source ID extracted from workbook URL; not proof of authority or service.',
        'sha256':'SHA-256 of original source-file bytes; identity does not establish authenticity.',
        'geometry_json':'EPSG:4326 geometry for passing features only; null for quarantine.',
        'source_geometry_wkb_hex':'Original feature WKB hexadecimal evidence, retained even when invalid.',
        'geometry_sha256':'SHA-256 of normalized EPSG:4326 WKB; exact duplicates only, not near-duplicates.',
        'geodesic_km':'WGS84 ellipsoidal geometry length in km; no travel-time inference.',
        'source_crs':'Reader CRS text from original spatial layer.',
        'crs_consistent':'Declared layer CRS and GeoPackage content/geometry SRIDs agree.',
        'association_status':'candidate, unresolved or not_applicable_loop; none is source-owner-confirmed.',
        'length_screen':'within_screening_tolerance, review_length_discrepancy, not_evaluated or not_applicable.',
        'match_method':'Conservative automatic file/layer/direction matching method; candidate evidence.',
        'difference_pct':'Absolute difference / positive declared km times 100; null if unpaired.',
        'navigation_status':'Always not_verified; mapping quality does not establish operations or boarding.',
        'quality_flags_json':'Sorted route/direction review codes; JSON encoded.',
        'dependencies_json':'Shapefile sidecar inventory, missing components and header-signature check.',
        'resolution_status':'Unresolved; this ETL does not simulate source-owner approval.',
        'before':'Extracted source value before the named transformation.',
        'after':'Derived value after the named transformation; source is preserved.',
        'rule':'Explicit normalization operation; no inferred repair or operational data.',
    }
    return descriptions.get(column,f'{column.replace("_"," ").capitalize()} in {table}; see methodology for table grain and quality limits.')


def length_km(value):
    value = text(value)
    if value is None:
        return None
    try:
        n = Decimal(value)
        return float(n.quantize(Decimal('0.000001'))) if n.is_finite() and n > 0 else None
    except (InvalidOperation, ValueError):
        return None


def issue(entity_type, entity_id, code, detail, severity='review'):
    key = encode([entity_type, entity_id, code, detail])
    return dict(issue_id=hashlib.sha256(key.encode()).hexdigest()[:24], entity_type=entity_type,
                entity_id=str(entity_id), code=code, severity=severity, detail=detail,
                resolution_status='unresolved')


def normalize(records):
    routes, directions, lgus, changes, issues = [], [], [], [], []
    for raw in records:
        if not re.fullmatch(r'\d+', raw['route_no']):
            raise ValueError('Non-numeric source route number; no stable key can be allocated')
        rid = f"ltfrb-r{raw['region']}-{int(raw['route_no']):04d}"
        r = dict(route_id=rid, source_record_id=f"{raw['source_workbook_sha256']}:{raw['excel_row']}",
                 source_route_no=int(raw['route_no']), source_excel_row=int(raw['excel_row']),
                 region=text(raw['region']), route_name=text(raw['route_name']),
                 name_match_key=match_key(raw['route_name']), mode=MODE.get((text(raw['mode']) or '').upper()),
                 classification=(text(raw['route_classification']) or '').upper(),
                 lptrp_classification=text(raw['lptrp_classification']), file_id=text(raw['file_id']),
                 source_url=text(raw['source_url']), workbook_sha256=raw['source_workbook_sha256'],
                 metadata_status='normalized', navigation_status='not_verified',
                 original_record_json=encode(raw))
        for f in ('route_name', 'mode', 'classification', 'file_id'):
            if not r[f] or (f == 'classification' and r[f] not in ('EXISTING', 'IRIP')):
                r['metadata_status'] = 'uncertain'
                issues.append(issue('route', rid, 'invalid_'+f, f'Unexpected or missing {f}: {r[f]}'))
        routes.append(r)
        for f, original in [('route_name', 'route_name'), ('mode', 'mode'), ('classification', 'route_classification'), ('lptrp_classification', 'lptrp_classification')]:
            if str(r[f]) != str(raw[original]):
                changes.append(dict(entity_id=rid, field=f, before=raw[original], after=r[f], rule='NFKC_whitespace_dash_or_explicit_enum'))
        for n in (1, 2):
            did = f'{rid}:d{n}'
            original_direction, original_km = raw[f'direction_{n}'], raw[f'length_km_{n}']
            label = text(original_direction)
            direction = DIRECTIONS.get(label.casefold(), 'UNKNOWN') if label else None
            km = length_km(original_km)
            not_applicable = n == 2 and DIRECTIONS.get((text(raw['direction_1']) or '').casefold()) == 'LOOP_ONE_DIRECTION' and not label and text(original_km) is None
            status = 'not_applicable_loop' if not_applicable else ('complete' if direction not in (None, 'UNKNOWN') and km else 'uncertain')
            d = dict(direction_id=did, route_id=rid, ordinal=n, direction=direction, declared_km=km,
                     corridor=text(raw[f'corridor_{n}']), metadata_status=status,
                     original_direction=original_direction, original_length_km=original_km)
            directions.append(d)
            if status == 'uncertain':
                issues.append(issue('direction', did, 'incomplete_direction', 'Direction or positive finite declared length is missing/unrecognized'))
            for f, before, after in [('direction', original_direction, direction), ('declared_km', original_km, km), ('corridor', raw[f'corridor_{n}'], d['corridor'])]:
                if str(before) != str(after):
                    changes.append(dict(entity_id=did, field=f, before=before, after=after, rule='explicit_direction_enum_positive_km_6dp_or_text_normalization'))
            raw_lgu = text(raw[f'lgu_{n}'])
            if raw_lgu:
                seen = set()
                for ordinal, token in enumerate(raw_lgu.split('/'), 1):
                    label = text(token)
                    if label is None:
                        issues.append(issue('direction', did, 'empty_lgu_token', f'Empty slash-delimited LGU token at ordinal {ordinal}'))
                        continue
                    name = re.sub(r'^Municipality\s+of\s+', '', label, flags=re.I)
                    admin = 'municipality_label' if name != label else ('city_label' if re.search(r'\bcity$', label, re.I) else 'unspecified')
                    if admin == 'city_label':
                        name = re.sub(r'\s+City$', '', name, flags=re.I)
                    key = match_key(name)
                    if key in seen:
                        issues.append(issue('direction', did, 'repeated_lgu_label', label))
                    seen.add(key)
                    lgus.append(dict(direction_id=did, ordinal=ordinal, source_label=label,
                                     locality_name=name, locality_match_key=key, admin_label_type=admin,
                                     canonical_psgc=None, identity_status='unverified_source_label'))
                    if re.match(r'^Municipality\b',label,re.I) and not re.match(r'^Municipality of\b',label,re.I):
                        issues.append(issue('direction',did,'malformed_admin_prefix',label))
                    if label != token or name != label:
                        changes.append(dict(entity_id=did, field=f'lgu_token_{ordinal}', before=token, after=name,
                                            rule='whitespace_and_explicit_admin_prefix_suffix_separation'))
    if len({r['route_id'] for r in routes}) != len(routes):
        raise ValueError('Duplicate source route number; stable key collision, release stopped')
    by_name = defaultdict(list)
    for r in routes:
        by_name[r['name_match_key']].append(r['route_id'])
    for key, ids in by_name.items():
        if len(ids) > 1:
            for rid in ids:
                issues.append(issue('route', rid, 'duplicate_name_candidate', encode(ids)))
    locality_types = defaultdict(set)
    for l in lgus:
        locality_types[l['locality_match_key']].add(l['admin_label_type'])
    for key, types in locality_types.items():
        if 'city_label' in types and 'municipality_label' in types:
            issues.append(issue('locality_label', key, 'conflicting_admin_labels', encode(sorted(types))))
    return dict(routes=routes, directions=directions, route_localities=lgus, transformations=changes, issues=issues)


def inventory(folder):
    return [dict(name=p.name, bytes=p.stat().st_size, sha256=digest(p))
            for p in sorted(Path(folder).iterdir(), key=lambda p:p.name.casefold()) if p.is_file()]


def inspect_asset(file_id, folder, entries):
    """Audit a source and return geometry passes without modifying or repairing it."""
    matching = [e for e in entries if Path(e['name']).stem == file_id]
    ordered = sorted(matching, key=lambda e:(Path(e['name']).suffix.lower() != '.gpkg', Path(e['name']).suffix.lower() == '.partial', e['name']))
    asset = dict(file_id=file_id, status='missing', sha256=None, filename=None, integrity=None,
                 layer_count=0, error=None, dependencies_json='[]')
    layers, features, issues = [], [], []
    if not ordered:
        issues.append(issue('asset', file_id, 'missing_source', 'No file supplied for workbook Drive ID', 'error'))
        return dict(asset=asset, layers=layers, features=features, issues=issues)
    entry = ordered[0]; path = Path(folder)/entry['name']
    asset.update(filename=entry['name'], sha256=entry['sha256'])
    ext = path.suffix.lower()
    if len([e for e in matching if Path(e['name']).suffix.lower() in ('.gpkg', '.shp')]) > 1:
        issues.append(issue('asset', file_id, 'multiple_source_candidates', encode([e['name'] for e in ordered])))
    try:
        if ext == '.partial':
            asset.update(status='incomplete_download', error='Partial extension is never promoted to a complete source')
            issues.append(issue('asset', file_id, 'incomplete_download', f"{path.name}: {entry['bytes']} bytes", 'error'))
            return dict(asset=asset, layers=[], features=[], issues=issues)
        if ext == '.shp':
            supplied = {Path(e['name']).suffix.lower(): e['name'] for e in matching}
            required = ['.shp', '.shx', '.dbf', '.prj']
            absent = [s for s in required if s not in supplied]
            with path.open('rb') as handle:
                header = handle.read(100)
            signature_ok = len(header) == 100 and struct.unpack('>i', header[:4])[0] == 9994
            asset['dependencies_json'] = encode(dict(supplied=supplied, missing=absent, shp_header_valid=signature_ok))
            if absent or not signature_ok:
                asset.update(status='incomplete_shapefile' if signature_ok else 'invalid_shapefile_header',
                             error=f'Missing dependencies: {absent}; valid SHP header: {signature_ok}')
                issues.append(issue('asset', file_id, asset['status'], asset['error'], 'error'))
                return dict(asset=asset, layers=[], features=[], issues=issues)
        elif ext == '.gpkg':
            audited, _, _ = audit_file(path, file_id)
            asset.update(status=audited['file_status'], integrity=audited['sqlite_integrity'],
                         layer_count=audited['layer_count'], error=audited['error'] or None)
            if audited['file_status'] not in ('audited', 'partial_layer_failure'):
                issues.append(issue('asset', file_id, 'failed_file_audit', encode(audited), 'error'))
                return dict(asset=asset, layers=[], features=[], issues=issues)
        else:
            asset.update(status='unsupported_format', error=f'Unsupported extension: {ext}')
            issues.append(issue('asset', file_id, 'unsupported_format', ext, 'error'))
            return dict(asset=asset, layers=[], features=[], issues=issues)
        for name, geom_type in pyogrio.list_layers(path):
            if geom_type is None:
                continue
            lid = hashlib.sha256(encode([file_id, str(name)]).encode()).hexdigest()[:24]
            layer = dict(layer_id=lid, file_id=file_id, layer_name=str(name), feature_count=0,
                         source_crs=None, crs_consistent=False, status='unreadable', error=None)
            try:
                frame = gpd.read_file(path, layer=name, engine='pyogrio', fid_as_index=True)
                layer.update(feature_count=len(frame), source_crs=str(frame.crs) if frame.crs else None)
                consistent = frame.crs is not None
                if ext == '.gpkg':
                    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)) as con:
                        ids = con.execute('SELECT c.srs_id,g.srs_id FROM gpkg_contents c JOIN gpkg_geometry_columns g ON c.table_name=g.table_name WHERE c.table_name=?', (str(name),)).fetchone()
                    consistent = consistent and bool(ids) and ids[0] == ids[1] and (frame.crs.to_epsg() is None or frame.crs.to_epsg() == ids[1])
                layer['crs_consistent'] = bool(consistent)
                target = frame.to_crs(4326) if consistent else None
                for fid, row in frame.iterrows():
                    geom = row.geometry
                    feature_id = hashlib.sha256(encode([file_id, str(name), str(fid)]).encode()).hexdigest()[:24]
                    reason = None
                    if geom is None: reason = 'null_geometry'
                    elif geom.is_empty: reason = 'empty_geometry'
                    elif not geom.is_valid: reason = 'invalid_geometry: '+explain_validity(geom)
                    elif geom.geom_type not in ('LineString', 'MultiLineString'): reason = 'non_route_geometry: '+geom.geom_type
                    elif not consistent: reason = 'missing_or_inconsistent_crs'
                    transformed = target.loc[fid].geometry if target is not None else None
                    if reason is None and (not transformed.is_valid or not all(math.isfinite(v) for v in transformed.bounds)):
                        reason = 'invalid_transformed_geometry'
                    if reason is None:
                        x1,y1,x2,y2 = transformed.bounds
                        if not (115 <= x1 <= x2 <= 130 and 4 <= y1 <= y2 <= 23):
                            reason = 'outside_broad_philippines_extent'
                    length = abs(GEOD.geometry_length(transformed))/1000 if reason is None else None
                    if reason is None and (not math.isfinite(length) or length <= 0):
                        reason = 'nonpositive_geodesic_length'
                    item = dict(feature_id=feature_id, file_id=file_id, layer_id=lid, source_fid=str(fid),
                                source_geometry_type=geom.geom_type if geom is not None else None,
                                source_geometry_wkb_hex=geom.wkb_hex if geom is not None else None,
                                status='quarantined' if reason else 'geometry_pass', reason=reason,
                                geometry_json=encode(mapping(transformed)) if reason is None else None,
                                geometry_sha256=hashlib.sha256(transformed.normalize().wkb).hexdigest() if reason is None else None,
                                geodesic_km=round(length, 6) if reason is None else None)
                    features.append(item)
                    if reason:
                        issues.append(issue('feature', feature_id, 'geometry_quarantine', reason, 'error'))
                layer['status'] = 'inspected'
            except Exception as exc:
                layer['error'] = f'{type(exc).__name__}: {exc}'
                issues.append(issue('layer', lid, 'layer_read_failure', layer['error'], 'error'))
            layers.append(layer)
        asset['layer_count'] = len(layers)
        if any(l['error'] for l in layers):
            asset['status'] = 'partial_layer_failure'
        elif layers:
            asset['status'] = 'inspected'
        else:
            asset.update(status='no_spatial_layers', error='No spatial layers enumerated')
    except Exception as exc:
        asset.update(status='unreadable', error=f'{type(exc).__name__}: {exc}')
        issues.append(issue('asset', file_id, 'unreadable_source', asset['error'], 'error'))
    return dict(asset=asset, layers=layers, features=features, issues=issues)


def sql_write(path, tables):
    """Normalized tables with explicit primary keys and referential constraints."""
    primary = {'routes': ['route_id'], 'directions': ['direction_id'],
               'route_localities': ['direction_id', 'ordinal'], 'assets': ['file_id'],
               'layers': ['layer_id'], 'features': ['feature_id'], 'associations': ['direction_id'],
               'issues': ['issue_id']}
    foreign = {'directions': [('route_id', 'routes', 'route_id')],
               'route_localities': [('direction_id', 'directions', 'direction_id')],
               'layers': [('file_id', 'assets', 'file_id')],
               'features': [('file_id', 'assets', 'file_id'), ('layer_id', 'layers', 'layer_id')],
               'associations': [('direction_id', 'directions', 'direction_id'), ('feature_id', 'features', 'feature_id')]}
    with closing(sqlite3.connect(path)) as con:
        con.execute('PRAGMA foreign_keys=ON')
        for name, rows in tables.items():
            if not rows:
                # Empty tables still have stable documented schemas.
                empty_schemas = {
                    'transformations': dict(entity_id='',field='',before='',after='',rule=''),
                    'issues': issue('','','',''),
                    'route_localities': dict(direction_id='',ordinal=0,source_label='',locality_name='',locality_match_key='',admin_label_type='',canonical_psgc=None,identity_status=''),
                    'layers': dict(layer_id='',file_id='',layer_name='',feature_count=0,source_crs=None,crs_consistent=False,status='',error=None),
                    'features': dict(feature_id='',file_id='',layer_id='',source_fid='',source_geometry_type=None,source_geometry_wkb_hex=None,status='',reason=None,geometry_json=None,geometry_sha256=None,geodesic_km=None),
                    'assets': dict(file_id='',status='',sha256=None,filename=None,integrity=None,layer_count=0,error=None,dependencies_json='[]'),
                }
                rows_for_schema = [empty_schemas[name]]
            else:
                rows_for_schema = rows
            columns = list(rows_for_schema[0])
            kinds = {}
            for c in columns:
                values = [r[c] for r in rows_for_schema if r[c] is not None]
                kinds[c] = 'INTEGER' if values and all(isinstance(v, (int,bool)) for v in values) else ('REAL' if values and all(isinstance(v,(int,float,bool)) for v in values) else 'TEXT')
            numeric_reals = {'declared_km','measured_km','geodesic_km','absolute_difference_km','difference_pct'}
            for c in numeric_reals.intersection(columns): kinds[c]='REAL'
            specs = [f'"{c}" {kinds[c]}'+(' NOT NULL' if c in primary.get(name,[]) else '') for c in columns]
            if name in primary:
                specs.append('PRIMARY KEY ('+','.join('"'+x+'"' for x in primary[name])+')')
            specs.extend(f'FOREIGN KEY ("{a}") REFERENCES "{b}"("{c}")' for a,b,c in foreign.get(name, []))
            con.execute(f'CREATE TABLE "{name}" ('+','.join(specs)+')')
            con.executemany(f'INSERT INTO "{name}" VALUES ('+','.join('?' for _ in columns)+')', [[r[c] for c in columns] for r in rows])
        con.execute('CREATE INDEX features_by_file ON features(file_id)')
        con.execute('CREATE INDEX directions_by_route ON directions(route_id)')
        con.execute('CREATE INDEX routes_by_name ON routes(name_match_key)')
        con.execute('CREATE INDEX issues_by_entity ON issues(entity_type,entity_id)')
        con.commit()
        assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert con.execute('PRAGMA foreign_key_check').fetchall() == []


def verify_release(folder):
    manifest = json.loads((Path(folder)/'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['outputs']:
        if digest(Path(folder)/entry['path']) != entry['sha256']:
            raise ValueError(f"Existing release output modified: {entry['path']}")
    return manifest


def build(workbook, gis_dir, output, refresh=False):
    workbook, gis_dir, output = Path(workbook).resolve(), Path(gis_dir).resolve(), Path(output).resolve()
    if not workbook.is_file() or not gis_dir.is_dir():
        raise ValueError('Workbook file and GIS directory must exist')
    if output == gis_dir or gis_dir in output.parents or output in gis_dir.parents or output == workbook.parent:
        raise ValueError('Outputs must be separate from raw source paths')
    output.mkdir(parents=True, exist_ok=True)
    source_inventory = inventory(gis_dir)
    workbook_sha = digest(workbook)
    dependencies = {n:importlib.metadata.version(n) for n in ('geopandas','shapely','pyproj','pyogrio','pandas')}
    code_hash = hashlib.sha256(''.join(digest(ROOT/'scripts'/n) for n in ('observatory_etl.py','extract_ltfrb_routes.py','validate_ltfrb_gis.py')).encode()).hexdigest()
    signature = dict(pipeline=VERSION, code_sha256=code_hash, dependencies=dependencies, python_version=sys.version.split()[0],
                     workbook_sha256=workbook_sha, gis_inventory=source_inventory)
    version = hashlib.sha256(encode(signature).encode()).hexdigest()[:20]
    release = output/'releases'/version
    if release.exists() and not refresh:
        manifest = verify_release(release)
        write_json(output/'latest.json', dict(version=version, release=f'releases/{version}'))
        print(encode(dict(version=version, status='verified_existing_release', stats=manifest['statistics'])))
        return release
    if release.exists():
        raise ValueError('Immutable release already exists; use verification without --refresh, or a new output root for forced reconstruction')
    records = extract(workbook)
    if not records:
        raise ValueError('Workbook contains no route records')
    tables = normalize(records)
    by_id = defaultdict(list)
    for r in tables['routes']:
        if r['file_id']:
            by_id[r['file_id']].append(r['route_id'])
    assets, layers, features = [], [], []
    cache = output/'cache'; cache.mkdir(exist_ok=True)
    hits = 0
    for i, file_id in enumerate(sorted(by_id), 1):
        entries = [e for e in source_inventory if Path(e['name']).stem == file_id]
        cache_key = hashlib.sha256(encode([code_hash, dependencies, file_id, entries]).encode()).hexdigest()
        cache_path = cache/(cache_key+'.json')
        result = None
        if cache_path.exists() and not refresh:
            try:
                candidate = json.loads(cache_path.read_text(encoding='utf-8'))
                if all(k in candidate for k in ('asset','layers','features','issues')) and candidate['asset']['file_id']==file_id:
                    result=candidate; hits+=1
            except (ValueError,KeyError,TypeError):
                pass  # Corrupt or incompatible cache is rebuilt from read-only source.
        if result is None:
            result = inspect_asset(file_id, gis_dir, source_inventory)
            write_json(cache_path, result)
        assets.append(result['asset']); layers.extend(result['layers']); features.extend(result['features'])
        tables['issues'].extend(result['issues'])
        if len(by_id[file_id]) > 1:
            for rid in by_id[file_id]:
                tables['issues'].append(issue('route', rid, 'shared_source_file', encode(by_id[file_id])))
        if i % 50 == 0:
            print(f'Inspected {i}/{len(by_id)} source IDs; {hits} cached', flush=True)
    geometry_groups = defaultdict(list)
    for f in features:
        if f['geometry_sha256']:
            geometry_groups[f['geometry_sha256']].append(f['feature_id'])
    for ids in geometry_groups.values():
        if len(ids) > 1:
            for fid in ids:
                tables['issues'].append(issue('feature', fid, 'exact_duplicate_geometry', encode(ids)))
    duplicated_features={fid for ids in geometry_groups.values() if len(ids)>1 for fid in ids}
    for f in features:
        if f['status']!='geometry_pass' or f['feature_id'] in duplicated_features:
            for rid in by_id[f['file_id']]:
                tables['issues'].append(issue('route',rid,'source_geometry_review',f['reason'] or 'Exact duplicate geometry across source features'))
    layer_candidates = defaultdict(list)
    features_by_layer = defaultdict(list)
    for f in features:
        features_by_layer[f['layer_id']].append(f)
    for layer in layers:
        fs = features_by_layer[layer['layer_id']]
        if len(fs) == 1 and fs[0]['status'] == 'geometry_pass' and not layer['error']:
            layer_candidates[layer['file_id']].append(dict(layer_name=layer['layer_name'],feature_count=1,
                geodesic_line_km=fs[0]['geodesic_km'],invalid_geometry=0,null_geometry=0,empty_geometry=0,
                crs_present=True,crs_metadata_consistent=True,error='',feature_id=fs[0]['feature_id']))
    comparisons = comparison_rows(records, layer_candidates)
    comparison_index = {(int(c['route_no']), c['direction_index']): c for c in comparisons}
    associations = []
    raw_by_no = {int(r['route_no']):r for r in records}
    for d in tables['directions']:
        no = int(d['route_id'].rsplit('-',1)[1]); c = comparison_index.get((no,d['ordinal']))
        matched = c and c['measured_length_km'] is not None
        feature_id = None
        if matched:
            feature_id = next(x['feature_id'] for x in layer_candidates[raw_by_no[no]['file_id']] if x['layer_name']==c['matched_layer'])
        status = 'not_applicable_loop' if d['metadata_status']=='not_applicable_loop' else ('candidate' if matched else 'unresolved')
        associations.append(dict(direction_id=d['direction_id'], feature_id=feature_id, association_status=status,
                                 match_method=c['match_confidence'] if c else None,
                                 length_screen=c['threshold_result'] if c else 'not_applicable',
                                 measured_km=c['measured_length_km'] if matched else None,
                                 absolute_difference_km=c['absolute_difference_km'] if matched else None,
                                 difference_pct=c['percentage_difference'] if matched else None,
                                 reason=c['reason'] if c else 'Explicit loop has no second direction'))
        if status == 'unresolved':
            tables['issues'].append(issue('direction', d['direction_id'], 'unresolved_geometry_association', c['reason'] if c else 'No defensible candidate'))
        if matched and c['threshold_result']=='review_length_discrepancy':
            tables['issues'].append(issue('direction',d['direction_id'],'length_discrepancy',encode(c)))
    assets_by_id = {a['file_id']:a for a in assets}
    for r in tables['routes']:
        if r['file_id'] not in assets_by_id or assets_by_id[r['file_id']]['status'] != 'inspected':
            tables['issues'].append(issue('route',r['route_id'],'source_not_spatially_inspected',r['file_id'] or 'missing ID'))
    route_issues = defaultdict(list)
    direction_routes = {d['direction_id']:d['route_id'] for d in tables['directions']}
    for item in tables['issues']:
        if item['entity_type']=='route': route_issues[item['entity_id']].append(item['code'])
        elif item['entity_type']=='direction': route_issues[direction_routes[item['entity_id']]].append(item['code'])
    for r in tables['routes']:
        r['quality_flags_json'] = encode(sorted(set(route_issues[r['route_id']])))
        r['review_status'] = 'needs_review' if route_issues[r['route_id']] else 'candidate_metadata_only'
    tables.update(assets=assets, layers=layers, features=features, associations=associations)
    tables['issues'] = sorted({r['issue_id']:r for r in tables['issues']}.values(), key=lambda x:x['issue_id'])
    stats = dict(source_route_records=len(records), normalized_route_records=len(tables['routes']),
                 source_unique_names=len({r['route_name'] for r in records}), normalized_unique_names=len({r['name_match_key'] for r in tables['routes']}),
                 linked_source_ids=len(by_id), local_directory_files=len(source_inventory),
                 asset_statuses=dict(Counter(a['status'] for a in assets)), spatial_layers=len(layers),
                 feature_statuses=dict(Counter(f['status'] for f in features)),
                 geometry_duplicate_groups=sum(len(v)>1 for v in geometry_groups.values()),
                 direction_statuses=dict(Counter(d['metadata_status'] for d in tables['directions'])),
                 association_statuses=dict(Counter(a['association_status'] for a in associations)),
                 length_screening=dict(Counter(a['length_screen'] for a in associations)),
                 route_review_statuses=dict(Counter(r['review_status'] for r in tables['routes'])),
                 lgu_label_rows=len(tables['route_localities']), canonical_municipalities_verified=0,
                 transformation_events=len(tables['transformations']), issue_codes=dict(Counter(i['code'] for i in tables['issues'])),
                 navigation_ready_routes=None)
    # Check raw bytes a second time before publishing any generated release.
    if inventory(gis_dir) != source_inventory or digest(workbook) != workbook_sha:
        raise RuntimeError('Raw sources changed during processing; no release promoted')
    (output/'releases').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='observatory-', dir=output) as temporary:
        staging = Path(temporary)
        for name, rows in tables.items():
            write_json(staging/(name+'.json'), rows)
            pd.DataFrame(rows).to_csv(staging/(name+'.csv'),index=False,lineterminator='\n')
        uncertain = [r for r in tables['routes'] if r['review_status']=='needs_review']
        write_json(staging/'uncertain_routes.json', uncertain)
        pd.DataFrame(uncertain).to_csv(staging/'uncertain_routes.csv',index=False,lineterminator='\n')
        quarantined = [f for f in features if f['status']!='geometry_pass']
        write_json(staging/'quarantined_features.json', quarantined)
        passes = [f for f in features if f['status']=='geometry_pass']
        collection = dict(type='FeatureCollection',features=[dict(type='Feature',geometry=json.loads(f['geometry_json']),properties={
            'feature_id':f['feature_id'],'file_id':f['file_id'],'layer_id':f['layer_id'],
            'geodesic_km':f['geodesic_km'],'geometry_status':'geometry_pass',
            'route_identity':'not_confirmed','navigation_status':'not_verified',
            'duplicate_geometry':len(geometry_groups[f['geometry_sha256']])>1}) for f in passes])
        write_json(staging/'geometry_pass.geojson', collection)
        if passes:
            frame = gpd.GeoDataFrame.from_features(collection['features'],crs=4326)
            frame.to_file(staging/'geometry_pass.gpkg',layer='geometry_pass',driver='GPKG',engine='pyogrio')
            reread = gpd.read_file(staging/'geometry_pass.gpkg',engine='pyogrio')
            if len(reread)!=len(passes) or not reread.geometry.is_valid.all() or reread.crs.to_epsg()!=4326:
                raise RuntimeError('Generated spatial output failed round-trip validation')
        sql_write(staging/'observatory.sqlite', tables)
        write_json(staging/'statistics.json', stats)
        dictionary = []
        for table, rows in tables.items():
            if rows:
                for column in rows[0]:
                    dictionary.append(dict(table=table,column=column,nullable=any(r[column] is None for r in rows),
                        description=field_description(table,column)))
        write_json(staging/'data_dictionary.json',dictionary)
        (staging/'DATA_DICTIONARY.md').write_text('# Release data dictionary\n\n'+
            '| Table | Column | Description |\n|---|---|---|\n'+
            '\n'.join(f"| {d['table']} | {d['column']} | {d['description']} |" for d in dictionary)+'\n',encoding='utf-8')
        write_json(staging/'provenance.json',dict(**signature, source_effective_date=None,
            publication_permission='not_established', spatial_scope='Region XI and intercity; no Davao-only filter',
            identity_limit='Geometry pass is structural; associations are candidates; locality names are source labels, not verified PSGC entities',
            repairs_applied=False, shared_source_records_merged=False))
        report = ['# LTFRB cleaned release quality report','',f'Release: `{version}`','',
                  'Original files were read only and rehashed before promotion. No repairs, route merges or operational inferences were applied.',
                  '', '## Before and after', '',
                  f"- Workbook records: {len(records)}; normalized records retained: {len(tables['routes'])}.",
                  f"- Original unique names: {stats['source_unique_names']}; normalized comparison keys: {stats['normalized_unique_names']}.",
                  f"- Transformation events: {stats['transformation_events']}; source values remain in original_record_json and transformation tables.",
                  '', '## Measured results','', '```json',json.dumps(stats,indent=2),'```','',
                  '## Output interpretation','',
                  '`geometry_pass` contains structurally valid, finite, positive-length linear geometry transformed to EPSG:4326. Duplicate geometry is flagged, not silently deduplicated. Route identity and current service are not confirmed.',
                  '`quarantined_features.json` and the SQLite features table retain rejected feature identities, reasons and original WKB. Invalid geometry is not repaired or exported as a trusted line.',
                  '`associations` includes unambiguous automatic candidates only; no candidate is promoted to a confirmed direction. Shared source-file IDs remain unresolved.',
                  '`route_localities` separates explicit administrative wording but does not resolve homonymous places, spelling variants or historical municipality/city labels. canonical_psgc remains null.',
                  '`uncertain_routes` contains route-level or direction-level review cases. Spatial features and issues must also be consulted; metadata cleanliness is not spatial certification.',
                  '', '## Remaining work','',
                  'Complete partial downloads and shapefile bundles; review invalid features and duplicate linework; confirm route/layer/direction identities; review locality labels against an authoritative gazetteer; confirm permissions before publication.',
                  'Cross-route partial-overlap analysis, map matching, connectivity and source-owner approval are not performed by this release.',
                  '', '## Publication','', 'PRIVATE DERIVED DATA. No external publication or deployment was performed. Raw-source licensing and permitted derived-data release remain separate decisions.']
        (staging/'QUALITY_REPORT.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
        outputs = [dict(path=p.name,bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(staging.iterdir()) if p.is_file()]
        write_json(staging/'manifest.json',dict(version=version,pipeline=VERSION,statistics=stats,outputs=outputs))
        # Promote only completed staging. Same-volume rename is atomic; no partial latest pointer.
        staging.rename(release)
    verify_release(release)
    write_json(output/'latest.json',dict(version=version,release=f'releases/{version}'))
    write_json(output/'last_run.json',dict(version=version,completed_at_utc=datetime.now(timezone.utc).isoformat(),
                                         assets_processed=len(assets)-hits,asset_cache_hits=hits,raw_checksums_unchanged=True))
    print(encode(dict(version=version,status='created',release=str(release),statistics=stats)))
    return release


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workbook',required=True,type=Path)
    p.add_argument('--gis-dir',required=True,type=Path)
    p.add_argument('--out',type=Path,default=ROOT/'data/processed/ltfrb_observatory')
    p.add_argument('--refresh',action='store_true',help='Ignore per-asset cache; existing releases remain immutable')
    args = p.parse_args()
    try:
        build(args.workbook,args.gis_dir,args.out,args.refresh)
    except Exception as exc:
        print(f'ETL failed: {type(exc).__name__}: {exc}',file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
