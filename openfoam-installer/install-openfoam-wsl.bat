@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "OPENFOAM_SCRIPT=%~dp0install-openfoam-wsl.ps1"
if not exist "%OPENFOAM_SCRIPT%" (
  echo PowerShell script was not found: "%OPENFOAM_SCRIPT%"
  pause
  exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%OPENFOAM_SCRIPT%"
set "OPENFOAM_EXIT=%ERRORLEVEL%"

echo.
if "%OPENFOAM_EXIT%"=="2" (
  echo Installation was canceled by the user.
) else if not "%OPENFOAM_EXIT%"=="0" (
  echo Installation did not complete. Check the error above.
) else (
  echo Installation completed successfully.
)
pause
exit /b %OPENFOAM_EXIT%
