"""Build checked static OSM assets and an isolated, unpublished LTFRB proposal."""
import argparse
from collections import defaultdict
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform
from scripts.export_osm_public import export, encoded, digest, OUTPUT, ROOT
from scripts.verify_observatory import verify

WEB = ROOT/'dashboard/observatory'
PRIVATE = ROOT/'reports/observatory-private/publication-proposal'
ROUTE_KEYS = {'route_id','route_name','source','mode','classification','geography','observed_at','directions','quality','provenance'}
DIRECTION_KEYS = {'ordinal','direction','declared_km','association_status'}
FEATURE_KEYS = {'route_ids','candidate_route_ids','status','source','association'}
TO_METERS=Transformer.from_crs(4326,32651,always_xy=True).transform
TO_WGS=Transformer.from_crs(32651,4326,always_xy=True).transform


def compact(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':')).encode()


def validate(bundle):
    if set(bundle) != {'schema_version','publication','routes','features','provenance','display'} or bundle['schema_version'] != 1:
        raise ValueError('Invalid bundle schema')
    ids=set()
    for route in bundle['routes']:
        if set(route)!=ROUTE_KEYS or route['source'] not in {'OSM','LTFRB'} or route['route_id'] in ids:
            raise ValueError('Route allowlist or identity violation')
        ids.add(route['route_id'])
        if not isinstance(route['route_name'],str) or not isinstance(route['geography'],list):raise ValueError('Invalid route types')
        for d in route['directions']:
            if set(d)!=DIRECTION_KEYS or type(d['ordinal']) is not int or (d['declared_km'] is not None and (type(d['declared_km']) not in (float,int) or d['declared_km']<0)):
                raise ValueError('Invalid direction schema')
        if route['source']=='LTFRB' and re.search(r'https?://|@|[A-Za-z0-9_-]{32,}',json.dumps(route)):
            # Controlled public IDs are short; source paths/IDs/URLs cannot enter route text.
            raise ValueError('Restricted source text in LTFRB proposal')
    for f in bundle['features']:
        if set(f)!={'type','id','geometry','properties'} or set(f['properties'])!=FEATURE_KEYS:
            raise ValueError('Feature allowlist violation')
        if not set(f['properties']['route_ids'])<=ids:raise ValueError('Dangling route association')
        g=shape(f['geometry'])
        if g.geom_type not in {'LineString','MultiLineString'} or not g.is_valid or g.is_empty:raise ValueError('Invalid line geometry')
    if bundle['publication']=='osm_public' and any(r['source']!='OSM' for r in bundle['routes']):
        raise ValueError('Government detail cannot enter public package')


def check_osm():
    p=json.loads((OUTPUT/'latest.json').read_text())
    if not re.fullmatch('[a-f0-9]{20}',p['version']) or p['release']!='releases/'+p['version']:raise ValueError('Unsafe pointer')
    directory=OUTPUT/p['release'];m=json.loads((directory/'manifest.json').read_text())
    if m['version']!=p['version'] or digest(encoded(m['outputs']))[:20]!=p['version']:raise ValueError('Manifest identity mismatch')
    for name,sha in m['outputs'].items():
        if Path(name).name!=name or digest((directory/name).read_bytes())!=sha:raise ValueError('OSM release checksum mismatch')
    return directory


def osm_bundle():
    directory=check_osm()
    provenance=json.loads((directory/'provenance.json').read_text(encoding='utf-8'))
    rows=json.loads((directory/'routes.json').read_text(encoding='utf-8'))
    features=json.loads((directory/'lines.geojson').read_text(encoding='utf-8'))['features']
    grouped=defaultdict(list)
    for f in features:grouped[f['properties']['route_id']].append(f['geometry']['coordinates'])
    routes=[];original=[]
    for r in rows:
        t=r['source_tags'];rid=r['route_id']
        routes.append(dict(route_id=rid,route_name=t.get('name') or t.get('ref') or 'Unnamed OSM relation',source='OSM',mode=t['route'],classification='Not applicable',geography=[v for v in [t.get('from'),t.get('to')] if v],observed_at=provenance['snapshot_accessed_at'],directions=[dict(ordinal=1,direction=' to '.join([t.get('from','Not supplied'),t.get('to','Not supplied')]),declared_km=None,association_status='explicit_osm_membership')],quality=f"{r['line_members_exported']} explicit way members; {r['line_members_unavailable']} unavailable; {r['line_members_rejected']} rejected. Service activity unverified.",provenance=r['source_url']))
        if grouped[rid]:original.append(dict(type='Feature',id=rid+'-lines',geometry={'type':'MultiLineString','coordinates':grouped[rid]},properties=dict(route_ids=[rid],candidate_route_ids=[],status='structural_checks_passed',source='OSM',association='explicit_osm_membership')))
    return routes,original,provenance


