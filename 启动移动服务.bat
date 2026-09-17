@echo off
rem ============================================================
rem Qimingxing System - Mobile Service (one-click)
rem   Starts backend FastAPI (127.0.0.1:8765) + unified server (0.0.0.0:3000)
rem   Phone connects via Tailscale: http://<pc-tailscale-ip>:3000
rem   Token: printed below and saved to .qm-token (enter it once in
rem   mobile Settings -> server address page)
rem NOTE: keep this file ASCII-only (cmd parses .bat with system codepage)
rem ============================================================
setlocal
cd /d "%~dp0"

echo ========================================
echo   Qimingxing - Mobile Service Start
echo ========================================
echo.

rem --- 1. generate / read access token ---
set QM_TOKEN=
if exist .qm-token for /f "usebackq delims=" %%t in (".qm-token") do set QM_TOKEN=%%t
if "%QM_TOKEN%"=="" (
    python -c "import secrets;print(secrets.token_hex(24))" > .qm-token 2>nul
    for /f "usebackq delims=" %%t in (".qm-token") do set QM_TOKEN=%%t
)
if "%QM_TOKEN%"=="" (
    echo [ERROR] failed to generate token. Is Python installed?
    pause
    exit /b 1
)
echo   ACCESS TOKEN: %QM_TOKEN%
echo   (enter this once on your phone: Settings - server address page)
echo.

rem --- 2. build frontend if dist missing ---
if not exist frontend\dist\index.html (
    echo [build] frontend\dist not found - building...
    cd frontend && call npm run build && cd ..
)

rem --- 3. start backend (loopback only) ---
echo [start] backend FastAPI on 127.0.0.1:8765 ...
start "Qimingxing-Backend" cmd /k "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765"
timeout /t 4 /nobreak >nul

rem --- 4. start unified server (this window, port 3000) ---
echo [start] unified server on 0.0.0.0:3000 ...
echo.
echo ========================================
echo   NOW OPEN ON YOUR PHONE:
echo   http://YOUR-PC-TAILSCALE-IP:3000
echo   (find the IP in the Tailscale app on your PC)
echo   Token: %QM_TOKEN%
echo ========================================
echo.
set QM_TOKEN=%QM_TOKEN% node server.js
pause
