import hashlib
from pathlib import Path
import sys
import unittest
import tempfile
import geopandas as gpd
from shapely.geometry import LineString, Polygon
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.m5_delivery import diagnostics, numeric
from scripts.validate_ltfrb_gis import audit_file, comparison_rows

class DeliveryTests(unittest.TestCase):
    def test_missing_evidence_does_not_become_zero_percent_validity(self):
        q=diagnostics([dict(file_id='x',route_no='1',mode='PUJ',route_name='test',route_classification='EXISTING')],[],[],[])
        self.assertIsNone(next(r for r in q if r['kpi']=='clean_geometry_crs')['value_pct'])
        self.assertEqual(next(r for r in q if r['kpi']=='navigation_readiness')['status'],'not_verified')

    def test_invalid_numeric_lengths(self):
        for value in ['n/a','NaN','inf','-4','0']:self.assertFalse(numeric(value))

    def test_crs_mismatch_and_unknown_identity_prevent_length_claim(self):
        r=dict(route_no='1',route_name='x',mode='PUJ',route_classification='EXISTING',file_id='x',direction_1='Northbound',length_km_1='4',direction_2='',length_km_2='')
        layer=dict(layer_name='northbound',feature_count=1,geodesic_line_km=4,invalid_geometry=0,null_geometry=0,empty_geometry=0,crs_present=True,crs_metadata_consistent=False,error='')
        self.assertIsNone(comparison_rows([r],{'x':[layer]})[0]['measured_length_km'])
        layer.update(layer_name='unlabelled',crs_metadata_consistent=True)
        r['direction_1']='Unspecified'
        self.assertIsNone(comparison_rows([r],{'x':[layer]})[0]['measured_length_km'])

    def test_invalid_geometry_detected_and_source_bytes_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'invalid.gpkg'
            gpd.GeoDataFrame(geometry=[Polygon([(125,7),(126,8),(125,8),(126,7),(125,7)])],crs=4326).to_file(path,layer='invalid',driver='GPKG')
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            report,layers,_=audit_file(path,'test')
            self.assertEqual(layers[0]['invalid_geometry'],1)
            self.assertEqual(report['layers_with_valid_geometries'],0)
            self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())

    def test_committed_aggregate_reconciliations(self):
        import pandas as pd
        p=ROOT/'data/processed/m5'
        if not p.exists():self.skipTest('Aggregate outputs not generated yet')
        seg=pd.read_csv(p/'segmentation.csv')
        for dim in ['mode','route_classification','mode x route_classification','mode x route_classification x GIS status','mode x direction state','mode x metadata state']:
            self.assertEqual(int(seg[seg.dimension==dim]['count'].sum()),285)
        history=pd.read_csv(p/'kpi_history.csv')
        self.assertEqual(history.snapshot_date.nunique(),2)
        self.assertEqual(history.kpi.nunique(),5)
        self.assertTrue((history.numerator<=history.denominator).all())
        self.assertTrue(((history.value_pct-history.numerator/history.denominator*100).abs()<0.011).all())

if __name__=='__main__':unittest.main()
