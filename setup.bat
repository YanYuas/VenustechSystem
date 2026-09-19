@echo off
rem ============================================================
rem Qimingxing System - environment setup (run ONCE, or after wiping deps)
rem
rem Replaces the old 初始化项目.bat, which was written at project-bootstrap
rem time and had two problems:
rem   1. it created stray dirs (src\, tests\, config\) that do not belong to
rem      the current layout (backend\ frontend\ docs\ scripts\)
rem   2. it ran `git add -A` + `git commit` unattended
rem This script only prepares dependencies - it never touches git.
rem
rem Requires: Python 3.11+, Node.js 18+. uv is used when available (faster).
rem NOTE: keep this file ASCII-only (cmd parses .bat with the system codepage)
rem ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   Qimingxing - Environment Setup
echo ========================================
echo.

rem --- 1/5 tool check ---
echo [1/5] Checking tools ...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] python not found. Install Python 3.11+ first.
    pause
    exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] node not found. Install Node.js 18+ first.
    pause
    exit /b 1
)

set "HAS_UV="
where uv >nul 2>&1 && set "HAS_UV=1"
if defined HAS_UV (echo       uv: found - will be used for backend deps) else (echo       uv: not found - falling back to pip)

rem --- 2/5 backend venv ---
echo.
echo [2/5] Preparing backend venv (backend\.venv) ...
set "VENV_PY=%~dp0backend\.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    echo       venv already exists - reusing
) else (
    if defined HAS_UV (
        uv venv "%~dp0backend\.venv"
    ) else (
        python -m venv "%~dp0backend\.venv"
    )
    if not exist "%VENV_PY%" (
        echo [ERROR] failed to create venv. Check the python/uv output above.
        pause
        exit /b 1
    )
)

rem --- 3/5 backend deps ---
echo.
echo [3/5] Installing backend dependencies (requirements.txt) ...
if defined HAS_UV (
    uv pip install -r "%~dp0backend\requirements.txt" --python "%VENV_PY%"
) else (
    "%VENV_PY%" -m pip install --upgrade pip >nul
    "%VENV_PY%" -m pip install -r "%~dp0backend\requirements.txt"
)
"%VENV_PY%" -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] backend deps still missing after install. See output above.
    pause
    exit /b 1
)
echo       backend deps OK

rem --- 4/5 frontend deps ---
echo.
echo [4/5] Installing frontend dependencies (npm install) ...
pushd frontend
call npm install
set "NPM_RC=%errorlevel%"
popd
if not "%NPM_RC%"=="0" (
    echo [ERROR] npm install failed. See output above.
    pause
    exit /b 1
)
echo       frontend deps OK

rem --- 5/5 done ---
echo.
echo [5/5] Setup complete.
echo.
echo ========================================
echo   Next: double-click start-dev.bat
echo ========================================
echo   Backend : 127.0.0.1:8765 (migrations + seed run on first start)
echo   Frontend: http://localhost:5173
echo.
echo   For phone access instead: start-mobile.bat
echo.
pause
