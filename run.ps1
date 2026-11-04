param(
    [ValidateSet('1', '2', '4', '5', 'all')]
    [string]$Lab = '4'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = 'D:\uniproject\data_mining\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Project Python environment missing.' }
$labScripts = @{
    '1' = @('src\lab1\preprocess.py')
    '2' = @('src\lab2\entities.py', 'src\lab2\check.py')
    '4' = @('src\lab4\coref.py', 'src\lab4\figures.py')
    '5' = @('src\lab5\extract.py', 'src\lab5\finalize.py', 'src\lab5\figures.py', 'src\lab5\check.py')
}
$selectedLabs = if ($Lab -eq 'all') { @('1', '2', '4', '5') } else { @($Lab) }
foreach ($labNumber in $selectedLabs) {
    Write-Host "Running lab $labNumber"
    foreach ($scriptPath in $labScripts[$labNumber]) {
        & $pythonPath (Join-Path $PSScriptRoot $scriptPath)
        if ($LASTEXITCODE -ne 0) { throw "Lab $labNumber failed: $scriptPath" }
    }
}
