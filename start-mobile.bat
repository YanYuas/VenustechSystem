@echo off
rem ============================================================
rem Qimingxing System - MOBILE service startup  (thin forwarding shell)
rem
rem All startup logic lives in ops\start.ps1 (single implementation,
rem D-11): backend loopback 8765 + unified edge server 0.0.0.0:3000
rem (static + /api proxy + access token).
rem
rem This file only forwards arguments; keep it ASCII-only because
rem cmd.exe parses .bat with the system codepage.
rem
rem Extra arguments are passed through, e.g.:
rem   start-mobile.bat -WhatIf
rem ============================================================
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\start.ps1" -Mode mobile %*
exit /b %errorlevel%
