@echo off
rem ============================================================
rem Qimingxing System - DEMO startup  (thin forwarding shell)
rem
rem All startup logic lives in ops\start.ps1 (single implementation,
rem D-11). This file only forwards arguments; keep it ASCII-only
rem because cmd.exe parses .bat with the system codepage.
rem
rem Extra arguments are passed through, e.g.:
rem   start-demo.bat -WhatIf
rem ============================================================
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\start.ps1" -Mode demo %*
exit /b %errorlevel%
