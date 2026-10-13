@echo off
setlocal
chcp 65001 >nul
title KlipForge Local
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
set "KLIPFORGE_EXIT_CODE=%ERRORLEVEL%"

if not "%KLIPFORGE_EXIT_CODE%"=="0" (
  echo.
  echo KlipForge baslatilamadi. Yukaridaki hata mesajini kontrol edin.
  echo Bu pencereyi kapatmak icin bir tusa basin.
  pause >nul
)

exit /b %KLIPFORGE_EXIT_CODE%
