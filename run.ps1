$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = 'D:\miniconda3\envs\dm_scenic_lab\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw '请先按README.md在D盘Miniconda中创建dm_scenic_lab独立环境。'
}
& $pythonPath (Join-Path $PSScriptRoot 'src\run_lab1.py')
if ($LASTEXITCODE -ne 0) { throw '实验执行失败，请查看错误信息。' }
