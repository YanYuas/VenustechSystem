@echo off
rem ============================================================
rem Qimingxing System - one-click DEV startup
rem   Backend  FastAPI  127.0.0.1:8765  (--reload, auto-seeds on first run)
rem   Frontend Vite     http://localhost:5173
rem
rem Requires: Python 3.11+, Node.js 18+; run setup.bat once beforehand.
rem NOTE: keep this file ASCII-only (cmd parses .bat with the system codepage)
rem ============================================================
setlocal
cd /d "%~dp0"

echo ========================================
echo   Qimingxing - Dev One-click Start
echo ========================================
echo.

rem --- tool check ---
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] node not found. Install Node.js 18+ first.
    pause
    exit /b 1
)

rem --- resolve python: ALWAYS prefer the project venv ---
rem Why: backend dependencies live in backend\.venv. A bare `python` on PATH is
rem usually a different interpreter without fastapi/uvicorn, so the backend
rem window would die instantly with ModuleNotFoundError.
rem PYRUN is kept RELATIVE to the backend dir (backend\.venv\Scripts\python.exe
rem holds no spaces) so the `start ... cmd /k` line needs no nested quotes.
set "PYFULL=%~dp0backend\.venv\Scripts\python.exe"
set "PYRUN=.venv\Scripts\python.exe"
if not exist "%PYFULL%" (
    echo [WARN] project venv not found: backend\.venv
    echo        Falling back to `python` on PATH - it may lack backend deps.
    echo        Run setup.bat once to create the venv properly.
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] python not found. Install Python 3.11+ first.
        pause
        exit /b 1
    )
    set "PYFULL=python"
    set "PYRUN=python"
)

rem --- verify the chosen interpreter can actually run the backend ---
"%PYFULL%" -c "import uvicorn, fastapi" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] backend dependencies missing for:
    echo         %PYFULL%
    echo         Run setup.bat to install them, then retry.
    pause
    exit /b 1
)
echo   Python : %PYFULL%

if not exist "%~dp0frontend\node_modules" (
    echo [ERROR] frontend deps missing. Run setup.bat, or: cd frontend ^&^& npm install
    pause
    exit /b 1
)

rem --- port check ---
netstat -ano | findstr ":8765" | findstr "LISTENING" >nul 2>&1 && echo [HINT] port 8765 in use (backend may already be running)
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul 2>&1 && echo [HINT] port 5173 in use (frontend may already be running)

echo.
echo [1/3] Starting backend FastAPI (127.0.0.1:8765, --reload) ...
start "qmx-backend" /D "%~dp0backend" cmd /k "chcp 65001 >nul && %PYRUN% -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload"

echo [2/3] Starting frontend Vite (http://localhost:5173) ...
start "qmx-frontend" /D "%~dp0frontend" cmd /k "chcp 65001 >nul && npm run dev"

echo [3/3] Waiting for services, then opening browser ...
timeout /t 8 /nobreak >nul
start http://localhost:5173

echo.
echo Started. Close the backend/frontend window to stop each service.
echo   Backend : 127.0.0.1:8765
echo   Frontend: http://localhost:5173
echo.
echo If the page reports "cannot connect", check the backend window for errors.
pause
