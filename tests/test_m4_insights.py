"""Repeatable offline tests for M4 interpretation and artifact generation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.m4_insights import load_data, summarise, run


class Milestone4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = ROOT / 'data' / 'processed'
        cls.stops, cls.routes, cls.rs = load_data(cls.base)
        cls.m = summarise(cls.stops, cls.routes, cls.rs)

    def test_expected_m3_snapshot_counts(self):
        self.assertEqual(self.m['routes'], 14)
        self.assertEqual(self.m['stops'], 122)
        self.assertEqual(self.m['route_stop_occurrences'], 37)
        self.assertEqual(self.m['routes_with_ordered_stops'], 7)
        self.assertEqual(self.m['routes_without_ordered_stops'], 7)

    def test_metadata_and_shared_stops(self):
        self.assertEqual(self.m['named_stops'] + self.m['unnamed_stops'], self.m['stops'])
        self.assertEqual(self.m['geocoded_stops'] + self.m['stops_without_coordinates'], self.m['stops'])
        self.assertEqual(self.m['shared_stops'], 10)
        self.assertEqual(self.m['ordered_adjacent_pairs'], 30)

    def test_rejects_broken_foreign_key(self):
        broken = self.rs.copy()
        broken.loc[broken.index[0], 'route_id'] = 'relation:does-not-exist'
        with tempfile.TemporaryDirectory() as folder:
            location = Path(folder)
            for name in ('stops.csv','routes.csv'):
                (location / name).write_bytes((self.base / name).read_bytes())
            broken.to_csv(location / 'route_stops.csv', index=False)
            with self.assertRaisesRegex(ValueError, 'unknown route'):
                load_data(location)

    def test_reproducible_outputs_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder)
            figures = dest/'output'/'figures'
            doc = dest/'docs'/'MILESTONE4_INSIGHTS.md'
            dashboard = dest/'dashboard'/'index.html'
            # Copy inputs because the build intentionally writes a computed summary.
            (dest/'data'/'processed').mkdir(parents=True)
            for name in ('stops.csv','routes.csv','route_stops.csv'):
                (dest/'data'/'processed'/name).write_bytes((self.base/name).read_bytes())
            run(dest/'data'/'processed', figures, doc, dashboard)
            self.assertEqual(len(list(figures.glob('*.png'))), 4)
            self.assertIn('Cautious inference', doc.read_text(encoding='utf-8'))
            html = dashboard.read_text(encoding='utf-8')
            self.assertIn('not verified', html.lower())
            for name in ('01_route_stop_coverage.png','02_stop_metadata_quality.png','03_stop_coordinate_spread.png','04_candidate_transfer_stops.png'):
                self.assertIn('assets/figures/' + name, html)
                self.assertTrue((dashboard.parent/'assets'/'figures'/name).exists())
            m = json.loads((dest/'data'/'processed'/'m4_insights_summary.json').read_text())
            self.assertEqual(m['routes'], 14)
            self.assertFalse(m['fare_data_available'])
            for p in figures.glob('*.png'):
                self.assertGreater(p.stat().st_size, 10000)


if __name__ == '__main__':
    unittest.main()
