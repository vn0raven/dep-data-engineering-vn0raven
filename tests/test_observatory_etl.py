"""Synthetic data contracts and end-to-end immutable-release tests."""
import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
import unittest
import zipfile

import geopandas as gpd
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.extract_ltfrb_routes import COLS
from scripts.observatory_etl import (normalize, length_km, text, inspect_asset,
                                     inventory, build, verify_release)


def record(**kwargs):
    r = dict(zip(COLS, ['1','11','PUJ','Test route','EXISTING','Intra-City',
                       'Test corridor','Davao City','Loop Route (One Direction Only)','3.5',
                       'n/a','n/a','n/a','n/a','https://drive.google.com/file/d/TEST/view']))
    r.update(file_id='TEST',excel_row=3,source_workbook_sha256='a'*64)
    r.update(kwargs)
    return r


def workbook(path, records):
    from xml.sax.saxutils import escape
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="SUMMARY" sheetId="1" r:id="r1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        rows=[]
        for i,r in enumerate(records,3):
            cells=''.join(f'<c r="{chr(65+j)}{i}" t="inlineStr"><is><t>{escape(str(r[c]))}</t></is></c>' for j,c in enumerate(COLS))
            rows.append(f'<row r="{i}">{cells}</row>')
        z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{ns}"><sheetData>'+''.join(rows)+'</sheetData></worksheet>')


class NormalizationTests(unittest.TestCase):
    def test_values_are_cleaned_without_erasing_source_evidence(self):
        raw=record(route_name='  Jade\u00a0Valley\u2013Buhangin  ', mode='UVE',length_km_1='3.1690999999999998')
        n=normalize([raw])
        self.assertEqual(n['routes'][0]['route_name'],'Jade Valley-Buhangin')
        self.assertEqual(n['routes'][0]['mode'],'UV_EXPRESS')
        self.assertEqual(n['directions'][0]['declared_km'],3.1691)
        self.assertEqual(json.loads(n['routes'][0]['original_record_json']),raw)
        self.assertEqual(n['directions'][1]['metadata_status'],'not_applicable_loop')
        self.assertIsNone(n['route_localities'][0]['canonical_psgc'])

    def test_nonfinite_and_nonpositive_lengths_are_never_valid(self):
        for v in ['NaN','Infinity','-2','0','n/a','garbage',None]:
            self.assertIsNone(length_km(v))

    def test_duplicate_names_retained_and_conflicting_admin_labels_flagged(self):
        a=record(lgu_1='Tagum City / Municipality of Tagum / Tagum City')
        b=record(route_no='2',excel_row=4,route_name='test ROUTE')
        n=normalize([a,b]);codes={i['code'] for i in n['issues']}
        self.assertEqual(len(n['routes']),2)
        self.assertIn('duplicate_name_candidate',codes)
        self.assertIn('repeated_lgu_label',codes)
        self.assertIn('conflicting_admin_labels',codes)

    def test_route_identifier_collision_stops_release(self):
        with self.assertRaises(ValueError):normalize([record(),record()])


class SpatialTests(unittest.TestCase):
    def test_incomplete_download_never_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'TEST.partial').write_bytes(b'SQLite format 3\x00')
            result=inspect_asset('TEST',p,inventory(p))
            self.assertEqual(result['asset']['status'],'incomplete_download')
            self.assertEqual(result['features'],[])

    def test_shapefile_dependencies_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'TEST.shp').write_bytes(struct.pack('>i',9994)+b'\x00'*96)
            result=inspect_asset('TEST',p,inventory(p))
            self.assertEqual(result['asset']['status'],'incomplete_shapefile')
            self.assertIn('.prj',json.loads(result['asset']['dependencies_json'])['missing'])

    def test_projected_line_reprojects_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);file=p/'TEST.gpkg'
            original=gpd.GeoDataFrame(geometry=[LineString([(125.55,7.05),(125.57,7.08)])],crs=4326).to_crs(32651)
            original.to_file(file,driver='GPKG',layer='loop')
            before=hashlib.sha256(file.read_bytes()).hexdigest()
            result=inspect_asset('TEST',p,inventory(p));f=result['features'][0]
            self.assertEqual(f['status'],'geometry_pass')
            self.assertTrue(3.9<f['geodesic_km']<4.1)
            self.assertEqual(before,hashlib.sha256(file.read_bytes()).hexdigest())

    def test_outside_extent_is_quarantined(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            gpd.GeoDataFrame(geometry=[LineString([(0,0),(1,1)])],crs=4326).to_file(p/'TEST.gpkg',driver='GPKG',layer='loop')
            result=inspect_asset('TEST',p,inventory(p))
            self.assertEqual(result['features'][0]['status'],'quarantined')
            self.assertIsNone(result['features'][0]['geometry_json'])


class ReleaseTests(unittest.TestCase):
    def test_end_to_end_release_idempotency_incremental_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);raw=p/'raw';raw.mkdir();book=p/'source.xlsx';out=p/'processed'
            workbook(book,[record()])
            gpd.GeoDataFrame(geometry=[LineString([(125.55,7.05),(125.57,7.08)])],crs=4326).to_file(raw/'TEST.gpkg',driver='GPKG',layer='loop')
            release=build(book,raw,out)
            first=verify_release(release)
            mtimes={f.name:f.stat().st_mtime_ns for f in release.iterdir()}
            self.assertEqual(build(book,raw,out),release)
            self.assertEqual(mtimes,{f.name:f.stat().st_mtime_ns for f in release.iterdir()})
            with closing(sqlite3.connect(release/'observatory.sqlite')) as con:
                self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
                self.assertEqual(con.execute('SELECT COUNT(*) FROM routes').fetchone()[0],1)
            # New unrelated intake manifest changes the release signature; unchanged asset is cached.
            (raw/'intake.csv').write_text('status\nreceived\n')
            second=build(book,raw,out)
            self.assertNotEqual(release,second)
            self.assertEqual(json.loads((out/'last_run.json').read_text())['asset_cache_hits'],1)
            self.assertEqual(first['statistics'],verify_release(second)['statistics'] | {'local_directory_files':1})
            (release/'routes.csv').write_text('tampered')
            with self.assertRaises(ValueError):verify_release(release)

    def test_outputs_inside_raw_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);raw=p/'raw';raw.mkdir();book=p/'book.xlsx';workbook(book,[record()])
            with self.assertRaises(ValueError):build(book,raw,raw/'derived')


if __name__=='__main__':unittest.main()
