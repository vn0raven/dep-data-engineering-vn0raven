import json
from html.parser import HTMLParser
from pathlib import Path
import unittest
from urllib.parse import unquote, urlsplit
ROOT=Path(__file__).resolve().parents[1]

class Links(HTMLParser):
    def __init__(self):super().__init__();self.targets=[]
    def handle_starttag(self,tag,attrs):
        self.targets.extend(v for k,v in attrs if k in ('href','src'))

class ArtifactTests(unittest.TestCase):
    def test_dashboard_local_assets_exist(self):
        path=ROOT/'dashboard/m5.html'
        parser=Links();parser.feed(path.read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(parser.targets),10)
        for target in parser.targets:
            if not urlsplit(target).scheme:
                self.assertTrue((path.parent/unquote(target.split('#')[0])).is_file(),target)

    def test_notebook_saved_outputs_and_no_errors(self):
        nb=json.loads((ROOT/'notebooks/m5_segmentation_kpis.ipynb').read_text(encoding='utf-8'))
        code=[c for c in nb['cells'] if c['cell_type']=='code']
        self.assertGreaterEqual(len(code),6)
        self.assertTrue(all(c['execution_count'] is not None for c in code))
        self.assertTrue(any(c.get('outputs') for c in code))
        self.assertFalse(any(o['output_type']=='error' for c in code for o in c.get('outputs',[])))

    def test_public_aggregates_exclude_private_paths_and_urls(self):
        for folder in ('data/processed/m5','dashboard/m5_data'):
            for path in (ROOT/folder).iterdir():
                if path.is_file():
                    body=path.read_text(encoding='utf-8')
                    self.assertNotIn('drive.google.com/file/d/',body)
                    self.assertNotIn('C:\\Users\\',body)

if __name__=='__main__':unittest.main()
