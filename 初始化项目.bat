@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Venustech System init
cd /d "%~dp0"
chcp 936 >nul
echo ==== Venustech System init ====

if not exist .git (
  echo [1/6] git init
  git init -b main
  if errorlevel 1 echo [FAIL] git init & pause & exit /b 1
) else (
  echo [1/6] git exists
)

echo [2/6] mkdir dirs
mkdir src tests docs scripts config 2>nul
mkdir docs\management 2>nul
mkdir docs\design 2>nul

echo [3/6] support docs
if not exist README.md echo # Venustech System> README.md
if not exist CHANGELOG.md echo # Changelog> CHANGELOG.md
if not exist CONTRIBUTING.md echo # Contributing> CONTRIBUTING.md

echo [4/6] .gitignore
if not exist .gitignore (
  echo # Python>.gitignore
  echo __pycache__/>>.gitignore
  echo *.pyc>>.gitignore
  echo venv/>>.gitignore
  echo .env>>.gitignore
  echo # Node>>.gitignore
  echo node_modules/>>.gitignore
  echo dist/>>.gitignore
  echo build/>>.gitignore
  echo # IDE>>.gitignore
  echo .vscode/>>.gitignore
  echo .idea/>>.gitignore
  echo # OS>>.gitignore
  echo .DS_Store>>.gitignore
  echo Thumbs.db>>.gitignore
  echo *.log>>.gitignore
)

echo [5/6] git add + commit
git add -A 2>nul
git commit -m "chore: project init" 2>nul || echo [skip] nothing to commit

echo [6/6] done
echo ==== init complete ====
pause
