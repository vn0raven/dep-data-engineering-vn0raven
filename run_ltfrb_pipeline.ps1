param(
    [Parameter(Mandatory=$true)][string]$Workbook,
    [Parameter(Mandatory=$true)][string]$GeoPackageDir
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe scripts/run_m5.py --workbook $Workbook --gis-dir $GeoPackageDir --execute-notebook
if ($LASTEXITCODE -ne 0) { throw 'M5 pipeline failed' }
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'M5 tests failed' }
