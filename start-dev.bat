@echo off
rem ============================================================
rem Qimingxing System - DEV startup  (thin forwarding shell)
rem
rem All startup logic lives in ops\start.ps1 (single implementation,
rem D-11). This file only forwards arguments; keep it ASCII-only
rem because cmd.exe parses .bat with the system codepage.
rem
rem Extra arguments are passed through, e.g.:
rem   start-dev.bat -WhatIf
rem   start-dev.bat -DataDir .\data-fusion
rem ============================================================
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\start.ps1" -Mode dev %*
exit /b %errorlevel%
