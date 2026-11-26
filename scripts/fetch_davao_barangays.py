"""Fetch and load Davao City barangay boundaries (CC-BY-IGO, faeldon/philippines-json-maps)."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import requests
from shapely.geometry import shape, mapping

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / 'data/raw/davao_barangays_cod_ab.geojson'
META_PATH = ROOT / 'data/raw/davao_barangays_cod_ab.metadata.json'
DAVAO_LOWRES_URL = (
    'https://raw.githubusercontent.com/faeldon/philippines-json-maps/master/'
    'latest/geojson/municities/lowres/bgysubmuns-municity-1130700000.0.001.json'
)
ALLOWED_BARANGAY_KEYS = {'psgc', 'name', 'municipality', 'source'}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _round_ring(ring):
    return [[round(float(x), 5), round(float(y), 5)] for x, y in ring]


def _round_geom(geom_dict):
    gtype = geom_dict.get('type')
    coords = geom_dict.get('coordinates')
    if gtype == 'Polygon':
        return {'type': 'Polygon', 'coordinates': [_round_ring(r) for r in coords]}
    if gtype == 'MultiPolygon':
        return {'type': 'MultiPolygon', 'coordinates': [[_round_ring(r) for r in poly] for poly in coords]}
    raise ValueError(f'Unsupported barangay geometry type: {gtype}')


def _find_davao_file_url():
    return DAVAO_LOWRES_URL, 'bgysubmuns-municity-1130700000.0.001.json'


def fetch_davao_barangays(raw_path: Path = RAW_PATH, meta_path: Path = META_PATH):
    """Download Davao City barangay boundaries from faeldon/philippines-json-maps."""
    download_url, filename = _find_davao_file_url()
    resp = requests.get(download_url, timeout=60)
    resp.raise_for_status()
    text = resp.text.replace('\r\n', '\n')
    data = json.loads(text)
    if data.get('type') != 'FeatureCollection' or not data.get('features'):
        raise ValueError(f'Unexpected GeoJSON content from {download_url}')
    raw_bytes = text.encode('utf-8')
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw_bytes)
    accessed_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    metadata = {
        'source_name': 'NAMRIA and PSA via OCHA COD-AB (faeldon/philippines-json-maps)',
        'source_file_remote': filename,
        'source_url': download_url,
        'accessed_at_utc': accessed_at,
        'license': 'CC-BY-IGO',
        'license_url': 'https://creativecommons.org/licenses/by/3.0/igo/',
        'attribution': 'NAMRIA and PSA via OCHA COD-AB (faeldon/philippines-json-maps)',
        'attribution_url': 'https://github.com/faeldon/philippines-json-maps',
        'response': {'sha256': _digest(raw_bytes), 'bytes': len(raw_bytes)},
    }
    meta_bytes = (json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    meta_path.write_bytes(meta_bytes)
    return len(data['features']), metadata


def load_davao_barangays(raw_path: Path = RAW_PATH):
    """Verify raw barangay GeoJSON checksum and return allowlisted FeatureCollection + provenance."""
    raw_path = Path(raw_path)
    meta_path = raw_path.with_suffix('.metadata.json')
    if not raw_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f'Missing Davao barangays GeoJSON or metadata: {raw_path}')
    raw_bytes = raw_path.read_bytes().replace(b'\r\n', b'\n')
    metadata = json.loads(meta_path.read_text(encoding='utf-8'))
    if metadata.get('license') != 'CC-BY-IGO' or 'NAMRIA' not in metadata.get('source_name', ''):
        raise ValueError('Barangay boundary metadata license or source mismatch')
    if metadata.get('response', {}).get('sha256') != _digest(raw_bytes):
        raise ValueError('Barangay boundary raw snapshot SHA-256 mismatch')

    raw_fc = json.loads(raw_bytes.decode('utf-8'))
    features = []
    seen_psgc = set()
    for idx, feat in enumerate(raw_fc.get('features', []), 1):
        props = feat.get('properties') or {}
        psgc = str(
            props.get('adm4_psgc')
            or props.get('ADM4_PCODE')
            or props.get('psgc')
            or props.get('PSGC')
            or f'davao-brgy-{idx:03}'
        )
        name = str(
            props.get('adm4_en')
            or props.get('ADM4_EN')
            or props.get('name')
            or props.get('NAME')
            or props.get('brgy_name')
            or f'Barangay {idx}'
        ).strip()
        geom = shape(feat['geometry'])
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty or geom.geom_type not in {'Polygon', 'MultiPolygon'}:
            continue
        rounded_geom = _round_geom(mapping(geom))
        if psgc in seen_psgc:
            psgc = f'{psgc}-{idx}'
        seen_psgc.add(psgc)
        features.append({
            'type': 'Feature',
            'id': f'brgy-{psgc}',
            'geometry': rounded_geom,
            'properties': {
                'psgc': psgc,
                'name': name,
                'municipality': 'City of Davao',
                'source': 'NAMRIA_PSA_COD_AB',
            },
        })

    features.sort(key=lambda f: (f['properties']['name'], f['properties']['psgc']))
    provenance = {
        'source': 'NAMRIA and PSA via OCHA COD-AB (faeldon/philippines-json-maps)',
        'source_file': raw_path.name,
        'source_url': metadata.get('source_url', ''),
        'source_sha256': metadata['response']['sha256'],
        'snapshot_accessed_at': metadata['accessed_at_utc'],
        'license': 'CC-BY-IGO',
        'license_url': 'https://creativecommons.org/licenses/by/3.0/igo/',
        'attribution': 'NAMRIA and PSA via OCHA COD-AB (faeldon/philippines-json-maps)',
        'attribution_url': 'https://github.com/faeldon/philippines-json-maps',
        'feature_count': len(features),
    }
    return {'type': 'FeatureCollection', 'features': features}, provenance


if __name__ == '__main__':
    count, meta = fetch_davao_barangays()
    fc, prov = load_davao_barangays()
    print(json.dumps({
        'raw_features': count,
        'exported_barangays': len(fc['features']),
        'source_url': meta['source_url'],
        'accessed_at_utc': meta['accessed_at_utc'],
    }, indent=2))
