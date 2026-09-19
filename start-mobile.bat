@echo off
rem ============================================================
rem Qimingxing System - MOBILE service (one-click)
rem   Backend  FastAPI  127.0.0.1:8765  (loopback only)
rem   Unified  node server.js  0.0.0.0:3000  (static + /api proxy, token-gated)
rem   Phone connects via Tailscale/LAN:  http://<pc-ip>:3000
rem   Access token is printed below and kept in .qm-token - enter it once in
rem   the mobile app: Settings -> server address page.
rem
rem Requires: run setup.bat once beforehand.
rem NOTE: keep this file ASCII-only (cmd parses .bat with the system codepage)
rem ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   Qimingxing - Mobile Service Start
echo ========================================
echo.

rem --- 0. resolve python (deps live in the project venv) ---
rem PYFULL: absolute, for direct invocation (quoted)
rem PYRUN : relative to backend dir, no spaces, for the `cmd /k` line (unquoted)
set "PYFULL=%~dp0backend\.venv\Scripts\python.exe"
set "PYRUN=.venv\Scripts\python.exe"
if not exist "%PYFULL%" (
    echo [ERROR] project venv not found: backend\.venv
    echo         Run setup.bat once to create it and install dependencies.
    pause
    exit /b 1
)
"%PYFULL%" -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] backend deps missing in the venv. Run setup.bat.
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] node not found. Install Node.js 18+ first.
    pause
    exit /b 1
)

rem --- 1. generate / read access token ---
set QM_TOKEN=
if exist .qm-token for /f "usebackq delims=" %%t in (".qm-token") do set QM_TOKEN=%%t
if "%QM_TOKEN%"=="" (
    "%PYFULL%" -c "import secrets;print(secrets.token_hex(24))" > .qm-token 2>nul
    for /f "usebackq delims=" %%t in (".qm-token") do set QM_TOKEN=%%t
)
if "%QM_TOKEN%"=="" (
    echo [ERROR] failed to generate the access token. Check the python above.
    pause
    exit /b 1
)
echo   ACCESS TOKEN: %QM_TOKEN%
echo   (enter this ONCE on your phone: Settings - server address page)
echo.

rem --- 2. build frontend if dist missing ---
rem pushd/popd instead of `cd x && ... && cd ..`: if the build fails the old
rem form skipped the `cd ..`, leaving the rest of the script in the wrong dir.
if not exist "frontend\dist\index.html" (
    echo [build] frontend\dist not found - building ^(may take a minute^) ...
    pushd frontend
    call npm run build
    rem `if errorlevel 1` 是运行时判定；若写成 set "RC=%errorlevel%" 放在块内，
    rem %展开% 会在进入该块时就完成，取到的是旧值。
    if errorlevel 1 (
        popd
        echo [ERROR] frontend build failed. See output above.
        pause
        exit /b 1
    )
    popd
)

rem --- 3. start backend (loopback only) ---
echo [start] backend FastAPI on 127.0.0.1:8765 ...
start "Qimingxing-Backend" /D "%~dp0backend" cmd /k "chcp 65001 >nul && %PYRUN% -m uvicorn app.main:app --host 127.0.0.1 --port 8765"
timeout /t 5 /nobreak >nul

rem --- 4. start unified server (this window, port 3000) ---
echo [start] unified server on 0.0.0.0:3000 ...
echo.
echo ========================================
echo   NOW OPEN ON YOUR PHONE:
echo   http://YOUR-PC-IP:3000
echo   ^(Tailscale IP, or the LAN IP if on the same WiFi^)
echo.
echo   ACCESS TOKEN: %QM_TOKEN%
echo ========================================
echo.
echo Keep this window open. Press Ctrl+C to stop the unified server.
echo.
set QM_TOKEN=%QM_TOKEN%
node server.js
pause
