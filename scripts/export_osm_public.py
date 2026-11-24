"""Build an immutable, OSM-only public database; does not publish or read LTFRB."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import LineString
from pyproj import Geod

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/raw/osm_davao_transit_elements_20260801T102121Z.json'
OUTPUT = ROOT / 'data/processed/osm_public'
MODES = {'bus', 'minibus', 'share_taxi', 'trolleybus', 'tram', 'train', 'subway', 'light_rail', 'ferry'}
VERSION = '2'
GEOD = Geod(ellps='WGS84')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)+'\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def derive(payload):
    if payload.get('remark'):
        raise ValueError('Overpass reported a possibly incomplete response')
    elements = payload['elements']
    routes, features, rejected = [], [], []
    seen = set()
    for relation in elements:
        tags = relation.get('tags', {})
        if relation.get('type') != 'relation' or tags.get('type') != 'route' or tags.get('route') not in MODES:
            continue
        rid = relation['id']
        if not isinstance(rid, int) or rid <= 0 or rid in seen:
            raise ValueError('Invalid or duplicate route relation ID')
        seen.add(rid)
        route_id = f'osm-relation-{rid}'
        accepted = 0
        unavailable = 0
        length = 0.0
        for ordinal, member in enumerate(relation.get('members', [])):
            if member.get('type') != 'way' or member.get('role', '') in {'platform', 'platform_entry_only', 'platform_exit_only'}:
                continue
            geometry = member.get('geometry')
            if not geometry:
                unavailable += 1
                continue
            try:
                coords = [[point['lon'], point['lat']] for point in geometry]
                if len(coords) < 2 or any(type(v) not in (int, float) or not math.isfinite(v) for xy in coords for v in xy):
                    raise ValueError('Invalid coordinates')
                if any(not (-180 <= x <= 180 and -90 <= y <= 90) for x,y in coords):
                    raise ValueError('Coordinates outside WGS84 bounds')
                line = LineString(coords)
                if not line.is_valid or line.is_empty or line.length == 0:
                    raise ValueError('Degenerate or invalid line')
            except (KeyError, TypeError, ValueError):
                rejected.append({'route_id': route_id, 'member_ordinal': ordinal, 'reason': 'invalid_member_geometry'})
                continue
            km = abs(GEOD.geometry_length(line))/1000
            length += km
            accepted += 1
            features.append({'type': 'Feature', 'id': f'{route_id}-member-{ordinal}',
                'geometry': {'type': 'LineString', 'coordinates': coords},
                'properties': {'route_id': route_id, 'osm_way_id': member.get('ref'),
                    'member_ordinal': ordinal, 'member_role': member.get('role',''),
                    'association': 'explicit_osm_relation_membership', 'structural_status': 'passed',
                    'geodesic_km': round(km,6)}})
        # Explicit field allowlist: no contributors, contact tags, notes or government inputs.
        fields = {key: tags[key] for key in ('name','ref','route','from','to') if isinstance(tags.get(key), str)}
        routes.append({'route_id':route_id, 'osm_relation_id':rid, 'source_url':f'https://www.openstreetmap.org/relation/{rid}',
            'source_tags': fields, 'line_members_exported':accepted, 'line_members_unavailable':unavailable,
            'line_members_rejected':sum(item['route_id']==route_id for item in rejected),
            'summed_member_km':round(length,6), 'service_activity':'not_verified',
            'government_classification':None})
    routes.sort(key=lambda row: row['osm_relation_id'])
    features.sort(key=lambda row: row['id'])
    return {'routes.json':routes, 'lines.geojson':{'type':'FeatureCollection','features':features},
        'quality.json':{'route_relations':len(routes),'line_member_features':len(features),
            'routes_without_lines':sum(not r['line_members_exported'] for r in routes),
            'unavailable_line_members':sum(r['line_members_unavailable'] for r in routes),
            'rejected_line_members':rejected}}


def export(source=SOURCE, output=OUTPUT):
    source = Path(source).resolve()
    # Deliberately restrict input to existing OSM ingestion naming and directory.
    if source.parent != (ROOT/'data/raw').resolve() or not source.name.startswith('osm_davao_transit_elements_'):
        raise ValueError('Only project OSM ingestion snapshots are accepted')
    raw = source.read_bytes()
    metadata = json.loads(source.with_suffix('.metadata.json').read_text(encoding='utf-8'))
    if metadata.get('source_name') != 'OpenStreetMap data via Overpass API' or metadata['response']['sha256'] != digest(raw.replace(b'\r\n', b'\n')):
        raise ValueError('OSM provenance or input checksum mismatch')
    files = derive(json.loads(raw))
    files['provenance.json'] = {'source':'OpenStreetMap contributors','source_file':source.name,
        'source_sha256':metadata['response']['sha256'], 'checksum_handling':'CRLF normalized to LF only for source checksum verification','snapshot_accessed_at':metadata['accessed_at_utc'],
        'exporter_version':VERSION,'license':'ODbL-1.0',
        'license_url':'https://opendatacommons.org/licenses/odbl/1-0/',
        'attribution':'© OpenStreetMap contributors','attribution_url':'https://www.openstreetmap.org/copyright',
        'limitations':['Historical snapshot, not live service data.',
            'OSM relations are not LTFRB register records; no cross-source matching performed.',
            'Separate member lines are not repaired, joined or inferred across gaps.',
            'Summed member length counts repeated or overlapping members; not a verified trip distance.',
            'Query selected relations intersecting Davao; member geometry may extend beyond the city.',
            'No verified boarding access, transfers, service activity or completeness claim.']}
    blobs = {name:encoded(value) for name,value in files.items()}
    manifest = {name:digest(blob) for name,blob in sorted(blobs.items())}
    version = digest(encoded(manifest))[:20]
    release = Path(output)/'releases'/version
    blobs['manifest.json'] = encoded({'version':version,'outputs':manifest})
    release.mkdir(parents=True,exist_ok=True)
    for name,blob in blobs.items():
        target=release/name
        if target.exists() and target.read_bytes()!=blob:
            raise ValueError('Existing immutable output was modified: '+name)
    for name,blob in blobs.items():
        if not (release/name).exists(): (release/name).write_bytes(blob)
    pointer=Path(output)/'latest.json'
    temporary=pointer.with_suffix('.tmp')
    temporary.write_bytes(encoded({'version':version,'release':f'releases/{version}'}))
    temporary.replace(pointer)
    return {'version':version,'path':str(release),'quality':files['quality.json']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    print(json.dumps(export(args.source,args.output),indent=2))
