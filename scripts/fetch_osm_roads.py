"""Fetch and load open-licensed OpenStreetMap Davao City road network (ODbL-1.0)."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import requests
from pyproj import Transformer
from shapely.geometry import LineString, mapping
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / 'data/raw/osm_davao_roads_snapshot.json'
META_PATH = ROOT / 'data/raw/osm_davao_roads_snapshot.metadata.json'
BBOX = (6.92, 125.38, 7.34, 125.72)  # (south, west, north, east)
MIRRORS = [
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://lz4.overpass-api.de/api/interpreter',
]
HIGHWAY_MAP = {
    'motorway': 'trunk',
    'motorway_link': 'trunk',
    'trunk': 'trunk',
    'trunk_link': 'trunk',
    'primary': 'primary',
    'primary_link': 'primary',
    'secondary': 'secondary',
    'secondary_link': 'secondary',
    'tertiary': 'tertiary',
    'tertiary_link': 'tertiary',
    'residential': 'residential',
}
SIMPLIFY_TOLERANCE_M = {
    'trunk': 10.0,
    'primary': 10.0,
    'secondary': 12.0,
    'tertiary': 12.0,
    'residential': 15.0,
}
ALLOWED_ROAD_KEYS = {'osm_way_id', 'name', 'highway', 'source'}
ALLOWED_HIGHWAY_CLASSES = {'trunk', 'primary', 'secondary', 'tertiary', 'residential'}

TO_METERS = Transformer.from_crs(4326, 32651, always_xy=True).transform
TO_WGS = Transformer.from_crs(32651, 4326, always_xy=True).transform


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _round_coords(coords):
    return [[round(float(x), 5), round(float(y), 5)] for x, y in coords]


def fetch_osm_roads(raw_path: Path = RAW_PATH, meta_path: Path = META_PATH):
    """Download Davao City highway ways from Overpass API and save snapshot + metadata."""
    s, w, n, e = BBOX
    query = (
        '[out:json][timeout:120];'
        f'way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]({s},{w},{n},{e});'
        'out body geom;'
    )
    last_err = None
    payload_bytes = None
    used_url = None
    for mirror in MIRRORS:
        try:
            resp = requests.post(
                mirror,
                data={'data': query},
                headers={'User-Agent': 'davao-commute-router/1.0 (educational)', 'Accept': 'application/json'},
                timeout=130,
            )
            resp.raise_for_status()
            text = resp.text.replace('\r\n', '\n')
            data = json.loads(text)
            if 'elements' not in data:
                raise ValueError(f'Missing elements in Overpass response from {mirror}')
            if data.get('remark'):
                raise ValueError(f'Overpass remark from {mirror}: {data["remark"]}')
            payload_bytes = text.encode('utf-8')
            used_url = mirror
            break
        except Exception as exc:
            last_err = exc
    if payload_bytes is None:
        raise RuntimeError(f'All Overpass mirrors failed: {last_err}')

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(payload_bytes)
    accessed_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    metadata = {
        'source_name': 'OpenStreetMap data via Overpass API',
        'source_url': used_url,
        'accessed_at_utc': accessed_at,
        'license': 'ODbL-1.0',
        'license_url': 'https://opendatacommons.org/licenses/odbl/1-0/',
        'attribution': '© OpenStreetMap contributors',
        'attribution_url': 'https://www.openstreetmap.org/copyright',
        'bbox': list(BBOX),
        'response': {'sha256': _digest(payload_bytes), 'bytes': len(payload_bytes)},
    }
    meta_bytes = (json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    meta_path.write_bytes(meta_bytes)
    return len(json.loads(payload_bytes)['elements']), metadata


def load_osm_roads(raw_path: Path = RAW_PATH):
    """Verify raw OSM roads snapshot checksum and build simplified GeoJSON + provenance."""
    raw_path = Path(raw_path)
    meta_path = raw_path.with_suffix('.metadata.json')
    if not raw_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f'Missing OSM roads snapshot or metadata: {raw_path}')
    raw_bytes = raw_path.read_bytes().replace(b'\r\n', b'\n')
    metadata = json.loads(meta_path.read_text(encoding='utf-8'))
    if metadata.get('source_name') != 'OpenStreetMap data via Overpass API' or metadata.get('license') != 'ODbL-1.0':
        raise ValueError('OSM roads metadata license or source mismatch')
    if metadata.get('response', {}).get('sha256') != _digest(raw_bytes):
        raise ValueError('OSM roads raw snapshot SHA-256 mismatch')

    elements = json.loads(raw_bytes.decode('utf-8')).get('elements', [])
    features = []
    seen_ids = set()
    class_counts = {c: 0 for c in ALLOWED_HIGHWAY_CLASSES}

    for way in elements:
        if way.get('type') != 'way':
            continue
        wid = way.get('id')
        tags = way.get('tags') or {}
        hw_raw = tags.get('highway')
        if not isinstance(wid, int) or wid <= 0 or wid in seen_ids or hw_raw not in HIGHWAY_MAP:
            continue
        geom = way.get('geometry') or []
        if len(geom) < 2:
            continue
        try:
            coords = [[pt['lon'], pt['lat']] for pt in geom]
            if any(type(v) not in (int, float) or not math.isfinite(v) for xy in coords for v in xy):
                continue
            if any(not (-180 <= x <= 180 and -90 <= y <= 90) for x, y in coords):
                continue
            line = LineString(coords)
            if line.is_empty or not line.is_valid or line.length == 0:
                continue
            hw_class = HIGHWAY_MAP[hw_raw]
            tol = SIMPLIFY_TOLERANCE_M[hw_class]
            simplified = transform(TO_WGS, transform(TO_METERS, line).simplify(tol, preserve_topology=True))
            if simplified.is_empty or not simplified.is_valid or simplified.geom_type != 'LineString':
                continue
            rounded = _round_coords(simplified.coords)
            if len(rounded) < 2 or rounded[0] == rounded[-1] and len(rounded) == 2:
                continue
            final_line = LineString(rounded)
            if final_line.is_empty or not final_line.is_valid or final_line.length == 0:
                continue
        except (KeyError, TypeError, ValueError):
            continue

        seen_ids.add(wid)
        class_counts[hw_class] += 1
        name = tags.get('name') if isinstance(tags.get('name'), str) else ''
        features.append({
            'type': 'Feature',
            'id': f'osm-way-{wid}',
            'geometry': {'type': 'LineString', 'coordinates': rounded},
            'properties': {
                'osm_way_id': wid,
                'name': name,
                'highway': hw_class,
                'source': 'OSM',
            },
        })

    features.sort(key=lambda f: f['properties']['osm_way_id'])
    provenance = {
        'source': 'OpenStreetMap contributors',
        'source_file': raw_path.name,
        'source_sha256': metadata['response']['sha256'],
        'snapshot_accessed_at': metadata['accessed_at_utc'],
        'license': 'ODbL-1.0',
        'license_url': 'https://opendatacommons.org/licenses/odbl/1-0/',
        'attribution': '© OpenStreetMap contributors',
        'attribution_url': 'https://www.openstreetmap.org/copyright',
        'bbox': metadata.get('bbox', list(BBOX)),
        'highway_classes': sorted(ALLOWED_HIGHWAY_CLASSES),
        'feature_count': len(features),
        'class_counts': class_counts,
    }
    return {'type': 'FeatureCollection', 'features': features}, provenance


if __name__ == '__main__':
    count, meta = fetch_osm_roads()
    fc, prov = load_osm_roads()
    print(json.dumps({
        'raw_elements': count,
        'exported_roads': len(fc['features']),
        'class_counts': prov['class_counts'],
        'accessed_at_utc': meta['accessed_at_utc'],
    }, indent=2))
