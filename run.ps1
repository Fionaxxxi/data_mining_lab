param(
    [ValidateSet('1', '2', 'all')]
    [string]$Lab = '1'
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = 'D:\miniconda3\envs\dm_scenic_lab\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw '请先按README.md在D盘Miniconda中创建dm_scenic_lab独立环境。'
}
$labScripts = @{
    '1' = @('src\lab1\preprocess.py')
    '2' = @('src\lab2\entities.py', 'src\lab2\check.py')
}
$selectedLabs = if ($Lab -eq 'all') { @('1', '2') } else { @($Lab) }
foreach ($labNumber in $selectedLabs) {
    Write-Host "运行实验 $labNumber"
    foreach ($scriptPath in $labScripts[$labNumber]) {
        & $pythonPath (Join-Path $PSScriptRoot $scriptPath)
        if ($LASTEXITCODE -ne 0) { throw "实验 $labNumber 执行失败：$scriptPath" }
    }
}
