"""Inspect the explicit M5 commit candidate list and the real Git index; never stage."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PRIVATE_PREFIXES=('data/raw/ltfrb/','data/staging/ltfrb/','data/processed/ltfrb/',
                  'data/processed/ltfrb_observatory/','reports/ltfrb/','reports/observatory-private/')
PRIVATE_EXTENSIONS={'.gpkg','.geojson','.shp','.shx','.dbf','.prj','.xlsx','.docx','.pdf','.zip','.sqlite','.partial'}


def inspect(paths):
    violations=[]
    for name in paths:
        normalized=name.replace('\\','/')
        p=ROOT/normalized
        if normalized.startswith(PRIVATE_PREFIXES) or p.suffix.lower() in PRIVATE_EXTENSIONS:
            violations.append(dict(path=normalized,reason='private path or detailed-source format'))
            continue
        if not p.is_file():
            violations.append(dict(path=normalized,reason='listed file missing'))
            continue
        if p.suffix.lower() in {'.md','.txt','.csv','.json','.html','.ipynb','.py','.yml','.ps1'}:
            body=p.read_text(encoding='utf-8')
            if re.search(r'https?://drive\.google\.com/file/d/[A-Za-z0-9_-]{20,}',body):
                violations.append(dict(path=normalized,reason='government source Drive URL'))
            # Long source identifiers are excluded even when URL prefixes were removed.
            if re.search(r'\b1[A-Za-z0-9_-]{25,45}\b',body) and p.suffix.lower() not in {'.py','.ipynb'}:
                # Hashes are legitimate provenance; scan structured source-ID contexts only.
                if re.search(r'\b(?:ID|IDs|file_id)\s*[:=]?\s*1[A-Za-z0-9_-]{25,45}',body):
                    violations.append(dict(path=normalized,reason='source identifier detail'))
            if p.suffix.lower() in {'.csv','.json'} and normalized.startswith(('data/processed/m5/','dashboard/m5_data/')):
                for token in ('source_geometry_wkb_hex','geometry_json','"route_id"','"source_fid"','"source_url"','"coordinates"'):
                    if token in body:violations.append(dict(path=normalized,reason='row-level or geometry token: '+token))
    return violations


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--files',type=Path,default=ROOT/'reports/m5/PUBLIC_FILES.txt')
    p.add_argument('--report',type=Path,default=ROOT/'reports/m5/PRIVACY_REVIEW.json')
    a=p.parse_args()
    candidates=[x.strip() for x in a.files.read_text().splitlines() if x.strip()]
    staged=subprocess.check_output(['git','diff','--cached','--name-only','--diff-filter=ACMR'],cwd=ROOT,text=True).splitlines()
    violations=inspect(sorted(set(candidates+staged)))
    # Every private directory must still be ignored by Git.
    ignored=[]
    for prefix in PRIVATE_PREFIXES:
        result=subprocess.run(['git','check-ignore','--quiet',prefix+'privacy-probe.json'],cwd=ROOT)
        ignored.append(dict(prefix=prefix,ignored=result.returncode==0))
        if result.returncode:violations.append(dict(path=prefix,reason='private prefix not ignored'))
    report=dict(status='passed' if not violations else 'failed',candidate_files=len(candidates),
                staged_files=len(staged),index_modified=False,ignored_prefixes=ignored,violations=violations,
                limitation='Automated checks support human review; passing is not publication authorization or licensing approval.')
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return bool(violations)


if __name__=='__main__':sys.exit(main())
