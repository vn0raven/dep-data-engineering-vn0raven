"""Offline synthetic tests; no government data or network calls required."""
import csv
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.extract_ltfrb_routes import extract, OUTPUT_COLS
from scripts.validate_ltfrb_gis import (audit_file,comparison_rows,numerical,classify_direction)
from scripts.m5_path_b import analyze


class ExtractionTests(unittest.TestCase):
    def test_extract_summary_from_minimal_xlsx(self):
        ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        rel='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'example.xlsx'
            with zipfile.ZipFile(p,'w') as out:
                out.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="SUMMARY" sheetId="1" r:id="rId1"/></sheets></workbook>')
                out.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
                out.writestr('xl/sharedStrings.xml',f'<sst xmlns="{ns}"><si><t>PUJ</t></si><si><t>Test Route</t></si><si><t>EXISTING</t></si></sst>')
                out.writestr('xl/worksheets/sheet1.xml',f'''<worksheet xmlns="{ns}"><sheetData><row r="3"><c r="A3"><v>1</v></c><c r="C3" t="s"><v>0</v></c><c r="D3" t="s"><v>1</v></c><c r="E3" t="s"><v>2</v></c><c r="I3" t="inlineStr"><is><t>Northbound</t></is></c><c r="J3"><v>1.5</v></c><c r="O3" t="inlineStr"><is><t>https://drive.google.com/file/d/1testing_ABC123/view</t></is></c></row></sheetData></worksheet>''')
            rows=extract(p)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['route_name'],'Test Route')
            self.assertEqual(rows[0]['file_id'],'1testing_ABC123')
            self.assertEqual(rows[0]['length_km_1'],'1.5')
            self.assertEqual(rows[0]['excel_row'],3)


class GISValidationTests(unittest.TestCase):
    def test_bad_sqlite_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            bad=Path(t)/'BAD.gpkg';bad.write_bytes(b'not a valid gpkg')
            result, layers, _ = audit_file(bad, 'BAD')
            self.assertIn(result['file_status'], ('invalid_or_empty_file','invalid_format'))
            self.assertEqual(layers, [])

    def test_directional_matching_is_conservative(self):
        record={'route_no':'1','route_name':'Synthetic','mode':'PUJ','route_classification':'EXISTING',
                'file_id':'TEST','direction_1':'Northbound','length_km_1':'4',
                'direction_2':'Southbound','length_km_2':'4.1'}
        good={'layer_name':'northbound','feature_count':1,'geodesic_line_km':4.05,
              'invalid_geometry':0,'null_geometry':0,'empty_geometry':0,'crs_present':True,
              'crs_metadata_consistent':True,'error':''}
        cmp=comparison_rows([record],{'TEST':[good]})
        self.assertEqual(cmp[0]['match_confidence'],'direction_label_candidate')
        self.assertEqual(cmp[0]['threshold_result'],'within_screening_tolerance')
        self.assertEqual(cmp[1]['threshold_result'],'not_evaluated')
        # An ambiguous shared Drive ID must not create a distance claim.
        cmp=comparison_rows([record,dict(record,route_no='2')],{'TEST':[good]})
        self.assertTrue(all(r['measured_length_km'] is None for r in cmp))

    def test_valid_geopackage_and_geodesic_distance(self):
        try:
            import geopandas as gpd
            from shapely.geometry import LineString
        except ImportError:self.skipTest('optional geopandas and shapely unavailable')
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'TEST.gpkg'
            gpd.GeoDataFrame({'label':['route']},geometry=[LineString([(125.55,7.05),(125.57,7.08)])],crs='EPSG:4326').to_file(path,driver='GPKG',layer='northbound')
            result,layers,_=audit_file(path,'TEST')
            self.assertEqual(result['sqlite_integrity'],'ok')
            self.assertEqual(result['file_status'],'audited')
            self.assertEqual(len(layers),1)
            self.assertEqual(layers[0]['feature_count'],1)
            self.assertTrue(layers[0]['crs_metadata_consistent'])
            self.assertTrue(3.9 < layers[0]['geodesic_line_km'] < 4.1)


class KPIUnitTests(unittest.TestCase):
    def test_missing_gis_is_unverified_not_navigation_ready(self):
        register=[{'mode':'PUJ','route_classification':'EXISTING','lptrp_classification':'Intra-City',
                    'file_id':'ABC','direction_1':'Loop Route','length_km_1':'3.5',
                    'direction_2':'n/a','length_km_2':'n/a'}]
        k=analyze(register,[],[],[],{'routes':14,'stops':122,'route_stop_occurrences':37})
        self.assertEqual(k['one_direction_loop_rows'],1)
        self.assertEqual(k['audit_file_ids_readable'],0)
        self.assertFalse(k['gis_evidence_present'])
        self.assertIsNone(k['navigation_eligible_routes'])
        self.assertIn('NOT PERFORMED',k['cross_source_matching'])

if __name__=='__main__':unittest.main()
