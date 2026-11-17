"""Notebook QA — reviewer expects saved, sequentially executed M4 outputs."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class SavedNotebookTests(unittest.TestCase):
    def test_all_m4_code_cells_executed_and_no_errors(self):
        nb=json.loads((ROOT/'notebooks'/'m4_initial_insights.ipynb').read_text(encoding='utf-8'))
        code=[c for c in nb['cells'] if c['cell_type']=='code']
        self.assertEqual(len(code),7)
        self.assertEqual([c['execution_count'] for c in code],list(range(1,8)))
        self.assertTrue(all(c['outputs'] for c in code))
        self.assertFalse(any(out.get('output_type')=='error' for c in code for out in c['outputs']))
        png=sum(1 for c in code for out in c['outputs'] if 'image/png' in out.get('data',{}))
        self.assertEqual(png,4)

if __name__=='__main__':unittest.main()
