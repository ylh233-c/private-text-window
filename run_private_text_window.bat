@echo off
setlocal
cd /d "%~dp0"

set "PYTHONW="
for /f "delims=" %%I in ('where pythonw.exe 2^>nul') do (
  set "PYTHONW=%%I"
  goto :run_pythonw
)

:run_pythonw
if defined PYTHONW (
  start "" "%PYTHONW%" "%~dp0private_text_window.py"
  exit /b
)

where pyw.exe >nul 2>nul
if %errorlevel%==0 (
  start "" pyw.exe -3 "%~dp0private_text_window.py"
  exit /b
)

start "" python "%~dp0private_text_window.py"
exit /b
