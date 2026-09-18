@echo off
rem ============================================================
rem Qimingxing - push main + all mod-* branches to GitHub
rem NOTE: keep this file ASCII-only (cmd parses .bat with system codepage)
rem ============================================================
setlocal
cd /d "%~dp0"

echo [1/2] pushing main ...
git push origin main
if errorlevel 1 (
    echo [WARN] main push failed - check your network and run again.
    goto :mods
)

:mods
echo [2/2] pushing module branches ...
for %%m in (dashboard execution knowledge life asset companion tools platform) do (
    echo   - mod-%%m
    git push origin mod-%%m
)

echo.
echo Done. If any line shows an error above, just run this file again.
pause
