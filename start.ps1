# StudyFlow PowerShell 启动脚本
# 用法： powershell -ExecutionPolicy Bypass -File .\start.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "  StudyFlow - AI 学习管理平台" -ForegroundColor Cyan
Write-Host "  -----------------------------------------"
Write-Host ""

$candidates = @()
if (Test-Path ".\.venv\Scripts\python.exe") {
  $candidates += @{ Command = ".\.venv\Scripts\python.exe"; Args = @() }
}
$candidates += @{ Command = "py"; Args = @("-3") }
$candidates += @{ Command = "python"; Args = @() }

$python = $null
foreach ($candidate in $candidates) {
  $executable = Get-Command $candidate.Command -ErrorAction SilentlyContinue
  if (-not $executable) { continue }
  try {
    & $candidate.Command @($candidate.Args + @("-c", "import flask")) 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
      $python = $candidate
      break
    }
  } catch {
    continue
  }
}

if (-not $python) {
  Write-Host "[错误] 没有找到已安装 Flask 的 Python 环境。" -ForegroundColor Red
  Write-Host "请先创建虚拟环境并安装依赖："
  Write-Host "  python -m venv .venv"
  Write-Host "  .\.venv\Scripts\Activate.ps1"
  Write-Host "  pip install -r requirements.txt"
  Write-Host "详细步骤见 README.md。"
  exit 1
}

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
  Copy-Item ".env.example" ".env"
  Write-Host "[StudyFlow] 已根据 .env.example 创建 .env。" -ForegroundColor Yellow
}

Write-Host "[StudyFlow] 正在启动 http://127.0.0.1:5000 ..." -ForegroundColor Green
Write-Host "[StudyFlow] 按 Ctrl+C 停止服务。"
Write-Host ""
& $python.Command @($python.Args + @("run.py"))
