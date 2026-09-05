@echo off
rem ============================================================
rem Qimingxing System - one-click dev startup
rem   Starts backend FastAPI (127.0.0.1:8765, --reload) + frontend Vite (localhost:5173)
rem   Close the backend/frontend window to stop that service
rem Requires: Python 3.11+, Node.js 18+ (frontend node_modules installed)
rem NOTE: keep this file ASCII-only (cmd parses .bat with system codepage)
rem ============================================================
setlocal
cd /d "%~dp0"

echo ========================================
echo   Qimingxing - Dev One-click Start
echo ========================================
echo.

rem --- dependency check ---
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
if not exist "%~dp0frontend\node_modules" (
    echo [HINT] frontend deps missing. Run: cd frontend ^&^& npm install
)

rem --- port check ---
netstat -ano | findstr ":8765" | findstr "LISTENING" >nul 2>&1 && echo [HINT] port 8765 in use (backend may be running)
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul 2>&1 && echo [HINT] port 5173 in use (frontend may be running)

echo.
echo [1/3] Starting backend FastAPI (127.0.0.1:8765, --reload) ...
start "qmx-backend" /D "%~dp0backend" cmd /k "chcp 65001 >nul && python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload"

echo [2/3] Starting frontend Vite (http://localhost:5173) ...
start "qmx-frontend" /D "%~dp0frontend" cmd /k "chcp 65001 >nul && npm run dev"

echo [3/3] Opening browser ...
timeout /t 6 /nobreak >nul
start http://localhost:5173

echo.
echo Started. Close the backend/frontend window to stop each service.
echo   Backend : 127.0.0.1:8765  (demo data auto-seeded on first run, backend\data)
echo   Frontend: http://localhost:5173
echo.
pause
