import copy
import json
from pathlib import Path
import pytest
from scripts import build_observatory_layers as layers
from scripts.check_observatory_public import check


def test_osm_package_reproducible_and_schema(tmp_path,monkeypatch):
    monkeypatch.setattr(layers,'WEB',tmp_path)
    # Bundle builds do not need frontend files. The gate checks these four separately.
    for name in ['app.js','explorer.js','index.html','style.css']:(tmp_path/name).write_text('test')
    bundle,path=layers.build()
    hashes={p.name:p.read_bytes() for p in path.iterdir()}
    again,other=layers.build()
    assert bundle==again and path==other and hashes=={p.name:p.read_bytes() for p in path.iterdir()}
    assert check(tmp_path)['routes']==14
    assert bundle['display']['display_vertices']<bundle['display']['original_vertices']
    bad=copy.deepcopy(bundle);bad['routes'][0]['private_note']='do not publish'
    with pytest.raises(ValueError,match='allowlist'):layers.validate(bad)
    (tmp_path/'extra.sqlite').write_text('private')
    with pytest.raises(ValueError,match='Unexpected'):check(tmp_path)
    (tmp_path/'extra.sqlite').unlink()
    (path/'bundle.json').write_text('{}')
    with pytest.raises(ValueError,match='Checksum'):check(tmp_path)


def test_proposal_boundary_and_missing_geometry(tmp_path,monkeypatch):
    if not (layers.ROOT/'data/processed/ltfrb_observatory/latest.json').exists():pytest.skip('private release unavailable')
    monkeypatch.setattr(layers,'PRIVATE',tmp_path)
    bundle,path=layers.build(proposal=True)
    government=[r for r in bundle['routes'] if r['source']=='LTFRB']
    assert len(government)==285
    mapped={rid for f in bundle['features'] for rid in f['properties']['route_ids']}
    assert any(r['route_id'] not in mapped for r in government)
    assert all(f['properties']['association']=='candidate_direction_match' for f in bundle['features'] if f['properties']['source']=='LTFRB')
    with pytest.raises(ValueError,match='blocked|Unexpected'):check(tmp_path)
    bad=copy.deepcopy(bundle);bad['publication']='osm_public'
    with pytest.raises(ValueError,match='Government'):layers.validate(bad)
    assert (tmp_path/'REVIEW_SAMPLES.json').exists()

def test_exact_publication_authorization(tmp_path):
    import shutil
    root=layers.ROOT/'dashboard/observatory'
    if not (root/'publication-approval.json').exists():pytest.skip('No approved mixed release in this checkout')
    shutil.copytree(root,tmp_path,dirs_exist_ok=True)
    assert check(tmp_path)['routes']==299
    approval=tmp_path/'publication-approval.json'
    original=approval.read_text()
    approval.unlink()
    with pytest.raises(ValueError,match='blocked'):check(tmp_path)
    payload=json.loads(original);payload['release_version']='0'*20
    approval.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='exact release'):check(tmp_path)
