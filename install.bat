@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM ============================================
REM docsort Windows install script
REM Usage: install.bat [mirror]
REM   mirror - use Tsinghua PyPI mirror (recommended in China)
REM ============================================

set "PY="
for %%P in (python py python3) do (
    if not defined PY (
        %%P --version >nul 2>&1 && set "PY=%%P"
    )
)
if not defined PY (
    echo [ERROR] Python not found. Install Python 3.9-3.13 from python.org
    echo         and CHECK "Add python.exe to PATH" during setup.
    exit /b 1
)

%PY% -c "import sys; v=sys.version_info; sys.exit(0 if v>=(3,9) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.9+ required. Current:
    %PY% --version
    exit /b 1
)
for /f "tokens=2" %%V in ('%PY% --version 2^>^&1') do set PYVER=%%V
echo ==^> Python %PYVER% OK

echo ==^> Creating virtual environment .venv
if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        exit /b 1
    )
)

set "VPY=.venv\Scripts\python.exe"

echo ==^> Upgrading pip
"%VPY%" -m pip install --upgrade pip -q

set "MIRROR="
if "%~1"=="mirror" set "MIRROR=-i https://pypi.tuna.tsinghua.edu.cn/simple"
echo ==^> Installing dependencies ^(rapidocr ~60MB, needs network^)
%VPY% -m pip install -r requirements.txt %MIRROR%
if errorlevel 1 (
    echo [ERROR] pip install failed. Check network or retry with: install.bat mirror
    exit /b 1
)

echo ==^> Verifying base dependencies
"%VPY%" -c "import fitz, cv2, yaml, numpy; print('  base deps OK (PyMuPDF/OpenCV/PyYAML)')"
if errorlevel 1 exit /b 1

echo ==^> Verifying OCR backends
"%VPY%" -c "import rapidocr_onnxruntime; print('  rapidocr OK')" 2>nul
"%VPY%" -c "import paddleocr; print('  paddle OK')" 2>nul
"%VPY%" -c "import yaml; b=(yaml.safe_load(open('rules.yaml',encoding='utf-8')).get('ocr') or {}).get('backend','paddle') if __import__('os').path.exists('rules.yaml') else None; print('  rules.yaml backend:', b) if b else print('  [hint] no rules.yaml yet')"
"%VPY%" -m docsort --help >nul 2>&1 && echo   docsort command OK

echo.
echo Install finished. Usage:
if exist rules.yaml (
    echo   rules.yaml found. Test OCR backend: .venv\Scripts\python tests\ocr_probe.py
) else (
    echo   Create config first: copy rules.example.yaml rules.yaml
)
echo   docsort.bat run ^<file-or-dir^> --config rules.yaml
echo   docsort.bat watch ^<dir^> --config rules.yaml
endlocal
