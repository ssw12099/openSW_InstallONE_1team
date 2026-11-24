@echo off
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
if not exist .venv\Scripts\python.exe (
 py -3.13 -m venv .venv
 if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
if not exist .env (
 .venv\Scripts\python.exe -m src.common.setup_env
 if errorlevel 1 goto fail
)
echo Edit PUBLIC_API_BASE in .env before starting.
notepad .env
pause
exit /b 0
:fail
echo Setup failed. Check Python 3.13 and network access.
pause
exit /b 1
