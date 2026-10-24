@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 -m pip install --user --upgrade .
) else (
  python -m pip install --user --upgrade .
)
if errorlevel 1 (
  echo.
  echo Installation failed. Check Python 3.10+ and your internet connection.
  pause
  exit /b 1
)
echo.
echo Zeqou Harness CLI installed.
echo Open a terminal inside your project folder and run: py -m zeqouhcli
pause
