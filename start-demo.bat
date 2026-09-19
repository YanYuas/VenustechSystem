@echo off
rem ============================================================
rem Qimingxing System - DEMO environment (rich sample data)
rem
rem Starts BOTH services pointing at the demo database:
rem   Backend  FastAPI  127.0.0.1:8765  -> backend\data_demo
rem   Frontend Vite     http://localhost:5173
rem
rem Your real database (backend\data) is never touched: the demo run
rem only differs by the VENUSTECH_DATA_DIR environment variable.
rem
rem Run ONLY ONE of start-dev.bat / start-demo.bat at a time -
rem both want port 8765 and 5173.
rem
rem NOTE: keep this file ASCII-only (cmd parses .bat with the system codepage)
rem ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   Qimingxing - DEMO (sample data)
echo ========================================
echo.

rem --- resolve python: ALWAYS the project venv ---
set "PYFULL=%~dp0backend\.venv\Scripts\python.exe"
set "PYRUN=.venv\Scripts\python.exe"
if not exist "%PYFULL%" (
    echo [ERROR] project venv not found: backend\.venv
    echo         Run setup.bat first.
    pause
    exit /b 1
)
"%PYFULL%" -c "import uvicorn, fastapi" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] backend dependencies missing. Run setup.bat, then retry.
    pause
    exit /b 1
)

set "DEMO_DIR=%~dp0backend\data_demo"

rem --- generate demo data on first run ---
if not exist "%DEMO_DIR%\app.db" (
    echo [1/3] Demo database not found - generating it now ...
    echo       "%PYFULL%" scripts\seed_demo.py --reset --yes
    pushd "%~dp0backend"
    "%PYFULL%" scripts\seed_demo.py --reset --yes
    popd
    if errorlevel 1 (
        echo [ERROR] demo data generation failed ^(exit code ^>=1^).
        pause
        exit /b 1
    )
    if not exist "%DEMO_DIR%\app.db" (
        echo [ERROR] seed finished but %DEMO_DIR%\app.db is missing.
        pause
        exit /b 1
    )
    echo       Done.
) else (
    echo [1/3] Demo database found: %DEMO_DIR%\app.db
)
echo.

if not exist "%~dp0frontend\node_modules" (
    echo [ERROR] frontend deps missing. Run setup.bat, or: cd frontend ^&^& npm install
    pause
    exit /b 1
)

rem --- port check: demo and dev share 8765 / 5173 ---
netstat -ano | findstr ":8765" | findstr "LISTENING" >nul 2>&1 && (
    echo [ERROR] port 8765 is already in use - another backend is running.
    echo         Close the start-dev.bat / start-mobile.bat window first,
    echo         then run this file again.
    echo.
    pause
    exit /b 1
)
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul 2>&1 && (
    echo [ERROR] port 5173 is already in use - another frontend is running.
    echo         Close it first, then run this file again.
    echo.
    pause
    exit /b 1
)

echo [2/3] Starting backend + frontend ...
echo.
echo   Data dir : %DEMO_DIR%
echo   Backend  : 127.0.0.1:8765
echo   Frontend : http://localhost:5173
echo.
echo   Your real database ^(backend\data^) is NOT touched.
echo.

rem Backend MUST be launched with the backend dir as CWD: uvicorn imports
rem `app.main`, and `app` only exists under backend\. Launching from the
rem repo root is what used to fail with "ModuleNotFoundError: No module
rem named 'app'".
rem
rem VENUSTECH_DATA_DIR must be a WINDOWS path (D:\...). A Git Bash style
rem /d/... becomes \d\... on Windows (drive letter lost), so the service
rem would open a DIFFERENT, empty database and show no data.
start "qmx-demo-backend" /D "%~dp0backend" cmd /k "chcp 65001 >nul && set "VENUSTECH_DATA_DIR=%DEMO_DIR%" && %PYRUN% -m uvicorn app.main:app --host 127.0.0.1 --port 8765"

start "qmx-demo-frontend" /D "%~dp0frontend" cmd /k "chcp 65001 >nul && npm run dev"

echo [3/3] Waiting for services, then opening browser ...
timeout /t 10 /nobreak >nul
start http://localhost:5173

echo.
echo Started. Close the two windows to stop the demo.
echo.
echo If a page shows no data: check the backend window - it must say
echo   "Data dir" / it must NOT contain a ModuleNotFoundError.
echo.
pause
