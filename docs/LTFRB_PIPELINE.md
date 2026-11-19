# Local GIS audit and M5 reproduction

Python 3.12 is the tested Windows runtime. No PowerShell environment activation is required. The pyogrio wheel supplies the GIS reader; Fiona is unnecessary.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe scripts/run_m5.py --execute-notebook
.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/m5/pytest-results.xml
```

Full local refresh (read-only source access):

```powershell
.\.venv\Scripts\python.exe scripts/run_m5.py --workbook "C:\Users\dinga\Downloads\LTFRB DATA\LTFRB DATA\REGION 11 ROUTE STRUCTURE DATABASE.xlsx" --gis-dir "C:\Users\dinga\Downloads\LTFRB DATA\LTFRB DATA\LTFRB_GeoPackages" --execute-notebook
```

Public aggregate-only rebuild needs no government files. Full refresh stages private workbook records, validates all linked source IDs, rebuilds aggregate products from actual audit evidence, recalculates two OSM observations, and optionally executes the notebook. Failures propagate as nonzero exit codes. Individual unreadable files are retained as failed records so the rest of the batch can complete. Repeated unchanged runs reuse content-addressed audit evidence and produce deterministic aggregate outputs.

Data flow: external read-only sources → data/staging/ltfrb (private) → reports/ltfrb (private detailed audit) → data/processed/m5 (aggregate release candidates) → reports/m5 and dashboard. No raw geometry is needed for the aggregate-only reproduction.

Local preview: `.\.venv\Scripts\python.exe -m http.server 8000 --directory dashboard`, then open http://localhost:8000/m5.html. This is a local preview, not a deployed M6 URL.

The notebook is in notebooks/m5_segmentation_kpis.ipynb and uses committed-candidate aggregate data. Verify the source hash and rerun full validation after any raw-file replacement. The old `m5_path_b.py` generator remains for compatibility; `run_m5.py` is the supported full delivery entry point.
