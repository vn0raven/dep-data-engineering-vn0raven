"""Submission consistency contracts; public aggregate data only."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.m5_release import brief as render_brief
from scripts.m5_delivery import temporal


class M5SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.p=ROOT/'data/processed/m5'
        self.summary=json.loads((self.p/'cleaned_release_summary.json').read_text())

    def test_cleaned_quality_formula_and_denominators(self):
        q=pd.read_csv(self.p/'cleaned_quality_kpis.csv').set_index('kpi')
        known=q[q.status=='measured']
        self.assertTrue(((known.value_pct-100*known.numerator/known.denominator).abs()<0.011).all())
        self.assertEqual(q.loc['geometry_feature_pass','denominator'],266)
        self.assertEqual(q.loc['geometry_feature_pass','numerator'],263)
        self.assertEqual(q.loc['unresolved_populated_direction','denominator'],442)
        self.assertEqual(q.loc['unresolved_populated_direction','numerator'],324)
        self.assertTrue(pd.isna(q.loc['navigation_readiness','value_pct']))
        self.assertEqual(q.loc['navigation_readiness','status'],'not_verified')

    def test_cleaned_segments_reconcile_grains(self):
        seg=pd.read_csv(self.p/'cleaned_segmentation.csv')
        totals={'mode x association status':570,'mode x review status':285,
                'mode x classification':285,'asset status':266,'feature status':266,
                'association status':570,'route review status':285}
        for dim,total in totals.items():
            self.assertEqual(seg[seg.dimension==dim]['count'].sum(),total)
            self.assertTrue((seg[seg.dimension==dim].denominator==total).all())

    def test_two_actual_osm_observations_recompute(self):
        existing=pd.read_csv(self.p/'kpi_history.csv')
        computed=pd.DataFrame(temporal())
        columns=['snapshot_date','kpi','numerator','denominator','value_pct']
        pd.testing.assert_frame_equal(existing[columns],computed[columns],check_dtype=False)

    def test_primary_and_cleaned_definitions_and_mirrors(self):
        primary=json.loads((self.p/'kpi_definitions.json').read_text())
        self.assertEqual(len(primary),5)
        for k in primary:
            for f in ['numerator','denominator','formula','decision','target','limitations']:
                self.assertTrue(k[f])
        for f in self.p.iterdir():
            if f.is_file():
                self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(),hashlib.sha256((ROOT/'dashboard/m5_data'/f.name).read_bytes()).hexdigest())

    def test_brief_matches_generated_cleaned_evidence(self):
        brief=(ROOT/'reports/m5/M5_STAKEHOLDER_BRIEF.md').read_text(encoding='utf-8')
        self.assertEqual(render_brief(self.summary),brief)
        self.assertIn('About 73% of the route directions',brief)
        self.assertLessEqual(len(brief.split()),500)
        n=json.loads((ROOT/'notebooks/m5_segmentation_kpis.ipynb').read_text(encoding='utf-8'))
        displayed=[o.get('data', {}).get('text/markdown', [])
                   for c in n['cells'] for o in c.get('outputs', [])]
        self.assertIn(brief.strip(), [''.join(output).strip() for output in displayed])
        markdown='\n'.join(''.join(c['source']) for c in n['cells'] if c['cell_type']=='markdown')
        self.assertIn('Davao Transport Data Observatory',markdown)
        self.assertNotIn(chr(65533),markdown)

    def test_no_private_detail_in_projected_baseline(self):
        for path in self.p.glob('cleaned*'):
            text=path.read_text()
            for prohibited in ['drive.google.com','source_geometry_wkb','geometry_json','route_id','direction_id','source_fid','source_url']:
                self.assertNotIn(prohibited,text,path.name)


if __name__=='__main__':unittest.main()