def ltfrb_bundle():
    root=ROOT/'data/processed/ltfrb_observatory';p=json.loads((root/'latest.json').read_text())
    if not re.fullmatch('[a-f0-9]{20}',p['version']) or p['release']!='releases/'+p['version']:raise ValueError('Unsafe private pointer')
    release=root/p['release'];verify(release)
    routes=[];features=[]
    with closing(sqlite3.connect((release/'observatory.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        for i,r in enumerate(db.execute('SELECT route_id,route_name,mode,classification,metadata_status FROM routes ORDER BY route_id'),1):
            rid=f'ltfrb-record-{i:03}'
            ds=list(db.execute('SELECT d.ordinal,d.direction,d.declared_km,a.association_status,a.feature_id FROM directions d LEFT JOIN associations a USING(direction_id) WHERE d.route_id=? ORDER BY ordinal',(r['route_id'],)))
            geog=[x[0] for x in db.execute('SELECT DISTINCT locality_name FROM route_localities JOIN directions USING(direction_id) WHERE route_id=? AND locality_name IS NOT NULL ORDER BY locality_name',(r['route_id'],))]
            routes.append(dict(route_id=rid,route_name=r['route_name'] or 'Unnamed register record',source='LTFRB',mode=r['mode'],classification=r['classification'],geography=geog,observed_at='Source observation date not supplied',directions=[dict(ordinal=d['ordinal'],direction=d['direction'],declared_km=d['declared_km'],association_status=d['association_status']) for d in ds],quality='Metadata: '+str(r['metadata_status'])+'. Geography labels are unverified source labels. Candidate matches are not government confirmation.',provenance='LTFRB Region XI register; supplied directly for educational project. Redistribution terms not specified.'))
            for d in ds:
                if d['association_status']!='candidate' or not d['feature_id']:continue
                f=db.execute("SELECT geometry_json FROM features WHERE feature_id=? AND status='geometry_pass'",(d['feature_id'],)).fetchone()
                if f:features.append(dict(type='Feature',id=rid+'-direction-'+str(d['ordinal']),geometry=json.loads(f[0]),properties=dict(route_ids=[rid],candidate_route_ids=[rid],status='structural_checks_passed',source='LTFRB',association='candidate_direction_match')))
    return routes,features,{'source':'LTFRB Region XI','license':'Not specified. No open licence or agency endorsement claimed.','source_release_verified':True,'association_method':'Existing conservative ETL candidate pairing only; unresolved directions carry no geometry. No OSM matching performed.'}


def build(proposal=False, authorized=False):
    if proposal and authorized: raise ValueError("Choose local proposal or authorized public build")
    routes,original,provenance=osm_bundle()
    if proposal or authorized:
        r,f,p=ltfrb_bundle();routes+=r;original+=f;provenance={'OSM':provenance,'LTFRB':p}
    display=[];before=after=0
    for f in original:
        g=shape(f['geometry']);before+=sum(len(x.coords) for x in g.geoms) if g.geom_type=='MultiLineString' else len(g.coords)
        simplified=transform(TO_WGS,transform(TO_METERS,g).simplify(10,preserve_topology=True))
        after+=sum(len(x.coords) for x in simplified.geoms) if simplified.geom_type=='MultiLineString' else len(simplified.coords)
        display.append({**f,'geometry':mapping(simplified)})
    bundle=dict(schema_version=1,publication='local_proposal_not_authorized' if proposal else ('maintainer_authorized_ltfrb' if authorized else 'osm_public'),routes=routes,features=display,provenance=provenance,display={'tolerance_m':10,'crs':'EPSG:32651','original_vertices':before,'display_vertices':after,'area_comparisons':'Original unsimplified geometry; lines grouped per OSM relation or LTFRB candidate direction.'})
    validate(bundle)
    blobs={'bundle.json':compact(bundle),'originals.geojson':compact({'type':'FeatureCollection','features':original}),'provenance.json':encoded(provenance)}
    hashes={k:digest(v) for k,v in blobs.items()};version=digest(compact(hashes))[:20]
    base=PRIVATE/'data' if proposal else WEB/'data';release=base/'releases'/version
    release.mkdir(parents=True,exist_ok=True)
    blobs['manifest.json']=compact({'version':version,'outputs':hashes})
    for name,body in blobs.items():
        target=release/name
        if target.exists() and target.read_bytes()!=body:raise ValueError('Immutable package altered')
        if not target.exists():target.write_bytes(body)
    (base/'latest.json').write_bytes(compact({'version':version,'release':'releases/'+version}))
    if proposal:
        for name in ['index.html','style.css','app.js','explorer.js']:shutil.copyfile(WEB/name,PRIVATE/name)
        (PRIVATE/'REVIEW_SAMPLES.json').write_bytes(encoded({'publication':'NOT AUTHORIZED','examples': [next(r for r in routes if r['source']=='LTFRB'),next(r for r in routes if r['source']=='LTFRB' and not any(r['route_id'] in f['properties']['route_ids'] for f in display))]}))
    print(json.dumps({'version':version,'proposal':proposal,'routes':len(routes),'features':len(display),'bundle_bytes':len(blobs['bundle.json']),'original_bytes':len(blobs['originals.geojson']),'vertices_before':before,'vertices_after':after}))
    return bundle,release


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proposal',action='store_true');p.add_argument('--authorized-ltfrb',action='store_true');args=p.parse_args();build(args.proposal,args.authorized_ltfrb)
