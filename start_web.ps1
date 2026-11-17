$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = 'D:\uniproject\data_mining\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Project Python environment missing: D:\uniproject\data_mining\.venv' }
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $projectRoot
Write-Host 'Shanxu Web: http://127.0.0.1:8767/  (Ctrl+C to stop)'
& $pythonPath (Join-Path $projectRoot 'src\lab7\web_server.py')
