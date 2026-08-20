$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvPythonw = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$Launcher = Join-Path $ProjectRoot "windows\launcher.pyw"

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "当前脚本只支持 Windows 11。"
}

function Test-Python312 {
    param([Parameter(Mandatory = $true)][string]$Executable)
    & $Executable -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
    return $LASTEXITCODE -eq 0
}

if (-not (Test-Path -LiteralPath $VenvPython) -or -not (Test-Python312 -Executable $VenvPython)) {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $PyLauncher) {
        & py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
        if ($LASTEXITCODE -ne 0) {
            throw "需要 Python 3.12 或更新版本。"
        }
        & py -3 -m venv (Join-Path $ProjectRoot ".venv")
    }
    else {
        $Python = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $Python) {
            throw "需要 Python 3.12 或更新版本。请先从 python.org 安装。"
        }
        $PythonExecutable = $Python.Source
        if (-not (Test-Python312 -Executable $PythonExecutable)) {
            throw "需要 Python 3.12 或更新版本。请先从 python.org 安装。"
        }
        & $PythonExecutable -m venv (Join-Path $ProjectRoot ".venv")
    }
}

Write-Host "正在安装依赖..."
& $VenvPython -m pip install -e $ProjectRoot

Write-Host "正在启动 AI Translate..."
Start-Process -FilePath $VenvPythonw -ArgumentList @("`"$Launcher`"") -WorkingDirectory $ProjectRoot
Write-Host "AI Translate 已启动。设置保存在 %APPDATA%\AI Translate\.env。"
