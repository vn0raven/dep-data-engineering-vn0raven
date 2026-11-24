"""Fail closed before Pages uploads: exact files, checksums and OSM-only data."""
import hashlib
import json
from pathlib import Path
import re
import sys


def check(root):
    root=Path(root)
    pointer=json.loads((root/'data/latest.json').read_text())
    version=pointer['version']
    if not re.fullmatch('[0-9a-f]{20}',version) or pointer['release']!='releases/'+version:raise ValueError('Invalid pointer')
    relative='data/'+pointer['release']
    manifest=json.loads((root/relative/'manifest.json').read_text())
    files={'bundle.json','originals.geojson','provenance.json'}
    if manifest['version']!=version or set(manifest['outputs'])!=files:raise ValueError('Invalid manifest')
    canonical=json.dumps(manifest['outputs'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    if hashlib.sha256(canonical).hexdigest()[:20]!=version:raise ValueError('Release identity mismatch')
    expected={'app.js','explorer.js','index.html','style.css','data/latest.json'}|{relative+'/'+n for n in files|{'manifest.json'}}
    approval=root/'publication-approval.json'
    approved=None
    if approval.exists():
        approved=json.loads(approval.read_text())
        if approved.get('release_version')!=version or approved.get('authority')!='project_maintainer_not_source_agency':raise ValueError('Approval does not cover this exact release')
        expected.add('publication-approval.json')
    actual={str(p.relative_to(root)).replace('\\','/') for p in root.rglob('*') if p.is_file()}
    if actual!=expected:raise ValueError('Unexpected publish files: '+str(actual^expected))
    for name,sha in manifest['outputs'].items():
        if hashlib.sha256((root/relative/name).read_bytes()).hexdigest()!=sha:raise ValueError('Checksum mismatch: '+name)
    bundle=json.loads((root/relative/'bundle.json').read_text(encoding='utf-8'))
    mixed=bundle['publication']=='maintainer_authorized_ltfrb' and approved is not None
    if not mixed and (bundle['publication']!='osm_public' or any(r['source']!='OSM' for r in bundle['routes'])):raise ValueError('LTFRB proposal is blocked from Pages')
    allowed={'route_id','route_name','source','mode','classification','geography','observed_at','directions','quality','provenance'}
    for r in bundle['routes']:
        if set(r)!=allowed or not re.fullmatch('osm-relation-[0-9]+|ltfrb-record-[0-9]{3}',r['route_id']):raise ValueError('Route field boundary violation')
        if r['source']=='LTFRB':
            if not mixed or re.search(r'https?://|@|[A-Za-z0-9_-]{32,}',json.dumps(r)):raise ValueError('Government field boundary violation')
            continue
        if r['source']!='OSM':raise ValueError('Unknown source')
        if r['provenance']!='https://www.openstreetmap.org/relation/'+r['route_id'].split('-')[-1]:raise ValueError('Source link boundary violation')
    for f in bundle['features']+json.loads((root/relative/'originals.geojson').read_text())['features']:
        if f['properties']['source']=='LTFRB':
            if not mixed or f['properties']['association']!='candidate_direction_match':raise ValueError('Unapproved government geometry')
        elif f['properties']['source']!='OSM' or f['properties']['candidate_route_ids']:raise ValueError('Non-OSM geometry')
    return {'status':'passed','version':version,'files':sorted(expected),'routes':len(bundle['routes'])}


if __name__=='__main__':
    print(json.dumps(check(sys.argv[1] if len(sys.argv)>1 else 'dashboard/observatory'),indent=2))
