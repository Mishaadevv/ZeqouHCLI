@echo off
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 -m zeqouhcli %*
  exit /b %ERRORLEVEL%
)
python -m zeqouhcli %*
exit /b %ERRORLEVEL%
