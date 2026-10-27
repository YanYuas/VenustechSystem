@echo off
rem ============================================================
rem Qimingxing System - environment setup  (thin forwarding shell)
rem
rem All install logic lives in ops\setup.ps1 (single implementation,
rem D-11). This file only forwards arguments; keep it ASCII-only
rem because cmd.exe parses .bat with the system codepage.
rem
rem It prepares dependencies only (venv + pip + npm); it never
rem touches git.
rem
rem Extra arguments are passed through, e.g.:
rem   setup.bat -WhatIf
rem ============================================================
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\setup.ps1" %*
exit /b %errorlevel%
