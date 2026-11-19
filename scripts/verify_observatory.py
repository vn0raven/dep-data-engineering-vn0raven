"""Read-only release verification: hashes, relational integrity and spatial parity."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import geopandas as gpd
from shapely.geometry import shape

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.observatory_etl import verify_release, GEOD, write_json


def verify(folder):
    folder=Path(folder)
    manifest=verify_release(folder)
    with closing(sqlite3.connect((folder/'observatory.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert con.execute('PRAGMA foreign_key_check').fetchall()==[]
        for table in ['routes','directions','route_localities','assets','layers','features','associations','transformations','issues']:
            records=json.loads((folder/(table+'.json')).read_text(encoding='utf-8'))
            assert con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]==len(records), table
        assert con.execute("SELECT COUNT(*) FROM associations WHERE association_status='candidate' AND feature_id IS NULL").fetchone()[0]==0
        assert con.execute("SELECT COUNT(*) FROM features WHERE status='quarantined' AND geometry_json IS NOT NULL").fetchone()[0]==0
        assert con.execute("SELECT COUNT(*) FROM routes WHERE navigation_status!='not_verified'").fetchone()[0]==0
    features=json.loads((folder/'features.json').read_text(encoding='utf-8'))
    passing={f['feature_id']:f for f in features if f['status']=='geometry_pass'}
    geojson=json.loads((folder/'geometry_pass.geojson').read_text(encoding='utf-8'))
    assert len(geojson['features'])==len(passing)
    checked=0
    if passing:
        gpkg=gpd.read_file(folder/'geometry_pass.gpkg',engine='pyogrio').set_index('feature_id')
        assert gpkg.crs.to_epsg()==4326 and len(gpkg)==len(passing)
        for f in geojson['features']:
            key=f['properties']['feature_id'];geom=shape(f['geometry'])
            assert geom.is_valid and not geom.is_empty
            assert geom.equals_exact(gpkg.loc[key].geometry,1e-10)
            assert abs(abs(GEOD.geometry_length(geom))/1000-passing[key]['geodesic_km'])<0.000001
            checked+=1
    return dict(version=manifest['version'],checksummed_outputs=len(manifest['outputs']),
                sqlite_integrity='ok',foreign_key_violations=0,geometry_roundtrip_features=checked,
                status='passed',statistics=manifest['statistics'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT/'data/processed/ltfrb_observatory')
    p.add_argument('--release',type=Path)
    p.add_argument('--report',type=Path)
    a=p.parse_args()
    folder=a.release or a.root/json.loads((a.root/'latest.json').read_text())['release']
    result=verify(folder)
    if a.report:write_json(a.report,result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
