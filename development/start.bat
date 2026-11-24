@echo off
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
if not exist .venv\Scripts\python.exe (
 echo Run setup.bat first.
 pause
 exit /b 1
)
if not exist .env (
 echo Run setup.bat first.
 pause
 exit /b 1
)
start "FastAPI" cmd /k .venv\Scripts\python.exe -m uvicorn src.app.api:app --host 0.0.0.0 --port 8000 --no-access-log
start "Admin Web" cmd /k .venv\Scripts\python.exe -m streamlit run src/ui/admin_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
start "User Web" cmd /k .venv\Scripts\python.exe -m streamlit run src/ui/user_app.py --server.address 0.0.0.0 --server.port 8502 --server.headless true
echo Admin: http://127.0.0.1:8501
echo User: http://127.0.0.1:8502 (local test)
echo Close the three server windows to stop.
pause
