@echo off
rem ============================================================
rem Qimingxing System - DEMO environment (rich sample data)
rem
rem Starts the backend against backend\data_demo instead of your real
rem database (backend\data). Your actual data is never touched.
rem
rem First run: generate the demo data
rem   backend\.venv\Scripts\python.exe backend\scripts\seed_demo.py --reset --yes
rem
rem Then: double-click this file, and use the normal frontend
rem (start-dev.bat starts the frontend; this file only starts the backend,
rem  so run ONLY ONE of start-dev.bat / start-demo.bat at a time -
rem  both want port 8765).
rem
rem NOTE: keep this file ASCII-only (cmd parses .bat with the system codepage)
rem ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   Qimingxing - DEMO backend (data_demo)
echo ========================================
echo.

set "PYFULL=%~dp0backend\.venv\Scripts\python.exe"
set "DEMO_DIR=%~dp0backend\data_demo"

if not exist "%PYFULL%" (
    echo [ERROR] project venv not found: backend\.venv
    echo         Run setup.bat first.
    pause
    exit /b 1
)

if not exist "%DEMO_DIR%\app.db" (
    echo [ERROR] demo database not found: %DEMO_DIR%\app.db
    echo.
    echo Generate it first ^(takes a few seconds^):
    echo   "%PYFULL%" "%~dp0backend\scripts\seed_demo.py" --reset --yes
    echo.
    pause
    exit /b 1
)

rem 端口占用检查：demo 与正式环境都用 8765，不能同时跑
netstat -ano | findstr ":8765" | findstr "LISTENING" >nul 2>&1 && (
    echo [WARN] port 8765 is already in use - another backend is running.
    echo        Stop it first ^(close the start-dev / start-mobile window^).
    echo.
    pause
    exit /b 1
)

echo   Data dir : %DEMO_DIR%
echo   Backend  : 127.0.0.1:8765
echo.
echo   Your real database ^(backend\data^) is NOT touched.
echo.
echo   Use the normal frontend: http://localhost:5173
echo   ^(start it with start-dev.bat in another window, or use the
echo    already-running Vite dev server^)
echo.

rem 用 Windows 绝对路径传环境变量。
rem 注意：不要用 Git Bash 的 /d/... 形式 —— Path("/d/x") 在 Windows 上会
rem 解析成 \d\x（丢掉盘符），导致服务打开另一个库、看到空数据。
set "VENUSTECH_DATA_DIR=%DEMO_DIR%"
"%PYFULL%" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
pause
