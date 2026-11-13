param(
    [ValidateSet('1', '2', '3', '4', '5', '6', '7', 'all')]
    [string]$Lab = '4',
    [switch]$Online
)
$ErrorActionPreference = 'Stop'
if ($Online -and $Lab -ne '7') { throw '-Online is only supported with -Lab 7.' }
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONUTF8 = '1'
$env:MPLCONFIGDIR = Join-Path $PSScriptRoot 'outputs\maintenance\mplconfig'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = 'D:\miniconda3\envs\dm_scenic_lab\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Project Python environment missing.' }
$lab7Dir = [string]::Concat([char]0x5B9E, [char]0x9A8C, [char]0x4E03)
$labScripts = @{
    '1' = @('src\lab1\preprocess.py')
    '2' = @('src\lab2\entities.py', 'src\lab2\check.py')
    '3' = @('src\lab3\build_dataset.py', 'src\lab3\parse_route.py', 'src\lab3\time_hierarchy.py', 'src\lab3\compare_routes.py')
    '4' = @('src\lab4\coref.py', 'src\lab4\figures.py')
    '6' = @('src\lab6\build.py', 'src\lab6\query.py', 'src\lab6\figures.py', 'src\lab6\check.py')
    '5' = @('src\lab5\extract.py', 'src\lab5\finalize.py', 'src\lab5\figures.py', 'src\lab5\check.py')
    '7' = @("$lab7Dir\src\lab7\tests.py", "$lab7Dir\src\lab7\check.py")
}
$selectedLabs = if ($Lab -eq 'all') { @('1', '2', '3', '4', '5', '6', '7') } else { @($Lab) }
foreach ($labNumber in $selectedLabs) {
    Write-Host "Running lab $labNumber"
    foreach ($scriptPath in $labScripts[$labNumber]) {
        & $pythonPath (Join-Path $PSScriptRoot $scriptPath)
        if ($LASTEXITCODE -ne 0) { throw "Lab $labNumber failed: $scriptPath" }
    }
    if ($labNumber -eq '7' -and $Online) {
        Write-Host 'Running the 8 real-LLM scenarios serially; automatic retries are disabled.'
        & $pythonPath (Join-Path $PSScriptRoot "$lab7Dir\src\lab7\online_tests.py")
        if ($LASTEXITCODE -ne 0) { throw 'Lab 7 online scenario suite failed.' }
    }
}
