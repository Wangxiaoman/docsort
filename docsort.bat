@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM docsort Windows runner
REM Usage: docsort.bat run <file-or-dir> --config rules.yaml
REM        docsort.bat watch <dir> --config rules.yaml

if not exist ".venv\Scripts\python.exe" (
    echo Not installed yet. Run install.bat first.
    exit /b 1
)

REM Ensure UTF-8 for Chinese filenames / console output
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

.venv\Scripts\python.exe -m docsort %*
endlocal
