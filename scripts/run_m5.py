"""One entry point: regenerate public outputs or audit local private inputs."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def run(*args):
    subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,check=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--workbook',type=Path)
    p.add_argument('--gis-dir',type=Path)
    p.add_argument('--execute-notebook',action='store_true')
    p.add_argument('--release',type=Path,help='Integrate an existing private cleaned release without raw-source reprocessing')
    args=p.parse_args()
    if bool(args.workbook)!=bool(args.gis_dir):p.error('Supply both --workbook and --gis-dir, or neither for aggregate-only rebuild')
    if args.workbook:
        register=ROOT/'data/staging/ltfrb/route_register.csv'
        run('scripts/extract_ltfrb_routes.py','--workbook',args.workbook,'--out',register)
        run('scripts/validate_ltfrb_gis.py','--register',register,'--gis-dir',args.gis_dir,'--out',ROOT/'reports/ltfrb')
        run('scripts/observatory_etl.py','--workbook',args.workbook,'--gis-dir',args.gis_dir)
        import json
        base=ROOT/'data/processed/ltfrb_observatory'
        release=base/json.loads((base/'latest.json').read_text())['release']
        run('scripts/m5_delivery.py','--register',register,'--release',release)
    elif args.release:run('scripts/m5_delivery.py','--release',args.release)
    else:run('scripts/m5_delivery.py')
    if args.execute_notebook:
        import nbformat
        from nbclient import NotebookClient
        path=ROOT/'notebooks/m5_segmentation_kpis.ipynb'
        nb=nbformat.read(path,as_version=4)
        NotebookClient(nb,timeout=180,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
        nbformat.write(nb,path)
    print('M5 pipeline completed; no publication performed.')

if __name__=='__main__':main()
