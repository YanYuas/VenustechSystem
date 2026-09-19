@echo off
rem ============================================================
rem Qimingxing System - push main + all mod-* branches + tags
rem   Use when GitHub was unreachable and pushes timed out: just run again.
rem NOTE: keep this file ASCII-only (cmd parses .bat with the system codepage)
rem ============================================================
setlocal
cd /d "%~dp0"

echo ========================================
echo   Qimingxing - Push Branches
echo ========================================
echo.

set FAILED=0

echo [1/3] pushing main ...
git push origin main
if errorlevel 1 (
    echo [WARN] main push failed - check network, then run this file again.
    set FAILED=1
)

echo.
echo [2/3] pushing module branches ...
for %%m in (dashboard execution knowledge life asset companion tools platform) do (
    echo   - mod-%%m
    git push origin mod-%%m
    if errorlevel 1 (
        echo [WARN] mod-%%m push failed
        set FAILED=1
    )
)

echo.
echo [3/3] pushing tags ...
git push origin --tags
if errorlevel 1 (
    echo [WARN] tag push failed
    set FAILED=1
)

echo.
if "%FAILED%"=="1" (
    echo Done WITH FAILURES. Re-run this file when the network recovers.
) else (
    echo Done. All refs pushed.
)
pause
