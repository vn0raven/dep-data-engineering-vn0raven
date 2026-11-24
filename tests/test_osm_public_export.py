import json
import hashlib
import pytest
from scripts.export_osm_public import derive, export, SOURCE


def fixture():
    return {'elements':[{'type':'relation','id':1,'tags':{'type':'route','route':'bus','name':'Test',
        'phone':'PRIVATE','operator':'EXCLUDED'},'members':[
        {'type':'way','ref':2,'geometry':[{'lon':125,'lat':7},{'lon':125.1,'lat':7.1}]},
        {'type':'way','ref':3},
        {'type':'way','ref':4,'geometry':[{'lon':999,'lat':7},{'lon':125,'lat':7}]}]},
        {'type':'relation','id':5,'tags':{'type':'route','route':'hiking'}}]}


def test_allowlist_missing_invalid_and_no_gap_repair():
    result=derive(fixture())
    assert len(result['routes.json'])==1
    assert len(result['lines.geojson']['features'])==1
    assert result['quality.json']['unavailable_line_members']==1
    assert len(result['quality.json']['rejected_line_members'])==1
    assert 'PRIVATE' not in json.dumps(result) and 'EXCLUDED' not in json.dumps(result)
    assert result['routes.json'][0]['government_classification'] is None
    assert result['lines.geojson']['features'][0]['properties']['association']=='explicit_osm_relation_membership'


def test_duplicate_and_overpass_error_fail_closed():
    data=fixture();data['elements'].append(data['elements'][0])
    with pytest.raises(ValueError,match='duplicate'):derive(data)
    with pytest.raises(ValueError,match='incomplete'):derive({'remark':'timeout','elements':[]})


def test_real_export_idempotent_and_tamper_detection(tmp_path):
    raw_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    first=export(output=tmp_path); second=export(output=tmp_path)
    assert first==second
    from pathlib import Path
    release=Path(first['path'])
    manifest=json.loads((release/'manifest.json').read_text())
    for name,sha in manifest['outputs'].items():
        assert hashlib.sha256((release/name).read_bytes()).hexdigest()==sha
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==raw_hash
    (release/'routes.json').write_text('tampered')
    with pytest.raises(ValueError,match='modified'):export(output=tmp_path)


def test_reject_non_osm_input(tmp_path):
    with pytest.raises(ValueError,match='Only project OSM'):export(tmp_path/'government.json',tmp_path/'out')
